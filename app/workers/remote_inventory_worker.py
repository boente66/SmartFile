from PyQt6.QtCore import QThread, pyqtSignal


class RemoteBrowseWorker(QThread):
    succeeded=pyqtSignal(int,object);failed=pyqtSignal(int,str)
    def __init__(self,provider,parent_id,request_id,parent=None):
        super().__init__(parent);self.provider=provider;self.parent_id=parent_id;self.request_id=request_id
    def run(self):
        try:self.succeeded.emit(self.request_id,self.provider.list_children(self.parent_id))
        except Exception as exc:self.failed.emit(self.request_id,str(exc))


class RemoteInventoryWorker(QThread):
    progress=pyqtSignal(int,str);succeeded=pyqtSignal(int);failed=pyqtSignal(str)
    def __init__(self,service,organization_id,mount_id,parent=None):
        super().__init__(parent);self.service=service;self.organization_id=organization_id;self.mount_id=mount_id
    def run(self):
        try:
            count=self.service.scan(
                self.organization_id,self.mount_id,
                progress=lambda value,message:self.progress.emit(min(95,value),message),
                cancelled=self.isInterruptionRequested,
            );self.succeeded.emit(count)
        except Exception as exc:self.failed.emit(str(exc))


class MulticloudReconciliationWorker(QThread):
    progress=pyqtSignal(int,str);succeeded=pyqtSignal(str);failed=pyqtSignal(str)
    def __init__(self,service,organization_id,plan_id,parent=None):
        super().__init__(parent);self.service=service;self.organization_id=organization_id;self.plan_id=plan_id
    def run(self):
        try:self.succeeded.emit(self.service.execute(
            self.organization_id,self.plan_id,
            progress=lambda value,message:self.progress.emit(value,message),
            cancelled=self.isInterruptionRequested,
        ))
        except Exception as exc:self.failed.emit(str(exc))
