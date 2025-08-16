from PySide6.QtCore import Qt, QRectF, QSize
from PySide6.QtGui import QPainter, QPen, QFont
from PySide6.QtWidgets import QWidget
from elements.element import Element
import math

# ---------- Base class: shared state & API ----------
class GaugeBase(Element):
    def __init__(self, *, x, y, width, height, centered,
                 label="Label",
                 bar_color=Qt.green,
                 track_color=Qt.gray,
                 bg_color=Qt.black,
                 text_color=Qt.white,
                 redline_color=Qt.red,
                 font_size=14,
                 max_val=9.0,
                 redline=None,
                 parent=None, **kwargs):
        super().__init__(x, y, width, height, centered, bg_color, parent)
        self._label = label
        self._bar_color = bar_color
        self._track_color = track_color
        self._text_color = text_color
        self._redline_color = redline_color
        self._font_size = font_size
        self._max_val = float(max_val)
        self._redline = float(redline) if redline is not None else float(max_val)
        self._value = 0.0

        self._channel = kwargs.get("channel", None)
        self._scale   = kwargs.get("scale", 1.0)   # optional multiplier
        self._offset  = kwargs.get("offset", 0.0)  # optional offset

    # ---- common API ----
    def sizeHint(self) -> QSize:
        return QSize(self.width(), self.height())

    def set_value(self, v: float):
        v = 0.0 if v is None else float(v)
        v = max(0.0, min(self._max_val, v))
        if abs(v - self._value) > 1e-6:
            self._value = v
            self.update()

    def set_max_val(self, m: float):
        self._max_val = max(1e-9, float(m))
        if self._value > self._max_val:
            self._value = self._max_val
        if self._redline > self._max_val:
            self._redline = self._max_val
        self.update()

    def set_redline(self, r: float):
        self._redline = max(0.0, min(float(r), self._max_val))
        self.update()

    def update_val(self, store):
        if not self._channel:
            return
        v = store.get(self._channel)
        if v is None:
            return
        # Example: convert RPM to kRPM if max_val is in thousands
        self.set_value(self._offset + self._scale * float(v))

    def _ratio(self) -> float:
        return 0.0 if self._max_val <= 0 else (self._value / self._max_val)

    # Template method: subclasses implement _paint(p)
    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.fillRect(self.rect(), self._bg_color)
        self._paint(p)  # implemented by subclasses
        p.end()

    def _paint(self, p: QPainter):
        raise NotImplementedError


# ---------- Round gauge ----------
class RoundGauge(GaugeBase):
    def __init__(self, *,
                 thickness=24,
                 start_angle=225,    # degrees
                 span_angle=-270,    # degrees (clockwise)
                 minor_per_segment=4,
                 **kwargs):
        super().__init__(**kwargs)
        self._thickness = thickness
        self._start_angle = float(start_angle)
        self._span_angle = float(span_angle)
        self._minor_per_segment = int(minor_per_segment)

    def _angle_for_value(self, v: float) -> float:
        return self._start_angle + (self._span_angle * (v / self._max_val))

    def _paint(self, p: QPainter):
        side = min(self.width(), self.height())
        r = QRectF((self.width()-side)/2 + self._thickness/2,
                   (self.height()-side)/2 + self._thickness/2,
                   side - self._thickness,
                   side - self._thickness)

        start = int(self._start_angle * 16)
        full_span = int(self._span_angle * 16)
        val_span  = int(full_span * self._ratio())

        # Track
        pen = QPen(self._track_color, self._thickness)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        p.drawArc(r, start, full_span)

        # Ticks & labels
        cx, cy = self.rect().center().x(), self.rect().center().y()
        radius_mid   = r.width() / 2.0
        radius_inner = radius_mid - self._thickness / 2.0
        scale = side / 260.0
        gap_from_ring   = 6 * scale
        major_len       = 14 * scale
        minor_len       = 8 * scale
        major_w         = max(1.0, 2.0 * scale)
        minor_w         = max(1.0, 1.0 * scale)

        def polar(rad, deg):
            a = math.radians(deg)
            return (cx + rad * math.cos(a), cy - rad * math.sin(a))

        tick_major_pen = QPen(self._text_color, major_w)
        tick_minor_pen = QPen(self._track_color, minor_w)

        max_int = int(round(self._max_val))
        label_font = QFont("DejaVu Sans", max(8, int(12 * scale)))

        for i in range(0, max_int + 1):
            ang = self._angle_for_value(i)
            r0 = radius_inner - gap_from_ring
            r1 = r0 - major_len
            x0, y0 = polar(r0, ang); x1, y1 = polar(r1, ang)
            p.setPen(tick_major_pen); p.drawLine(int(x0), int(y0), int(x1), int(y1))

            # label
            lr = r1 - (10 * scale)
            lx, ly = polar(lr, ang)
            w, h = 26 * scale, 18 * scale
            p.setPen(self._text_color); p.setFont(label_font)
            p.drawText(QRectF(lx - w/2, ly - h/2, w, h), Qt.AlignCenter, str(i))

            # minors
            if i < max_int:
                for m in range(1, self._minor_per_segment):
                    v = i + (m / self._minor_per_segment)
                    if v > self._max_val: break
                    mang = self._angle_for_value(v)
                    r0m = r0; r1m = r0m - minor_len
                    xm0, ym0 = polar(r0m, mang); xm1, ym1 = polar(r1m, mang)
                    p.setPen(tick_minor_pen)
                    p.drawLine(int(xm0), int(ym0), int(xm1), int(ym1))

        # Value bar (swap to red at/after redline)
        pen.setColor(self._redline_color if self._value >= self._redline else self._bar_color)
        p.setPen(pen)
        if self._value > 0:
            p.drawArc(r, start, val_span)

        # Center text
        p.setPen(self._text_color)
        p.setFont(QFont("DejaVu Sans", self._font_size))
        inner_ratio = 0.55
        inner_side  = side * inner_ratio
        ctr = QRectF(self.rect().center().x() - inner_side/2,
                     self.rect().center().y() - inner_side/2,
                     inner_side, inner_side)
        p.drawText(ctr, Qt.AlignCenter | Qt.TextWordWrap,
                   f"{self._label}\n{self._value:.1f}")

