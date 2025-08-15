from PySide6.QtCore import Qt, QRectF, QSize, QRect
from PySide6.QtGui import QPainter, QPen, QFont
from PySide6.QtWidgets import QWidget

class Gauge(QWidget):
    def __init__(self, label="Label", bar_color=Qt.green, track_color=Qt.gray, bg_color=Qt.black,
                 thickness=24, initial_value = 0.0, start_angle = 225, 
                 span_angle = -270, text_color=Qt.white,
                 font_size = 10,
                   parent=None):
        super().__init__(parent)
        self._value = initial_value
        self._thickness = thickness
        self._bg_color = bg_color
        self._track_color = track_color
        self._bar_color = bar_color
        self._label = label
        self._start_angle = start_angle
        self._span_angle = span_angle
        self._text_color = text_color
        self._font_size = font_size



        # self.setMinimumSize(220, 220)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)

    def sizeHint(self) -> QSize:
        return QSize(260, 260)

    def set_value(self, v: float):
        v = 0.0 if v is None else max(0.0, min(1.0, float(v)))
        if abs(v - self._value) > 1e-6:
            self._value = v
            self.update()

    def paintEvent(self, e):
        side = min(self.width(), self.height())
        r = QRectF((self.width()-side)/2 + self._thickness/2,
                   (self.height()-side)/2 + self._thickness/2,
                   side - self._thickness,
                   side - self._thickness)

        start = int(self._start_angle * 16)
        full_span = int(self._span_angle * 16)
        val_span  = int(full_span * self._value)

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        # Background
        p.fillRect(self.rect(), self._bg_color)

        # Track (full arc)
        pen = QPen(self._track_color, self._thickness)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawArc(r, start, full_span)

        # Bar (value arc)
        pen.setColor(self._bar_color)
        p.setPen(pen)
        if self._value > 0:
            p.drawArc(r, start, val_span)

        # Text
        p.setPen(self._text_color)
        p.setFont(QFont("DejaVu Sans", self._font_size))
        percent = int(round(self._value * 100))
        
        p.drawText(self.rect(), Qt.AlignCenter, f"{self._label}\n{percent}%")

        p.end()