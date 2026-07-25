import os
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PyQt6.QtWidgets import QApplication

from app.controllers.convert_controller import ConvertController
from app.errors.conversion_exceptions import ConversionCancelledError
from app.models.convert_job import ConvertJob
from app.services.convert_service import ConvertService
from app.services.doc_service import DOCService
from app.services.pdf_service import PDFService
from app.ui.icon_provider import IconProvider
from app.views.convert_views import ConvertView
from app.workers.convert_worker import ConvertWorker


_APPLICATION = None


def _app():
    global _APPLICATION
    _APPLICATION = QApplication.instance() or QApplication([])
    return _APPLICATION


def _docx_job(tmp_path: Path) -> ConvertJob:
    input_path = tmp_path / "entrada.docx"
    input_path.write_bytes(b"docx")
    return ConvertJob(
        input_path=input_path,
        output_path=tmp_path / "saida.pdf",
        source_format="DOCX",
        target_format="PDF",
    )


def test_docx_to_pdf_dispatches_to_docx_service(tmp_path: Path, monkeypatch):
    job = _docx_job(tmp_path)
    received = []

    monkeypatch.setattr(
        DOCService,
        "convert_docx_to_pdf",
        lambda current_job, progress: received.append(current_job),
    )

    ConvertService.execute(job)

    assert job.conversion_key == "DOCX->PDF"
    assert received == [job]


def test_worker_emits_succeeded_without_overriding_qthread_finished(
    tmp_path: Path, monkeypatch
):
    job = _docx_job(tmp_path)
    events = []
    monkeypatch.setattr(
        ConvertService,
        "execute",
        lambda **kwargs: job.output_path.write_bytes(b"pdf"),
    )
    worker = ConvertWorker(job)
    worker.succeeded.connect(lambda: events.append("succeeded"))

    worker.run()

    assert events == ["succeeded"]
    assert "finished" not in ConvertWorker.__dict__


def test_worker_emits_failed_without_success(tmp_path: Path, monkeypatch):
    job = _docx_job(tmp_path)
    events = []

    def fail(**kwargs):
        raise RuntimeError("falha controlada")

    monkeypatch.setattr(ConvertService, "execute", fail)
    worker = ConvertWorker(job)
    worker.succeeded.connect(lambda: events.append("succeeded"))
    worker.failed.connect(lambda message: events.append(message))

    worker.run()

    assert events == ["falha controlada"]


def test_supported_conversion_matrix_matches_service_dispatch():
    assert ConvertService.available_targets("pdf") == ("DOCX", "JPG")
    assert ConvertService.available_targets("jpeg") == ("PDF",)
    assert ConvertService.available_targets("tif") == ("PDF", "JPG")
    assert ConvertService.supports("CSV", "XLSX") is True
    assert ConvertService.supports("PDF", "XLSX") is False


def test_convert_view_filters_formats_and_suggests_output(tmp_path: Path):
    _app()
    source = tmp_path / "relatorio.docx"
    source.write_bytes(b"docx")
    view = ConvertView()

    view.set_input_path(str(source))
    view.set_available_formats("DOCX", ("PDF", "JPG"))

    assert view.format_combo.count() == 2
    assert view.format_combo.currentText() == "DOCX → PDF"
    assert view.current_target() == "PDF"
    assert view.output_edit.text().endswith("relatorio_convertido.pdf")
    assert view.btn_convert.isEnabled()
    view.close()


def test_controller_builds_job_from_selected_target(tmp_path: Path):
    source = tmp_path / "imagem.png"
    source.write_bytes(b"png")
    controller = object.__new__(ConvertController)
    controller.view = SimpleNamespace(set_output_path=lambda *_args: None)

    job = controller._build_job({
        "input": str(source),
        "output": str(tmp_path / "imagem_convertida.jpg"),
        "target": "JPG",
    })

    assert job.source_format == "PNG"
    assert job.target_format == "JPG"


def test_controller_rejects_incompatible_output_extension(tmp_path: Path):
    source = tmp_path / "entrada.pdf"
    source.write_bytes(b"pdf")
    controller = object.__new__(ConvertController)
    controller.view = SimpleNamespace(set_output_path=lambda *_args: None)

    with pytest.raises(ValueError, match="deve terminar com .docx"):
        controller._build_job({
            "input": str(source),
            "output": str(tmp_path / "saida.xlsx"),
            "target": "DOCX",
        })


def test_worker_emits_cancelled_before_dispatch(tmp_path: Path, monkeypatch):
    job = _docx_job(tmp_path)
    events = []
    worker = ConvertWorker(job)
    worker.cancelled.connect(lambda: events.append("cancelled"))
    monkeypatch.setattr(worker, "isInterruptionRequested", lambda: True)

    worker.run()

    assert events == ["cancelled"]


def test_convert_service_cancellation_is_domain_error(tmp_path: Path):
    job = _docx_job(tmp_path)
    with pytest.raises(ConversionCancelledError):
        ConvertService.execute(job, cancellation_callback=lambda: True)


def test_linux_docx_conversion_uses_libreoffice_atomically(
    tmp_path: Path, monkeypatch,
):
    job = _docx_job(tmp_path)
    calls = []
    monkeypatch.setattr("app.services.doc_service.sys.platform", "linux")
    monkeypatch.setattr(
        "app.services.doc_service.shutil.which",
        lambda name: "/usr/bin/libreoffice" if name == "libreoffice" else None,
    )

    def run(command, **kwargs):
        calls.append((command, kwargs))
        output_dir = Path(command[command.index("--outdir") + 1])
        (output_dir / "entrada.pdf").write_bytes(b"converted")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("app.services.doc_service.subprocess.run", run)

    DOCService.convert_docx_to_pdf(job)

    assert job.output_path.read_bytes() == b"converted"
    assert calls[0][1]["timeout"] == 300
    assert "--headless" in calls[0][0]


def test_pdf_converter_is_closed_when_conversion_fails(
    tmp_path: Path, monkeypatch,
):
    source = tmp_path / "entrada.pdf"
    source.write_bytes(b"pdf")
    job = ConvertJob(source, tmp_path / "saida.docx", "PDF", "DOCX")
    state = {"closed": False}

    class BrokenConverter:
        def __init__(self, _path):
            pass

        def convert(self, _path):
            raise RuntimeError("falha controlada")

        def close(self):
            state["closed"] = True

    monkeypatch.setattr("app.services.pdf_service.Converter", BrokenConverter)

    with pytest.raises(RuntimeError, match="falha controlada"):
        PDFService.convert_pdf_to_docx(job)
    assert state["closed"] is True


def test_txt_to_pdf_produces_real_output(tmp_path: Path):
    source = tmp_path / "anotacoes.txt"
    source.write_text("SmartFile\nConversão segura", encoding="utf-8")
    output = tmp_path / "anotacoes.pdf"
    job = ConvertJob(source, output, "TXT", "PDF")

    ConvertService.execute(job)

    assert output.is_file()
    assert output.read_bytes().startswith(b"%PDF")


def test_linux_docx_without_libreoffice_has_actionable_error(
    tmp_path: Path, monkeypatch,
):
    job = _docx_job(tmp_path)
    monkeypatch.setattr("app.services.doc_service.sys.platform", "linux")
    monkeypatch.setattr(
        "app.services.doc_service.shutil.which", lambda _name: None
    )

    with pytest.raises(RuntimeError, match="requer o LibreOffice"):
        DOCService.convert_docx_to_pdf(job)


def test_icon_provider_colors_sidebar_svg():
    _app()
    icon = IconProvider.colored_icon("converter", "#1769e8")
    assert not icon.pixmap(20, 20).isNull()
