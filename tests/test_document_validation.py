import hashlib
import os
import secrets
import sqlite3
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import fitz
import pytest

from app.database.database import Database
from app.entities.validation_record import ArtifactType as A, SignatureType as S
from app.models.document_validation_result import PublicValidationResult
from app.services.document_validation_service import DocumentValidationService
from app.services.validation_locator_service import ValidationLocatorService as Locator


def pdf(path, text="Valor: R$ 10.000"):
    with fitz.open() as doc:
        page = doc.new_page()
        page.insert_text((50, 80), text)
        doc.save(path)
    return path


@pytest.fixture
def service(tmp_path):
    database = Database(str(tmp_path / "data" / "smartfile.db"))
    service = DocumentValidationService(database)
    yield service
    database.close()


def pending(service, **changes):
    values = dict(logical_name="contrato.pdf", artifact_type=A.UNSIGNED_REGISTERED_DOCUMENT,
                  signature_type=S.NONE)
    values.update(changes)
    return service.create_pending(service.active_organization_id(), **values)


def active(service, tmp_path, **changes):
    record = pending(service, **changes)
    source = pdf(tmp_path / (record.public_token + ".pdf"))
    return service.activate(record, source), source


def test_local_payload_private_and_normalized_code(service):
    record = pending(service)
    payload = Locator.build_payload(record)
    assert payload == "smartfile:verify:v1:" + record.public_token
    assert len(record.public_token) == 48
    assert Locator.parse(payload) == ("TOKEN", record.public_token)
    code = "sfv-" + "-".join(record.human_code[i:i+4].lower() for i in range(3, 19, 4))
    assert Locator.parse(code) == ("CODE", record.human_code)
    assert payload.count(":") == 3
    assert "sha256" not in payload and "organization" not in payload


@pytest.mark.parametrize("url", ["https://localhost", "https://127.0.0.1", "https://127.1", "https://[::1]",
    "https://192.168.1.5", "https://foo.local", "javascript:alert(1)", "file:///tmp/doc", "data:x", "ftp://example.org",
    "http://example.org", "https://user:secret@example.org", "https://example.org/?token=x", "https://example.org/#x",
    "https://example.org/a/../b", "https://example.org:bad", "https://example.org\\evil", "https://example.org\n"])
def test_bad_web_base(url):
    with pytest.raises(ValueError):
        Locator.validate_base_url(url)


def test_web_snapshot_survives_configuration_change(service):
    org = service.active_organization_id()
    service.configure(org, "https://example.org/validation/")
    first = pending(service)
    assert Locator.build_payload(first) == f"https://example.org/validation/verify/{first.public_token}"
    assert Locator.parse(Locator.build_payload(first)) == ("TOKEN", first.public_token)
    service.configure(org, "https://example.net")
    second = pending(service)
    assert Locator.build_payload(first).startswith("https://example.org/")
    assert second.public_token != first.public_token
    assert first.publication_mode == "LOCAL_ONLY"
    service.configure(org, "")
    assert Locator.build_payload(pending(service)).startswith(Locator.PREFIX)


@pytest.mark.parametrize("payload", ["smartfile:verify:v2:abc", "smartfile:other:v1:abc", "SFV1-short", "https://example.org/verify/invalid", "../outside"])
def test_bad_payload(payload):
    with pytest.raises(ValueError):
        Locator.parse(payload)


