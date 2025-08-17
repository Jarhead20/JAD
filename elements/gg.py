# elements/gg.py
from __future__ import annotations
from collections import deque
from typing import Optional

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QPainter, QPen, QBrush, QColor, QFont
from PySide6.QtWidgets import QWidget

from elements.element import Element


def _qcolor(c):
    if isinstance(c, QColor): return c
    return QColor(str(c))


class GGDiagram(Element):
    """
    Longitudinal vs Lateral G diagram with trail and rings.
      - channels: lat_ch, long_ch in units of 'g' (e.g. 0..±2.5)
      - radius_g: max |g| shown at edge (both axes share same scale)
      - trail_len: number of historical samples to draw
      - ema: optional smoothing factor 0..1 (per axis) (e.g., 0.2)
      - invert_lat / invert_long: flip sign if needed
    """
    def __init__(self, x, y, width, height, centered=False,
                 bg_color=Qt.transparent,
                 *,
                 lat_ch: str = "acc_lat_g",
                 long_ch: str = "acc_long_g",
                 radius_g: float = 2.0,
                 padding: int = 10,
                 rings: int = 4,
                 show_square: bool = False,
                 show_labels: bool = True,
                 grid_color = "#2b2f36",
                 axis_color = "#5a616a",
                 trail_color = "#55ccff",
                 point_color = "#ffffff",
                 point_radius_px: int = 5,
                 trail_len: int = 200,
                 ema: Optional[float] = None,
                 invert_lat: bool = False,
                 invert_long: bool = False,
                 parent: QWidget | None = None):
        super().__init__(x, y, width, height, centered, bg_color, parent)

        self._lat_ch = lat_ch
        self._long_ch = long_ch
        self._radius_g = max(0.1, float(radius_g))
        self._padding = int(padding)
        self._rings = max(0, int(rings))
        self._show_square = bool(show_square)
        self._show_labels = bool(show_labels)

        self._grid_color = _qcolor(grid_color)
        self._axis_color = _qcolor(axis_color)
        self._trail_color = _qcolor(trail_color)
        self._point_color = _qcolor(point_color)
        self._point_r = int(point_radius_px)

        self._trail = deque(maxlen=int(trail_len))
        self._ema = float(ema) if (ema is not None) else None
        self._lat_s = None  # smoothed lat
        self._lon_s = None  # smoothed long
        self._invert_lat = bool(invert_lat)
        self._invert_long = bool(invert_long)

        self._trail.append((0.0, 0.0))

        # render perf hint (opaque only if bg has alpha>0)
        self.setAttribute(Qt.WA_OpaquePaintEvent, self._bg_color.alpha() > 0)

    # --- mapping helpers ---
    def _map(self, lon_g: float, lat_g: float):
        """Map g-values to widget coords (pixels). +lon = right, +lat = up."""
        r = self._radius_g
        rect = self.rect().adjusted(self._padding, self._padding, -self._padding, -self._padding)
        cx, cy = rect.center().x(), rect.center().y()
        radius_px = min(rect.width(), rect.height()) * 0.5
        # clamp to circle/square bounds visually
        x = cx + (max(-r, min(r, lon_g)) / r) * radius_px
        y = cy - (max(-r, min(r, lat_g)) / r) * radius_px
        return QPointF(x, y), rect, radius_px

    # --- Element API: consume channels each tick ---
    def update_val(self, store):
        lat = store.get(self._lat_ch)
        lon = store.get(self._long_ch)
        if lat is None or lon is None:
            return

        try:
            lat = float(lat)
            lon = float(lon)
        except Exception:
            return

        if self._invert_lat:  lat = -lat
        if self._invert_long: lon = -lon

        if self._ema and 0.0 < self._ema < 1.0:
            if self._lat_s is None:
                self._lat_s, self._lon_s = lat, lon
            else:
                a = self._ema
                self._lat_s = self._lat_s + a * (lat - self._lat_s)
                self._lon_s = self._lon_s + a * (lon - self._lon_s)
            lat, lon = self._lat_s, self._lon_s

        # append raw g sample; paint maps it to pixels
        self._trail.append((lon, lat))
        self.update()

    # --- painting ---
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)

        # optional background
        if self._bg_color.alpha() > 0:
            p.fillRect(self.rect(), self._bg_color)

        # base geometry
        _, rect, radius_px = self._map(0, 0)
        cx, cy = rect.center().x(), rect.center().y()

        # grid: rings
        if self._rings > 0:
            pen = QPen(self._grid_color, 1)
            pen.setCosmetic(True)
            p.setPen(pen)
            for i in range(1, self._rings + 1):
                r = (radius_px * i) / self._rings
                p.drawEllipse(QPointF(cx, cy), r, r)

        # optional bounding square
        if self._show_square:
            pen = QPen(self._grid_color, 1); pen.setCosmetic(True)
            p.setPen(pen)
            side = radius_px * 2
            p.drawRect(QRectF(cx - radius_px, cy - radius_px, side, side))

        # axes (crosshair)
        pen = QPen(self._axis_color, 1.5); pen.setCosmetic(True)
        p.setPen(pen)
        p.drawLine(int(rect.left()), int(cy), int(rect.right()), int(cy))  # longitudinal axis
        p.drawLine(int(cx), int(rect.top()), int(cx), int(rect.bottom()))  # lateral axis

        # labels
        if self._show_labels:
            p.setPen(self._grid_color)
            p.setFont(QFont("DejaVu Sans", 10))
            rg = self._radius_g
            p.drawText(int(cx + radius_px - 24), int(cy - 6), f"{rg:.1f}g")
            p.drawText(int(cx - radius_px + 6), int(cy - 6), f"{-rg:.1f}g")
            p.drawText(int(cx + 6), int(cy - radius_px + 14), f"{rg:.1f}g")
            p.drawText(int(cx + 6), int(cy + radius_px - 4), f"{-rg:.1f}g")

        # trail
        if len(self._trail) >= 2:
            n = len(self._trail)
            for i in range(1, n):
                lon0, lat0 = self._trail[i - 1]
                lon1, lat1 = self._trail[i]
                p0, _, _ = self._map(lon0, lat0)
                p1, _, _ = self._map(lon1, lat1)
                # fade older segments
                t = i / n
                col = QColor(self._trail_color)
                col.setAlpha(int(40 + 180 * t))  # 40..220
                pen = QPen(col, 2)
                p.setPen(pen)
                p.drawLine(p0, p1)

        # current point
        if self._trail:
            lon, lat = self._trail[-1]
            pt, _, _ = self._map(lon, lat)
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(self._point_color))
            r = self._point_r
            p.drawEllipse(QRectF(pt.x() - r, pt.y() - r, 2 * r, 2 * r))

        p.end()
