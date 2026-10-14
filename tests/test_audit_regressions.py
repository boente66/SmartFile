import os
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest
from PIL import Image
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QDialogButtonBox
from app.auth.session_context import SessionContext
from app.entities.organization_member_entity import OrganizationMemberEntity
from app.models.user_model import UserModel
from app.models.convert_job import ConvertJob
from app.models.capture_pdf_workspace import CapturePdfPage
from app.controllers.pdf_viewer_controller import PDFViewerController
from app.controllers.remote_mount_controller import RemoteMountController
from app.services.document_service import DocumentService
from app.services.capture_pdf_service import CapturePdfService
from app.services.document_geometry_service import DocumentGeometryService
from app.services.convert_service import ConvertService
from app.utils.atomic_output import atomic_output
from app.utils.file_naming import safe_output_path
from app.views.document_import_dialog import DocumentImportDialog
from app.views.scanner_import_dialog import ScannerImportDialog
from app.views.workspace_view import WorkspaceView
from app.workers.convert_worker import ConvertWorker

_APP = None

def application():
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def document_context(tmp_path, role='VIEWER'):
    service = DocumentService(db_path=str(tmp_path/'audit.sqlite'))
    organization = service.organization_service.active()
    context = SessionContext(current_user=UserModel(id=1,username="audit",email=None,display_name="Audit",phone=None,is_active=True,is_superuser=False,last_login_at=None), session_id=1,
        active_organization=organization,
        memberships=[OrganizationMemberEntity(organization_id=organization.id,user_id=1,role=role)])
    context._refresh_permissions()
    service.session_context = context
    service.folder_service.session_context = context
    return service, context


@pytest.mark.parametrize('operation', ['import', 'folder', 'delete', 'copy', 'rename'])
def test_viewer_cannot_bypass_controller_permissions(tmp_path, operation):
    service, _ = document_context(tmp_path)
    with pytest.raises(RuntimeError, match='Permissão insuficiente'):
        if operation == 'import': service.import_document(str(tmp_path/'not-readable.pdf'))
        elif operation == 'folder': service.folder_service.create(service.active_organization_id,'Forbidden')
        elif operation == 'delete': service.delete_document(123)
        elif operation == 'copy': service.copy_document(123)
        else: service.rename_document(123,'Forbidden')
    assert service.list_documents() == []


def test_permissions_are_taken_from_destination_membership(tmp_path):
    service, context = document_context(tmp_path, 'OWNER')
    other = service.organization_service.create('Another')
    context.memberships.append(OrganizationMemberEntity(organization_id=other.id,user_id=1,role='VIEWER'))
    with pytest.raises(RuntimeError,match='Permissão insuficiente'):
        service.import_document(str(tmp_path/'missing.pdf'), organization_id=other.id)
    organizations, _ = service.import_destinations()
    assert [o.id for o in organizations] == [context.active_organization.id]


def test_atomic_publication_does_not_overwrite_raced_destination(tmp_path):
    target = tmp_path/'document.pdf'
    with pytest.raises(FileExistsError):
        with atomic_output(target) as temporary:
            temporary.write_bytes(b'new')
            target.write_bytes(b'concurrent user file')
    assert target.read_bytes() == b'concurrent user file'
    assert len(list(tmp_path.iterdir())) == 1


def test_atomic_publication_rejects_dangling_symlink(tmp_path):
    target = tmp_path/'document.pdf'
    try: target.symlink_to(tmp_path/'other.pdf')
    except OSError: pytest.skip('Symlinks not permitted on this platform')
    with pytest.raises(FileExistsError):
        with atomic_output(target): pass
    assert target.is_symlink() and not (tmp_path/'other.pdf').exists()


def test_capture_preserves_previous_output_and_unrelated_part_file(tmp_path):
    image=Image.new('RGB',(20,30),'white')
    page=CapturePdfPage(image=image)
    target=tmp_path/'output.pdf'; target.write_bytes(b'previous')
    unrelated=tmp_path/'.output.pdf.part'; unrelated.write_bytes(b'unrelated work')
    with pytest.raises(FileExistsError): CapturePdfService.materialize([page],target)
    assert target.read_bytes()==b'previous' and unrelated.read_bytes()==b'unrelated work'
    image.close()