def test_original_and_identical_copy_open_and_export_exact_bytes(service, tmp_path):
    record, source = active(service, tmp_path)
    expected = source.read_bytes()
    renamed = tmp_path / "renamed.pdf"; renamed.write_bytes(expected)
    result = service.validate(record.organization_id, Locator.build_payload(record), renamed)
    assert (result.record_state, result.artifact_state, result.file_integrity) == ("FOUND", "AVAILABLE", "HASH_MATCH")
    assert result.signature_status == result.trust_status == "NOT_APPLICABLE"
    assert service.validate(record.organization_id, record.human_code, renamed).record.id == record.id
    assert service.validate(record.organization_id, file_path=renamed).record.id == record.id
    path = service.open_original(record.organization_id, record.id)
    assert path.read_bytes() == expected
    exported = service.export_original(record.organization_id, record.id, tmp_path / "export.pdf")
    assert exported.read_bytes() == expected
    assert hashlib.sha256(exported.read_bytes()).hexdigest() == record.final_sha256
    dto = asdict(PublicValidationResult.from_result(result))
    assert not set(dto) & {"id", "organization_id", "document_id", "path", "artifact_storage_ref", "public_token"}
    with pytest.raises(FileExistsError):
        service.export_original(record.organization_id, record.id, exported)
    assert exported.read_bytes() == expected


def test_copied_qr_social_engineering_always_resolves_original_a(service, tmp_path):
    from app.services.signature_verification_service import SignatureVerificationService as QR
    record = pending(service)
    source = pdf(tmp_path / "original.pdf")
    with fitz.open(source) as doc:
        QR.insert_qr(doc, Locator.build_payload(record), rect=(400, 30, 500, 130))
        doc.save(tmp_path / "qr-original.pdf")
    record = service.activate(record, tmp_path / "qr-original.pdf")
    modified = pdf(tmp_path / "fraud-copy.pdf", "Valor: R$ 100.000")
    with fitz.open(modified) as doc:
        QR.insert_qr(doc, Locator.build_payload(record), rect=(400, 30, 500, 130))
        doc.save(tmp_path / "qr-copy.pdf")
    result = service.validate(record.organization_id, Locator.build_payload(record), tmp_path / "qr-copy.pdf")
    assert result.file_integrity == "HASH_MISMATCH" and result.record.id == record.id
    with fitz.open(service.open_original(record.organization_id, record.id)) as doc:
        assert "10.000" in doc[0].get_text() and "100.000" not in doc[0].get_text()
    assert service.open_original(record.organization_id, record.id).read_bytes() == (tmp_path / "qr-original.pdf").read_bytes()


@pytest.mark.parametrize("mutation", ["byte", "reexport", "remove-qr"])
def test_modification_is_difference_not_automatic_fraud(service, tmp_path, mutation):
    if mutation == "remove-qr":
        from app.services.signature_verification_service import SignatureVerificationService as QR
        record = pending(service)
        plain = pdf(tmp_path / "plain.pdf")
        source = tmp_path / "with-qr.pdf"
        with fitz.open(plain) as doc:
            QR.insert_qr(doc, Locator.build_payload(record), rect=(400, 30, 500, 130))
            doc.save(source)
        record = service.activate(record, source)
    else:
        record, source = active(service, tmp_path)
    changed = tmp_path / "changed.pdf"
    if mutation == "byte":
        data = bytearray(source.read_bytes()); data[-1] ^= 1
        changed.write_bytes(data)
    else:
        with fitz.open(source) as doc:
            if mutation == "remove-qr":
                # Redaction/reconstruction changes bytes even when page appears similar.
                doc[0].add_redact_annot(fitz.Rect(400, 30, 500, 130))
                doc[0].apply_redactions()
            doc.save(changed, garbage=4, deflate=True)
    result = service.validate(record.organization_id, record.public_token, changed)
    assert result.file_integrity == "HASH_MISMATCH"
    assert service.get(record.organization_id, record.id).status == "ACTIVE"


def test_false_qr_and_pending_failed_are_never_positive(service, tmp_path):
    fake = "SFV1-" + secrets.token_urlsafe(32)
    result = service.validate(service.active_organization_id(), fake)
    assert result.record_state == "RECORD_NOT_FOUND"
    assert "falso" not in result.message
    record = pending(service)
    assert service.validate(record.organization_id, record.public_token).record_state == "PENDING"
    service.fail(record)
    assert service.validate(record.organization_id, record.public_token).record_state == "FAILED"
    with pytest.raises(ValueError):
        service.open_original(record.organization_id, record.id)


