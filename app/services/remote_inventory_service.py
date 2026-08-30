from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import PurePosixPath
from uuid import uuid4

from app.cloud.cloud_models import RemoteItemType
from app.entities.multicloud_entity import RemoteCatalogNodeEntity, RemoteMountEntity
from app.errors.multicloud_exceptions import RemoteMountError
from app.repositories.multicloud_repository import (
    LogicalCloudRepository, RemoteCatalogRepository, RemoteMountRepository,
)
from app.services.organization_feature_service import OrganizationFeatureService

logger = logging.getLogger(__name__)


class RemoteInventoryService:
    """Espelha apenas metadados. Nunca cria Document, storage ou item remoto."""

    MAX_NODES_PER_SCAN = 100_000

    def __init__(self, database, cloud_manager, context=None):
        self.database=database;self.cloud_manager=cloud_manager;self.context=context
        self.mounts=RemoteMountRepository(database=database)
        self.catalog=RemoteCatalogRepository(database=database)
        self.logical=LogicalCloudRepository(database=database)
        self.features=OrganizationFeatureService(database)

    def mount(self, organization_id: int, cloud_account_id: int, provider: str,
              remote_root_id: str, remote_root_name: str, logical_mount_name: str,
              *, collection_key: str | None = None) -> RemoteMountEntity:
        organization=self._require(organization_id,"cloud.view")
        account=self.cloud_manager.account(cloud_account_id,organization_id)
        normalized_provider=provider.strip().upper()
        if account.provider != normalized_provider:
            raise RemoteMountError("A conta não pertence ao provedor selecionado.")
        root_id=remote_root_id.strip();root_name=self._label(remote_root_name)
        logical_name=self._label(logical_mount_name)
        if not root_id:
            raise RemoteMountError("Selecione uma pasta remota.")
        # Confirma a identidade remota sem alterá-la.
        metadata=self.cloud_manager.provider_for_account(
            organization_id,cloud_account_id
        ).get_metadata(root_id)
        if metadata.item_type != RemoteItemType.FOLDER:
            raise RemoteMountError("Somente pastas remotas podem ser montadas.")
        key=self._collection_key(collection_key or str(uuid4()))
        now=self._now()
        mounted=self.mounts.create(RemoteMountEntity(
            organization_id=organization.id,cloud_account_id=cloud_account_id,
            provider=normalized_provider,remote_root_id=root_id,
            remote_root_name=metadata.name or root_name,
            logical_mount_name=logical_name,collection_key=key,created_at=now,
        ))
        logger.info("multicloud.mount.created org=%s mount=%s provider=%s",
                    organization_id,mounted.id,normalized_provider)
        return mounted

    def scan(self, organization_id: int, mount_id: int, *, progress=None,
             cancelled=None) -> int:
        self._require(organization_id,"cloud.view")
        mount=self.mounts.find(mount_id,organization_id)
        if mount is None: raise RemoteMountError("Montagem remota não encontrada.")
        provider=self.cloud_manager.provider_for_account(
            organization_id,mount.cloud_account_id
        )
        started=self._now();self.mounts.set_status(mount.id,organization_id,"SCANNING")
        queue=[(mount.remote_root_id,PurePosixPath("."))]
        visited={mount.remote_root_id};count=0
        try:
            while queue:
                if cancelled and cancelled():
                    raise RemoteMountError("Atualização do espelho cancelada.")
                parent_id,parent_path=queue.pop(0)
                for item in provider.list_children(parent_id):
                    if not item.remote_id or item.remote_id in visited:
                        continue
                    visited.add(item.remote_id)
                    node_type=("FOLDER" if item.item_type==RemoteItemType.FOLDER else "FILE")
                    logical_path=str(parent_path / self._path_component(item.name))
                    if logical_path.startswith("./"):logical_path=logical_path[2:]
                    saved=self.catalog.upsert(RemoteCatalogNodeEntity(
                        organization_id=organization_id,mount_id=mount.id,
                        cloud_account_id=mount.cloud_account_id,provider=mount.provider,
                        remote_id=item.remote_id,remote_parent_id=parent_id,
                        logical_path=logical_path,node_type=node_type,name=item.name,
                        mime_type=item.mime_type,size=item.size,modified_at=item.modified_at,
                        provider_hash=item.provider_hash,version=item.version,
                        discovered_at=started,last_seen_at=self._now(),
                    ))
                    count += 1
                    if saved.node_type == "FOLDER":queue.append((saved.remote_id,PurePosixPath(logical_path)))
                    if count > self.MAX_NODES_PER_SCAN:
                        raise RemoteMountError("O acervo excedeu o limite seguro desta versão.")
                    if progress and count % 25 == 0:progress(count,f"Catalogados {count} itens")
            self.catalog.mark_missing_before(mount.id,started)
            nodes=self.catalog.list_for_collection(organization_id,mount.collection_key)
            self.logical.rebuild_collection(organization_id,mount.collection_key,nodes,self._now())
            finished=self._now();self.mounts.set_status(
                mount.id,organization_id,"ACTIVE",scanned_at=finished,error=None
            )
            logger.info("multicloud.scan.done org=%s mount=%s nodes=%s",
                        organization_id,mount.id,count)
            return count
        except Exception as exc:
            self.mounts.set_status(mount.id,organization_id,"ERROR",error=str(exc)[:500])
            logger.exception("multicloud.scan.failed org=%s mount=%s",organization_id,mount.id)
            raise

    def unmount(self, organization_id: int, mount_id: int) -> bool:
        self._require(organization_id,"cloud.view")
        # Deliberadamente não resolve nem chama provider.delete().
        removed=self.mounts.unmount(mount_id,organization_id)
        logger.info("multicloud.mount.removed_local org=%s mount=%s",organization_id,mount_id)
        return removed

    def list_mounts(self, organization_id: int):
        self._require(organization_id,"cloud.view")
        return self.mounts.list_for_organization(organization_id)

    def nodes(self, organization_id: int, mount_id: int):
        self._require(organization_id,"cloud.view")
        if self.mounts.find(mount_id,organization_id) is None:
            raise RemoteMountError("Montagem remota não encontrada.")
        return self.catalog.list_for_mount(mount_id,organization_id)

    def _require(self, organization_id: int, permission: str):
        organization=getattr(self.context,"active_organization",None)
        if organization is None or organization.id != organization_id:
            raise PermissionError("Ative a organização do acervo remoto.")
        self.features.require(organization,"multicloud_workspace")
        if self.context:self.context.require_permission(permission)
        return organization

    @staticmethod
    def _label(value: str) -> str:
        clean=" ".join(value.split()).strip()
        if not clean or len(clean)>120:raise RemoteMountError("Nome de montagem inválido.")
        return clean

    @staticmethod
    def _path_component(value: str) -> str:
        clean=value.replace("/","⁄").replace("\0","").strip()
        return clean or "sem-nome"

    @staticmethod
    def _collection_key(value: str) -> str:
        clean=re.sub(r"[^a-zA-Z0-9_.-]","-",value.strip())[:100].strip("-.")
        if not clean:raise RemoteMountError("Identificador da coleção inválido.")
        return clean

    @staticmethod
    def _now() -> str:return datetime.now(timezone.utc).isoformat()
