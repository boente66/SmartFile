"""Compatibilidade da API de composição com o executor genérico de arquivos."""
from app.workers.file_operation_worker import FileOperationWorker


class CapturePdfWorker(FileOperationWorker):
    pass