@pytest.mark.parametrize("damage", ["corrupt", "missing", "symlink"])
def test_artifact_damage_blocks_original(service, tmp_path, damage):
    record, source = active(service, tmp_path)
    path = service.artifacts.path(record.organization_id, record.artifact_storage_ref)
    if damage == "corrupt":
        path.write_bytes(b"replacement")
    else:
        path.unlink()
        if damage == "symlink":
            try:
                path.symlink_to(source)
            except OSError:
                pytest.skip("Symlink permission unavailable")
    result = service.validate(record.organization_id, record.public_token, source)
    assert result.artifact_state == ("ARTIFACT_MISSING" if damage == "missing" else "ARTIFACT_CORRUPTED")
    with pytest.raises((ValueError, FileNotFoundError)):
        service.open_original(record.organization_id, record.id)
    with pytest.raises((ValueError, FileNotFoundError)):
        service.export_original(record.organization_id, record.id, tmp_path / "out.pdf")
    assert not (tmp_path / "out.pdf").exists()


def test_revoke_preserves_integrity_and_original(service, tmp_path):
    record, source = active(service, tmp_path)
    revoked = service.revoke(record.organization_id, record.id, "Substituído por nova versão")
    result = service.validate(record.organization_id, record.public_token, source)
    assert revoked.status == result.record.status == "REVOKED"
    assert result.artifact_state == "AVAILABLE" and result.file_integrity == "HASH_MATCH"
    assert service.open_original(record.organization_id, record.id).read_bytes() == source.read_bytes()


def test_no_overwrite_and_history_versions(service, tmp_path):
    first, source = active(service, tmp_path)
    second, second_source = active(service, tmp_path)
    assert first.public_token != second.public_token
    with pytest.raises(ValueError):
        service.activate(first, second_source)
    with pytest.raises(ValueError):
        service.artifacts.preserve(first.organization_id, first.public_token, second_source)
    assert service.open_original(first.organization_id, first.id).read_bytes() == source.read_bytes()
    with pytest.raises(sqlite3.IntegrityError):
        service.database.connect().execute("UPDATE validation_records SET final_sha256=? WHERE id=?", ("0" * 64, first.id))
    with pytest.raises(sqlite3.IntegrityError):
        service.database.connect().execute("DELETE FROM validation_records WHERE id=?", (first.id,))


def test_traversal_and_organization_bound_reference(service, tmp_path):
    org = service.active_organization_id()
    for reference in ("../outside", "/etc/passwd", "2/SFV1-" + "x"*43 + ".pdf"):
        with pytest.raises(ValueError):
            service.artifacts.path(org, reference)
    record, _ = active(service, tmp_path)
    with pytest.raises(ValueError):
        service.export_original(org, record.id, service.database.data_dir / "overwrite.pdf")


def test_org_isolation_and_permissions(service, tmp_path):
    from app.services.organization_service import OrganizationService
    record, source = active(service, tmp_path)
    other = OrganizationService(service.database).create("Outra")
    assert service.validate(other.id, record.public_token).record_state == "RECORD_NOT_FOUND"
    with pytest.raises(PermissionError):
        service.get(other.id, record.id)
    context = SimpleNamespace(active_organization=SimpleNamespace(id=record.organization_id), current_user=None)
    def denied(permission):
        raise PermissionError(permission)
    context.require_permission = denied
    scoped = DocumentValidationService(service.database, context)
    with pytest.raises(PermissionError):
        scoped.validate(record.organization_id, record.public_token)
    with pytest.raises(PermissionError):
        scoped.export_original(record.organization_id, record.id, tmp_path / "denied.pdf")
    with pytest.raises(PermissionError):
        scoped.revoke(record.organization_id, record.id, "reason")
    with pytest.raises(PermissionError):
        scoped.configure(record.organization_id, "https://example.org")
    with pytest.raises(PermissionError):
        scoped.get(other.id, record.id)


