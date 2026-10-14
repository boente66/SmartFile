import base64
from dataclasses import asdict, replace
from io import BytesIO
import hashlib
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import fitz
from PIL import Image
import pytest

from app.auth.session_context import SessionContext
from app.database.database import Database
from app.entities.organization_member_entity import OrganizationMemberEntity
from app.entities.user_entity import UserEntity
from app.models.user_model import UserModel
from app.repositories.organization_member_repository import OrganizationMemberRepository
from app.repositories.user_repository import UserRepository
from app.services.document_service import DocumentService
from app.services.organization_identity_service import OrganizationIdentityService
from app.services.document_validation_service import DocumentValidationService
from app.entities.validation_record import ArtifactType, SignatureType
from app.workers.file_operation_worker import FileOperationWorker


@pytest.fixture
def enterprise(tmp_path):
    def create(root):
        root.mkdir(parents=True,exist_ok=True)
        database=Database(str(root/'smartfile.db'))
        plain=DocumentService(database=database)
        organization=plain.organization_service.active()
        plain.organization_service.repository.set_feature_profile(organization.id,'BUSINESS','2026-10-13')
        organization=plain.organization_service.active()
        users=UserRepository(database=database);members=OrganizationMemberRepository(database=database)
        alice=users.create(UserEntity(username='alice',display_name='Alice',password_hash='unused',created_at='2026-10-13',updated_at='2026-10-13'))
        bob=users.create(UserEntity(username='bob',display_name='Bob',password_hash='unused',created_at='2026-10-13',updated_at='2026-10-13'))
        memberships=[members.create(OrganizationMemberEntity(organization_id=organization.id,user_id=u.id,role=role,created_at='2026-10-13',updated_at='2026-10-13')) for u,role in ((alice,'OWNER'),(bob,'EDITOR'))]
        context=SessionContext();context.login(UserModel.from_entity(alice),1,organization,memberships)
        documents=DocumentService(database=database,session_context=context)
        return SimpleNamespace(database=database,context=context,documents=documents,alice=alice,bob=bob,organization=organization,memberships=memberships,root=root)
    value=create(tmp_path/'local');value.create=create
    yield value
    value.database.close()


def make_pdf(path,text='document'):
    document=fitz.open();page=document.new_page();page.insert_text((50,50),text);document.save(path);document.close();return path


def import_text(e,name='document.txt',content=b'original',**kwargs):
    path=e.root/name;path.write_bytes(content)
    return e.documents.import_document(str(path),sync_cloud=False,**kwargs)


def switch_user(e,user):
    e.context.login(UserModel.from_entity(user),user.id,e.organization,e.memberships)


def events(e,document):
    return e.documents.audit.for_document(e.organization.id,document.id)


def validation(e,source,document_id=None):
    service=DocumentValidationService(e.database,e.context)
    record=service.create_pending(e.organization.id,logical_name=source.name,
        artifact_type=ArtifactType.UNSIGNED_REGISTERED_DOCUMENT,signature_type=SignatureType.NONE,document_id=document_id)
    return service,service.activate(record,source)


def test_two_users_same_organization_have_distinct_actors(enterprise):
    e=enterprise
    first=import_text(e,'first.txt')
    switch_user(e,e.bob)
    second=import_text(e,'second.txt',b'other bytes')
    rows=[events(e,d)[0] for d in (first,second)]
    assert [r.actor_username for r in rows]==['alice','bob']
    assert [r.user_id for r in rows]==[e.alice.id,e.bob.id]
    assert rows[0].instance_id==rows[1].instance_id
    assert rows[0].organization_uuid==rows[1].organization_uuid==e.organization.public_uuid


