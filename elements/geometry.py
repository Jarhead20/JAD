# elements/geometry.py
from __future__ import annotations
import math
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui  import QPainter, QPen, QBrush, QColor
from PySide6.QtWidgets import QWidget
from elements.element import Element

def _qcolor(c):
    if isinstance(c, QColor): return c
    if isinstance(c, (tuple, list)):
        return QColor(*c) if len(c) in (3,4) else QColor("transparent")
    q = QColor(str(c))
    return q if q.isValid() else QColor("transparent")

class GeometryElement(Element):
    """
    Basic geometry renderer.
      shape: "rect" | "round_rect" | "circle" | "ellipse" | "line" | "ring" | "arc"
      fill_color, stroke_color, stroke_width
      corner_radius (for round_rect)
      rotation (deg), opacity (0..1)

    Optional channel-driven span (for ring/arc):
      channel + scale/offset + max_val → ratio 0..1 → span = span_angle * ratio
      start_angle, span_angle (deg) — negative span draws clockwise (Qt style)
    """

    def __init__(self,
                 x:int, y:int, width:int, height:int,
                 centered:bool=False,
                 *,
                 shape:str="rect",
                 fill_color=Qt.transparent,
                 stroke_color=Qt.white,
                 stroke_width:float=2.0,
                 corner_radius:float=12.0,
                 # arc/ring parameters
                 start_angle:float=0.0,
                 span_angle:float=360.0,
                 ring_width:float=None,        # if set, overrides stroke_width for ring/arc thickness
                 # line parameters
                 line_dir:str="h",             # "h","v","diag1","diag2"
                 # transforms
                 rotation:float=0.0,
                 opacity:float=1.0,
                 # channels (optional)
                 channel:str|None=None,
                 scale:float=1.0,
                 offset:float=0.0,
                 max_val:float=1.0,
                 bg_color=Qt.transparent,
                 parent:QWidget|None=None):
        # center → top-left if requested
        if centered:
            x = int(x - width/2)
            y = int(y - height/2)

        super().__init__(x=x, y=y, width=int(width), height=int(height),
                         centered=False, bg_color=bg_color, parent=parent)

        self._shape = shape.lower()
        self._fill  = _qcolor(fill_color)
        self._stroke= _qcolor(stroke_color)
        self._sw    = float(stroke_width)
        self._cr    = float(corner_radius)
        self._start = float(start_angle)
        self._span  = float(span_angle)
        self._ringw = float(ring_width) if ring_width is not None else None
        self._line_dir = line_dir.lower()
        self._rot   = float(rotation)
        self._alpha = max(0.0, min(1.0, float(opacity)))

        # channel mapping
        self._channel = channel
        self._scale   = float(scale)
        self._offset  = float(offset)
        self._max     = max(1e-9, float(max_val))

    # optional: update from channels (for ring/arc span or anything else later)
    def update_val(self, store):
        # nothing to update unless we’re using span via channel
        if not self._channel:
            return
        v = store.get(self._channel)
        if v is None:
            return
        try:
            v = float(v)
        except Exception:
            return
        ratio = (self._offset + self._scale * v) / self._max
        ratio = max(0.0, min(1.0, ratio))
        # only affects ring/arc drawing (others ignore)
        self._ratio = ratio  # cached; defaults handled in paint
        self.update()

    def paintEvent(self, e):
        # element background (supports transparent)
        super().paintEvent(e)

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setOpacity(self._alpha)

        # rotation about widget center if non-zero
        if self._rot:
            c = self.rect().center()
            p.translate(c)
            p.rotate(self._rot)
            p.translate(-c)

        r = QRectF(self.rect())

        # pens/brushes
        pen = QPen(self._stroke, self._sw)
        brush = QBrush(self._fill)

        shape = self._shape
        if shape == "rect":
            p.setPen(pen); p.setBrush(brush)
            p.drawRect(r)

        elif shape == "round_rect":
            p.setPen(pen); p.setBrush(brush)
            p.drawRoundedRect(r, self._cr, self._cr)

        elif shape == "ellipse":
            p.setPen(pen); p.setBrush(brush)
            p.drawEllipse(r)

        elif shape == "circle":
            side = min(r.width(), r.height())
            rc = QRectF(r.center().x() - side/2, r.center().y() - side/2, side, side)
            p.setPen(pen); p.setBrush(brush)
            p.drawEllipse(rc)

        elif shape == "line":
            p.setPen(pen)
            cx, cy = r.center().x(), r.center().y()
            if self._line_dir == "v":
                p.drawLine(int(cx), int(r.top()), int(cx), int(r.bottom()))
            elif self._line_dir == "diag1":  # top-left → bottom-right
                p.drawLine(int(r.left()), int(r.top()), int(r.right()), int(r.bottom()))
            elif self._line_dir == "diag2":  # bottom-left → top-right
                p.drawLine(int(r.left()), int(r.bottom()), int(r.right()), int(r.top()))
            else:  # "h"
                p.drawLine(int(r.left()), int(cy), int(r.right()), int(cy))

        elif shape in ("ring", "arc"):
            # Qt drawArc uses 1/16 deg; negative span = clockwise
            start_deg = self._start
            span_deg  = self._span
            # channel-driven ratio if available
            ratio = getattr(self, "_ratio", None)
            if ratio is not None:
                span_deg = self._span * ratio

            side = min(r.width(), r.height())
            pad  = (self._ringw or self._sw) / 2.0 + 0.5
            rr = QRectF(r.center().x() - side/2 + pad,
                        r.center().y() - side/2 + pad,
                        side - 2*pad, side - 2*pad)

            ring_pen = QPen(self._stroke if shape == "arc" else self._fill,
                            self._ringw or self._sw, cap=Qt.RoundCap)
            # PySide6: set cap separately for compatibility
            ring_pen.setCapStyle(Qt.RoundCap)
            p.setPen(ring_pen)
            p.setBrush(Qt.NoBrush)
            p.drawArc(rr, int(start_deg*16), int(span_deg*16))

        p.end()
