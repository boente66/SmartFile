from PyQt6.QtCore import QPoint, QRect, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QMouseEvent, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QWidget


class PDFSignaturePlacementWidget(QWidget):
    area_changed = pyqtSignal(float, float, float, float)

    def __init__(self, pixmap: QPixmap, page_width: float, page_height: float, parent=None):
        super().__init__(parent)
        self._pixmap = pixmap
        self._page_width = page_width
        self._page_height = page_height
        self._selection = QRect()
        self._mode = "draw"
        self._origin = QPoint()
        self._move_offset = QPoint()
        self.setMinimumSize(380, 460)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        point = event.position().toPoint()
        if self._resize_handle().contains(point):
            self._mode = "resize"
        elif self._selection.contains(point):
            self._mode = "move"
            self._move_offset = point - self._selection.topLeft()
        else:
            self._mode = "draw"
            self._origin = point
            self._selection = QRect(point, point)
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        point = self._clamped(event.position().toPoint())
        page_rect = self._page_rect()
        if self._mode == "move" and not self._selection.isNull():
            top_left = point - self._move_offset
            top_left.setX(min(max(top_left.x(), page_rect.left()), page_rect.right() - self._selection.width()))
            top_left.setY(min(max(top_left.y(), page_rect.top()), page_rect.bottom() - self._selection.height()))
            self._selection.moveTopLeft(top_left)
        elif self._mode == "resize" and not self._selection.isNull():
            self._selection.setBottomRight(point)
            self._selection = self._selection.normalized()
        else:
            self._selection = QRect(self._origin, point).normalized()
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._emit_area()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#d9dde2"))
        target = self._page_rect()
        if not self._pixmap.isNull():
            painter.drawPixmap(target, self._pixmap)
        if not self._selection.isNull():
            painter.fillRect(self._selection, QColor(37, 99, 235, 55))
            painter.setPen(QPen(QColor("#2563eb"), 2))
            painter.drawRect(self._selection)
            painter.fillRect(self._resize_handle(), QColor("#2563eb"))
        painter.end()

    def _page_rect(self) -> QRect:
        if self._pixmap.isNull():
            return self.rect().adjusted(20, 20, -20, -20)
        scaled = self._pixmap.size().scaled(
            self.size() - self._margins(), Qt.AspectRatioMode.KeepAspectRatio
        )
        return QRect(
            (self.width() - scaled.width()) // 2,
            (self.height() - scaled.height()) // 2,
            scaled.width(), scaled.height(),
        )

    @staticmethod
    def _margins():
        from PyQt6.QtCore import QSize
        return QSize(24, 24)

    def _resize_handle(self) -> QRect:
        if self._selection.isNull():
            return QRect()
        return QRect(self._selection.bottomRight() - QPoint(5, 5), self._selection.bottomRight() + QPoint(5, 5))

    def _clamped(self, point: QPoint) -> QPoint:
        rect = self._page_rect()
        return QPoint(
            min(max(point.x(), rect.left()), rect.right()),
            min(max(point.y(), rect.top()), rect.bottom()),
        )

    def _emit_area(self):
        page = self._page_rect()
        selection = self._selection.intersected(page)
        if selection.width() < 8 or selection.height() < 8:
            return
        scale_x = self._page_width / page.width()
        scale_y = self._page_height / page.height()
        x1 = (selection.left() - page.left()) * scale_x
        x2 = (selection.right() - page.left()) * scale_x
        y1 = self._page_height - (selection.bottom() - page.top()) * scale_y
        y2 = self._page_height - (selection.top() - page.top()) * scale_y
        self.area_changed.emit(x1, y1, x2, y2)