def test_scan_import_rename_move_and_metadata_are_distinct(enterprise):
    e=enterprise
    scanned=import_text(e,source_type='SCANNER')
    initial=scanned.checksum
    renamed=e.documents.rename_document(scanned.id,'Renamed.txt')
    folder=e.documents.folder_service.create(e.organization.id,'Financeiro')
    moved=e.documents.move_document(scanned.id,folder.id)
    updated=e.documents.update_metadata(scanned.id,category='Contrato',tags='2026',notes='metadata')
    assert renamed.checksum==moved.checksum==updated.checksum==initial
    rows=events(e,scanned)
    assert {'SCAN','RENAME','MOVE','METADATA_UPDATED'}<= {r.action for r in rows}
    assert next(r for r in rows if r.action=='SCAN').sha256_after==initial
    metadata=next(r for r in rows if r.action=='METADATA_UPDATED')
    assert metadata.sha256_before is metadata.sha256_after is None
    assert Path(updated.path).read_bytes()==b'original'
    with pytest.raises(Exception):e.documents.update_metadata(scanned.id,checksum='bad')


def test_worker_captured_in_a_never_records_in_b(enterprise):
    e=enterprise
    actor=e.documents.audit.capture(e.organization.id)
    other=e.documents.organization_service.create('Another organization')
    membership=OrganizationMemberEntity(organization_id=other.id,user_id=e.alice.id,role='OWNER')
    e.context.memberships.append(membership)
    before_b=e.documents.audit.repository.find_by_organization(other.id)
    source=e.root/'worker.txt';source.write_bytes(b'worker original')
    worker=FileOperationWorker(lambda progress,cancelled:e.documents.import_document(str(source),organization_id=e.organization.id,sync_cloud=False),audit_actor=actor)
    e.documents.organization_service.set_active(other.id);e.context.set_active_organization(other)
    results=[];errors=[];worker.succeeded.connect(results.append);worker.failed.connect(errors.append)
    worker.run()
    assert not errors and len(results)==1
    row=e.documents.audit.repository.find_by_organization(e.organization.id)[0]
    assert row.actor_username=='alice' and row.organization_id==e.organization.id
    assert e.documents.audit.repository.find_by_organization(other.id)==before_b


def test_organization_isolation_for_document_history(enterprise):
    e=enterprise;document=import_text(e)
    other=e.documents.organization_service.create('Restricted')
    with pytest.raises(RuntimeError):e.documents.audit.for_document(other.id,document.id)


def test_permanent_delete_retains_queryable_immutable_evidence(enterprise):
    e=enterprise;document=import_text(e)
    e.documents.delete_document(document.id)
    e.documents.permanently_delete_document(document.id)
    rows=events(e,document)
    assert {'IMPORT','DELETE','PERMANENT_DELETE'} <= {r.action for r in rows}
    assert all(r.document_uuid==document.public_uuid for r in rows)
    connection=e.database.connect()
    for statement in ('UPDATE audit_log SET actor_username="forged"','DELETE FROM audit_log'):
        with pytest.raises(sqlite3.IntegrityError):connection.execute(statement)
    assert e.database.fetch_all('PRAGMA foreign_key_check')==[]


def test_cloud_content_change_records_actual_previous_and_new_hash(enterprise):
    e=enterprise;document=import_text(e)
    entity=e.documents.document_repository.find_by_id(document.id);entity.remote_id='shared-item'
    provider=SimpleNamespace(download=lambda remote_id,destination:destination.write_bytes(b'new cloud bytes'))
    e.documents.cloud_sync_service._download(provider,entity,actor=e.documents.audit.capture(e.organization.id))
    row=next(r for r in events(e,document) if r.action=='CONTENT_CHANGED')
    assert row.sha256_before==hashlib.sha256(b'original').hexdigest()
    assert row.sha256_after==hashlib.sha256(b'new cloud bytes').hexdigest()
    assert row.actor_username=='alice' and 'UNKNOWN' in row.details_json


