from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import fitz
import pytest
from PyQt6.QtCore import QPoint, QRectF, Qt
from PyQt6.QtGui import QImage
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from app.errors.handwritten_signature_exceptions import (
    EmptySignatureError,
    ExistingDigitalSignatureWarning,
    InvalidSignaturePositionError,
    SignedDocumentWriteError,
)
from app.models.handwritten_signature_request import HandwrittenSignatureRequest
from app.services.document_service import DocumentService
from app.services.handwritten_signature_service import HandwrittenSignatureService
from app.services.pdf_viewer_service import PDFViewerService
from app.views.pdf_viewer_view import PDFViewerView
from app.views.widgets.signature_canvas import SignatureCanvas
from app.views.widgets.signature_placement_widget import SignaturePlacementWidget
from app.workers.handwritten_signature_worker import HandwrittenSignatureWorker

_APPLICATION: QApplication | None = None


def _app() -> QApplication:
    global _APPLICATION
    _APPLICATION = QApplication.instance() or QApplication([])
    return _APPLICATION


def _pdf(path: Path, width: float = 300, height: float = 500, signature_field: bool = False) -> Path:
    document = fitz.open()
    page = document.new_page(width=width, height=height)
    page.insert_text((30, 50), "Documento original SmartFile")
    if signature_field:
        widget = fitz.Widget()
        widget.field_name = "ExistingSignature"
        widget.field_type = fitz.PDF_WIDGET_TYPE_SIGNATURE
        widget.rect = fitz.Rect(30, 80, 180, 120)
        page.add_widget(widget)
    document.set_metadata({"title": "Original"})
    document.save(path)
    document.close()
    return path


