import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from types import SimpleNamespace
from PyQt6.QtWidgets import QApplication
from app.cloud.cloud_models import RemoteItemType
from app.views.remote_mount_dialog import RemoteMountDialog
from app.controllers.remote_mount_controller import RemoteMountController

APP = QApplication.instance() or QApplication([])


def test_constructor_does_not_start_browse_and_empty_state_finishes():
    app=QApplication.instance() or QApplication([])
    account=SimpleNamespace(id=1,provider='GOOGLE_DRIVE',display_name='Conta')
    dialog=RemoteMountDialog([account])
    received=[];dialog.browse_requested.connect(lambda *args:received.append(args))
    assert not received
    dialog.load_root()
    assert received==[(1,None)]
    dialog.populate(None,[])
    assert dialog.progress.isHidden()
    assert 'Nenhuma pasta' in dialog.status.text()
    dialog.show_error('Erro de rede')
    assert dialog.progress.isHidden()
    assert dialog.status.text()=='Erro de rede'
    dialog.close()


def test_account_org_close_generation_and_parallel_expansions():
    app=QApplication.instance() or QApplication([])
    accounts=[SimpleNamespace(id=i,provider='GOOGLE_DRIVE',display_name=str(i)) for i in (1,2)]
    dialog=RemoteMountDialog(accounts)
    controller=RemoteMountController.__new__(RemoteMountController)
    controller.dialog=dialog;controller.context=SimpleNamespace(active_organization=SimpleNamespace(id=1))
    controller._pending_browse={1:(dialog,1,1,'first',0),2:(dialog,1,1,'second',0)}
    assert controller._valid_browse(1)
    assert controller._valid_browse(2)
    controller._pending_browse={3:(dialog,1,1,None,0)}
    dialog.account.setCurrentIndex(1)
    assert not controller._valid_browse(3)
    controller._pending_browse={4:(dialog,1,2,None,dialog.browse_generation)}
    controller.context.active_organization.id=2
    assert not controller._valid_browse(4)
    controller.context.active_organization.id=1
    controller._pending_browse={5:(dialog,1,2,None,dialog.browse_generation)}
    controller._close_browse(dialog)
    assert not controller._valid_browse(5)
    dialog.close()