def test_crop_failure_is_visible_and_does_not_publish_full_background(tmp_path,monkeypatch):
    image=Image.new('RGB',(50,80),'gray'); original=image.tobytes()
    page=CapturePdfPage(image=image,geometry=DocumentGeometryService.from_corners(image.size,((.1,.1),(.9,.1),(.9,.9),(.1,.9))))
    def failure(*_): raise RuntimeError('invalid transform')
    monkeypatch.setattr(DocumentGeometryService,'transform',failure)
    with pytest.raises(ValueError,match='aplicar o recorte'):
        CapturePdfService.materialize([page],tmp_path/'crop.pdf')
    assert not (tmp_path/'crop.pdf').exists() and image.tobytes()==original
    image.close()


def test_cancelled_conversion_does_not_delete_similarly_named_user_files(tmp_path,monkeypatch):
    source=tmp_path/'input.txt'; source.write_text('hello')
    unrelated=tmp_path/'output_2.jpg'; unrelated.write_bytes(b'user original')
    worker=ConvertWorker(ConvertJob(source,tmp_path/'output.jpg','TXT','JPG'))
    monkeypatch.setattr(worker,'isInterruptionRequested',lambda:True)
    worker.run()
    assert unrelated.read_bytes()==b'user original'


def test_multi_page_conversion_rolls_back_only_owned_files_on_collision(tmp_path):
    source=tmp_path/'input.tiff'
    first=Image.new('RGB',(20,30),'white'); second=Image.new('RGB',(20,30),'black')
    first.save(source,save_all=True,append_images=[second]);first.close();second.close()
    unrelated=tmp_path/'output_2.jpg'; unrelated.write_bytes(b'user original')
    with pytest.raises(FileExistsError):
        ConvertService.execute(ConvertJob(source,tmp_path/'output.jpg','TIFF','JPG'))
    assert unrelated.read_bytes()==b'user original' and not (tmp_path/'output.jpg').exists()
    assert not list(tmp_path.glob('smartfile-convert-*'))


def test_import_dialog_is_data_only_and_validation_is_visible():
    application()
    dialog=ScannerImportDialog([],{},None)
    dialog._accept_valid()
    assert dialog.error_label.text() and dialog.result()!=dialog.DialogCode.Accepted
    assert not hasattr(dialog,'service')
    dialog.close()


def test_import_labels_remain_legible_with_dark_document_parent():
    app=application(); parent=QWidget()
    parent.setStyleSheet('QLabel { color: #ffffff; }')
    dialog=DocumentImportDialog('Organization',[],parent=parent)
    dialog.show();app.processEvents()
    label=next(w for w in dialog.findChildren(QLabel) if w.text().startswith('Escolha'))
    assert label.palette().color(label.foregroundRole()).name()=='#172033'
    dialog._accept_if_valid()
    assert dialog.error_label.text()
    assert dialog.buttons.button(QDialogButtonBox.StandardButton.Cancel).text()=='Cancelar'
    dialog.close();parent.close()


def test_late_thumbnail_and_errors_do_not_modify_new_pdf(monkeypatch):
    application();controller=PDFViewerController(WorkspaceView())
    old=object(); current=object(); controller._thumbnail_worker=current; controller._path=Path('new.pdf')
    events=[]
    monkeypatch.setattr(controller.view,'set_thumbnail',lambda *args:events.append(args))
    monkeypatch.setattr(controller.view,'set_loading',lambda *args:events.append(args))
    controller._thumbnail_ready(old,1,None)
    controller._worker_failed(old,'thumbnail','previous document error')
    assert events==[]
    controller._thumbnail_ready(current,2,None)
    assert events==[(2,None)]
    controller._thumbnail_worker=None;controller._path=None;controller.view.close()


def test_remote_error_from_other_organization_is_ignored(monkeypatch):
    controller=RemoteMountController.__new__(RemoteMountController)
    controller.context=SimpleNamespace(active_organization=SimpleNamespace(id=2))
    controller._scan_request=3;controller._plan_request=1
    events=[]
    controller.view=SimpleNamespace(set_remote_inventory_status=lambda *args:events.append(args))
    controller._scan_failed('previous organization',1,3)
    controller._scan_failed('old request',2,2)
    assert not events


def test_safe_output_path_handles_timestamp_collision(tmp_path,monkeypatch):
    from app.utils import file_naming
    monkeypatch.setattr(file_naming,'datetime',SimpleNamespace(now=lambda:SimpleNamespace(strftime=lambda _: 'same_time')))
    target=tmp_path/'report.pdf';target.touch()
    (tmp_path/'report_same_time.pdf').touch()
    assert safe_output_path(target)==tmp_path/'report_same_time_2.pdf'


