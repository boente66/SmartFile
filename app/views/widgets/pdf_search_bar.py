from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget


class PDFSearchBar(QWidget):
    search_requested = pyqtSignal(str)
    previous_requested = pyqtSignal()
    next_requested = pyqtSignal()
    close_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        self.input = QLineEdit()
        self.input.setPlaceholderText("Pesquisar no documento")
        self.input.returnPressed.connect(lambda: self.search_requested.emit(self.input.text()))
        self.counter = QLabel("0 de 0")
        previous = QPushButton("Anterior")
        next_button = QPushButton("Próxima")
        close = QPushButton("×")
        previous.clicked.connect(self.previous_requested.emit)
        next_button.clicked.connect(self.next_requested.emit)
        close.clicked.connect(self.close_requested.emit)
        layout.addWidget(self.input, 1)
        layout.addWidget(self.counter)
        layout.addWidget(previous)
        layout.addWidget(next_button)
        layout.addWidget(close)
        self.hide()

    def open(self) -> None:
        self.show()
        self.input.setFocus()
        self.input.selectAll()

    def set_count(self, current: int, total: int) -> None:
        self.counter.setText(f"{current} de {total}")