def test_shared_onedrive_does_not_replace_smartfile_actor(enterprise):
    e=enterprise
    settings=SimpleNamespace(sync_mode='ONEDRIVE',paused=False,cloud_account_id=7)
    provider=SimpleNamespace(upload=lambda request:SimpleNamespace(remote_id='remote-'+request.local_path.name,version='1'))
    sync=e.documents.cloud_sync_service
    sync.manager=SimpleNamespace(settings=lambda org:settings,provider_for=lambda org:provider)
    sync.synchronize_structure=lambda *args,**kwargs:'shared-organization-root'
    first=import_text(e,'first.txt');sync.enqueue_upload(first.id,e.organization.id)
    switch_user(e,e.bob)
    second=import_text(e,'second.txt',b'another');sync.enqueue_upload(second.id,e.organization.id)
    sync.process_next(e.organization.id);sync.process_next(e.organization.id)
    actors=[next(r.actor_username for r in events(e,d) if r.action=='CLOUD_UPLOAD') for d in (first,second)]
    assert actors==['alice','bob']


def test_multiple_validation_records_with_same_hash_are_all_returned(enterprise):
    e=enterprise;source=make_pdf(e.root/'same.pdf')
    service,first=validation(e,source)
    _,second=validation(e,source)
    service.revoke(e.organization.id,first.id,'Substituído')
    result=service.validate(e.organization.id,file_path=source)
    assert result.record_state=='MULTIPLE_RECORDS' and result.record is None
    assert {r.id for r in result.matching_records}=={first.id,second.id}
    assert {r.status for r in result.matching_records}=={'ACTIVE','REVOKED'}


@pytest.mark.parametrize('revoked',[False,True])
def test_validation_detached_document_cannot_be_reassigned(enterprise,revoked):
    e=enterprise;source=make_pdf(e.root/'registered.pdf')
    document=e.documents.import_document(str(source),sync_cloud=False)
    service,record=validation(e,source,document.id)
    if revoked:service.revoke(e.organization.id,record.id,'Historical')
    e.documents.delete_document(document.id);e.documents.permanently_delete_document(document.id)
    assert service.get(e.organization.id,record.id).document_id is None
    service.validate(e.organization.id, locator=record.human_code)
    events=e.documents.audit.for_document(e.organization.id,document.id)
    assert any(event.action=='VALIDATION_CHECKED' and event.document_uuid==document.public_uuid for event in events)
    other=import_text(e,'other.txt',b'other')
    with pytest.raises(sqlite3.IntegrityError):e.database.connect().execute('UPDATE validation_records SET document_id=? WHERE id=?',(other.id,record.id))
    assert e.database.fetch_all('PRAGMA foreign_key_check')==[]


@pytest.mark.parametrize('field,value',[('revoked_at','2030-01-01'),('revoked_by_user_id',None),('revocation_reason','forged')])
def test_revocation_evidence_is_immutable(enterprise,field,value):
    e=enterprise;source=make_pdf(e.root/'registered.pdf')
    service,record=validation(e,source);revoked=service.revoke(e.organization.id,record.id,'Original reason')
    with pytest.raises(sqlite3.IntegrityError):e.database.connect().execute(f'UPDATE validation_records SET {field}=? WHERE id=?',(value,record.id))
    current=service.get(e.organization.id,record.id)
    assert current.revoked_at==revoked.revoked_at and current.revoked_by_user_id==e.alice.id and current.revocation_reason=='Original reason'


@pytest.mark.parametrize('cnpj',['11.222.333/0001-81','12.ABC.345/01DE-35','00.000.000/E08G-12'])
def test_numeric_and_alphanumeric_cnpj(cnpj):
    assert len(OrganizationIdentityService.normalize_cnpj(cnpj))==14


@pytest.mark.parametrize('cnpj',['00.000.000/0000-00','12.ABC.345/01DE-00','not a cnpj'])
def test_invalid_cnpj_is_rejected(cnpj):
    with pytest.raises(ValueError):OrganizationIdentityService.normalize_cnpj(cnpj)