def delivery_for_scope(tmp_path, organization_id=2, recipient=1):
    from app.services.document_delivery_service import DocumentDeliveryService
    service = DocumentDeliveryService.__new__(DocumentDeliveryService)
    row = {'delivery_id':1, 'received_path':str(tmp_path/'private.pdf'),
           'transfer_status':'VERIFIED','size':3,'sha256':'0'*64}
    service.database = SimpleNamespace(fetch_one=lambda *args:row)
    service.context=SessionContext(current_user=UserModel(1,'user',None,'User',None,True,False,None),session_id=1,
        active_organization=SimpleNamespace(id=organization_id),permissions={'delivery.download'},
        memberships=[OrganizationMemberEntity(organization_id=organization_id,user_id=1,role='VIEWER')])
    service.organizations=SimpleNamespace(repository=SimpleNamespace(find_by_id=lambda _:SimpleNamespace(id=1)))
    service.features=SimpleNamespace(require=lambda *args:None)
    service._delivery=lambda _:SimpleNamespace(organization_id=1,recipient_user_id=recipient,direction='INCOMING')
    return service


def test_download_received_item_rejects_other_organization_before_reading_file(tmp_path):
    service=delivery_for_scope(tmp_path)
    with pytest.raises(PermissionError,match='organização da entrega'):
        service.download_item(1,tmp_path/'out.pdf')
    assert not (tmp_path/'out.pdf').exists()


def test_download_received_item_rejects_other_recipient(tmp_path):
    service=delivery_for_scope(tmp_path,organization_id=1,recipient=2)
    with pytest.raises(PermissionError,match='destinatário'):
        service.download_item(1,tmp_path/'out.pdf')


def test_backup_does_not_overwrite_existing_backup(tmp_path):
    from app.services.backup_service import BackupService
    from app.errors.backup_exceptions import InvalidBackupDestinationError
    from dataclasses import replace
    service,context=document_context(tmp_path,'OWNER');context.current_user=replace(context.current_user,is_superuser=True)
    target=tmp_path/'backup.zip';target.write_bytes(b'previous backup')
    with pytest.raises(InvalidBackupDestinationError,match='já existe'):
        BackupService(service.database,context).create_full_backup(target)
    assert target.read_bytes()==b'previous backup'


def test_views_do_not_import_business_services_or_database():
    import ast
    root=Path(__file__).resolve().parents[1]/'app/views'
    for path in root.rglob('*.py'):
        tree=ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.ImportFrom):
                assert not (node.module or '').startswith(('app.services','app.repositories','app.database')), path.name


def test_invalid_signature_image_is_reported_by_acquisition_widget(tmp_path,monkeypatch):
    application()
    from app.views.widgets.signature_acquisition_widget import SignatureAcquisitionWidget
    from PyQt6.QtWidgets import QFileDialog,QMessageBox
    source=tmp_path/'broken.png';source.write_bytes(b'not an image')
    monkeypatch.setattr(QFileDialog,'getOpenFileName',lambda *args:(str(source),''))
    warnings=[];monkeypatch.setattr(QMessageBox,'warning',lambda *args:warnings.append(args[2]))
    widget=SignatureAcquisitionWidget();widget._choose_image()
    assert len(warnings)==1 and widget._imported==b''
    widget.close()


def test_oversized_signature_is_rejected_before_qt_decoding(monkeypatch):
    from io import BytesIO
    from app.imaging.signature_image import SignatureImageNormalizer,QImage
    from app.errors.handwritten_signature_exceptions import SignatureImageError
    data=BytesIO();Image.new('RGB',(5000,1),'white').save(data,format='PNG')
    def unexpected_decode(*args): raise AssertionError('Oversized image reached Qt decoder')
    monkeypatch.setattr(QImage,'fromData',unexpected_decode)
    with pytest.raises(SignatureImageError,match='4096'):
        SignatureImageNormalizer().normalize(data.getvalue())


def test_multi_page_tiff_conversion_produces_main_output_for_worker(tmp_path):
    source=tmp_path/'input.tiff';first=Image.new('RGB',(12,20),'white');second=Image.new('RGB',(12,20),'black')
    first.save(source,save_all=True,append_images=[second]);first.close();second.close()
    ConvertService.execute(ConvertJob(source,tmp_path/'output.jpg','TIFF','JPG'))
    assert (tmp_path/'output.jpg').is_file() and (tmp_path/'output_2.jpg').is_file()
    with Image.open(tmp_path/'output.jpg') as image:assert image.getpixel((3,3))[0]>240
    with Image.open(tmp_path/'output_2.jpg') as image:assert image.getpixel((3,3))[0]<20


