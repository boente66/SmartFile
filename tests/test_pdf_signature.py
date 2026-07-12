from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import fitz
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

from app.errors.signature_exceptions import (
    CertificateExpiredError, InvalidCertificatePasswordError, TimestampError,
)
from app.models.signature_request import SignatureRequest
from app.services.certificate_service import CertificateService
from app.services.pdf_signature_service import PDFSignatureService
from app.services.document_service import DocumentService
from app.workers.pdf_signature_worker import PDFSignatureWorker


def _certificate(path: Path, password: str = "secret", expired: bool = False) -> Path:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "SmartFile Teste")])
    now = datetime.now(timezone.utc)
    not_before = now - timedelta(days=30)
    not_after = now - timedelta(days=1) if expired else now + timedelta(days=30)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(name).public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before).not_valid_after(not_after)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True, content_commitment=True,
                key_encipherment=False, data_encipherment=False,
                key_agreement=False, key_cert_sign=False, crl_sign=False,
                encipher_only=None, decipher_only=None,
            ), critical=True,
        ).sign(key, hashes.SHA256())
    )
    path.write_bytes(
        pkcs12.serialize_key_and_certificates(
            b"smartfile-test", key, certificate, None,
            serialization.BestAvailableEncryption(password.encode()),
        )
    )
    return path


def _pdf(path: Path) -> Path:
    document = fitz.open()
    page = document.new_page(width=300, height=500)
    page.insert_text((30, 50), "Documento para assinatura")
    document.save(path); document.close()
    return path


def _request(tmp_path: Path, *, visible=False) -> SignatureRequest:
    tmp_path.mkdir(parents=True, exist_ok=True)
    return SignatureRequest(
        input_path=_pdf(tmp_path / "input.pdf"),
        output_path=tmp_path / "signed.pdf",
        certificate_path=_certificate(tmp_path / "test.p12"),
        certificate_password="secret",
        visible=visible,
        page_number=1 if visible else None,
        x1=30 if visible else None, y1=30 if visible else None,
        x2=250 if visible else None, y2=100 if visible else None,
        signer_name="SmartFile Teste", reason="Aprovação",
    )


@pytest.mark.parametrize("visible", [False, True])
def test_a1_signing_produces_real_pades_and_preserves_original(tmp_path: Path, visible: bool):
    request = _request(tmp_path, visible=visible)
    original = request.input_path.read_bytes()

    result = PDFSignatureService().sign(request)

    assert result.output_path.is_file()
    assert result.produced_profile == "PAdES-B-B"
    assert result.visible is visible
    assert request.input_path.read_bytes() == original
    assert request.certificate_password == ""
    validations = PDFSignatureService().validate(result.output_path)
    assert len(validations) == 1
    assert validations[0].integrity_ok is True
    assert validations[0].state in {"VALID", "UNTRUSTED"}
    assert validations[0].visible is visible


def test_wrong_password_expired_certificate_and_invalid_visible_area(tmp_path: Path):
    certificate = _certificate(tmp_path / "wrong.pfx")
    with pytest.raises(InvalidCertificatePasswordError):
        CertificateService().load_a1(certificate, "wrong")
    expired = _certificate(tmp_path / "expired.p12", expired=True)
    with pytest.raises(CertificateExpiredError):
        CertificateService().load_a1(expired, "secret")

    request = _request(tmp_path / "area", visible=True)
    request.x2 = request.x1
    with pytest.raises(ValueError):
        request.validate(page_count=1)


def test_timestamp_failure_cleans_temporary_output(tmp_path: Path, monkeypatch):
    request = _request(tmp_path)
    request.timestamp_url = "https://timestamp.invalid"

    def fail(*_args, **_kwargs):
        raise OSError("timestamp indisponível")

    monkeypatch.setattr("pyhanko.sign.signers.PdfSigner.sign_pdf", fail)
    with pytest.raises(TimestampError):
        PDFSignatureService().sign(request)

    assert not request.output_path.exists()
    assert list(tmp_path.glob(".*.tmp.pdf")) == []


def test_signature_worker_preserves_native_finished_signal():
    assert "finished" not in PDFSignatureWorker.__dict__


def test_signed_output_can_be_imported_into_ged(tmp_path: Path):
    request = _request(tmp_path)
    result = PDFSignatureService().sign(request)
    documents = DocumentService(db_path=str(tmp_path / "ged" / "smartfile.db"))

    imported = documents.import_document(str(result.output_path))
    documents.history_service.record_action(imported.id, "SIGNED", "PDF assinado")

    assert imported.managed is True
    assert Path(imported.storage_path).is_file()
    actions = documents.history_service.list_history(imported.id)
    assert {entry.action for entry in actions} == {"IMPORT", "SIGNED"}


def test_multiple_incremental_signatures_are_detected(tmp_path: Path):
    first_request = _request(tmp_path)
    service = PDFSignatureService()
    first = service.sign(first_request)
    second_request = SignatureRequest(
        input_path=first.output_path,
        output_path=tmp_path / "signed_twice.pdf",
        certificate_path=first_request.certificate_path,
        certificate_password="secret",
        field_name="SmartFileSignature2",
    )

    second = service.sign(second_request)

    assert len(service.validate(second.output_path)) == 2
