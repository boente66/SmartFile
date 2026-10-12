from pathlib import Path
import cv2
import numpy as np
import pytest
from PIL import Image
from io import BytesIO

from app.services.signature_verification_service import SignatureVerificationService as Verification


def test_qr_reads_exact_document_url():
    url='https://example.org/verificar/documento.pdf'
    image=Image.open(BytesIO(Verification.qr_png(url))).convert('RGB')
    value,_,_=cv2.QRCodeDetector().detectAndDecode(np.asarray(image))
    assert value==url


@pytest.mark.parametrize('url',['http://example.org','file:///tmp/test.pdf','javascript:alert(1)','https://user:secret@example.org',''])
def test_qr_rejects_invalid_urls(url):
    with pytest.raises(ValueError):Verification.qr_png(url)


def test_visual_signature_evidence_never_claims_identity(tmp_path):
    source=tmp_path/'document.pdf';source.write_bytes(b'content')
    evidence=Verification.evidence(source,kind='HANDWRITTEN')
    assert not evidence['identity_confirmed']
    assert len(evidence['sha256'])==64
