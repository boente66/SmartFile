from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

from PyQt6.QtWidgets import QMessageBox

from app.models.convert_job import ConvertJob
from app.services.convert_service import ConvertService
from app.views.convert_views import ConvertView
from app.workers.convert_worker import ConvertWorker

logger = logging.getLogger(__name__)


class ConvertController:
    """Coordena a interface e os casos de uso do módulo Conversor."""

    _ALIASES = {"JPEG": "JPG", "TIF": "TIFF"}

    def __init__(self, workspace, main_view):
        self.workspace = workspace
        self.main_view = main_view
        self.view = ConvertView()
        self._worker: ConvertWorker | None = None
        self._display_name: str | None = None
        self._managed_input_path: Path | None = None
        self._connect_signals()
        self.workspace.register_view("converter", self.view)

    def _connect_signals(self) -> None:
        self.view.convert_requested.connect(self.on_convert_requested)
        self.view.cancel_requested.connect(self.on_cancel_requested)
        self.view.input_path_changed.connect(self.on_input_path_changed)
        self.view.open_output_requested.connect(self.open_output)
        self.view.return_requested.connect(self.return_to_documents)

    def activate(self) -> None:
        self.main_view.sidebar.show()
        self.main_view.sidebar.set_active_tool("converter")
        self.workspace.show_view("converter")

    def open_document(
        self, input_path: str, display_name: str | None = None
    ) -> None:
        """Abre o Conversor com um arquivo previamente selecionado no GED."""

        self._display_name = display_name
        self._managed_input_path = Path(input_path).expanduser().resolve()
        self.view.set_input_path(input_path)
        if display_name and self.view.current_target():
            destination_dir = Path.home() / "Documents"
            if not destination_dir.is_dir():
                destination_dir = Path.home()
            stem = Path(display_name).stem or Path(input_path).stem
            target = self.view.current_target().lower()
            self.view.set_output_path(
                str(destination_dir / f"{stem}_convertido.{target}")
            )
            self.view.input_hint.setText(
                f"Documento do GED: {display_name}"
            )
        self.activate()

    def on_input_path_changed(self, value: str) -> None:
        if value and self._managed_input_path is not None:
            selected = Path(value).expanduser().resolve()
            if selected != self._managed_input_path:
                self._display_name = None
                self._managed_input_path = None
        source = self._source_format(Path(value)) if value else ""
        targets = ConvertService.available_targets(source)
        self.view.set_available_formats(source, targets)
        if self._display_name and value:
            self.view.input_hint.setText(
                f"Documento do GED: {self._display_name}"
            )

    def on_convert_requested(self, data: dict) -> None:
        try:
            if self._worker is not None:
                QMessageBox.information(
                    self.view,
                    "Conversão em andamento",
                    "Aguarde a conversão atual terminar ou solicite o cancelamento.",
                )
                return
            job = self._build_job(data)
            worker = ConvertWorker(job)
            self._worker = worker
            self.view.set_busy(True, self._display_name or str(job.input_path))
            self.main_view.progress.start("Convertendo")
            worker.progress.connect(self._on_progress)
            worker.succeeded.connect(
                lambda job=job: self._on_succeeded(job)
            )
            worker.cancelled.connect(self._on_cancelled)
            worker.failed.connect(self._on_failed)
            worker.finished.connect(
                lambda worker=worker: self._cleanup_worker(worker)
            )
            worker.finished.connect(worker.deleteLater)
            logger.info(
                "conversion.start source=%s target=%s input=%s output=%s",
                job.source_format,
                job.target_format,
                job.input_path,
                job.output_path,
            )
            worker.start()
        except Exception as exc:
            logger.warning("conversion.validation_failed error=%s", type(exc).__name__)
            self._worker = None
            QMessageBox.warning(self.view, "Não foi possível converter", str(exc))

    def on_cancel_requested(self) -> None:
        if self._worker is None:
            return
        self._worker.requestInterruption()
        self.view.show_cancelling()
        self.main_view.status.showMessage("Cancelando conversão...")
        logger.info("conversion.cancel_requested")

    def return_to_documents(self) -> None:
        if self._worker is not None:
            return
        self.main_view.sidebar.set_active_tool("documents")
        self.main_view.sidebar.tool_selected.emit("documents")

    def open_output(self, value: str) -> None:
        path = Path(value).expanduser().resolve()
        if not path.is_file():
            QMessageBox.warning(
                self.view,
                "Abrir resultado",
                "O arquivo convertido não está mais disponível.",
            )
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except OSError as exc:
            QMessageBox.warning(
                self.view,
                "Abrir resultado",
                f"Não foi possível abrir o arquivo: {exc}",
            )

    def _build_job(self, data: dict) -> ConvertJob:
        input_value = str(data.get("input") or "").strip()
        output_value = str(data.get("output") or "").strip()
        target = str(data.get("target") or "").strip().upper()
        if not input_value:
            raise ValueError("Selecione um arquivo de entrada.")
        if not output_value:
            raise ValueError("Escolha onde salvar o arquivo convertido.")
        input_path = Path(input_value).expanduser().resolve()
        output_path = Path(output_value).expanduser().resolve()
        if not input_path.exists() or not input_path.is_file():
            raise ValueError("O arquivo de entrada não existe ou não é regular.")
        if input_path.stat().st_size <= 0:
            raise ValueError("O arquivo de entrada está vazio.")
        source = self._source_format(input_path)
        if not ConvertService.supports(source, target):
            raise ValueError(
                f"A conversão {source or '?'} → {target or '?'} não é suportada."
            )
        expected_suffix = f".{target.lower()}"
        if output_path.suffix == "":
            output_path = output_path.with_suffix(expected_suffix)
            self.view.set_output_path(str(output_path))
        elif output_path.suffix.lower() != expected_suffix:
            raise ValueError(
                f"O arquivo de saída deve terminar com {expected_suffix}."
            )
        if not output_path.parent.exists() or not output_path.parent.is_dir():
            raise ValueError("A pasta de saída não existe.")
        if not os.access(output_path.parent, os.W_OK):
            raise PermissionError("Sem permissão para gravar na pasta de saída.")
        if output_path.exists():
            raise FileExistsError(
                "O arquivo de saída já existe. Escolha outro nome para preservar o original."
            )
        job = ConvertJob(
            input_path=input_path,
            output_path=output_path,
            source_format=source,
            target_format=target,
        )
        job.validate()
        return job

    def _on_progress(self, value: int, message: str) -> None:
        self.main_view.progress.update(value, message)
        self.view.update_progress(value, message)

    def _on_succeeded(self, job: ConvertJob) -> None:
        self.main_view.progress.finish("Conversão concluída")
        self.main_view.status.showMessage("Conversão concluída com sucesso")
        self.view.show_success(str(job.output_path))
        self.view.add_history(
            self._display_name or job.input_path.name,
            f"{job.source_format} → {job.target_format}",
            str(job.output_path),
        )
        logger.info(
            "conversion.succeeded source=%s target=%s output=%s",
            job.source_format,
            job.target_format,
            job.output_path,
        )

    def _on_cancelled(self) -> None:
        self.main_view.progress.finish("Conversão cancelada")
        self.main_view.status.showMessage("Conversão cancelada")
        self.view.show_cancelled()
        logger.info("conversion.cancelled")

    def _on_failed(self, message: str) -> None:
        self.main_view.progress.finish("Erro na conversão")
        self.main_view.status.showMessage("Falha na conversão")
        self.view.show_failure(message)
        logger.error("conversion.failed message=%s", message)
        QMessageBox.critical(self.view, "Erro na conversão", message)

    def _cleanup_worker(self, worker: ConvertWorker) -> None:
        if self._worker is worker:
            self._worker = None

    @classmethod
    def _source_format(cls, path: Path) -> str:
        source = path.suffix.lstrip(".").upper()
        return cls._ALIASES.get(source, source)