def _png() -> bytes:
    image = QImage(180, 60, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    for x in range(20, 160):
        image.setPixelColor(x, 30, Qt.GlobalColor.black)
    from PyQt6.QtCore import QBuffer, QByteArray
    data = QByteArray()
    buffer = QBuffer(data); buffer.open(QBuffer.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(data)


def _request(source: Path, output: Path, **changes) -> HandwrittenSignatureRequest:
    values = dict(
        input_path=source, output_path=output, page_number=1,
        x=40.0, y=100.0, width=160.0, height=55.0,
        signature_image=_png(), signer_name="Pessoa Teste",
        signed_at=datetime.now().astimezone(), color="#111827",
        stroke_width=3.5, add_caption=True,
    )
    values.update(changes)
    return HandwrittenSignatureRequest(**values)


def test_canvas_mouse_undo_redo_clear_and_transparent_crop():
    _app()
    canvas = SignatureCanvas()
    canvas.resize(600, 240)
    canvas.show()
    QTest.mousePress(canvas, Qt.MouseButton.LeftButton, pos=QPoint(100, 100))
    for x, y in ((120, 92), (145, 108), (170, 95), (205, 105)):
        QTest.mouseMove(canvas, QPoint(x, y), delay=1)
    QTest.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=QPoint(220, 100))

    assert canvas.is_empty is False
    data = canvas.export_png()
    image = QImage.fromData(data, "PNG")
    assert image.hasAlphaChannel()
    assert image.width() < canvas.width() * 2
    assert image.pixelColor(0, 0).alpha() == 0
    canvas.undo(); assert canvas.is_empty is True
    canvas.redo(); assert canvas.is_empty is False
    canvas.set_color("#1d4ed8"); canvas.set_stroke_width(6)
    assert canvas.color_name == "#1d4ed8" and canvas.stroke_width == 6
    canvas.clear(); assert canvas.export_png() == b""
    canvas.close()


@pytest.mark.parametrize(
    ("rotation", "expected"),
    [
        (0, (30.0, 100.0, 90.0, 100.0)),
        (90, (60.0, 300.0, 60.0, 150.0)),
        (180, (180.0, 300.0, 90.0, 100.0)),
        (270, (180.0, 50.0, 60.0, 150.0)),
    ],
)
def test_coordinate_conversion_handles_visual_rotation(rotation, expected):
    result = SignaturePlacementWidget.normalized_to_pdf(
        QRectF(0.1, 0.2, 0.3, 0.2), (300.0, 500.0), rotation
    )
    assert result == pytest.approx(expected)


@pytest.mark.parametrize("size", [(300, 500), (500, 300)])
def test_service_inserts_transparent_signature_preserves_original_and_metadata(tmp_path: Path, size):
    source = _pdf(tmp_path / "input.pdf", *size)
    original = source.read_bytes()
    request = _request(source, tmp_path / "output.pdf", width=min(160, size[0] - 40))

    result = HandwrittenSignatureService().apply(request)

    assert source.read_bytes() == original
    assert result.output_path.is_file()
    with fitz.open(result.output_path) as document:
        assert document.page_count == 1
        assert document.metadata["title"] == "Original"
        assert "Documento original SmartFile" in document[0].get_text()
        pixmap = document[0].get_pixmap()
        assert pixmap.width > 0
    assert PDFViewerService().document_info(result.output_path).signature_count == 0
    assert list(tmp_path.glob(".*.tmp.pdf")) == []


def test_validation_rejects_empty_and_outside_page(tmp_path: Path):
    source = _pdf(tmp_path / "input.pdf")
    with pytest.raises(EmptySignatureError):
        _request(source, tmp_path / "empty.pdf", signature_image=b"").validate(1, (300, 500))
    with pytest.raises(InvalidSignaturePositionError):
        _request(source, tmp_path / "outside.pdf", x=250, width=100).validate(1, (300, 500))
    with pytest.raises(InvalidSignaturePositionError):
        _request(source, source).validate(1, (300, 500))
    existing = tmp_path / "existing.pdf"; existing.write_bytes(b"existing")
    with pytest.raises(InvalidSignaturePositionError):
        _request(source, existing).validate(1, (300, 500))


def test_existing_digital_signature_requires_explicit_confirmation(tmp_path: Path):
    source = _pdf(tmp_path / "signed.pdf", signature_field=True)
    service = HandwrittenSignatureService()
    assert service.has_digital_signatures(source) is True
    request = _request(source, tmp_path / "copy.pdf")
    with pytest.raises(ExistingDigitalSignatureWarning):
        service.apply(request)
    assert not request.output_path.exists()
    request.existing_signatures_confirmed = True
    assert service.apply(request).had_digital_signatures is True


def test_write_failure_removes_temporary_file(tmp_path: Path, monkeypatch):
    source = _pdf(tmp_path / "input.pdf")
    request = _request(source, tmp_path / "output.pdf")

    def fail(*_args, **_kwargs):
        raise OSError("falha simulada")

    monkeypatch.setattr(fitz.Document, "save", fail)
    with pytest.raises(SignedDocumentWriteError):
        HandwrittenSignatureService().apply(request)
    assert not request.output_path.exists()
    assert list(tmp_path.glob(".*.tmp.pdf")) == []


def test_output_can_be_imported_with_handwritten_history(tmp_path: Path):
    source = _pdf(tmp_path / "input.pdf")
    result = HandwrittenSignatureService().apply(_request(source, tmp_path / "visual.pdf"))
    documents = DocumentService(db_path=str(tmp_path / "ged" / "smartfile.db"))
    imported = documents.import_document(str(result.output_path))
    documents.history_service.record_action(imported.id, "HANDWRITTEN_SIGNED", "Marca visual")
    actions = {item.action for item in documents.history_service.list_history(imported.id)}
    assert actions == {"IMPORT", "HANDWRITTEN_SIGNED"}
    assert Path(imported.storage_path).is_file()


def test_worker_preserves_native_finished_signal():
    assert "finished" not in HandwrittenSignatureWorker.__dict__


def test_viewer_keeps_three_signature_actions_separate():
    _app()
    view = PDFViewerView()
    labels = {button.accessibleName(): button for button in view.buttons}
    assert {"Assinar digitalmente", "Assinatura manuscrita", "Validar assinaturas"} <= labels.keys()
    assert not labels["Assinatura manuscrita"].icon().isNull()
    view.close()
