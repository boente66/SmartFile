from __future__ import annotations

from PyQt6.QtCore import QBuffer, QByteArray, QEvent, QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPainterPath, QPen, QTabletEvent
from PyQt6.QtWidgets import QWidget


class SignatureCanvas(QWidget):
    """Canvas HiDPI em memória para mouse, touch e caneta gráfica."""

    changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._strokes: list[list[QPointF]] = []
        self._redo: list[list[QPointF]] = []
        self._active: list[QPointF] | None = None
        self._color = QColor("#111827")
        self._stroke_width = 3.0
        self.setMinimumSize(560, 230)
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)
        self.setTabletTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)

    @property
    def is_empty(self) -> bool:
        return not any(len(stroke) > 1 for stroke in self._strokes)

    @property
    def color_name(self) -> str:
        return self._color.name()

    @property
    def stroke_width(self) -> float:
        return self._stroke_width

    def set_color(self, color: str) -> None:
        self._color = QColor(color)
        self.update()

    def set_stroke_width(self, width: float) -> None:
        self._stroke_width = max(1.0, min(float(width), 9.0))
        self.update()

    def clear(self) -> None:
        self._strokes.clear()
        self._redo.clear()
        self._active = None
        self.changed.emit(False)
        self.update()

    def undo(self) -> None:
        if self._strokes:
            self._redo.append(self._strokes.pop())
            self.changed.emit(not self.is_empty)
            self.update()

    def redo(self) -> None:
        if self._redo:
            self._strokes.append(self._redo.pop())
            self.changed.emit(True)
            self.update()

    def export_png(self, scale: float = 2.0, margin: int = 8) -> bytes:
        if self.is_empty:
            return b""
        bounds = self._stroke_bounds().adjusted(-margin, -margin, margin, margin).intersected(QRectF(self.rect()))
        width = max(1, round(bounds.width() * scale))
        height = max(1, round(bounds.height() * scale))
        image = QImage(width, height, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.scale(scale, scale)
        painter.translate(-bounds.topLeft())
        self._paint_strokes(painter)
        painter.end()
        data = QByteArray()
        buffer = QBuffer(data)
        buffer.open(QBuffer.OpenModeFlag.WriteOnly)
        image.save(buffer, "PNG")
        return bytes(data)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._begin(event.position())

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            self._append(event.position())

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._finish(event.position())

    def tabletEvent(self, event: QTabletEvent) -> None:
        if event.type() == QEvent.Type.TabletPress:
            self._begin(event.position())
        elif event.type() == QEvent.Type.TabletMove:
            self._append(event.position())
        elif event.type() == QEvent.Type.TabletRelease:
            self._finish(event.position())
        event.accept()

    def event(self, event: QEvent) -> bool:
        if event.type() in {QEvent.Type.TouchBegin, QEvent.Type.TouchUpdate, QEvent.Type.TouchEnd}:
            points = event.points()
            if points:
                point = points[0].position()
                if event.type() == QEvent.Type.TouchBegin:
                    self._begin(point)
                elif event.type() == QEvent.Type.TouchUpdate:
                    self._append(point)
                else:
                    self._finish(point)
            event.accept()
            return True
        return super().event(event)

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#ffffff"))
        painter.setPen(QPen(QColor("#cbd5e1"), 1, Qt.PenStyle.DashLine))
        painter.drawRect(self.rect().adjusted(1, 1, -2, -2))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self._paint_strokes(painter)

    def _begin(self, point: QPointF) -> None:
        self._redo.clear()
        self._active = [self._clamp(point)]
        self._strokes.append(self._active)
        self.update()

    def _append(self, point: QPointF) -> None:
        if self._active is None:
            return
        point = self._clamp(point)
        if not self._active or (point - self._active[-1]).manhattanLength() >= 1.0:
            self._active.append(point)
            self.update()

    def _finish(self, point: QPointF) -> None:
        self._append(point)
        if self._active is not None and len(self._active) < 2:
            self._strokes.remove(self._active)
        self._active = None
        self.changed.emit(not self.is_empty)
        self.update()

    def _paint_strokes(self, painter: QPainter) -> None:
        pen = QPen(self._color, self._stroke_width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        for points in self._strokes:
            if len(points) < 2:
                continue
            path = QPainterPath(points[0])
            for index in range(1, len(points)):
                previous = points[index - 1]
                current = points[index]
                midpoint = QPointF((previous.x() + current.x()) / 2, (previous.y() + current.y()) / 2)
                path.quadTo(previous, midpoint)
            path.lineTo(points[-1])
            painter.drawPath(path)

    def _stroke_bounds(self) -> QRectF:
        points = [point for stroke in self._strokes for point in stroke]
        left = min(point.x() for point in points)
        top = min(point.y() for point in points)
        right = max(point.x() for point in points)
        bottom = max(point.y() for point in points)
        padding = self._stroke_width / 2
        return QRectF(left - padding, top - padding, right - left + padding * 2, bottom - top + padding * 2)

    def _clamp(self, point: QPointF) -> QPointF:
        return QPointF(
            min(max(point.x(), 0.0), float(self.width() - 1)),
            min(max(point.y(), 0.0), float(self.height() - 1)),
        )
