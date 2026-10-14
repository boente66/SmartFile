from __future__ import annotations

import hashlib
import logging
from functools import wraps
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import replace
from typing import Optional
from uuid import uuid4, UUID

from app.database.database import Database
from app.entities.document_entity import DocumentEntity
from app.errors.persistence_exceptions import (
    DuplicateDocumentError,
    InvalidDocumentError,
    StorageError,
)
from app.models.document_model import DocumentModel
from app.models.document_search import DocumentSearchFilters
from app.repositories.document_repository import DocumentRepository
from app.services.history_service import HistoryService
from app.services.document_storage_service import DocumentStorageService
from app.services.folder_service import FolderService
from app.services.organization_service import OrganizationService
from app.services.storage_quota_service import StorageQuotaService
from app.services.cloud_storage_quota_service import CloudStorageQuotaService
from app.services.corporate_transport_service import CorporateTransportService
from app.cloud.cloud_manager import CloudManager
from app.cloud.cloud_sync_service import CloudSyncService
from app.services.cloud_folder_mapping_service import CloudFolderMappingService

logger = logging.getLogger(__name__)


def document_mutation(method):
    @wraps(method)
    def execute(self, *args, **kwargs):
        self.audit.context = self.session_context
        actor = self.audit.current_actor() or self.audit.capture(self.active_organization_id)
        with self.audit.bind(actor), self.database.transaction():
            return method(self, *args, **kwargs)
    return execute