# ---------- Linear gauge (horizontal by default) ----------
class LinearGauge(GaugeBase):
    def __init__(self, *,
                 thickness=24,
                 horizontal=True,
                 tick_step=10,            # major tick every 10 units
                 minor_per_major=4,
                 corner_radius=8,
                 **kwargs):
        super().__init__(**kwargs)
        self._thickness = thickness
        self._horizontal = bool(horizontal)
        self._tick_step = float(tick_step)
        self._minor_per_major = int(minor_per_major)
        self._corner_radius = corner_radius

    def _paint(self, p: QPainter):
        rect = self.rect().adjusted(16, 16, -16, -16)  # padding inside widget
        track_h = self._thickness
        if self._horizontal:
            # Track background line
            y = rect.center().y()
            x0, x1 = rect.left(), rect.right()
            pen = QPen(self._track_color, track_h)
            pen.setCapStyle(Qt.RoundCap); p.setPen(pen)
            p.drawLine(x0, y, x1, y)

            # Value bar
            pen.setColor(self._redline_color if self._value >= self._redline else self._bar_color)
            p.setPen(pen)
            xv = x0 + (x1 - x0) * self._ratio()
            p.drawLine(x0, y, int(xv), y)

            # Ticks & labels
            p.setPen(QPen(self._text_color, 1.5))
            font = QFont("DejaVu Sans", max(8, int(self._thickness * 0.5)))
            p.setFont(font)
            major = self._tick_step if self._tick_step > 0 else self._max_val
            v = 0.0
            while v <= self._max_val + 1e-6:
                t = v / self._max_val if self._max_val > 0 else 0
                xt = x0 + (x1 - x0) * t
                # major tick
                p.drawLine(int(xt), int(y + track_h/2 + 6), int(xt), int(y + track_h/2 + 6 + 10))
                # label
                if v < 1:
                    p.drawText(int(xt - 12), int(y + track_h/2 + 6 + 22), f"{v}")
                else:
                    p.drawText(int(xt - 12), int(y + track_h/2 + 6 + 22), f"{int(v)}")
                # minors
                if v + major <= self._max_val and self._minor_per_major > 1:
                    step = major / self._minor_per_major
                    for m in range(1, self._minor_per_major):
                        vm = v + m * step
                        tm = vm / self._max_val
                        xm = x0 + (x1 - x0) * tm
                        p.drawLine(int(xm), int(y + track_h/2 + 6),
                                   int(xm), int(y + track_h/2 + 6 + 6))
                v += major

            # Label/value
            p.setPen(self._text_color)
            p.setFont(QFont("DejaVu Sans", max(10, int(self._thickness * 0.6))))
            p.drawText(rect.adjusted(0, -int(track_h*1.8), 0, 0), Qt.AlignHCenter | Qt.AlignTop,
                       f"{self._label}: {self._value:.1f}")

        else:
            # Vertical: same idea, swap axes
            x = rect.center().x()
            y0, y1 = rect.bottom(), rect.top()
            pen = QPen(self._track_color, track_h); pen.setCapStyle(Qt.RoundCap); p.setPen(pen)
            p.drawLine(x, y0, x, y1)

            pen.setColor(self._redline_color if self._value >= self._redline else self._bar_color)
            p.setPen(pen)
            yv = y0 - (y0 - y1) * self._ratio()
            p.drawLine(x, y0, x, int(yv))

            p.setPen(QPen(self._text_color, 1.5))
            font = QFont("DejaVu Sans", max(8, int(self._thickness * 0.5)))
            p.setFont(font)
            major = self._tick_step if self._tick_step > 0 else self._max_val
            v = 0.0
            while v <= self._max_val + 1e-6:
                t = v / self._max_val if self._max_val > 0 else 0
                yt = y0 - (y0 - y1) * t
                p.drawLine(int(x - track_h/2 - 6), int(yt), int(x - track_h/2 - 6 - 10), int(yt))
                p.drawText(int(x - track_h/2 - 6 - 36), int(yt + 5), f"{int(v)}")
                if v + major <= self._max_val and self._minor_per_major > 1:
                    step = major / self._minor_per_major
                    for m in range(1, self._minor_per_major):
                        vm = v + m * step
                        tm = vm / self._max_val
                        ym = y0 - (y0 - y1) * tm
                        p.drawLine(int(x - track_h/2 - 6), int(ym), int(x - track_h/2 - 6 - 6), int(ym))
                v += major
            p.setPen(self._text_color)
            p.setFont(QFont("DejaVu Sans", max(10, int(self._thickness * 0.6))))
            p.drawText(rect.adjusted(int(track_h*0.8), 0, 0, 0), Qt.AlignLeft | Qt.AlignVCenter,
                       f"{self._label}: {self._value:.1f}")