def test_corrupt_notification_preferences_recover_without_interrupting_requests(tmp_path):
    from app.services.request_notification_service import RequestNotificationService
    service=DocumentService(db_path=str(tmp_path/'notifications.sqlite'))
    notifications=RequestNotificationService(service.database)
    service.database.execute_query('INSERT INTO app_settings(key,value) VALUES(?,?)',('requests.notifications.1.1','broken json'))
    request=SimpleNamespace(id=1,organization_id=1,assigned_to_user_id=1,requested_by_user_id=2,status='OPEN')
    notifications.activate(1,1,[request])
    assert notifications.unread=={1}
    request.status='COMPLETED';notifications.observe(1,1,[request])
    assert not notifications.unread


@pytest.mark.parametrize('name',['../private.pdf','C:private.pdf','original.pdf:hidden','CON.pdf','NUL','report.','..','line\nbreak.pdf'])
def test_delivery_filenames_are_safe_for_both_operating_systems(name):
    from app.services.document_delivery_service import DocumentDeliveryService
    from app.errors.delivery_exceptions import DeliveryValidationError
    with pytest.raises(DeliveryValidationError):DocumentDeliveryService._safe_name(name)


def test_close_pdf_removes_previous_document_thumbnail_and_search_state():
    application();controller=PDFViewerController(WorkspaceView())
    controller.view.thumbnails.prepare(3)
    controller.view.search_bar.input.setText('private previous search')
    controller.view.page_size_status.setText('previous dimensions')
    controller.close_document()
    assert controller.view.thumbnails.list_widget.count()==0
    assert not controller.view.search_bar.input.text() and not controller.view.page_size_status.text()
    controller.view.close()


def test_readonly_role_does_not_regain_signature_buttons_when_context_changes():
    from app.views.pdf_viewer_view import PDFViewerView
    from app.models.pdf_viewer_context import PDFViewerContext
    application();view=PDFViewerView();view._tools_permission=False
    view.set_document_loaded(True);view.set_context(PDFViewerContext.document())
    assert not view.btn_sign.isEnabled() and not view.btn_handwritten_sign.isEnabled()
    view.close()


def test_cancelled_file_worker_does_not_emit_late_error(monkeypatch):
    from app.workers.file_operation_worker import FileOperationWorker
    def task(*args):raise OSError('late error')
    worker=FileOperationWorker(task);events=[]
    worker.failed.connect(lambda _:events.append('failure'))
    worker.cancelled.connect(lambda:events.append('cancelled'))
    monkeypatch.setattr(worker,'isInterruptionRequested',lambda:True)
    worker.run()
    assert events==['cancelled']


def test_cancelled_import_preserves_original_and_leaves_no_document_or_reservation(tmp_path):
    service=DocumentService(db_path=str(tmp_path/'cancel-import.sqlite'))
    source=tmp_path/'source.txt';source.write_bytes(b'a'*(2*1024*1024))
    with pytest.raises(InterruptedError):service.import_document(str(source),cancelled=lambda:True)
    assert source.stat().st_size==2*1024*1024 and not service.list_documents()
    assert not list(service.database.paths.storage.rglob('*.*'))


def test_batch_import_uses_snapshot_destination_and_does_not_update_other_organization(tmp_path,monkeypatch):
    from PyQt6.QtCore import QEventLoop,QTimer
    from app.controllers.document_controller import DocumentController
    from app.views.document_view import DocumentView
    from PyQt6.QtWidgets import QDialog
    app=application();service=DocumentService(db_path=str(tmp_path/'batch.sqlite'))
    original_org=service.active_organization_id;other=service.organization_service.create('Other organization')
    source=tmp_path/'source.txt';source.write_text('original content')
    monkeypatch.setattr(DocumentImportDialog,'exec',lambda _:QDialog.DialogCode.Accepted)
    monkeypatch.setattr(DocumentImportDialog,'values',lambda _:dict(paths=(source,),folder_id=None,category=None,tags=None))
    controller=DocumentController.__new__(DocumentController)
    controller.service=service;controller.session_context=None;controller._import_worker=None;controller._closing=False
    controller.view=DocumentView();controller._current_folder_id=None
    updates=[]
    controller._refresh_folders=lambda:updates.append('folders');controller.on_refresh_documents=lambda:updates.append('documents')
    controller._auto_sync=lambda:None;controller._notify_transport_jobs=lambda:None
    controller.on_import_document()
    assert controller._import_worker is not None and not controller.view.btn_import.isEnabled()
    service.set_active_organization(other.id)
    loop=QEventLoop();timer=QTimer();timer.timeout.connect(lambda:loop.quit() if controller._import_worker is None else None)
    timer.start(10);QTimer.singleShot(10000,loop.quit);loop.exec();timer.stop();app.processEvents()
    assert controller._import_worker is None and not updates and service.list_documents()==[]
    service.set_active_organization(original_org)
    assert len(service.list_documents())==1 and source.read_text()=='original content'
    controller.view.close()


