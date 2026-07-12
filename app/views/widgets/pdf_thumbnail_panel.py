from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QImage, QPixmap
from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QVBoxLayout, QWidget


class PDFThumbnailPanel(QWidget):
    page_selected = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        self.list_widget = QListWidget()
        self.list_widget.setIconSize(QSize(130, 170))
        self.list_widget.currentRowChanged.connect(
            lambda row: self.page_selected.emit(row + 1) if row >= 0 else None
        )
        layout.addWidget(self.list_widget)

    def prepare(self, page_count: int) -> None:
        self.list_widget.clear()
        for page in range(1, page_count + 1):
            item = QListWidgetItem(f"Página {page}")
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
            self.list_widget.addItem(item)

    def set_thumbnail(self, page_number: int, image: QImage) -> None:
        if not 1 <= page_number <= self.list_widget.count():
            return
        pixmap = QPixmap.fromImage(image)
        self.list_widget.item(page_number - 1).setIcon(QIcon(pixmap))

    def select_page(self, page_number: int) -> None:
        if 1 <= page_number <= self.list_widget.count():
            self.list_widget.setCurrentRow(page_number - 1)
            self.list_widget.scrollToItem(self.list_widget.item(page_number - 1))