def test_branding_admin_preview_save_and_fallback(enterprise):
    e=enterprise;identity=OrganizationIdentityService(e.database,e.context)
    values={'display_name':'Empresa ABC','legal_name':'Empresa ABC Ltda.','cnpj':'11.222.333/0001-81','unit':'Financeiro','header_color':'#ffffff','accent_color':'#f4f4f4'}
    preview=identity.preview(e.organization.id,values)
    assert identity.get(e.organization.id).revision==0
    saved=identity.save(e.organization.id,values)
    assert identity.get(e.organization.id)==saved
    assert preview.foreground(preview.header_color)=='#000000'
    switch_user(e,e.bob)
    with pytest.raises(PermissionError):identity.save(e.organization.id,values)
    assert identity.get(e.organization.id).display_name=='Empresa ABC'
    with pytest.raises(ValueError):identity._editable({'header_color':'red; QWidget { color:red; }'},e.organization.public_uuid)


@pytest.mark.parametrize('color',['#000000','#ffffff','#2563eb','#f5f5f5','#808080','#ff0000'])
def test_corporate_text_contrast_is_at_least_45(color):
    from app.models.corporate_identity import CorporateIdentity
    assert CorporateIdentity.contrast(color,CorporateIdentity.foreground(color))>=4.5


def test_institutional_images_are_normalized_and_stable(enterprise):
    e=enterprise;service=OrganizationIdentityService(e.database,e.context)
    image=Image.new('RGB',(600,300),'red');output=BytesIO();image.save(output,format='JPEG');image.close()
    encoded=service.normalize_image(output.getvalue(),'institutional_image')
    saved=service.save(e.organization.id,{'institutional_image':encoded})
    assert service.get(e.organization.id).institutional_image==saved.institutional_image==encoded
    with pytest.raises(ValueError):service.normalize_image(b'<svg><script/></svg>')


def test_shared_identity_uses_existing_instances_and_rejects_other_organization(enterprise):
    e=enterprise;remote=e.create(e.root/'remote')
    local_service=OrganizationIdentityService(e.database,e.context);remote_service=OrganizationIdentityService(remote.database,remote.context)
    remote_identity=remote_service.save(remote.organization.id,{'display_name':'Empresa compartilhada'})
    local=local_service.instances.local(e.organization.id);peer=remote_service.instances.local(remote.organization.id)
    local_service.instances.register_peer(e.organization.id,peer.instance_id,'Remote','127.0.0.1',8765,e.alice.id)
    remote_service.instances.register_peer(remote.organization.id,local.instance_id,'Local','127.0.0.1',8765,remote.alice.id)
    package=remote_service.package_for_peer(local.instance_id)
    local_service.bind_source(e.organization.id,peer.instance_id,package)
    assert local_service.get(e.organization.id)==remote_identity
    assert len(local_service.instances.repository.list_peers(e.organization.id))==1
    with pytest.raises(PermissionError):local_service.save(e.organization.id,{'display_name':'Local forged'})
    changed=remote_service.save(remote.organization.id,{'display_name':'Nome novo'})
    switch_user(e,e.bob)
    client=SimpleNamespace(organization_identity=lambda *args:remote_service.package_for_peer(local.instance_id))
    assert local_service.synchronize(e.organization.id,client=client)==changed
    malicious={'instance_id':peer.instance_id,'identity':asdict(replace(changed,organization_uuid='00000000-0000-0000-0000-000000000001',revision=changed.revision+1))}
    with pytest.raises(PermissionError):local_service.synchronize(e.organization.id,client=SimpleNamespace(organization_identity=lambda *args:malicious))
    assert local_service.get(e.organization.id)==changed
    remote.database.close()


