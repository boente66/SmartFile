from pathlib import Path
from PyQt6.QtWidgets import QMessageBox

from app.views.convert_views import ConvertView
from app.models.convert_job import ConvertJob
from app.workers.convert_worker import ConvertWorker


class ConvertController:
    """
    Controller do módulo de conversão.
    """

    def __init__(self, workspace, main_view):
        self.workspace = workspace
        self.main_view = main_view
        self.view = ConvertView()
        self._worker = None  # referência viva da thread

        self._connect_signals()
        self._register_view()

    # -------------------------
    # Conexões
    # -------------------------
    def _connect_signals(self):
        self.view.convert_requested.connect(self.on_convert_requested)

    # -------------------------
    # Registro da View
    # -------------------------
    def _register_view(self):
        self.workspace.register_view("converter", self.view)

    # -------------------------
    # Ativação do módulo
    # -------------------------
    def activate(self):
        self.workspace.show_view("converter")

    def open_document(self, input_path: str):
        """Abre o conversor com um documento previamente selecionado."""
        self.view.set_input_path(input_path)
        self.activate()

    # -------------------------
    # Solicitação de conversão
    # -------------------------
    def on_convert_requested(self, data: dict):
        try:

            # Impede múltiplas conversões simultâneas
            if self._worker is not None:
                QMessageBox.warning(
                    self.view,
                    "Conversão em andamento",
                    "Aguarde a conversão atual terminar."
                )
                return

            input_path = Path(data["input"])
            output_path = Path(data["output"])

            # -------------------------
            # Validações
            # -------------------------

            if not input_path.exists():
                raise ValueError("Arquivo de entrada não existe.")

            if not output_path.parent.exists():
                raise ValueError("Diretório de saída inválido.")

            # Normaliza extensões
            source_format = input_path.suffix.replace(".", "").upper()
            target_format = output_path.suffix.replace(".", "").upper()

            # -------------------------
            # Cria Job
            # -------------------------

            job = ConvertJob(
                input_path=input_path,
                output_path=output_path,
                source_format=source_format,
                target_format=target_format
            )
            job.validate()

            # -------------------------
            # Worker
            # -------------------------

            worker = ConvertWorker(job)
            self._worker = worker

            progress = self.main_view.progress
            progress.start("Convertendo")

            worker.progress.connect(
                lambda v, m: progress.update(v, m)
            )

            worker.succeeded.connect(self._on_succeeded)
            worker.failed.connect(self._on_failed)
            worker.finished.connect(
                lambda worker=worker: self._cleanup_worker(worker)
            )
            worker.finished.connect(worker.deleteLater)

            worker.start()

        except Exception as e:

            QMessageBox.critical(
                self.view,
                "Erro na conversão",
                str(e)
            )

            self._worker = None

    # -------------------------
    # Conversão concluída
    # -------------------------
    def _on_succeeded(self):

        if self.main_view and self.main_view.progress:
            self.main_view.progress.finish("Conversão concluída")

    # -------------------------
    # Erro na conversão
    # -------------------------
    def _on_failed(self, message: str):

        if self.main_view and self.main_view.progress:
            self.main_view.progress.finish("Erro")

        QMessageBox.critical(
            self.view,
            "Erro na conversão",
            message
        )

    def _cleanup_worker(self, worker: ConvertWorker):
        if self._worker is worker:
            self._worker = None
