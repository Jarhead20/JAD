from PySide6.QtCore import Qt, QRectF, QSize, QRect
from PySide6.QtGui import QPainter, QPen, QFont
from PySide6.QtWidgets import QWidget
import math

class Gauge(QWidget):
    def __init__(self, label="Label", bar_color=Qt.green, track_color=Qt.gray, bg_color=Qt.black,
                 thickness=24, initial_value = 0.0, start_angle = 225, 
                 span_angle = -270, text_color=Qt.white,
                 redline_color=Qt.red,
                 font_size = 10,
                 redline = 8.0,
                 max_val = 9.0,

                 
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
        self._redline = redline
        self._redline_color = redline_color
        self._max_val = max_val



        # self.setMinimumSize(220, 220)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)

    def sizeHint(self) -> QSize:
        return QSize(260, 260)
    
    def _angle_for_value(self, v: float) -> float:
        """Return angle in degrees along the gauge arc for value v (0.._max_val)."""
        return self._start_angle + (self._span_angle * (v / self._max_val))

    def set_value(self, v: float):
        v = 0.0 if v is None else max(0.0, min(self._max_val, float(v)))
        if abs(v - self._value) > 1e-6:
            self._value = v
            self.update()

    def set_max_val(self, max: float) -> float:
        self._max_val = max

    def paintEvent(self, e):
        side = min(self.width(), self.height())
        r = QRectF((self.width()-side)/2 + self._thickness/2,
                   (self.height()-side)/2 + self._thickness/2,
                   side - self._thickness,
                   side - self._thickness)

        start = int(self._start_angle * 16)
        full_span = int(self._span_angle * 16)
        val_span  = int(full_span * (self._value/self._max_val))

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        # Background
        p.fillRect(self.rect(), self._bg_color)

        # Track (full arc)
        pen = QPen(self._track_color, self._thickness)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawArc(r, start, full_span)

        cx, cy = self.rect().center().x(), self.rect().center().y()
        radius_mid   = r.width() / 2.0                      # midline radius of arc
        radius_inner = radius_mid - self._thickness / 2.0   # inner edge of ring

        # Scale tick sizes with widget size
        scale = side / 260.0
        gap_from_ring   = 6 * scale      # gap inside the ring before ticks start
        major_len       = 14 * scale
        minor_len       = 8 * scale
        major_width     = max(1.0, 2.0 * scale)
        minor_width     = max(1.0, 1.0 * scale)
        minor_per_segment = 4            # 4 minor ticks between major ticks

        # Helpers
        def polar_point(rad, deg):
            rad_ang = math.radians(deg)
            # Qt Y axis goes down, so subtract the sin for screen coords
            return (cx + rad * math.cos(rad_ang),
                    cy - rad * math.sin(rad_ang))

        # Pens for ticks
        tick_major_pen = QPen(self._text_color, major_width)
        tick_minor_pen = QPen(self._track_color, minor_width)

        # Major ticks and labels (0 .. int(_max_val))
        max_int = int(round(self._max_val))
        label_font_px = max(8, int(12 * scale))
        label_font = QFont("DejaVu Sans", label_font_px)

        for i in range(0, max_int + 1):
            ang = self._angle_for_value(i)
            # Major tick line from just inside inner ring, inward
            r0 = radius_inner - gap_from_ring
            r1 = r0 - major_len
            x0, y0 = polar_point(r0, ang)
            x1, y1 = polar_point(r1, ang)
            p.setPen(tick_major_pen)
            p.drawLine(int(x0), int(y0), int(x1), int(y1))

            # Label a bit further in
            label_radius = r1 - (10 * scale)
            lx, ly = polar_point(label_radius, ang)
            # Center a small rect around the point for drawing the text
            box_w = 26 * scale
            box_h = 18 * scale
            text_rect = QRectF(lx - box_w/2, ly - box_h/2, box_w, box_h)
            p.setPen(self._text_color)
            p.setFont(label_font)
            p.drawText(text_rect, Qt.AlignCenter, str(i))

            # Minor ticks between this major and the next (skip after last)
            if i < max_int:
                for m in range(1, minor_per_segment):
                    v = i + (m / minor_per_segment)
                    # Don’t exceed _max_val if it’s not an integer
                    if v > self._max_val:
                        break
                    mang = self._angle_for_value(v)
                    r0m = radius_inner - gap_from_ring
                    r1m = r0m - minor_len
                    xm0, ym0 = polar_point(r0m, mang)
                    xm1, ym1 = polar_point(r1m, mang)
                    p.setPen(tick_minor_pen)
                    p.drawLine(int(xm0), int(ym0), int(xm1), int(ym1))

        # Bar (value arc)
        if self._value >= self._redline:
            pen.setColor(self._redline_color)
        else:
            pen.setColor(self._bar_color)
        p.setPen(pen)
        if self._value > 0:
            p.drawArc(r, start, val_span)

        # Text
        p.setPen(self._text_color)
        p.setFont(QFont("DejaVu Sans", self._font_size))

        p.end()