def test_upgrade_from_actual_v23_retains_history_and_checks_foreign_keys(tmp_path):
    path=tmp_path/'v23.db';connection=sqlite3.connect(path)
    connection.execute('PRAGMA journal_mode=WAL');connection.execute('PRAGMA synchronous=NORMAL')
    connection.executescript((Path(__file__).parent/'fixtures/schema_v23.sql').read_text())
    connection.execute('INSERT INTO documents(organization_id,name,original_name,path,file_type,extension,size,checksum,created_at,updated_at) VALUES (1,?,?,?,?,?,?,?,?,?)',('legacy.txt','legacy.txt','legacy.txt','TEXT','.txt',3,hashlib.sha256(b'old').hexdigest(),'2026-10-12','2026-10-12'))
    connection.execute("INSERT INTO history(document_id,action,description,created_at) VALUES (1,'IMPORT','Legacy document','2026-10-12')")
    connection.execute('PRAGMA user_version=23');connection.commit();connection.close()
    upgraded=Database(str(path))
    assert upgraded.fetch_one('PRAGMA user_version')[0]==24
    assert upgraded.fetch_all('PRAGMA foreign_key_check')==[]
    legacy=upgraded.fetch_one("SELECT * FROM audit_log WHERE description='Legacy document'")
    assert legacy['actor_username']=='LEGACY_UNKNOWN' and legacy['document_uuid']
    assert legacy['instance_id'] is None
    for name in ('validation_links_immutable','validation_revocation_immutable','audit_log_no_update','audit_log_no_delete'):
        assert upgraded.fetch_one('SELECT name FROM sqlite_master WHERE type="trigger" AND name=?',(name,))
    upgraded.close()


def test_audit_filters_and_admin_access(enterprise):
    e=enterprise;document=import_text(e)
    rows=e.documents.audit.list_for_organization(e.organization.id,5000,actor_username='alice',
        document_uuid=document.public_uuid,action='IMPORT',from_date='2026-01-01',to_date='2027-01-01')
    assert len(rows)==1 and rows[0].instance_id
    assert e.documents.audit.list_for_organization(e.organization.id,instance_id='unknown')==[]
    switch_user(e,e.bob)
    assert events(e,document)
    with pytest.raises(RuntimeError):e.documents.audit.list_for_organization(e.organization.id)


def test_audit_never_persists_credentials(enterprise):
    e=enterprise
    row=e.documents.audit.record('TEST',organization_id=e.organization.id,
        description='password=SECRET refresh_token=OAUTH',details={'nested':{'client_secret':'PRIVATE'},'access_token':'TOKEN','safe':'data'})
    text=(row.description or '')+(row.details_json or '')
    assert all(secret not in text for secret in ('SECRET','OAUTH','PRIVATE','TOKEN'))
    assert 'data' in text


def test_scope_cannot_be_overridden_by_explicit_actor_for_another_org(enterprise):
    e=enterprise;actor=e.documents.audit.capture(e.organization.id)
    other=e.documents.organization_service.create('B')
    other_actor=e.documents.audit.capture(other.id,user_id=e.alice.id)
    with e.documents.audit.bind(actor),pytest.raises(PermissionError):
        e.documents.audit.record('FORGED',organization_id=other.id,actor=other_actor)


def test_external_content_observed_on_open_is_not_attributed_to_opener_as_editor(enterprise):
    e=enterprise;document=import_text(e)
    Path(document.path).write_bytes(b'external bytes')
    opened=e.documents.open_document(document.id)
    assert opened.checksum==document.checksum
    row=next(r for r in events(e,document) if r.action=='CONTENT_CHANGED_OBSERVED')
    assert row.sha256_before==document.checksum
    assert row.sha256_after==hashlib.sha256(b'external bytes').hexdigest()
    assert 'UNKNOWN' in row.details_json and row.actor_username=='alice'


def test_physical_usage_keeps_ged_quota_separate(enterprise):
    e=enterprise;source=make_pdf(e.root/'source.pdf');document=e.documents.import_document(str(source),sync_cloud=False)
    before=e.documents.get_storage_usage().used_bytes
    validation(e,source,document.id);validation(e,source,document.id)
    usage=e.documents.get_physical_storage_usage()
    assert usage.ged_bytes==source.stat().st_size
    assert usage.validation_bytes==source.stat().st_size*2
    assert usage.installation_total_bytes>=usage.ged_bytes+usage.validation_bytes
    assert e.documents.get_storage_usage().used_bytes==before


