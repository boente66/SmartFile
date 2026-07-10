from PyQt6.QtCore import QThread, pyqtSignal as Signal


class BaseWorker(QThread):
    """
    Worker base para tarefas longas.
    """

    progress = Signal(int, str)
    finished = Signal()
    failed = Signal(str)

    def __init__(self):
        super().__init__()