def test_ged_permanent_delete_preserves_record_artifact_and_snapshot(service, tmp_path):
    from app.services.document_service import DocumentService
    documents = DocumentService(database=service.database)
    source = pdf(tmp_path / "source.pdf")
    document = documents.import_document(str(source))
    record = pending(service, document_id=document.id)
    record = service.activate(record, source)
    documents.delete_document(document.id)
    assert documents.permanently_delete_document(document.id)
    historical = service.get(record.organization_id, record.id)
    assert historical.document_id is None and historical.logical_name_snapshot == "contrato.pdf"
    assert service.open_original(record.organization_id, record.id).read_bytes() == source.read_bytes()
    assert service.database.fetch_all("PRAGMA foreign_key_check") == []


def test_collision_retry_and_crash_promotion_never_false_active(service, tmp_path, monkeypatch):
    first = pending(service)
    actual = secrets.token_urlsafe
    tokens = iter([first.public_token[5:], actual(32)])
    monkeypatch.setattr(secrets, "token_urlsafe", lambda _: next(tokens))
    second = pending(service)
    assert second.public_token != first.public_token
    source = pdf(tmp_path / "source.pdf")
    monkeypatch.setattr(service.repository, "activate", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("crash")))
    with pytest.raises(RuntimeError):
        service.activate(second, source)
    assert service.get(second.organization_id, second.id).status == "PENDING"
    assert service.validate(second.organization_id, second.public_token).artifact_state == "NOT_CHECKED"
    service.database.execute_query("UPDATE validation_records SET created_at='2000-01-01T00:00:00+00:00' WHERE id=?", (second.id,))
    assert service.recover_pending(second.organization_id) == 1
    assert service.get(second.organization_id, second.id).status == "FAILED"


def test_migration_22_to_23_idempotent_and_new_database(service):
    database = service.database
    database.execute_query("DROP TABLE validation_records")
    database.execute_query("PRAGMA user_version=22")
    database.create_tables(); database.create_tables()
    assert database.fetch_one("PRAGMA user_version")[0] == 23
    assert database.fetch_all("PRAGMA foreign_key_check") == []
    assert pending(service).status == "PENDING"


def test_human_code_collision_retry(service, monkeypatch):
    first = pending(service)
    real = secrets.choice
    values = iter(list(first.human_code[3:]) + [real(service.CODE_ALPHABET) for _ in range(16)])
    monkeypatch.setattr(secrets, "choice", lambda _: next(values))
    second = pending(service)
    assert second.human_code != first.human_code


def test_backup_retains_canonical_bytes_and_receipts(service, tmp_path):
    import zipfile
    from app.services.backup_service import BackupService
    record, source = active(service, tmp_path)
    receipts = service.database.data_dir / "delivery_receipts"
    receipts.mkdir(); (receipts / "historical.pdf").write_bytes(source.read_bytes())
    context = SimpleNamespace(current_user=SimpleNamespace(id=None), is_system_admin=lambda: True)
    backup = BackupService(service.database, context).create_full_backup(tmp_path / "backup.zip")
    with zipfile.ZipFile(backup.output_path) as archive:
        assert archive.read("validation_artifacts/" + record.artifact_storage_ref) == source.read_bytes()
        assert archive.read("delivery_receipts/historical.pdf") == source.read_bytes()


def test_visual_signature_local_qr_is_registered_and_never_digital(service, tmp_path):
    from test_handwritten_signature import _app, _request
    from app.services.handwritten_signature_service import HandwrittenSignatureService
    _app()
    source = pdf(tmp_path / "unsigned.pdf")
    request = _request(source, tmp_path / "visual.pdf", qr_visible=True, qr_rect=(400, 30, 500, 130))
    result = HandwrittenSignatureService(service).apply(request)
    checked = service.validate(service.active_organization_id(), file_path=result.output_path)
    assert checked.file_integrity == "HASH_MATCH"
    assert checked.record.signature_type == "VISUAL_HANDWRITTEN"
    assert checked.signature_status == checked.trust_status == "NOT_APPLICABLE"
    assert checked.record.artifact_type == "VISUAL_SIGNED_DOCUMENT"


