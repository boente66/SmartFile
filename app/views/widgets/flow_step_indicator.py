"""Reusable circle navigation. All request state is supplied by its controller."""
from math import sin, pi
from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QWidget


class FlowStepButton(QPushButton):
    def __init__(self,label,parent=None):
        super().__init__(parent)
        self.label=label;self.count=0;self.badge=0;self.halo=None
        self.setCheckable(True);self.setMinimumSize(110,112)
        self.setAccessibleName(label)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def paintEvent(self,event):
        painter=QPainter(self);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center=QPointF(self.width()/2,32)
        if self.halo:
            for radius,alpha in ((31,25),(28,50),(26,90)):
                color=QColor(self.halo);color.setAlpha(alpha)
                painter.setPen(QPen(color,4));painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(center,radius,radius)
        active=self.isChecked()
        painter.setPen(QPen(QColor("#1769e8" if active else "#b7c5d5"),2))
        painter.setBrush(QColor("#1769e8" if active else "#ffffff"))
        painter.drawEllipse(center,22,22)
        painter.setPen(QColor("#ffffff" if active else "#334155"))
        font=painter.font();font.setBold(True);font.setPointSize(12);painter.setFont(font)
        painter.drawText(QRectF(center.x()-22,10,44,44),Qt.AlignmentFlag.AlignCenter,str(self.count))
        font.setPointSize(10);painter.setFont(font)
        painter.setPen(QColor("#1769e8" if active else "#475569"))
        painter.drawText(QRectF(0,60,self.width(),24),Qt.AlignmentFlag.AlignCenter,self.label)
        if self.badge:
            font.setPointSize(9);painter.setFont(font);painter.setPen(QColor("#a42b3c"))
            painter.drawText(QRectF(0,85,self.width(),22),Qt.AlignmentFlag.AlignCenter,f"● {self.badge} nova(s)")
        if self.hasFocus():
            painter.setPen(QPen(QColor("#475569"),1,Qt.PenStyle.DotLine))
            painter.setBrush(Qt.BrushStyle.NoBrush);painter.drawRoundedRect(self.rect().adjusted(2,2,-2,-2),8,8)


class FlowStepIndicator(QWidget):
    step_clicked=pyqtSignal(int)
    LABELS=("Entrada","Atendimento","Preparação","Entrega","Finalizadas")

    def __init__(self,parent=None):
        super().__init__(parent)
        self.buttons=[];self.counts=[0]*5;self.badge=0;self.selected=0;self.phase=0
        layout=QHBoxLayout(self);layout.setSpacing(12);layout.setContentsMargins(4,4,4,4)
        for i,label in enumerate(self.LABELS):
            button=FlowStepButton(label,self)
            button.clicked.connect(lambda _checked=False,index=i:self.select(index))
            self.buttons.append(button);layout.addWidget(button,1)
        self.timer=QTimer(self);self.timer.setInterval(100);self.timer.timeout.connect(self._animate)
        self._refresh()

    def paintEvent(self,event):
        super().paintEvent(event)
        painter=QPainter(self);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#ccd6e1"),2))
        for first,second in zip(self.buttons,self.buttons[1:]):
            left=QPointF(first.x()+first.width()/2+25,first.y()+32)
            right=QPointF(second.x()+second.width()/2-25,second.y()+32)
            painter.drawLine(left,right)

    def select(self,index):
        self.selected=index;self._refresh();self.step_clicked.emit(index)

    def set_counts(self,counts,badge=0):
        self.counts=list(counts);self.badge=badge;self._refresh()

    def _refresh(self):
        for i,button in enumerate(self.buttons):
            button.count=self.counts[i];button.badge=self.badge if i==0 else 0
            button.setAccessibleName(f"{self.LABELS[i]}: {self.counts[i]}" + (f", {self.badge} nova(s)" if i==0 and self.badge else ""))
            button.setChecked(i==self.selected);button.update()
        self.update()

    def alert(self):
        self.phase=0;self.timer.start()

    def stop_alert(self):
        self.timer.stop();self.buttons[0].halo=None;self.buttons[0].update()

    def _animate(self):
        self.phase+=1
        if self.phase>=30:self.stop_alert();return
        weight=(sin(self.phase*pi/10)+1)/2
        self.buttons[0].halo=QColor(round(80+150*weight),110,round(230-130*weight))
        self.buttons[0].update()
