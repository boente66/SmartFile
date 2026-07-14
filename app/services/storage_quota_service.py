from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from app.database.database import Database
from app.entities.storage_reservation_entity import StorageReservationEntity
from app.errors.storage_exceptions import (
    InsufficientLocalDiskSpaceError,
    StorageQuotaExceededError,
    StorageQuotaError,
    StorageRecalculationError,
    StorageReservationError,
)
from app.repositories.document_repository import DocumentRepository
from app.repositories.organization_repository import OrganizationRepository
from app.repositories.organization_storage_repository import OrganizationStorageRepository
from app.repositories.storage_plan_repository import StoragePlanRepository
from app.repositories.storage_reservation_repository import StorageReservationRepository
from app.services.audit_service import AuditService

logger = logging.getLogger(__name__)
GB = 1024 ** 3


def gb_to_bytes(value: int | float) -> int:
    """Conversão central dos planos exibidos em GB para armazenamento em bytes."""
    if value < 0:
        raise ValueError("O valor em GB não pode ser negativo.")
    return int(value * GB)


def bytes_to_gb(value: int) -> float:
    return max(0, int(value)) / GB


PLAN_BY_TEMPLATE = {
    "PERSONAL": "PERSONAL_10GB",
    "STUDENT": "STUDENT_20GB",
    "BUSINESS": "BUSINESS_60GB",
    "EMPTY": "PERSONAL_10GB",
}


@dataclass(frozen=True, slots=True)
class StorageUsageSummary:
    organization_id: int
    plan_code: str
    plan_name: str
    quota_bytes: int
    used_bytes: int
    reserved_bytes: int
    available_bytes: int
    percent: float
    level: str
    local_free_bytes: int


