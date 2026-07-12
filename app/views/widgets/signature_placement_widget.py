from __future__ import annotations

from PyQt6.QtCore import QPoint, QRect, QRectF, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QMouseEvent, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QWidget


class SignaturePlacementWidget(QWidget):
    position_changed = pyqtSignal(float, float, float, float)

    def __init__(self, page: QPixmap, signature: QPixmap, page_size: tuple[float, float], rotation: int = 0, parent=None):
        super().__init__(parent)
        self._page = page
        self._signature = signature
        self._page_size = page_size
        self._rotation = rotation % 360
        self._selection = QRect()
        self._mode = "move"
        self._offset = QPoint()
        self.setMinimumSize(520, 540)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._selection.isNull():
            page = self._page_rect()
            width = max(80, page.width() // 3)
            ratio = self._signature.height() / max(self._signature.width(), 1)
            height = max(35, round(width * ratio))
            self._selection = QRect(page.center().x() - width // 2, page.center().y() - height // 2, width, height)
            self._selection = self._inside_page(self._selection)
            self._emit_position()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        point = event.position().toPoint()
        if self._handle().contains(point):
            self._mode = "resize"
        elif self._selection.contains(point):
            self._mode = "move"
            self._offset = point - self._selection.topLeft()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        point = event.position().toPoint()
        if self._mode == "move" and event.buttons() & Qt.MouseButton.LeftButton:
            moved = QRect(point - self._offset, self._selection.size())
            self._selection = self._inside_page(moved)
        elif self._mode == "resize" and event.buttons() & Qt.MouseButton.LeftButton:
            page = self._page_rect()
            width = max(40, min(point.x() - self._selection.left(), page.right() - self._selection.left()))
            ratio = self._signature.height() / max(self._signature.width(), 1)
            height = max(20, round(width * ratio))
            if self._selection.top() + height > page.bottom():
                height = page.bottom() - self._selection.top()
                width = round(height / max(ratio, 0.01))
            self._selection.setSize(QSize(width, height))
        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self._emit_position()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#d9dde2"))
        page = self._page_rect()
        painter.drawPixmap(page, self._page)
        if not self._selection.isNull():
            painter.drawPixmap(self._selection, self._signature)
            painter.setPen(QPen(QColor("#2563eb"), 2, Qt.PenStyle.DashLine))
            painter.drawRect(self._selection)
            painter.fillRect(self._handle(), QColor("#2563eb"))

    def pdf_position(self) -> tuple[float, float, float, float]:
        page = self._page_rect()
        relative = QRectF(
            (self._selection.left() - page.left()) / page.width(),
            (self._selection.top() - page.top()) / page.height(),
            self._selection.width() / page.width(),
            self._selection.height() / page.height(),
        )
        return self.normalized_to_pdf(relative, self._page_size, self._rotation)

    @staticmethod
    def normalized_to_pdf(rect: QRectF, page_size: tuple[float, float], rotation: int) -> tuple[float, float, float, float]:
        width, height = page_size
        corners = ((rect.left(), rect.top()), (rect.right(), rect.top()), (rect.left(), rect.bottom()), (rect.right(), rect.bottom()))
        mapped = []
        for u, v in corners:
            if rotation % 360 == 90:
                x, y = v * width, (1.0 - u) * height
            elif rotation % 360 == 180:
                x, y = (1.0 - u) * width, (1.0 - v) * height
            elif rotation % 360 == 270:
                x, y = (1.0 - v) * width, u * height
            else:
                x, y = u * width, v * height
            mapped.append((x, y))
        xs, ys = zip(*mapped)
        x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
        return x1, y1, x2 - x1, y2 - y1

    def _page_rect(self) -> QRect:
        if self._page.isNull():
            return self.rect().adjusted(20, 20, -20, -20)
        scaled = self._page.size().scaled(self.size() - QSize(30, 30), Qt.AspectRatioMode.KeepAspectRatio)
        return QRect((self.width() - scaled.width()) // 2, (self.height() - scaled.height()) // 2, scaled.width(), scaled.height())

    def _inside_page(self, rect: QRect) -> QRect:
        page = self._page_rect()
        rect.setWidth(min(rect.width(), page.width()))
        rect.setHeight(min(rect.height(), page.height()))
        rect.moveLeft(min(max(rect.left(), page.left()), page.right() - rect.width() + 1))
        rect.moveTop(min(max(rect.top(), page.top()), page.bottom() - rect.height() + 1))
        return rect

    def _handle(self) -> QRect:
        return QRect(self._selection.bottomRight() - QPoint(6, 6), QSize(12, 12))

    def _emit_position(self) -> None:
        if not self._selection.isNull():
            self.position_changed.emit(*self.pdf_position())
