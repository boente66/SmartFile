from pathlib import Path

from app.models.convert_job import ConvertJob
from app.services.convert_service import ConvertService
from app.services.doc_service import DOCService
from app.workers.convert_worker import ConvertWorker


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
    monkeypatch.setattr(ConvertService, "execute", lambda **kwargs: None)
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
