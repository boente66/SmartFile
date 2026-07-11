from PyQt6.QtCore import QThread, pyqtSignal


class BaseWorker(QThread):
    """
    Worker base para tarefas longas.
    """

    progress = pyqtSignal(int, str)
    succeeded = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self):
        super().__init__()