def test_a1_registration_signature_and_final_bytes(service, tmp_path):
    from test_pdf_signature import _request
    from app.services.pdf_signature_service import PDFSignatureService
    request = _request(tmp_path / "signing")
    request.qr_visible = True; request.qr_rect = (180, 300, 270, 390)
    original = request.input_path.read_bytes()
    signed = PDFSignatureService(validation_service=service).sign(request)
    checked = service.validate(service.active_organization_id(), file_path=signed.output_path)
    assert checked.file_integrity == "HASH_MATCH"
    assert checked.signature_status == "VALID"
    assert checked.trust_status in {"TRUSTED", "UNTRUSTED"}
    assert checked.record.signature_type == "A1_PADES"
    assert checked.record.final_sha256 == hashlib.sha256(signed.output_path.read_bytes()).hexdigest()
    assert request.input_path.read_bytes() == original
    assert service.open_original(checked.record.organization_id, checked.record.id).read_bytes() == signed.output_path.read_bytes()


def test_a1_failure_and_previously_signed_qr_leave_no_active(service, tmp_path):
    from test_pdf_signature import _request
    from app.services.pdf_signature_service import PDFSignatureService
    request = _request(tmp_path / "bad")
    request.qr_visible = True; request.certificate_password = "wrong"
    with pytest.raises(Exception):
        PDFSignatureService(validation_service=service).sign(request)
    assert request.certificate_password == ""
    assert service.database.fetch_one("SELECT status FROM validation_records ORDER BY id DESC")[0] == "FAILED"
    request = _request(tmp_path / "prior")
    signed = PDFSignatureService().sign(request)
    before = signed.output_path.read_bytes()
    request.input_path = signed.output_path; request.output_path = tmp_path / "changed.pdf"
    request.certificate_password = "secret"; request.qr_visible = True
    with pytest.raises(Exception, match="QR antes"):
        PDFSignatureService(validation_service=service).sign(request)
    assert signed.output_path.read_bytes() == before
    assert service.database.fetch_one("SELECT COUNT(*) FROM validation_records WHERE status='ACTIVE'")[0] == 0


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
@pytest.mark.parametrize("token", ["SFV1-" + "A"*43,
    "SFV1-YXDdXTcBCXBNxdYKuMlVuAm3kO6RGug1d6bQOtYLqgE"])
def test_qr_layout_on_rotated_pdf_readable_and_in_bounds(tmp_path, rotation, token):
    import cv2
    import numpy as np
    from app.services.signature_verification_service import SignatureVerificationService as QR
    with fitz.open() as doc:
        page = doc.new_page(width=300, height=500); page.set_rotation(rotation)
        QR.insert_qr(doc, Locator.PREFIX + token, rect=(20, 20, 130, 130), human_code="SFV"+"A"*16)
        pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
        image = np.frombuffer(pixmap.samples, np.uint8).reshape(pixmap.height, pixmap.width, 3)
        value, _, _ = cv2.QRCodeDetector().detectAndDecode(image)
        assert value == Locator.PREFIX + token
        assert "SFV-AAAA" in page.get_text()
        with pytest.raises(ValueError):
            QR.insert_qr(doc, Locator.PREFIX + token, page_number=2)
        with pytest.raises(ValueError):
            QR.insert_qr(doc, Locator.PREFIX + token, rect=(-10, 0, 100, 100))


