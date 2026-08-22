from __future__ import annotations

import hashlib
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from app.entities.document_delivery_entity import DocumentDeliveryEntity, DocumentDeliveryItemEntity, DeliveryHistoryEntity
from app.entities.document_request_entity import DocumentRequestEntity
from app.errors.delivery_exceptions import DeliveryIntegrityError, DeliveryNotFoundError, DeliveryValidationError
from app.repositories.delivery_history_repository import DeliveryHistoryRepository
from app.repositories.document_delivery_repository import DocumentDeliveryItemRepository, DocumentDeliveryRepository
from app.repositories.document_request_repository import DocumentRequestRepository
from app.repositories.organization_member_repository import OrganizationMemberRepository
from app.repositories.user_repository import UserRepository
from app.services.smartfile_instance_service import SmartFileInstanceService
from app.utils.file_naming import safe_output_path
from app.delivery.protocol import DELIVERY_PROTOCOL_VERSION


class DocumentDeliveryService:
    MAX_ITEM_SIZE = 4 * 1024 * 1024 * 1024
    CHUNK_SIZE = 1024 * 1024
    MAX_RETRY_ATTEMPTS = 8

    def __init__(self, database, context=None, document_service=None):
        self.database = database; self.context = context; self.document_service = document_service
        self.deliveries = DocumentDeliveryRepository(database=database)
        self.items = DocumentDeliveryItemRepository(database=database)
        self.history = DeliveryHistoryRepository(database=database)
        self.instances = SmartFileInstanceService(database, context)
        self.requests = DocumentRequestRepository(database=database)
        self.members = OrganizationMemberRepository(database=database)
        self.users = UserRepository(database=database)
        self.notification_callback = None

    def create(self, organization_id: int, basket, recipient_instance_id: str, message: str | None = None) -> DocumentDeliveryEntity:
        self._require(organization_id, "delivery.create")
        if not basket.items: raise DeliveryValidationError("A cesta de documentos está vazia.")
        if basket.recipient_user_id is None: raise DeliveryValidationError("Selecione o destinatário.")
        self._validate_recipient(organization_id, basket.recipient_user_id)
        local = self.instances.local(organization_id)
        peer = self.instances.repository.find_by_instance_id(recipient_instance_id)
        if peer is None or peer.organization_id != organization_id or peer.is_local:
            raise DeliveryValidationError("Instalação destinatária não cadastrada.")
        if peer.owner_user_id != basket.recipient_user_id:
            raise DeliveryValidationError("A instalação selecionada não pertence ao destinatário.")
        if basket.request_id:
            request = self.requests.find_by_id(basket.request_id, organization_id)
            if request is None or request.status != "ATTENDED":
                raise DeliveryValidationError("A solicitação deve estar ATENDIDA antes do envio.")
            if request.requested_by_user_id != basket.recipient_user_id:
                raise DeliveryValidationError("O destinatário difere do solicitante original.")
        item_snapshots = []
        for reference in basket.items:
            document = self.document_service.get_document(reference.document_id)
            if document is None: raise DeliveryValidationError(f"Documento {reference.document_id} não encontrado.")
            path = Path(document.path).resolve(strict=True)
            item_snapshots.append((document, path, path.stat().st_size, self._checksum(path)))
        now = self._now()
        with self.database.transaction():
            delivery = self.deliveries.create(DocumentDeliveryEntity(
                delivery_uuid=str(uuid4()), protocol_number=self._protocol(now), organization_id=organization_id,
                request_id=basket.request_id, sender_user_id=self.context.current_user.id,
                recipient_user_id=basket.recipient_user_id, sender_instance_id=local.instance_id,
                recipient_instance_id=peer.instance_id, recipient_host=peer.current_ip,
                recipient_port=peer.http_port, direction="OUTGOING", message=(message or "").strip() or None,
                status="CREATED", created_at=now,
            ))
            for document, _path, size, checksum in item_snapshots:
                self.items.create(DocumentDeliveryItemEntity(
                    item_uuid=str(uuid4()), delivery_id=delivery.id, document_id=document.id,
                    logical_name=self._safe_name(document.name), size=size,
                    sha256=checksum,
                ))
        self._record(delivery, "DELIVERY_CREATED", f"Protocolo {delivery.protocol_number} criado.")
        return delivery

    def queue(self, delivery_id: int, error: str | None = None) -> None:
        delivery = self._delivery(delivery_id); attempts = delivery.attempts + (1 if error else 0)
        if error and attempts >= self.MAX_RETRY_ATTEMPTS:
            self.deliveries.update(
                delivery_id, status="FAILED", attempts=attempts,
                next_attempt_at=None, last_error=error[:500],
            )
            self._record(delivery, "DELIVERY_FAILED", "Limite automático de tentativas atingido.")
            return
        delay = min(30 * (2 ** min(attempts, 6)), 3600)
        self.deliveries.update(delivery_id, status="QUEUED", attempts=attempts,
            queued_at=delivery.queued_at or self._now(), next_attempt_at=(datetime.now(timezone.utc)+timedelta(seconds=delay)).isoformat() if error else self._now(),
            last_error=(error or None)[:500] if error else None)
        self._request_transition(delivery, "DELIVERING")
        self._record(delivery, "DELIVERY_QUEUED", error or "Entrega adicionada à fila.")

    def mark_sending(self, delivery_id: int) -> None:
        self.deliveries.update(delivery_id, status="SENDING", sent_at=self._now(), last_error=None)

    def mark_delivered(self, delivery_id: int) -> None:
        delivery = self._delivery(delivery_id); now = self._now()
        self.deliveries.update(delivery_id, status="DELIVERED", delivered_at=now, next_attempt_at=None, last_error=None)
        self._request_transition(delivery, "DELIVERED")
        self._record(delivery, "DELIVERY_DELIVERED", "Todos os itens foram recebidos e verificados.")

    def mark_viewed(self, protocol: str, user_id: int) -> None:
        delivery = self._protocol_delivery(protocol); self._assert_recipient(delivery, user_id)
        if delivery.status not in {"DELIVERED", "VIEWED", "ACKNOWLEDGED"}: raise DeliveryValidationError("Entrega ainda não disponível.")
        if delivery.viewed_at is None:
            self.deliveries.update(delivery.id, status="VIEWED", viewed_at=self._now(), viewed_by_user_id=user_id)
            self._record(delivery, "DELIVERY_VIEWED", "Destinatário visualizou a entrega.", user_id)

    def acknowledge(self, protocol: str, user_id: int) -> None:
        delivery = self._protocol_delivery(protocol); self._assert_recipient(delivery, user_id)
        if delivery.status not in {"DELIVERED", "VIEWED", "ACKNOWLEDGED"}: raise DeliveryValidationError("Entrega ainda não disponível.")
        if delivery.acknowledged_at is None:
            now = self._now(); self.deliveries.update(delivery.id, status="ACKNOWLEDGED", acknowledged_at=now, completed_at=now)
            self._record(delivery, "DELIVERY_ACKNOWLEDGED", "Recebimento confirmado.", user_id)
            self._request_transition(delivery, "COMPLETED")

    def apply_remote_status(self, delivery_id: int, payload: dict) -> None:
        delivery = self._delivery(delivery_id); status = str(payload.get("status", ""))
        allowed = {"DELIVERED", "VIEWED", "ACKNOWLEDGED"}
        if status not in allowed: return
        values = {"status": status}
        for key in ("delivered_at", "viewed_at", "acknowledged_at"):
            if payload.get(key): values[key] = payload[key]
        self.deliveries.update(delivery_id, **values)
        if status == "ACKNOWLEDGED": self._request_transition(delivery, "COMPLETED")

    def receive_metadata(self, payload: dict) -> DocumentDeliveryEntity:
        required = {"delivery_uuid","protocol_number","request_uuid","sender_username","recipient_username","sender_instance_id","recipient_instance_id","message","items"}
        if not required <= payload.keys(): raise DeliveryValidationError("Metadados da entrega incompletos.")
        try:
            from uuid import UUID
            UUID(str(payload["delivery_uuid"]))
        except (ValueError, TypeError, AttributeError) as exc:
            raise DeliveryValidationError("Identidade da entrega inválida.") from exc
        sender = self.instances.repository.find_by_instance_id(str(payload["sender_instance_id"]))
        if sender is None or sender.is_local: raise DeliveryValidationError("Instalação remetente não cadastrada.")
        organization_id = sender.organization_id; local = self.instances.local(organization_id)
        if payload["recipient_instance_id"] != local.instance_id: raise DeliveryValidationError("Entrega destinada a outra instalação.")
        sender_user = self.users.find_by_username(str(payload["sender_username"] or ""))
        recipient_user = self.users.find_by_username(str(payload["recipient_username"] or ""))
        if sender_user is None or recipient_user is None:
            raise DeliveryValidationError("Usuários da entrega não existem nesta instalação.")
        self._validate_recipient(organization_id, sender_user.id)
        self._validate_recipient(organization_id, recipient_user.id)
        existing = self.deliveries.find_by_protocol(str(payload["protocol_number"]))
        if existing: return existing
        validated_items = []
        if not isinstance(payload["items"], list) or not payload["items"]:
            raise DeliveryValidationError("A entrega deve possuir ao menos um documento.")
        for value in payload["items"]:
            size = int(value["size"])
            if size < 0 or size > self.MAX_ITEM_SIZE: raise DeliveryValidationError("Tamanho de item inválido.")
            checksum = str(value["sha256"]).lower()
            if not re.fullmatch(r"[0-9a-f]{64}", checksum): raise DeliveryValidationError("Checksum inválido.")
            item_uuid = str(value["item_uuid"])
            if not re.fullmatch(r"[A-Za-z0-9-]{1,80}", item_uuid): raise DeliveryValidationError("Identidade do item inválida.")
            validated_items.append((item_uuid, self._safe_name(str(value["logical_name"])), size, checksum))
        request_uuid = str(payload.get("request_uuid") or "").strip()
        request = self.requests.find_by_uuid(request_uuid) if request_uuid else None
        if request_uuid and request is None:
            raise DeliveryValidationError("A solicitação relacionada ainda não foi recebida nesta instalação.")
        now = self._now()
        with self.database.transaction():
            delivery = self.deliveries.create(DocumentDeliveryEntity(
                delivery_uuid=str(payload["delivery_uuid"]), protocol_number=self._valid_protocol(str(payload["protocol_number"])),
                organization_id=organization_id, request_id=request.id if request else None,
                sender_user_id=sender_user.id, recipient_user_id=recipient_user.id,
                sender_instance_id=sender.instance_id, recipient_instance_id=local.instance_id,
                recipient_host=sender.current_ip, recipient_port=sender.http_port, direction="INCOMING",
                message=(str(payload["message"]).strip() or None) if payload["message"] else None,
                status="SENDING", created_at=now, sent_at=now,
            ))
            for item_uuid, logical_name, size, checksum in validated_items:
                self.items.create(DocumentDeliveryItemEntity(item_uuid=item_uuid, delivery_id=delivery.id,
                    logical_name=logical_name, size=size, sha256=checksum, transfer_status="PENDING"))
        self._record(delivery, "DELIVERY_RECEIVED_METADATA", "Metadados da entrega recebidos.")
        if self.notification_callback:
            self.notification_callback(
                "Novo documento recebido",
                f"Protocolo {delivery.protocol_number} recebido de {sender_user.display_name}.",
            )
        return delivery

    def receive_item(self, protocol: str, item_uuid: str, stream, content_length: int) -> Path:
        delivery = self._protocol_delivery(protocol); item = self.items.find_by_uuid(item_uuid)
        if item is None or item.delivery_id != delivery.id: raise DeliveryNotFoundError("Item da entrega não encontrado.")
        if content_length != item.size: raise DeliveryIntegrityError("Tamanho recebido difere do informado.")
        root = (self.database.paths.data_dir / "delivery_inbox" / protocol).resolve(); root.mkdir(parents=True, exist_ok=True)
        suffix = Path(item.logical_name).suffix.lower()[:12]; final = root / f"{item.item_uuid}{suffix}"; temporary = root / f".{item.item_uuid}.part"
        digest = hashlib.sha256(); remaining = content_length
        try:
            with temporary.open("wb") as handle:
                while remaining:
                    chunk = stream.read(min(self.CHUNK_SIZE, remaining))
                    if not chunk: raise DeliveryIntegrityError("Transferência interrompida.")
                    handle.write(chunk); digest.update(chunk); remaining -= len(chunk)
                handle.flush(); import os; os.fsync(handle.fileno())
            if digest.hexdigest() != item.sha256:
                raise DeliveryIntegrityError("Falha de integridade SHA-256.")
            temporary.replace(final); now = self._now(); self.items.update_received(item_uuid, "VERIFIED", str(final), now)
            return final
        except Exception:
            temporary.unlink(missing_ok=True); self.items.update_received(item_uuid, "FAILED", None, None); raise

    def complete_incoming(self, protocol: str) -> DocumentDeliveryEntity:
        delivery = self._protocol_delivery(protocol); items = self.items.list_by_delivery(delivery.id)
        if not items or any(item.transfer_status != "VERIFIED" for item in items): raise DeliveryIntegrityError("Nem todos os itens foram verificados.")
        self.mark_delivered(delivery.id); return self._delivery(delivery.id)

    def download_item(self, item_id: int, output: Path) -> Path:
        self.context.require_permission("delivery.download")
        row = self.database.fetch_one("SELECT * FROM document_delivery_items WHERE id=?", (item_id,))
        if row is None or not row["received_path"]: raise DeliveryNotFoundError("Arquivo recebido não encontrado.")
        source = Path(row["received_path"]).resolve(strict=True); target = safe_output_path(output.expanduser().resolve())
        target.parent.mkdir(parents=True, exist_ok=True)
        with source.open("rb") as incoming, target.open("xb") as outgoing:
            while chunk := incoming.read(self.CHUNK_SIZE): outgoing.write(chunk)
        return target

    def add_received_to_ged(self, item_id: int, **metadata):
        if self.document_service is None: raise DeliveryValidationError("Serviço documental indisponível.")
        row = self.database.fetch_one("SELECT * FROM document_delivery_items WHERE id=?", (item_id,))
        if row is None or not row["received_path"]: raise DeliveryNotFoundError("Arquivo recebido não encontrado.")
        return self.document_service.import_document(row["received_path"], title=metadata.pop("title", row["logical_name"]), **metadata)

    def metadata(self, delivery_id: int) -> dict:
        delivery = self._delivery(delivery_id); items = self.items.list_by_delivery(delivery_id)
        request = self.requests.find_by_id(delivery.request_id, delivery.organization_id) if delivery.request_id else None
        sender = self.users.find_by_id(delivery.sender_user_id) if delivery.sender_user_id else None
        recipient = self.users.find_by_id(delivery.recipient_user_id) if delivery.recipient_user_id else None
        values = {key: getattr(delivery, key) for key in ("delivery_uuid","protocol_number","organization_id","sender_instance_id","recipient_instance_id","message")}
        values["sender_username"] = sender.username if sender else None
        values["recipient_username"] = recipient.username if recipient else None
        values["request_uuid"] = request.request_uuid if request else None
        values["items"] = [{key: getattr(item,key) for key in ("item_uuid","logical_name","size","sha256")} for item in items]
        return values

    def request_payload(self, request_id: int) -> dict:
        request = self.requests.find_by_id(request_id)
        if request is None:
            raise DeliveryNotFoundError("Solicitação não encontrada.")
        requester = self.users.find_by_id(request.requested_by_user_id) if request.requested_by_user_id else None
        assignee = self.users.find_by_id(request.assigned_to_user_id) if request.assigned_to_user_id else None
        return {
            "request_uuid": request.request_uuid,
            "organization_id": request.organization_id,
            "title": request.title,
            "description": request.description,
            "requester_username": requester.username if requester else None,
            "assignee_username": assignee.username if assignee else None,
            "status": request.status,
            "due_at": request.due_at,
            "created_at": request.created_at,
            "origin_instance_id": request.origin_instance_id,
            "target_instance_id": request.target_instance_id,
        }

    def receive_request(self, payload: dict) -> DocumentRequestEntity:
        required = {
            "request_uuid", "organization_id", "title", "requester_username",
            "assignee_username", "status", "created_at", "origin_instance_id",
            "target_instance_id",
        }
        if not required <= payload.keys():
            raise DeliveryValidationError("Metadados da solicitação incompletos.")
        request_uuid = str(payload["request_uuid"])
        try:
            from uuid import UUID
            UUID(request_uuid)
        except (ValueError, TypeError, AttributeError) as exc:
            raise DeliveryValidationError("Identidade da solicitação inválida.") from exc
        existing = self.requests.find_by_uuid(request_uuid)
        if existing:
            return existing
        origin = self.instances.repository.find_by_instance_id(str(payload["origin_instance_id"]))
        if origin is None or origin.is_local:
            raise DeliveryValidationError("Instalação solicitante não cadastrada.")
        organization_id = origin.organization_id
        local = self.instances.local(organization_id)
        if str(payload["target_instance_id"]) != local.instance_id:
            raise DeliveryValidationError("Solicitação destinada a outra instalação.")
        requester = self.users.find_by_username(str(payload["requester_username"] or ""))
        assignee = self.users.find_by_username(str(payload["assignee_username"] or ""))
        if requester is None or assignee is None:
            raise DeliveryValidationError("Usuários da solicitação não existem nesta instalação.")
        self._validate_recipient(organization_id, requester.id)
        self._validate_recipient(organization_id, assignee.id)
        status = str(payload["status"])
        if status not in {"OPEN", "IN_PROGRESS", "ATTENDED"}:
            raise DeliveryValidationError("Estado remoto de solicitação inválido.")
        title = " ".join(str(payload["title"]).split())
        if not title:
            raise DeliveryValidationError("Título da solicitação inválido.")
        now = self._now()
        created = self.requests.create(DocumentRequestEntity(
            request_uuid=request_uuid,
            organization_id=organization_id,
            title=title[:180],
            description=(str(payload.get("description") or "").strip() or None),
            requested_by_user_id=requester.id,
            assigned_to_user_id=assignee.id,
            status=status,
            due_at=str(payload.get("due_at")) if payload.get("due_at") else None,
            created_at=str(payload["created_at"]),
            updated_at=now,
            origin_instance_id=origin.instance_id,
            target_instance_id=local.instance_id,
        ))
        self._record_request(created, "REQUEST_RECEIVED", "Solicitação recebida de outra instalação SmartFile.")
        return created

    def status_payload(self, protocol: str) -> dict:
        delivery = self._protocol_delivery(protocol)
        return {key: getattr(delivery, key) for key in ("protocol_number","status","delivered_at","viewed_at","acknowledged_at")}

    def identity_payload(self) -> dict:
        organization_id = getattr(
            getattr(self.context, "active_organization", None), "id", None,
        )
        if not organization_id:
            raise DeliveryValidationError("Nenhuma organização ativa para a recepção LAN.")
        local = self.instances.local(int(organization_id))
        return {
            "instance_id": local.instance_id,
            "device_name": local.device_name,
            "protocol_version": DELIVERY_PROTOCOL_VERSION,
        }

    def mark_request_dispatched(self, request_id: int) -> None:
        request = self.requests.find_by_id(request_id)
        if request:
            self._record_request(
                request, "REQUEST_DISPATCHED",
                "Solicitação entregue à instalação responsável.",
            )

    def _request_transition(self, delivery, target: str) -> None:
        if not delivery.request_id: return
        request = self.requests.find_by_id(delivery.request_id, delivery.organization_id)
        if not request: return
        allowed = {("ATTENDED","DELIVERING"), ("DELIVERING","DELIVERED"), ("DELIVERED","COMPLETED")}
        recovered_remote = (
            target == "DELIVERED" and request.status in {"OPEN", "IN_PROGRESS", "ATTENDED"}
        ) or (
            target == "COMPLETED" and request.status not in {"COMPLETED", "CANCELLED"}
        )
        if (request.status, target) in allowed or recovered_remote:
            column = {"DELIVERING":None,"DELIVERED":"delivered_at","COMPLETED":"completed_at"}[target]
            self.requests.update_status(request.id, request.organization_id, target, self._now(), column)

    def _record(self, delivery, event: str, description: str, actor: int | None = None) -> None:
        self.history.record(DeliveryHistoryEntity(organization_id=delivery.organization_id, request_id=delivery.request_id,
            delivery_id=delivery.id, event_type=event, actor_user_id=actor or getattr(getattr(self.context,"current_user",None),"id",None), description=description, created_at=self._now()))

    def _record_request(self, request, event: str, description: str) -> None:
        self.history.record(DeliveryHistoryEntity(
            organization_id=request.organization_id,
            request_id=request.id,
            event_type=event,
            actor_user_id=getattr(getattr(self.context, "current_user", None), "id", None),
            description=description,
            created_at=self._now(),
        ))

    def _require(self, organization_id: int, permission: str) -> None:
        if not self.context: return
        if organization_id != getattr(getattr(self.context,"active_organization",None),"id",None): raise PermissionError("Ative a organização da entrega.")
        self.context.require_permission(permission)

    def _validate_recipient(self, organization_id: int, user_id: int) -> None:
        user = self.users.find_by_id(user_id); member = self.members.find(organization_id, user_id)
        if user is None or not user.is_active or member is None or member.status != "ACTIVE": raise DeliveryValidationError("Destinatário deve ser membro ativo da organização.")

    def _assert_recipient(self, delivery, user_id: int) -> None:
        if delivery.recipient_user_id != user_id: raise PermissionError("Somente o destinatário pode executar esta ação.")

    def _delivery(self, delivery_id: int):
        value = self.deliveries.find_by_id(delivery_id)
        if value is None: raise DeliveryNotFoundError("Entrega não encontrada.")
        return value

    def _protocol_delivery(self, protocol: str):
        value = self.deliveries.find_by_protocol(self._valid_protocol(protocol))
        if value is None: raise DeliveryNotFoundError("Protocolo não encontrado.")
        return value

    def _protocol(self, now: str) -> str:
        date = now[:10].replace("-", "")
        row = self.database.fetch_one("SELECT COUNT(*) count FROM document_deliveries WHERE protocol_number LIKE ?", (f"SF-{date}-%",))
        return f"SF-{date}-{int(row['count'])+1:06d}-{uuid4().hex[:4].upper()}"

    @staticmethod
    def _valid_protocol(value: str) -> str:
        if not re.fullmatch(r"SF-\d{8}-\d{6}-[0-9A-F]{4}", value): raise DeliveryValidationError("Protocolo inválido.")
        return value

    @staticmethod
    def _safe_name(value: str) -> str:
        name = value.strip()
        if not name or name != Path(name).name or any(char in name for char in "\0/\\"): raise DeliveryValidationError("Nome de documento inválido.")
        return name[:255]

    @staticmethod
    def _checksum(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while chunk := handle.read(DocumentDeliveryService.CHUNK_SIZE): digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _now() -> str: return datetime.now(timezone.utc).isoformat()