class DocumentService:
    """Regras documentais sobre a API do DocumentRepository."""

    def __init__(
        self,
        db_path: Optional[str] = None,
        *,
        database: Database | None = None,
        storage_service: DocumentStorageService | None = None,
        session_context=None,
    ):
        if database is not None and db_path is not None:
            raise ValueError("Informe database ou db_path, não ambos.")
        self.session_context = session_context
        self.database = database or Database(db_name=db_path)
        self.document_repository = DocumentRepository(database=self.database)
        self.organization_service = OrganizationService(self.database)
        self.folder_service = FolderService(self.database, session_context=session_context)
        self.cloud_manager = CloudManager(self.database)
        self.cloud_sync_service = CloudSyncService(self.database, self.cloud_manager, session_context)
        self.cloud_folder_mapping_service = CloudFolderMappingService(
            self.database, self.cloud_manager
        )
        self.cloud_storage_quota_service = CloudStorageQuotaService(self.cloud_manager)
        self.storage_service = storage_service or DocumentStorageService(self.database.paths)
        self.storage_quota_service = StorageQuotaService(
            self.database, self.storage_service.paths.storage
        )
        self.corporate_transport_service = CorporateTransportService(
            self.database, self.storage_service,
        )
        self.history_service = HistoryService(database=self.database, context=session_context)
        self.audit = self.history_service.audit

    def _require(self, permission: str, organization_id: int | None = None) -> None:
        if self.session_context is not None:
            self.audit.context=self.session_context
            actor = self.audit.current_actor()
            if actor is not None and actor.organization_id != (organization_id if organization_id is not None else self.active_organization_id):
                raise PermissionError('A operação foi iniciada em outra organização.')
            if actor is not None and actor.username != getattr(self.session_context.current_user, 'username', None):
                raise PermissionError('A sessão que iniciou a operação não está mais ativa.')
            if organization_id is None and getattr(self.session_context.active_organization, "id", None) != self.active_organization_id:
                raise PermissionError("A organização ativa mudou; atualize a operação.")
            self.session_context.require_organization_permission(
                organization_id if organization_id is not None else self.active_organization_id, permission)

    def import_destinations(self, allowed_organization_ids=None):
        from app.errors.auth_exceptions import AuthenticationError
        allowed = None if allowed_organization_ids is None else set(allowed_organization_ids)
        organizations = []
        folders = {}
        for organization in self.organization_service.list_organizations():
            if allowed is not None and organization.id not in allowed:
                continue
            try:
                self._require("document.import", organization.id)
            except AuthenticationError:
                continue
            organizations.append(organization)
            folders[organization.id] = self.folder_service.list_folders(organization.id)
        if not organizations:
            raise PermissionError("Você não possui permissão para adicionar documentos às organizações disponíveis.")
        return organizations, folders

    @property
    def active_organization_id(self) -> int:
        return self.organization_service.active_id

    def set_active_organization(self, organization_id: int):
        self._require("document.view", organization_id)
        return self.organization_service.set_active(organization_id)

    def import_document(
        self,
        file_path: str,
        folder_id: int | None = None,
        *,
        organization_id: int | None = None,
        title: str | None = None,
        category: str | None = None,
        description: str | None = None,
        tags: str | None = None,
        document_date: str | None = None,
        notes: str | None = None,
        source_type: str = "IMPORT",
        sync_cloud: bool = True,
        cancelled=None,
        public_uuid=None,
    ) -> DocumentModel:
        organization_id = organization_id or self.active_organization_id
        self._require("document.import", organization_id)
        if public_uuid is not None:
            try:
                public_uuid = str(UUID(public_uuid))
            except (ValueError, TypeError) as exc:
                raise InvalidDocumentError('Identidade documental inválida.') from exc
            existing = self.document_repository.find_by_public_uuid(public_uuid)
            if existing is not None:
                raise DuplicateDocumentError('A identidade documental já existe nesta instalação.')
        path = self._validated_path(file_path)
        extension = path.suffix.lower()
        checksum = self._calculate_checksum(path) if cancelled is None else self._calculate_checksum(path, cancelled=cancelled)
        source_type = source_type.strip().upper()
        allowed_sources = {
            "IMPORT", "SCANNER", "CONVERTER", "PDF_TOOLS", "DIGITAL_SIGNATURE",
            "HANDWRITTEN_SIGNATURE", "CLOUD_DOWNLOAD", "DELIVERY",
        }
        if source_type not in allowed_sources:
            raise InvalidDocumentError("Origem documental inválida.")
        if folder_id is not None:
            folder = self.folder_service.repository.find_by_id(folder_id, organization_id)
            if folder is None or folder.status != "ACTIVE":
                raise InvalidDocumentError("A pasta selecionada não pertence à organização ativa.")
        if self.document_repository.exists_checksum(checksum, organization_id):
            raise DuplicateDocumentError("Este documento já foi importado.")

        operation_id = self.storage_quota_service.reserve(
            organization_id, path.stat().st_size, str(uuid4())
        )
        stored = None
        committed = False
        now = self._now()
        try:
            stored = (self.storage_service.store(path, checksum) if cancelled is None
                      else self.storage_service.store(path, checksum, cancelled=cancelled))
            with self.database.transaction():
                document_name = (title or path.name).strip() or path.name
                if not Path(document_name).suffix:
                    document_name += extension
                entity = DocumentEntity(
                    organization_id=organization_id,
                    folder_id=folder_id,
                    public_uuid=public_uuid,
                    name=document_name,
                    original_name=path.name,
                    path=stored.storage_path,
                    source_path=str(path),
                    storage_path=stored.storage_path,
                    internal_name=stored.internal_name,
                    managed=True,
                    extension=extension,
                    file_type=self._classify_file_type(extension),
                    size=stored.size,
                    checksum=checksum,
                    category=category or self._classify_category(extension),
                    description=description or None,
                    favorite=False,
                    status="ACTIVE",
                    created_at=now,
                    updated_at=now,
                    last_accessed_at=None,
                    source_type=source_type,
                    tags=tags or None,
                    document_date=document_date or None,
                    notes=notes or None,
                )
                created = self.document_repository.create(entity)
                action = "SCAN" if source_type == "SCANNER" else "IMPORT"
                self._record_history(created.id, action, f"Documento adicionado: {document_name}", sha256_after=checksum)
                self.storage_quota_service.commit_reservation(operation_id)
            committed = True
            logger.info("Documento importado id=%s", created.id)
            if sync_cloud:
                try:
                    self.cloud_sync_service.enqueue_upload(created.id, organization_id)
                except Exception:
                    logger.exception("Documento salvo localmente, mas a sincronização não foi enfileirada")
            self._enqueue_transport_upload(created.id, organization_id)
            refreshed = self.document_repository.find_by_id(created.id, organization_id)
            return DocumentModel.from_entity(refreshed or created)
        except Exception:
            if not committed:
                self.storage_quota_service.release_reservation(operation_id)
            try:
                if stored is not None and not committed:
                    self.storage_service.remove(stored.storage_path)
            except StorageError:
                logger.exception("Falha ao remover arquivo após rollback da importação")
            raise

    def get_document(self, document_id: int) -> Optional[DocumentModel]:
        self._require("document.view")
        entity = self.document_repository.find_by_id(document_id, self.active_organization_id)
        return DocumentModel.from_entity(entity) if entity else None

    def list_documents(self, folder_id: int | None = None) -> list[DocumentModel]:
        self._require("document.view")
        return self._models(self.document_repository.find_all(self.active_organization_id, folder_id))

    def search_documents(
        self,
        term: str,
        file_type: str | None = None,
        folder_id: int | None = None,
        filters: DocumentSearchFilters | None = None,
    ) -> list[DocumentModel]:
        self._require("document.search")
        if filters is not None:
            file_type = filters.file_type or file_type
        if not term.strip() and not (filters and filters.active):
            return self.filter_by_type(file_type or "Todos", folder_id)
        return self._models(
            self.document_repository.smart_search(
                [item for item in term.strip().split() if item],
                organization_id=self.active_organization_id,
                folder_id=folder_id,
                filters=filters or DocumentSearchFilters(file_type=file_type),
            )
        )

    @document_mutation
    def rename_document(self, document_id: int, new_name: str) -> DocumentModel:
        self._require("document.update")
        entity = self.document_repository.find_by_id(document_id, self.active_organization_id)
        if entity is None or entity.status != "ACTIVE":
            raise InvalidDocumentError("Documento não encontrado.")
        clean = " ".join(new_name.split())
        if not clean or len(clean) > 255 or Path(clean).name != clean:
            raise InvalidDocumentError("Informe um nome de documento válido.")
        original_suffix = Path(entity.name).suffix.casefold() or entity.extension.casefold()
        supplied_suffix = Path(clean).suffix.casefold()
        if not supplied_suffix:
            clean += original_suffix
        elif supplied_suffix != original_suffix:
            raise InvalidDocumentError("A extensão do documento não pode ser alterada ao renomear.")
        if clean == entity.name:
            return DocumentModel.from_entity(entity)
        previous = entity.name
        entity.name = clean
        entity.updated_at = self._now()
        updated = self.document_repository.update(entity)
        self._record_history(document_id, "RENAME", f"Documento renomeado de {previous} para {clean}")
        try:
            self.cloud_sync_service.enqueue_rename(document_id, self.active_organization_id)
        except Exception:
            logger.exception("Documento renomeado localmente, mas a nuvem não foi enfileirada")
        return DocumentModel.from_entity(updated)

    def filter_by_type(self, file_type: str, folder_id: int | None = None) -> list[DocumentModel]:
        self._require("document.view")
        if not file_type or file_type.lower() == "todos":
            return self.list_documents(folder_id)
        return self._models(
            self.document_repository.find_by_type(
                file_type, self.active_organization_id, folder_id
            )
        )

    def get_recent_documents(self) -> list[DocumentModel]:
        self._require("document.view")
        return self._models(self.document_repository.find_recent(10, self.active_organization_id))

    def get_favorite_documents(self) -> list[DocumentModel]:
        self._require("document.view")
        return self._models(self.document_repository.find_favorites(self.active_organization_id))

    def get_trashed_documents(self) -> list[DocumentModel]:
        self._require("document.view")
        return self._models(self.document_repository.find_trashed(self.active_organization_id))

    @document_mutation
    def toggle_favorite(self, document_id: int) -> DocumentModel:
        self._require("document.update")
        updated = self.document_repository.toggle_favorite(document_id, self.active_organization_id)
        if updated is None:
            raise InvalidDocumentError("Documento não encontrado.")
        self._record_history(updated.id, "FAVORITE", f"Favorito atualizado: {updated.name}")
        return DocumentModel.from_entity(updated)

    @document_mutation
    def delete_document(self, document_id: int) -> bool:
        self._require("document.delete")
        entity = self.document_repository.find_by_id(document_id, self.active_organization_id)
        if entity is None:
            return False
        changed = self.document_repository.soft_delete(document_id, self.active_organization_id)
        if changed:
            self._record_history(document_id, "DELETE", f"Documento movido para lixeira: {entity.name}")
        return changed

    @document_mutation
    def restore_document(self, document_id: int) -> DocumentModel:
        self._require("document.update")
        if not self.document_repository.restore(document_id, self.active_organization_id):
            raise InvalidDocumentError("Documento não encontrado.")
        restored = self.document_repository.find_by_id(document_id, self.active_organization_id)
        if restored is None:
            raise InvalidDocumentError("Documento não encontrado.")
        self._record_history(document_id, "RESTORE", f"Documento restaurado: {restored.name}")
        return DocumentModel.from_entity(restored)

    @document_mutation
    def copy_document(self, document_id: int, folder_id: int | None = None) -> DocumentModel:
        self._require("document.create")
        source=self.document_repository.find_by_id(document_id,self.active_organization_id)
        if source is None: raise InvalidDocumentError("Documento não encontrado.")
        path=Path(source.storage_path or source.path).expanduser().resolve()
        if not path.is_file(): raise InvalidDocumentError("Arquivo do documento não encontrado.")
        operation_id=self.storage_quota_service.reserve(self.active_organization_id,source.size,str(uuid4()))
        stored=None
        committed=False
        now=self._now()
        try:
            stored=self.storage_service.store(path,source.checksum)
            entity=replace(source,id=None,public_uuid=None,folder_id=folder_id,name=f"Cópia de {source.name}",path=stored.storage_path,storage_path=stored.storage_path,internal_name=stored.internal_name,status="ACTIVE",favorite=False,created_at=now,updated_at=now,last_accessed_at=None,cloud_status="LOCAL_ONLY",cloud_provider=None,remote_id=None,remote_version=None,last_synced_at=None)
            with self.database.transaction():
                created=self.document_repository.create(entity)
                self._record_history(created.id,"COPY",f"Cópia criada de {source.name}")
                self.storage_quota_service.commit_reservation(operation_id)
            committed=True
            try:self.cloud_sync_service.enqueue_upload(created.id,self.active_organization_id)
            except Exception:logger.exception("Cópia local criada, mas a sincronização não foi enfileirada")
            self._enqueue_transport_upload(created.id, self.active_organization_id)
            return DocumentModel.from_entity(created)
        except Exception:
            if not committed:self.storage_quota_service.release_reservation(operation_id)
            if stored is not None and not committed:self.storage_service.remove(stored.storage_path)
            raise

    def open_document(self, document_id: int) -> DocumentModel:
        self._require("document.open")
        entity = self.document_repository.find_by_id(document_id, self.active_organization_id)
        if entity is None:
            raise InvalidDocumentError("Documento não encontrado.")
        if entity.status != "ACTIVE":
            raise InvalidDocumentError("O documento está na lixeira.")
        if entity.managed:
            if not entity.storage_path or not self.storage_service.exists(entity.storage_path):
                raise InvalidDocumentError("O arquivo interno do documento não foi encontrado.")
            path = Path(entity.storage_path)
        else:
            path = Path(entity.path).expanduser().resolve()
        if not path.exists() or not path.is_file():
            raise InvalidDocumentError("O arquivo não existe mais no caminho registrado.")
        entity.last_accessed_at = self._now()
        entity.updated_at = entity.last_accessed_at
        updated = self.document_repository.update(entity)
        observed=self._calculate_checksum(path)
        if observed != entity.checksum:
            previous=self.audit.repository.find_by_organization(entity.organization_id,1,document_uuid=entity.public_uuid,action='CONTENT_CHANGED_OBSERVED')
            before=previous[0].sha256_after if previous else entity.checksum
            import re
            before=before if before and re.fullmatch(r'[a-f0-9]{64}',before) else None
            if before != observed:
                self._record_history(entity.id,'CONTENT_CHANGED_OBSERVED','Alteração dos bytes observada ao abrir; autor externo desconhecido',
                    sha256_before=before,sha256_after=observed,details={'content_editor':'UNKNOWN','catalog_hash_changed':False})
        self._record_history(entity.id, "OPEN", f"Documento aberto: {entity.name}",sha256_after=observed)
        return DocumentModel.from_entity(updated)

    @document_mutation
    def permanently_delete_document(self, document_id: int) -> bool:
        """Remove registro e arquivo gerenciado; ainda não exposto pela interface."""
        self._require("document.delete")
        entity = self.document_repository.find_by_id(document_id, self.active_organization_id)
        if entity is None or entity.status != "TRASHED":
            return False
        quarantine: Path | None = None
        original_storage: Path | None = None
        if entity.managed and entity.storage_path:
            original_storage = Path(entity.storage_path).resolve()
            if not self.storage_service.is_managed_path(original_storage):
                raise StorageError("Caminho interno inválido para exclusão permanente.")
            if original_storage.exists():
                quarantine = self.storage_service.create_temp_path(original_storage.suffix)
                original_storage.replace(quarantine)
        try:
            with self.database.transaction():
                self.corporate_transport_service.prepare_document_delete(
                    document_id, self.active_organization_id,
                )
                self._record_history(
                    document_id,
                    "PERMANENT_DELETE",
                    f"Documento excluído permanentemente: {entity.name}",
                )
                deleted = self.document_repository.hard_delete(document_id, self.active_organization_id)
                if deleted and entity.managed:
                    self.storage_quota_service.release_used(entity.organization_id, entity.size)
        except Exception:
            if quarantine and quarantine.exists() and original_storage:
                original_storage.parent.mkdir(parents=True, exist_ok=True)
                quarantine.replace(original_storage)
            raise
        if quarantine and quarantine.exists():
            try:
                quarantine.unlink()
            except OSError:
                logger.exception(
                    "Documento removido do catálogo, mas a limpeza da quarentena falhou "
                    "document_id=%s",
                    document_id,
                )
        return deleted

    def empty_trash(self) -> int:
        self._require("document.delete")
        documents = self.document_repository.find_trashed(self.active_organization_id)
        count = 0
        for document in documents:
            if self.permanently_delete_document(document.id):
                count += 1
        return count

    @document_mutation
    def update_metadata(self, document_id: int, **values) -> DocumentModel:
        self._require('document.update')
        allowed = {'category', 'tags', 'description', 'notes', 'document_date'}
        if not values or not set(values).issubset(allowed):
            raise InvalidDocumentError('Campos de metadados inválidos.')
        entity = self.document_repository.find_by_id(document_id, self.active_organization_id)
        if entity is None:
            raise InvalidDocumentError('Documento não encontrado.')
        changed = []
        for key, value in values.items():
            if value is not None and (not isinstance(value, str) or len(value) > 4000):
                raise InvalidDocumentError('Metadado inválido ou muito longo.')
            value = value.strip() or None if isinstance(value, str) else value
            if getattr(entity, key) != value:
                setattr(entity, key, value)
                changed.append(key)
        if changed:
            entity.updated_at = self._now()
            self.document_repository.update(entity)
            self._record_history(document_id, 'METADATA_UPDATED', 'Metadados atualizados', details={'fields': sorted(changed)})
        return DocumentModel.from_entity(entity)

    def export_document(self, document_id: int, destination, *, cancelled=None, organization_id=None):
        scope = organization_id if organization_id is not None else self.active_organization_id
        self._require('document.open', scope)
        entity = self.document_repository.find_by_id(document_id, scope)
        if entity is None:
            raise InvalidDocumentError('Documento não encontrado.')
        actor = self.audit.capture(entity.organization_id)
        source = Path(entity.storage_path or entity.path)
        if self._calculate_checksum(source, cancelled) != entity.checksum:
            raise StorageError('O arquivo atual não corresponde ao SHA-256 do catálogo.')
        result = self.storage_service.export(str(source), Path(destination))
        with self.audit.bind(actor):
            self._record_history(document_id, 'EXPORT', 'Documento exportado com SHA-256 confirmado', sha256_after=entity.checksum)
        return result

    def record_output(self, output, source_paths=(), *, action='CREATE', public_uuid=None, source_type='PDF_TOOLS'):
        from types import SimpleNamespace
        actor=self.audit.current_actor() or self.audit.capture(self.active_organization_id)
        self._require('tools.use',actor.organization_id)
        paths=tuple(dict.fromkeys(Path(path).resolve() for path in source_paths if path))
        sources=[self.document_repository.find_by_scoped_path(path,actor.organization_id) for path in paths]
        known=[document for document in sources if document is not None]
        document=known[0] if len(paths)==1 and len(known)==1 else SimpleNamespace(
            public_uuid=public_uuid or str(uuid4()),name=Path(output).name,source_type=source_type)
        before=self._calculate_checksum(paths[0]) if len(paths)==1 and paths[0].is_file() else None
        after=self._calculate_checksum(Path(output))
        self.audit.record(action,organization_id=actor.organization_id,actor=actor,
            target_type='document',target_id=getattr(document,'id',None),document=document,
            sha256_before=before,sha256_after=after,source_type=source_type,
            details={'source_preserved':True,'output_name':Path(output).name,
                'source_documents':[doc.public_uuid for doc in known]})

    def get_physical_storage_usage(self, organization_id=None, *, cancelled=None):
        scope = organization_id if organization_id is not None else self.active_organization_id
        self._require('document.view', scope)
        from app.services.physical_storage_service import PhysicalStorageService
        return PhysicalStorageService(self.database).for_organization(scope, cancelled=cancelled)

    def get_storage_usage(self):
        self._require("document.view")
        return self.storage_quota_service.get_usage_summary(self.active_organization_id)

    def recalculate_storage_usage(self):
        self._require("document.update")
        return self.storage_quota_service.recalculate_usage(self.active_organization_id)

    def get_largest_documents(self, limit: int = 10) -> list[DocumentModel]:
        self._require("document.view")
        return self._models(
            self.document_repository.find_largest(self.active_organization_id, limit)
        )

    @document_mutation
    def move_document(self, document_id: int, folder_id: int | None) -> DocumentModel:
        self._require("document.update")
        if folder_id is not None:
            folder = self.folder_service.repository.find_by_id(folder_id, self.active_organization_id)
            if folder is None or folder.status != "ACTIVE":
                raise InvalidDocumentError("Pasta inválida para a organização ativa.")
        if not self.document_repository.move_to_folder(
            document_id, self.active_organization_id, folder_id
        ):
            raise InvalidDocumentError("Documento não encontrado na organização ativa.")
        document = self.get_document(document_id)
        if document is None:
            raise InvalidDocumentError("Documento não encontrado.")
        self._record_history(document_id, "MOVE", "Documento movido para outra pasta lógica")
        try:
            self.cloud_sync_service.enqueue_move(document_id, self.active_organization_id)
        except Exception:
            logger.exception("Movimento local concluído, mas não foi enfileirado na nuvem")
        return document

    @document_mutation
    def delete_folder(self, folder_id: int) -> bool:
        self._require("folder.delete")
        affected = self.document_repository.find_in_folder_tree(
            self.active_organization_id, folder_id
        )
        changed = self.folder_service.delete(self.active_organization_id, folder_id)
        if changed:
            self.document_repository.clear_deleted_folders(self.active_organization_id)
            for document in affected:
                try:
                    self.cloud_sync_service.enqueue_move(
                        document.id, self.active_organization_id
                    )
                except Exception:
                    logger.exception(
                        "Pasta removida localmente, mas movimento remoto não foi enfileirado"
                    )
        return changed

    def _record_history(self, document_id: Optional[int], action: str, description: str, **evidence) -> None:
        self.history_service.record_action(document_id, action, description, **evidence)

    def _enqueue_transport_upload(self, document_id: int, organization_id: int) -> None:
        try:
            self.corporate_transport_service.enqueue_upload(
                document_id, organization_id,
            )
        except Exception:
            logger.exception(
                "Documento salvo localmente, mas o transporte corporativo não foi enfileirado "
                "organization_id=%s document_id=%s",
                organization_id, document_id,
            )

    @staticmethod
    def _validated_path(file_path: str) -> Path:
        try:
            path = Path(file_path).expanduser().resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise InvalidDocumentError("O arquivo informado não existe.") from exc
        if not path.is_file():
            raise InvalidDocumentError("O caminho informado não é um arquivo regular.")
        return path

    @staticmethod
    def _models(entities: list[DocumentEntity]) -> list[DocumentModel]:
        return [DocumentModel.from_entity(entity) for entity in entities]

    @staticmethod
    def _calculate_checksum(path: Path, cancelled=None) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                if cancelled and cancelled():raise InterruptedError("Importação cancelada.")
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _classify_file_type(extension: str) -> str:
        if extension == ".pdf":
            return "PDF"
        if extension in {".doc", ".docx"}:
            return "DOCX"
        if extension in {".xls", ".xlsx", ".csv"}:
            return "SPREADSHEET"
        if extension in {".jpg", ".jpeg", ".png", ".tiff", ".bmp"}:
            return "IMAGE"
        if extension in {".txt", ".md", ".rtf"}:
            return "TEXT"
        return "OTHER"

    @staticmethod
    def _classify_category(extension: str) -> str:
        if extension in {".pdf", ".doc", ".docx"}:
            return "Documento"
        if extension in {".xls", ".xlsx", ".csv"}:
            return "Planilha"
        if extension in {".jpg", ".jpeg", ".png", ".tiff", ".bmp"}:
            return "Imagem"
        if extension in {".txt", ".md", ".rtf"}:
            return "Texto"
        return "Arquivo"

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