def test_viewer_original_readonly_and_path_hidden(service, tmp_path):
    from test_handwritten_signature import _app
    from app.views.pdf_viewer_view import PDFViewerView
    from app.models.pdf_viewer_context import PDFViewerContext
    from app.services.pdf_viewer_service import PDFViewerService
    _app()
    record, _ = active(service, tmp_path)
    path = service.open_original(record.organization_id, record.id)
    view = PDFViewerView()
    view.set_document(PDFViewerService().document_info(path))
    view.set_context(PDFViewerContext(kind="VALIDATION_ORIGINAL", title=record.logical_name_snapshot))
    view.set_document_loaded(True)
    assert not view.btn_sign.isEnabled() and not view.btn_handwritten_sign.isEnabled()
    assert str(service.artifacts.root) not in view.info_panel._labels["path"].text()
    assert view.info_panel._labels["name"].text() == "contrato.pdf"
    view.set_context(PDFViewerContext.document())
    assert view.btn_sign.isEnabled() and view.btn_handwritten_sign.isEnabled()
    view.close()


def test_worker_stale_result_dropped_on_input_change_and_close(service):
    from test_handwritten_signature import _app
    from PyQt6.QtTest import QTest
    from app.views.pdf_viewer_view import PDFViewerView
    from app.controllers.document_validation_controller import DocumentValidationController
    import threading
    _app()
    view = PDFViewerView()
    viewer = SimpleNamespace(view=view, _path=None)
    controller = DocumentValidationController(viewer, service.database)
    controller.show()
    release = threading.Event()
    results = []
    controller._start(lambda _: release.wait(2), results.append)
    controller.dialog.locator.setText("changed")
    release.set()
    for _ in range(100):
        QTest.qWait(10)
        if not controller._workers:
            break
    assert results == []
    controller.close()
    assert controller.dialog is None
    view.close()


def test_qr_form_no_url_requirement():
    from test_handwritten_signature import _app
    from app.views.widgets.signature_qr_options import SignatureQrOptions
    _app()
    form = SignatureQrOptions(1)
    form.visible.setChecked(True)
    assert form.values()["qr_visible"]
    assert "verification_url" not in form.values()
    assert "local" in form.mode.text()


def test_forged_pending_type_cannot_bypass_create_permission(service, tmp_path):
    from dataclasses import replace
    record = pending(service)
    context = SimpleNamespace(active_organization=SimpleNamespace(id=record.organization_id), current_user=None)
    def permission(name):
        if name not in {"validation.view", "delivery.acknowledge"}:
            raise PermissionError(name)
    context.require_permission = permission
    scoped = DocumentValidationService(service.database, context)
    forged = replace(record, artifact_type="DELIVERY_RECEIPT")
    source = pdf(tmp_path / "forged.pdf")
    with pytest.raises(PermissionError, match="validation.create"):
        scoped.activate(forged, source)
    with pytest.raises(PermissionError, match="validation.create"):
        scoped.fail(forged)
    assert service.get(record.organization_id, record.id).status == "PENDING"


def test_fail_is_scoped_to_active_org(service):
    from app.services.organization_service import OrganizationService
    record = pending(service)
    other = OrganizationService(service.database).create("Outra organização")
    context = SimpleNamespace(active_organization=SimpleNamespace(id=other.id), current_user=None,
                              require_permission=lambda _: None)
    scoped = DocumentValidationService(service.database, context)
    with pytest.raises(PermissionError):
        scoped.fail(record)
    assert service.get(record.organization_id, record.id).status == "PENDING"


def test_https_scheme_case_is_normalized_without_changing_token(service):
    org = service.active_organization_id()
    service.configure(org, "HTTPS://example.org/validation/")
    record = pending(service)
    payload = Locator.build_payload(record)
    assert payload == f"https://example.org/validation/verify/{record.public_token}"
    assert Locator.parse(payload.replace("https://", "HTTPS://", 1)) == ("TOKEN", record.public_token)
    assert record.public_token == payload.rsplit("/", 1)[1]
