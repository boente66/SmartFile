from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from app.cloud.cloud_models import CloudUploadRequest
from app.entities.multicloud_entity import MulticloudPlanActionEntity, MulticloudPlanEntity
from app.errors.multicloud_exceptions import ReconciliationAuthorizationError, ReplicaConflictError
from app.repositories.multicloud_repository import (
    LogicalCloudRepository, MulticloudPlanRepository, RemoteCatalogRepository,
    RemoteMountRepository,
)
from app.services.organization_feature_service import OrganizationFeatureService

logger=logging.getLogger(__name__)


class MulticloudReconciliationService:
    """Propõe primeiro; somente um plano explicitamente autorizado pode escrever."""
    def __init__(self,database,cloud_manager,context):
        self.database=database;self.cloud_manager=cloud_manager;self.context=context
        self.mounts=RemoteMountRepository(database=database)
        self.catalog=RemoteCatalogRepository(database=database)
        self.logical=LogicalCloudRepository(database=database)
        self.plans=MulticloudPlanRepository(database=database)
        self.features=OrganizationFeatureService(database)

    def build_plan(self,organization_id:int,collection_key:str):
        self._require(organization_id,"cloud.view")
        now=self._now();plan=self.plans.create_plan(MulticloudPlanEntity(
            organization_id=organization_id,plan_uuid=str(uuid4()),created_at=now,
        ))
        mounts=[m for m in self.mounts.list_for_organization(organization_id)
                if m.collection_key==collection_key and m.status!="DISCONNECTED"]
        for obj in self.logical.objects(organization_id,collection_key):
            replicas=self.logical.replicas(obj.id,organization_id)
            present={item.mount_id for item in replicas}
            if obj.identity_state=="DIVERGED":
                continue
            for target in mounts:
                if target.id in present or not replicas or obj.object_type!="FILE":continue
                source=replicas[0]
                source_detail=self.plans.replica_detail(source.id,organization_id)
                if source_detail is None or str(source_detail["mime_type"] or "").startswith(
                    "application/vnd.google-apps."
                ):
                    # Documentos nativos exigem exportação explícita; não são bytes comuns.
                    continue
                parent_path=obj.logical_path.rpartition("/")[0]
                target_parent=target.remote_root_id
                if parent_path:
                    folder=self.catalog.find_path(
                        target.id,organization_id,parent_path
                    )
                    # Não achata a estrutura nem cria pastas implicitamente.
                    if folder is None or folder.node_type!="FOLDER":continue
                    target_parent=folder.remote_id
                key=hashlib.sha256(
                    f"{organization_id}:{obj.id}:{source.id}:{target.id}:REPLICATE".encode()
                ).hexdigest()
                self.plans.add_action(MulticloudPlanActionEntity(
                    organization_id=organization_id,plan_id=plan.id,
                    action_type="REPLICATE_FILE",source_replica_id=source.id,
                    target_mount_id=target.id,target_parent_remote_id=target_parent,
                    logical_object_id=obj.id,risk_level="LOW",
                    reason=f"Réplica ausente em {target.logical_mount_name}",
                    idempotency_key=key,created_at=now,
                ))
        logger.info("multicloud.plan.created org=%s plan=%s actions=%s",organization_id,
                    plan.id,len(self.plans.actions(plan.id,organization_id)))
        return plan,self.plans.actions(plan.id,organization_id)

    def authorize(self,organization_id:int,plan_id:int,action_ids:list[int]):
        self._require(organization_id,"cloud.sync")
        user_id=getattr(getattr(self.context,"current_user",None),"id",None)
        if user_id is None:raise ReconciliationAuthorizationError("Usuário autenticado obrigatório.")
        actions={item.id:item for item in self.plans.actions(plan_id,organization_id)}
        selected=[actions[item] for item in action_ids if item in actions]
        if len(selected)!=len(set(action_ids)):
            raise ReconciliationAuthorizationError("A seleção contém ação inválida.")
        if any(item.risk_level=="HIGH" for item in selected):
            raise ReconciliationAuthorizationError(
                "Ações destrutivas exigem confirmação individual e não são automáticas."
            )
        self.plans.authorize(plan_id,organization_id,action_ids,user_id,self._now())

    def execute(self,organization_id:int,plan_id:int,*,progress=None,cancelled=None):
        self._require(organization_id,"cloud.sync")
        plan=self.plans.find_plan(plan_id,organization_id)
        if plan is None or plan.status!="AUTHORIZED":
            raise ReconciliationAuthorizationError("Autorize o plano antes de executar.")
        actions=[a for a in self.plans.actions(plan_id,organization_id)
                 if a.status=="AUTHORIZED"]
        self.plans.set_plan_status(plan_id,organization_id,"RUNNING")
        failures=0
        for index,action in enumerate(actions,1):
            if cancelled and cancelled():
                self.plans.set_plan_status(plan_id,organization_id,"PARTIAL",error="Cancelado pelo usuário")
                return "PARTIAL"
            try:
                self.plans.set_action_status(action.id,organization_id,"RUNNING")
                if action.action_type!="REPLICATE_FILE":
                    raise ReconciliationAuthorizationError("Ação ainda não suportada com segurança.")
                self._replicate(organization_id,action)
                self.plans.set_action_status(action.id,organization_id,"COMPLETED",completed_at=self._now())
                if progress:progress(int(index*100/max(1,len(actions))),"Réplica concluída")
            except Exception as exc:
                failures+=1;self.plans.set_action_status(
                    action.id,organization_id,"ERROR",error=str(exc)[:500]
                );logger.exception("multicloud.action.failed action=%s",action.id)
        status="PARTIAL" if failures else "COMPLETED"
        self.plans.set_plan_status(plan_id,organization_id,status,completed_at=self._now(),
                                   error=f"{failures} falha(s)" if failures else None)
        return status

    def _replicate(self,organization_id:int,action):
        source=self.plans.replica_detail(action.source_replica_id,organization_id)
        target=self.mounts.find(action.target_mount_id,organization_id)
        if source is None or target is None:raise ReplicaConflictError("Origem ou destino não existe mais.")
        source_provider=self.cloud_manager.provider_for_account(
            organization_id,int(source["cloud_account_id"]),permission="cloud.sync"
        );target_provider=self.cloud_manager.provider_for_account(
            organization_id,target.cloud_account_id,permission="cloud.sync"
        )
        existing=target_provider.list_children(action.target_parent_remote_id)
        if any(item.name==source["logical_name"] for item in existing):
            raise ReplicaConflictError(
                "Já existe um item com esse nome no destino; a identidade não foi presumida."
            )
        temp=(self.database.temp_dir/f"multicloud-{uuid4().hex}.part").resolve()
        if self.database.temp_dir.resolve() not in temp.parents:
            raise ReplicaConflictError("Caminho temporário inseguro.")
        try:
            source_provider.download(str(source["remote_id"]),temp)
            digest=self._sha256(temp)
            if temp.stat().st_size != int(source["size"]):
                raise ReplicaConflictError("O tamanho baixado difere do inventário.")
            target_provider.upload(CloudUploadRequest(
                local_path=temp,remote_name=str(source["logical_name"]),
                remote_parent_id=action.target_parent_remote_id,
            ))
            logger.info("multicloud.replica.created action=%s sha256=%s",action.id,digest)
        finally:
            temp.unlink(missing_ok=True)

    def _require(self,organization_id:int,permission:str):
        org=getattr(self.context,"active_organization",None)
        if org is None or org.id!=organization_id:raise PermissionError("Ative a organização do plano.")
        self.features.require(org,"multicloud_workspace")
        self.context.require_permission(permission)

    @staticmethod
    def _sha256(path:Path)->str:
        digest=hashlib.sha256()
        with path.open("rb") as handle:
            while chunk:=handle.read(1024*1024):digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _now()->str:return datetime.now(timezone.utc).isoformat()
