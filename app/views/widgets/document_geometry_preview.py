from PyQt6.QtCore import QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen, QPolygonF
from PyQt6.QtWidgets import QLabel

from app.views.widgets.preview_widget import PreviewWidget


class GeometryImageLabel(QLabel):
    corners_changed = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.corners = None
        self.dragging = None
        self.setAccessibleName("Enquadramento da folha: quatro cantos ajustáveis")
        self.setToolTip("Arraste cada alça numerada para ajustar a folha.")

    def _rect(self):
        pixmap = self.pixmap()
        if pixmap is None or pixmap.isNull(): return None
        return ((self.width()-pixmap.width())/2,(self.height()-pixmap.height())/2,pixmap.width(),pixmap.height())

    def paintEvent(self,event):
        super().paintEvent(event)
        rect = self._rect()
        if not rect or not self.corners:return
        x,y,w,h=rect
        points=[QPointF(x+px*w,y+py*h) for px,py in self.corners]
        painter=QPainter(self);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#1676d2"),3));painter.drawPolygon(QPolygonF(points))
        for i,point in enumerate(points):
            painter.setBrush(QColor("white"));painter.drawEllipse(point,9,9)
            painter.drawText(point+QPointF(-4,4),str(i+1))

    def mousePressEvent(self,event):
        rect=self._rect()
        if rect and self.corners:
            x,y,w,h=rect
            for i,(px,py) in enumerate(self.corners):
                if (event.position()-QPointF(x+px*w,y+py*h)).manhattanLength()<24:
                    self.dragging=i;event.accept();return
        super().mousePressEvent(event)

    def mouseMoveEvent(self,event):
        if self.dragging is not None and self._rect():
            x,y,w,h=self._rect()
            points=list(self.corners)
            points[self.dragging]=(min(1,max(0,(event.position().x()-x)/w)),min(1,max(0,(event.position().y()-y)/h)))
            self.corners_changed.emit(tuple(points))
            event.accept();return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self,event):
        self.dragging=None
        super().mouseReleaseEvent(event)


class DocumentGeometryPreview(PreviewWidget):
    corners_changed=pyqtSignal(object)

    def __init__(self):
        super().__init__()
        old=self.scroll.takeWidget();old.deleteLater()
        self.image_label=GeometryImageLabel()
        self.scroll.setWidget(self.image_label)
        self.image_label.corners_changed.connect(self.corners_changed.emit)

    def set_geometry(self,geometry):
        self.image_label.corners=geometry.normalized_corners if geometry else None
        self.image_label.update()