def test_branded_receipt_preserves_all_technical_evidence_and_original(enterprise):
    e=enterprise
    from app.services.delivery_receipt_pdf_service import DeliveryReceiptPdfService
    from app.models.delivery_receipt_request import DeliveryReceiptRequest,DeliveryReceiptDocument
    identity=OrganizationIdentityService(e.database,e.context).save(e.organization.id,{'display_name':'Empresa ABC','unit':'Financeiro','legal_name':'Empresa ABC Ltda.','cnpj':'11.222.333/0001-81','show_legal_details_on_receipts':True})
    original=make_pdf(e.root/'original.pdf');before=original.read_bytes();checksum=hashlib.sha256(before).hexdigest()
    signature=Image.new('RGB',(100,35),'white');buffer=BytesIO();signature.save(buffer,format='PNG');signature.close()
    request=DeliveryReceiptRequest(output_path=e.root/'receipt.pdf',receipt_uuid='receipt',protocol_number='SF-20261013-000001-ABCD',
        organization_name=e.organization.name,sender_name='Alice',recipient_name='Bob',received_at='2026-10-13T10:00:00Z',confirmed_at='2026-10-13T10:01:00Z',
        documents=[DeliveryReceiptDocument('original.pdf',len(before),checksum)],signature_image=buffer.getvalue(),signature_method='DRAWN',
        corporate_identity=identity,sender_instance_id='SF-source',recipient_instance_id='SF-target',signer_username='bob')
    DeliveryReceiptPdfService().generate(request)
    with fitz.open(request.output_path) as pdf:text='\n'.join(page.get_text() for page in pdf)
    for value in ('Empresa ABC','Financeiro',request.protocol_number,'Alice','Bob','SF-source','SF-target',checksum,'SmartFile','ACKNOWLEDGED'):
        assert value in text,value
    assert original.read_bytes()==before


def test_corporate_header_keeps_product_and_design_preview_does_not_save(enterprise):
    from PyQt6.QtWidgets import QApplication
    from app.views.corporate_design_dialog import CorporateDesignDialog
    e=enterprise
    app=QApplication.instance() or QApplication([])
    identity=OrganizationIdentityService(e.database,e.context)
    dialog=CorporateDesignDialog(identity.get(e.organization.id))
    dialog.edits['display_name'].setText('<script>Empresa</script>')
    preview=identity.preview(e.organization.id,dialog.values())
    dialog.preview.apply_identity(preview)
    assert dialog.preview.product.text()=='SmartFile'
    assert dialog.preview.name.text()=='<script>Empresa</script>'
    assert identity.get(e.organization.id).revision==0
    dialog.restore_visual()
    assert dialog.values()['display_name']==''
    dialog.close()


def test_audit_reports_preserve_rows_and_csv_does_not_execute_formula(enterprise):
    from app.services.audit_report_service import AuditReportService
    e=enterprise;document=import_text(e)
    e.documents.rename_document(document.id,'=SUM(1).txt')
    e.documents.audit.record('UNICODE_TEST', organization_id=e.organization.id, description='Documento 中文')
    reports=AuditReportService(e.database,e.context)
    csv=e.root/'audit.csv';pdf=e.root/'audit.pdf'
    reports.export(e.organization.id,csv,'CSV')
    assert "'=SUM(1).txt" in csv.read_text(encoding='utf-8-sig')
    reports.export(e.organization.id,pdf,'PDF')
    with fitz.open(pdf) as output:text='\n'.join(page.get_text() for page in output)
    assert document.public_uuid in text and 'alice' in text and 'SmartFile' in text
    assert '中文' in text


def test_foreign_membership_cannot_grant_access_to_current_user(enterprise):
    e = enterprise
    switch_user(e, e.bob)
    assert not e.context.has_permission('audit.view')
    with pytest.raises(Exception, match='Permissão insuficiente'):
        e.context.require_organization_permission(e.organization.id, 'audit.view')
    e.context.memberships = [e.memberships[0]]
    e.context._refresh_permissions()
    assert not e.context.has_permission('document.open')
    with pytest.raises(Exception, match='não pertence'):
        e.context.set_active_organization(e.organization)


