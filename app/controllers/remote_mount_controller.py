from __future__ import annotations

from PyQt6.QtWidgets import QDialog,QMessageBox

from app.services.remote_inventory_service import RemoteInventoryService
from app.views.remote_mount_dialog import RemoteMountDialog
from app.views.remote_workspace_dialog import RemoteWorkspaceDialog
from app.workers.remote_inventory_worker import (
    MulticloudReconciliationWorker,RemoteBrowseWorker,RemoteInventoryWorker,
)
from app.services.multicloud_reconciliation_service import MulticloudReconciliationService


class RemoteMountController:
    def __init__(self,database,cloud_manager,context,view,parent=None):
        self.database=database;self.cloud_manager=cloud_manager;self.context=context
        self.view=view;self.parent=parent or view
        self.service=RemoteInventoryService(database,cloud_manager,context)
        self.reconciliation=MulticloudReconciliationService(database,cloud_manager,context)
        self.dialog=None;self.browse_worker=None;self.scan_worker=None;self.plan_worker=None;self._request=0
        self._browse_org_id=None;self._scan_org_id=None

    def open(self):
        try:
            org=self.context.active_organization
            mounts=self.service.list_mounts(org.id)
            if mounts:
                manager=RemoteWorkspaceDialog(mounts,self.parent)
                manager.add_requested.connect(lambda:self._open_mount(org.id))
                manager.scan_requested.connect(lambda mount_id:self._scan(mount_id,org.id))
                manager.unmount_requested.connect(lambda mount_id:self._unmount(org.id,mount_id,manager))
                manager.reconcile_requested.connect(lambda key:self._reconcile(org.id,key))
                manager.exec();return
            self._open_mount(org.id)
        except Exception as exc:QMessageBox.warning(self.parent,"Acervo remoto",str(exc))

    def _open_mount(self,organization_id):
        try:
            org=self.context.active_organization
            if org.id!=organization_id:return
            accounts=self.cloud_manager.accounts_for_organization(org.id)
            if not accounts:raise ValueError("Conecte uma conta OneDrive ou Google Drive primeiro.")
            dialog=RemoteMountDialog(accounts,self.parent);self.dialog=dialog
            dialog.browse_requested.connect(self._browse)
            if dialog.exec()!=QDialog.DialogCode.Accepted:return
            account,metadata,logical,collection=dialog.values()
            mount=self.service.mount(org.id,account.id,account.provider,metadata.remote_id,
                                     metadata.name,logical,collection_key=collection)
            self._scan(mount.id,org.id)
        except Exception as exc:QMessageBox.warning(self.parent,"Acervo remoto",str(exc))

    def _unmount(self,organization_id,mount_id,dialog):
        answer=QMessageBox.question(
            dialog,"Desmontar acervo",
            "Remover somente o espelho local? Nenhum arquivo remoto será excluído.",
        )
        if answer==QMessageBox.StandardButton.Yes:
            self.service.unmount(organization_id,mount_id);dialog.accept();self.refresh()

    def _reconcile(self,organization_id,collection_key):
        try:
            plan,actions=self.reconciliation.build_plan(organization_id,collection_key)
            if not actions:
                QMessageBox.information(self.parent,"Plano multicloud","Nenhuma readequação segura foi proposta.");return
            lines="\n".join(f"• {item.reason} [{item.risk_level}]" for item in actions)
            answer=QMessageBox.question(
                self.parent,"Autorizar plano multicloud",
                f"Plano somente proposto; nada foi executado ainda.\n\n{lines}\n\nAutorizar estas ações?",
            )
            if answer!=QMessageBox.StandardButton.Yes:return
            self.reconciliation.authorize(organization_id,plan.id,[item.id for item in actions])
            self.view.set_remote_inventory_status("SYNCING","Executando plano autorizado…")
            worker=MulticloudReconciliationWorker(
                self.reconciliation,organization_id,plan.id,self.parent
            );self.plan_worker=worker
            worker.succeeded.connect(lambda status,org=organization_id:self._plan_done(org,status))
            worker.failed.connect(lambda message:self._scan_failed(message))
            worker.finished.connect(worker.deleteLater);worker.start()
        except Exception as exc:QMessageBox.warning(self.parent,"Plano multicloud",str(exc))

    def _plan_done(self,organization_id,status):
        if organization_id!=getattr(self.context.active_organization,"id",None):return
        QMessageBox.information(self.parent,"Plano multicloud",f"Execução concluída: {status}.")
        self.refresh()

    def _browse(self,account_id,parent_id):
        try:
            org_id=self.context.active_organization.id
            self._browse_org_id=org_id
            provider=self.cloud_manager.provider_for_account(org_id,account_id)
            self._request+=1;request=self._request
            worker=RemoteBrowseWorker(provider,parent_id,request,self.parent);self.browse_worker=worker
            worker.succeeded.connect(lambda req,items,p=parent_id:self._browsed(req,p,items))
            worker.failed.connect(lambda req,msg:self._browse_failed(req,msg))
            worker.finished.connect(worker.deleteLater);worker.start()
        except Exception as exc:self.dialog.show_error(str(exc))
    def _browsed(self,request,parent_id,items):
        if (request!=self._request or self.dialog is None or
            self._browse_org_id!=getattr(self.context.active_organization,"id",None)):return
        self.dialog.populate(parent_id,items)
    def _browse_failed(self,request,message):
        if (request==self._request and self.dialog and
            self._browse_org_id==getattr(self.context.active_organization,"id",None)):
            self.dialog.show_error(message)
    def _scan(self,mount_id,organization_id):
        self._scan_org_id=organization_id
        self.view.set_remote_inventory_status("SCANNING","Atualizando espelho…")
        worker=RemoteInventoryWorker(self.service,organization_id,mount_id,self.parent);self.scan_worker=worker
        worker.succeeded.connect(lambda _count,org=organization_id:self._scan_done(org))
        worker.failed.connect(lambda message:self._scan_failed(message))
        worker.finished.connect(worker.deleteLater);worker.start()
    def _scan_done(self,organization_id):
        if organization_id==getattr(self.context.active_organization,"id",None):self.refresh()
    def _scan_failed(self,message):
        self.view.set_remote_inventory_status("ERROR",message)
        QMessageBox.warning(self.parent,"Acervo remoto",message)
    def refresh(self):
        try:
            org_id=self.context.active_organization.id
            mounts=self.service.list_mounts(org_id)
            nodes={mount.id:self.service.nodes(org_id,mount.id) for mount in mounts}
            self.view.set_remote_mounts(mounts,nodes)
            self.view.set_remote_inventory_status("ACTIVE",f"{len(mounts)} montagem(ns)")
        except PermissionError:self.view.set_remote_mounts([],{});self.view.set_remote_inventory_status("HIDDEN","")

    def shutdown(self):
        for worker in (self.browse_worker,self.scan_worker,self.plan_worker):
            if worker is not None and worker.isRunning():worker.requestInterruption();worker.wait(5000)