class StorageQuotaService:
    """Controla cota, reservas concorrentes e uso efetivo por organização."""

    def __init__(self, database: Database, storage_path: Path | None = None):
        self.database = database
        self.storage_path = Path(storage_path or database.storage_dir)
        self.plans = StoragePlanRepository(database=database)
        self.organizations = OrganizationRepository(database=database)
        self.storage = OrganizationStorageRepository(database=database)
        self.reservations = StorageReservationRepository(database=database)
        self.documents = DocumentRepository(database=database)
        self.audit = AuditService(database)

    def assign_plan(self, organization_id: int, plan_code: str, template_code: str = "EMPTY"):
        plan = self.plans.find_by_code(plan_code)
        if plan is None or not plan.is_active:
            raise StorageQuotaError("Plano de armazenamento inválido ou inativo.")
        current = self.storage.find_by_organization(organization_id)
        if current and current.used_bytes + current.reserved_bytes > plan.quota_bytes:
            raise StorageQuotaError(
                "O plano selecionado é menor que o uso e as reservas atuais da organização."
            )
        now = self._now()
        with self.database.transaction():
            result = self.storage.assign_plan(organization_id, plan.id, plan.quota_bytes, now)
            self.organizations.set_storage_profile(organization_id, template_code, plan.code, now)
        logger.info("Plano atribuído organization_id=%s plan=%s", organization_id, plan.code)
        self.audit.record(
            "STORAGE_PLAN_ASSIGNED", organization_id=organization_id,
            target_type="storage_plan", target_id=plan.id, description=f"Plano atribuído: {plan.code}",
        )
        return result

    def ensure_organization(self, organization_id: int, template_code: str = "EMPTY"):
        current = self.storage.find_by_organization(organization_id)
        if current:
            return current
        plan_code = PLAN_BY_TEMPLATE.get(template_code.upper(), "PERSONAL_10GB")
        return self.assign_plan(organization_id, plan_code, template_code)

    def get_quota(self, organization_id: int) -> int:
        return self.ensure_organization(organization_id).quota_bytes

    def get_used(self, organization_id: int) -> int:
        return self.ensure_organization(organization_id).used_bytes

    def get_reserved(self, organization_id: int) -> int:
        return self.ensure_organization(organization_id).reserved_bytes

    def get_available(self, organization_id: int) -> int:
        item = self.ensure_organization(organization_id)
        return max(0, item.quota_bytes - item.used_bytes - item.reserved_bytes)

    def can_store(self, organization_id: int, size_bytes: int) -> bool:
        return int(size_bytes) >= 0 and int(size_bytes) <= self.get_available(organization_id)

    def validate_local_space(self, size_bytes: int) -> None:
        self.storage_path.mkdir(parents=True, exist_ok=True)
        free = shutil.disk_usage(self.storage_path).free
        if int(size_bytes) > free:
            raise InsufficientLocalDiskSpaceError(
                "Não há espaço suficiente no disco local para armazenar este documento."
            )

    def reserve(
        self,
        organization_id: int,
        size_bytes: int,
        operation_id: str | None = None,
        expires_in: timedelta = timedelta(minutes=30),
    ) -> str:
        size = int(size_bytes)
        if size < 0:
            raise StorageReservationError("O tamanho reservado não pode ser negativo.")
        self.validate_local_space(size)
        operation = operation_id or str(uuid4())
        now = self._now()
        expires_at = (datetime.now(timezone.utc) + expires_in).isoformat()
        try:
            with self.database.transaction():
                self._cleanup_expired_locked(now)
                current = self.ensure_organization(organization_id)
                if not self.storage.reserve_if_available(organization_id, size, now):
                    raise StorageQuotaExceededError(
                        current.used_bytes + current.reserved_bytes, current.quota_bytes, size
                    )
                self.reservations.create(StorageReservationEntity(
                    operation_id=operation, organization_id=organization_id, size_bytes=size,
                    status="RESERVED", created_at=now, expires_at=expires_at,
                ))
        except StorageQuotaExceededError:
            self.audit.record(
                "STORAGE_QUOTA_EXCEEDED", organization_id=organization_id,
                target_type="storage", description=f"Reserva recusada: {size} bytes",
            )
            raise
        logger.info("Reserva criada organization_id=%s operation_id=%s size=%s", organization_id, operation, size)
        self.audit.record(
            "STORAGE_RESERVED", organization_id=organization_id, target_type="storage_reservation",
            description=f"Reserva {operation}: {size} bytes",
        )
        return operation

    def commit_reservation(self, operation_id: str) -> None:
        now = self._now()
        with self.database.transaction():
            reservation = self._reserved(operation_id)
            if not self.storage.commit_reserved(reservation.organization_id, reservation.size_bytes, now):
                raise StorageReservationError("A reserva não corresponde ao total reservado da organização.")
            if not self.reservations.update_status(operation_id, "RESERVED", "COMMITTED", "committed_at", now):
                raise StorageReservationError("Não foi possível confirmar a reserva.")
        logger.info("Reserva confirmada operation_id=%s", operation_id)
        self.audit.record(
            "STORAGE_RESERVATION_COMMITTED", organization_id=reservation.organization_id,
            target_type="storage_reservation", description=f"Reserva confirmada: {operation_id}",
        )

    def release_reservation(self, operation_id: str) -> bool:
        now = self._now()
        with self.database.transaction():
            reservation = self.reservations.find_by_operation(operation_id)
            if reservation is None or reservation.status != "RESERVED":
                return False
            if not self.storage.release_reserved(reservation.organization_id, reservation.size_bytes, now):
                raise StorageReservationError("Não foi possível liberar o espaço reservado.")
            if not self.reservations.update_status(operation_id, "RESERVED", "RELEASED", "released_at", now):
                raise StorageReservationError("Não foi possível liberar a reserva.")
        logger.info("Reserva liberada operation_id=%s", operation_id)
        self.audit.record(
            "STORAGE_RESERVATION_RELEASED", organization_id=reservation.organization_id,
            target_type="storage_reservation", description=f"Reserva liberada: {operation_id}",
        )
        return True

    def release_used(self, organization_id: int, size_bytes: int) -> None:
        self.storage.release_used(organization_id, max(0, int(size_bytes)), self._now())

    def cleanup_expired(self) -> int:
        with self.database.transaction():
            return self._cleanup_expired_locked(self._now())

    def recalculate_usage(self, organization_id: int) -> int:
        try:
            total = 0
            for document in self.documents.find_managed_for_usage(organization_id):
                path = Path(document.storage_path or document.path)
                if path.is_file():
                    total += path.stat().st_size
            self.ensure_organization(organization_id)
            self.storage.set_used(organization_id, total, self._now())
            logger.info("Cota recalculada organization_id=%s used=%s", organization_id, total)
            self.audit.record(
                "STORAGE_RECALCULATED", organization_id=organization_id,
                target_type="storage", description=f"Uso recalculado: {total} bytes",
            )
            return total
        except Exception as exc:
            raise StorageRecalculationError("Não foi possível recalcular o armazenamento.") from exc

    def get_usage_summary(self, organization_id: int) -> StorageUsageSummary:
        item = self.ensure_organization(organization_id)
        plan = next((p for p in self.plans.find_all(False) if p.id == item.storage_plan_id), None)
        percent = 100.0 if item.quota_bytes == 0 else min(100.0, item.used_bytes * 100 / item.quota_bytes)
        level = "BLOQUEADO" if percent >= 100 else "CRÍTICO" if percent >= 90 else "ATENÇÃO" if percent >= 80 else "NORMAL"
        self.storage_path.mkdir(parents=True, exist_ok=True)
        return StorageUsageSummary(
            organization_id=organization_id, plan_code=plan.code if plan else "",
            plan_name=plan.name if plan else "Plano", quota_bytes=item.quota_bytes,
            used_bytes=item.used_bytes, reserved_bytes=item.reserved_bytes,
            available_bytes=max(0, item.quota_bytes-item.used_bytes-item.reserved_bytes),
            percent=percent, level=level, local_free_bytes=shutil.disk_usage(self.storage_path).free,
        )

    def _cleanup_expired_locked(self, now: str) -> int:
        expired = self.reservations.find_expired(now)
        for reservation in expired:
            self.storage.release_reserved(reservation.organization_id, reservation.size_bytes, now)
            self.reservations.update_status(
                reservation.operation_id, "RESERVED", "EXPIRED", "released_at", now
            )
        return len(expired)

    def _reserved(self, operation_id: str) -> StorageReservationEntity:
        reservation = self.reservations.find_by_operation(operation_id)
        if reservation is None or reservation.status != "RESERVED":
            raise StorageReservationError("Reserva inexistente ou já finalizada.")
        return reservation

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