def test_export_preserves_original_and_records_individual_actor(enterprise):
    e = enterprise
    document = import_text(e)
    destination = e.root / 'exported.txt'
    e.documents.export_document(document.id, destination)
    assert destination.read_bytes() == b'original'
    assert Path(document.path).read_bytes() == b'original'
    rows = e.documents.audit.for_document(e.organization.id, document.id)
    event = next(row for row in rows if row.action == 'EXPORT')
    assert event.actor_username == 'alice'
    assert event.sha256_after == document.checksum
    assert event.sha256_before is None


def test_a1_password_is_cleared_when_authorization_fails(tmp_path):
    from app.models.signature_request import SignatureRequest
    from app.services.pdf_signature_service import PDFSignatureService
    def denied(*args):
        raise PermissionError('denied')
    validation = SimpleNamespace(active_organization_id=lambda: 1, _require=denied)
    request = SignatureRequest(tmp_path/'in.pdf', tmp_path/'out.pdf', tmp_path/'a1.pfx', 'sensitive-test')
    with pytest.raises(PermissionError):
        PDFSignatureService(validation_service=validation).sign(request)
    assert request.certificate_password == ''


def test_each_published_conversion_output_is_audited(enterprise, monkeypatch):
    from app.models.convert_job import ConvertJob
    from app.services.convert_service import ConvertService
    from app.workers.convert_worker import ConvertWorker
    e = enterprise
    source = make_pdf(e.root/'input.pdf')
    output = e.root/'page.jpg'
    second = e.root/'page_2.jpg'
    def execute(**kwargs):
        output.write_bytes(b'first')
        second.write_bytes(b'second')
        return output, second
    monkeypatch.setattr(ConvertService, 'execute', execute)
    worker = ConvertWorker(ConvertJob(source, output, 'PDF', 'JPG'), document_service=e.documents)
    failures = []
    worker.failed.connect(failures.append)
    worker.run()
    assert not failures
    events = e.documents.audit.list_for_organization(e.organization.id, action='CONVERT')
    assert {event.document_name for event in events} == {'page.jpg', 'page_2.jpg'}
    assert {event.sha256_after for event in events} == {hashlib.sha256(b'first').hexdigest(), hashlib.sha256(b'second').hexdigest()}


def test_physical_storage_enumeration_can_be_cancelled(enterprise):
    e = enterprise
    import_text(e)
    with pytest.raises(InterruptedError):
        e.documents.get_physical_storage_usage(cancelled=lambda: True)


def test_unmanaged_validation_artifact_has_public_identity_and_name(enterprise):
    e = enterprise
    source = make_pdf(e.root/'unmanaged.pdf')
    service, record = validation(e, source)
    service.validate(e.organization.id, locator=record.human_code)
    rows = e.documents.audit.list_for_organization(e.organization.id, action='VALIDATION_CHECKED')
    assert rows[0].document_uuid == 'validation:' + record.human_code
    assert rows[0].document_name == record.logical_name_snapshot
    assert rows[0].source_type == 'VALIDATION'


def test_upgrade_23_to_24_rolls_back_on_failure():
    from app.database.migrations import migrate
    from app.errors.persistence_exceptions import DatabaseError
    connection = sqlite3.connect(':memory:')
    connection.row_factory = sqlite3.Row
    connection.executescript((Path(__file__).parent/'fixtures/schema_v23.sql').read_text())
    connection.execute('PRAGMA user_version=23')
    connection.set_authorizer(lambda action, first, second, database, source:
        sqlite3.SQLITE_DENY if action == sqlite3.SQLITE_CREATE_TRIGGER
        and first == 'audit_log_no_update' else sqlite3.SQLITE_OK)
    try:
        with pytest.raises(DatabaseError):
            migrate(connection, Path('app/database/schema.sql'))
        connection.set_authorizer(None)
        assert connection.execute('PRAGMA user_version').fetchone()[0] == 23
        assert 'public_uuid' not in {row['name'] for row in connection.execute('PRAGMA table_info(documents)')}
        assert connection.execute('PRAGMA foreign_key_check').fetchall() == []
    finally:
        connection.close()
