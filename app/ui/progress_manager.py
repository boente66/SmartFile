from PyQt6.QtWidgets import QProgressBar


class ProgressManager:
    """
    Gerencia a barra de progresso global da aplicação.
    """

    def __init__(self, status_bar):
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setVisible(False)

        status_bar.addPermanentWidget(self.progress_bar)

    def start(self, message: str = ""):
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat(message + " %p%")
        self.progress_bar.setVisible(True)

    def update(self, value: int, message: str | None = None):
        self.progress_bar.setValue(value)
        if message:
            self.progress_bar.setFormat(message + " %p%")

    def finish(self, message: str = "Concluído"):
        self.progress_bar.setValue(100)
        self.progress_bar.setFormat(message)
        self.progress_bar.setVisible(False)