@pytest.mark.parametrize('reader',[False,True])
def test_repository_operations_cannot_join_transaction_started_after_connect(tmp_path,reader,monkeypatch):
    import threading
    from app.database.database import Database
    from app.repositories.base_repository import BaseRepository
    database=Database(str(tmp_path/'threads.sqlite'));repository=BaseRepository(database=database)
    database.execute_query('CREATE TABLE audit_thread_rows(value TEXT)')
    real_connection=database.connect()
    start_owner=threading.Event();owner_started=threading.Event();release=threading.Event();finished=threading.Event()
    results=[];errors=[]
    class ConnectionProxy:
        def __getattr__(self,name):return getattr(real_connection,name)
        @property
        def in_transaction(self):
            if threading.current_thread().name=='independent-writer':
                start_owner.set();owner_started.wait(.2)
            return real_connection.in_transaction
        def execute(self,query,params=()):
            if threading.current_thread().name=='independent-reader' and query.startswith('SELECT'):
                start_owner.set();owner_started.wait(.2)
            return real_connection.execute(query,params)
    proxy=ConnectionProxy()
    monkeypatch.setattr(database,'connect',lambda:proxy)
    def owner():
        try:
            assert start_owner.wait(3)
            with database.transaction() as connection:
                connection.execute("INSERT INTO audit_thread_rows VALUES ('rolled back')")
                owner_started.set();release.wait(3)
                raise RuntimeError('intentional rollback')
        except RuntimeError:pass
        except Exception as error:errors.append(error)
    def other():
        try:
            if reader:results.extend(repository._fetch_all('SELECT * FROM audit_thread_rows'))
            else:repository._write("INSERT INTO audit_thread_rows VALUES ('independent')")
        except Exception as error:errors.append(error)
        finally:finished.set()
    first=threading.Thread(target=owner);second=threading.Thread(target=other,name='independent-reader' if reader else 'independent-writer')
    first.start();second.start()
    try:
        assert finished.wait(3)
        assert owner_started.wait(3)
    finally:release.set();first.join(3);second.join(3)
    assert not errors and not first.is_alive() and not second.is_alive()
    rows=database.fetch_all('SELECT value FROM audit_thread_rows')
    assert [row['value'] for row in rows]==([] if reader else ['independent'])
    assert results==[]
    monkeypatch.undo();database.close()

@pytest.mark.parametrize('outer_valid', [True, False])
def test_parallel_receiving_preserves_verified_file(tmp_path, outer_valid):
    import hashlib
    import io
    from app.services.document_delivery_service import DocumentDeliveryService
    from app.errors.delivery_exceptions import DeliveryIntegrityError
    good, bad = b'valid document', b'wrong document'
    item = SimpleNamespace(item_uuid='item', delivery_id=1, logical_name='document.pdf',
        size=len(good), sha256=hashlib.sha256(good).hexdigest(), transfer_status='PENDING')
    def update(uuid, status, path, received_at):
        item.transfer_status, item.received_path = status, path
    def fail(uuid):
        if item.transfer_status != 'VERIFIED': update(uuid, 'FAILED', None, None)
    service = DocumentDeliveryService.__new__(DocumentDeliveryService)
    service.database = SimpleNamespace(paths=SimpleNamespace(data_dir=tmp_path))
    service.items = SimpleNamespace(find_by_uuid=lambda uuid: item,
        update_received=update, mark_failed_unless_verified=fail)
    service._protocol_delivery = lambda protocol: SimpleNamespace(id=1)
    service._now = lambda: '2026-10-13T00:00:00Z'
    class NestedStream(io.BytesIO):
        triggered = False
        def read(self, size=-1):
            if not self.triggered:
                self.triggered = True
                try:
                    service.receive_item('protocol', 'item', io.BytesIO(bad if outer_valid else good), len(good))
                except DeliveryIntegrityError:
                    assert outer_valid
            return super().read(size)
    if outer_valid:
        service.receive_item('protocol', 'item', NestedStream(good), len(good))
    else:
        with pytest.raises(DeliveryIntegrityError):
            service.receive_item('protocol', 'item', NestedStream(bad), len(good))
    assert item.transfer_status == 'VERIFIED'
    assert Path(item.received_path).read_bytes() == good
    assert not list(tmp_path.rglob('*.part'))
