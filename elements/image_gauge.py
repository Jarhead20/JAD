# elements/image_gauge.py
from __future__ import annotations
import os
from typing import Optional, Tuple

from PySide6.QtCore import Qt, QRectF, QSize, QPointF
from PySide6.QtGui import QPainter, QColor, QImage, QPixmap, QTransform, QPen, QBrush
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QWidget

from elements.element import Element

def _qcolor(c):
    return c if isinstance(c, QColor) else QColor(str(c))

def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t

def _mix(c1: QColor, c2: QColor, t: float) -> QColor:
    t = max(0.0, min(1.0, t))
    return QColor(
        int(_lerp(c1.red(),   c2.red(),   t)),
        int(_lerp(c1.green(), c2.green(), t)),
        int(_lerp(c1.blue(),  c2.blue(),  t)),
        int(_lerp(c1.alpha(), c2.alpha(), t)),
    )

class ImageGauge(Element):
    """
    Draws a white image (PNG/JPG/SVG) tinted by a color that depends on a channel value 0..1.
    Default mapping: 0 -> green (no damage), 1 -> red (full damage).
    Options allow adding a mid color (yellow) and/or inverting the mapping.
    """
    def __init__(self, x, y, width, height, centered,
                 path: str,
                 channel: str,
                 *,
                 min_color = "#18c964",    # green
                 mid_color: Optional[str] = None,  # e.g. "#ffd400"
                 max_color = "#ff3b30",    # red
                 invert: bool = False,
                 mode: str = "contain",    # contain | cover | stretch
                 align: str = "center",    # left/right/top/bottom/center
                 opacity: float = 1.0,
                 rotation: float = 0.0,
                 scale: float = 1.0,       # multiplier applied to channel
                 offset: float = 0.0,      # offset added to channel
                 ema: Optional[float] = None,
                 bg_color = Qt.transparent,
                 black_point: float = 0.15,   # ≤ this luminance = fully tinted
                 white_point: float = 0.95,   # ≥ this luminance = fully transparent
                 gamma: float = 1.0,          # curve softness (1=linear)
                 parent: QWidget | None = None):
        super().__init__(x, y, width, height, centered, bg_color, parent)
        self._path = path
        self._channel = channel
        self._min_c = _qcolor(min_color)
        self._mid_c = _qcolor(mid_color) if mid_color else None
        self._max_c = _qcolor(max_color)
        self._invert = bool(invert)
        self._mode = str(mode).lower()
        self._align = str(align).lower()
        self._opacity = max(0.0, min(1.0, float(opacity)))
        self._rotation = float(rotation)
        self._scale = float(scale)
        self._offset = float(offset)
        self._ema = float(ema) if (ema is not None) else None
        self._v_s = None  # smoothed
        self._black_point = float(black_point)   # ≤ this luminance = fully tinted
        self._white_point = float(white_point)   # ≥ this luminance = fully transparent
        self._gamma       = max(0.1, float(gamma))
        

        # source
        self._is_svg = self._path.lower().endswith(".svg")
        self._svg = QSvgRenderer(self._path) if self._is_svg else None
        self._img: Optional[QImage] = None
        if not self._is_svg:
            img = QImage(self._path)
            if not img.isNull():
                self._img = img.convertToFormat(QImage.Format_ARGB32_Premultiplied)

        self.setAttribute(Qt.WA_OpaquePaintEvent, self._bg_color.alpha() > 0)

    # ---- value update from channels ----
    def update_val(self, store):
        if not self._channel:
            return
        v = store.get(self._channel)
        if v is None:
            return
        try:
            v = self._offset + self._scale * float(v)
        except Exception:
            return
        # clamp 0..1
        v = 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)

        # EMA smoothing if requested
        if self._ema and 0.0 < self._ema < 1.0:
            if self._v_s is None:
                self._v_s = v
            else:
                a = self._ema
                self._v_s = self._v_s + a * (v - self._v_s)
            v = self._v_s

        self._value = v  # keep for debugging/inspection
        self.update()

    # ---- color ramp ----
    def _color_for(self, v: float) -> QColor:
        t = 1.0 - v if self._invert else v
        if self._mid_c is None:
            return _mix(self._min_c, self._max_c, t)
        # two-segment: min -> mid -> max
        if t <= 0.5:
            return _mix(self._min_c, self._mid_c, t * 2.0)
        return _mix(self._mid_c, self._max_c, (t - 0.5) * 2.0)

    # ---- layout helpers ----
    def _target_rect(self) -> QRectF:
        r = QRectF(0, 0, self.width(), self.height()).adjusted(0, 0, -0, -0)
        return r

    def _image_rect(self, native_w: int, native_h: int, target: QRectF) -> QRectF:
        tw, th = target.width(), target.height()
        if self._mode == "stretch" or native_w == 0 or native_h == 0:
            return target

        ar_src = native_w / native_h
        ar_dst = tw / th

        if self._mode == "contain":
            if ar_src > ar_dst:  # fit width
                w = tw; h = w / ar_src
            else:                # fit height
                h = th; w = h * ar_src
        else:  # "cover"
            if ar_src > ar_dst:  # fill height
                h = th; w = h * ar_src
            else:                # fill width
                w = tw; h = w / ar_src

        # align inside target
        x = target.x()
        y = target.y()
        if "center" in self._align:
            x += (tw - w) * 0.5; y += (th - h) * 0.5
        else:
            if "right" in self._align:  x += (tw - w)
            if "bottom" in self._align: y += (th - h)
            if "left" in self._align:   x += 0
            if "top" in self._align:    y += 0
        return QRectF(x, y, w, h)

    # ---- painting ----
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)

        if self._bg_color.alpha() > 0:
            p.fillRect(self.rect(), self._bg_color)

        target = self._target_rect()

        # render source to an alpha mask image at target size
        # (we ignore source colors; we only care about shape/alpha)
        if self._is_svg and self._svg is not None and self._svg.isValid():
            # draw SVG into an ARGB image
            # determine target rect with SVG's intrinsic size if possible
            sz = self._svg.defaultSize()
            iw, ih = (sz.width() or 256), (sz.height() or 256)
        else:
            if self._img is None or self._img.isNull():
                p.end(); return
            iw, ih = self._img.width(), self._img.height()

        im_rect = self._image_rect(iw, ih, target)
        if im_rect.width() <= 0 or im_rect.height() <= 0:
            p.end(); return

        # build the mask image
        src_img = QImage(int(im_rect.width()), int(im_rect.height()),
                     QImage.Format_ARGB32_Premultiplied)
        src_img.fill(Qt.transparent)
        sp = QPainter(src_img)
        sp.setRenderHint(QPainter.Antialiasing, True)
        sp.setRenderHint(QPainter.SmoothPixmapTransform, True)

        if self._is_svg and self._svg is not None and self._svg.isValid():
            self._svg.render(sp, QRectF(0, 0, src_img.width(), src_img.height()))
        else:
            scaled = self._img.scaled(src_img.size(),
                                    Qt.KeepAspectRatioByExpanding if self._mode=="cover" else Qt.KeepAspectRatio,
                                    Qt.SmoothTransformation)
            dx = (src_img.width() - scaled.width()) // 2
            dy = (src_img.height() - scaled.height()) // 2
            sp.drawImage(dx, dy, scaled)
        sp.end()

        # Darkness mask: compute alpha from luminance
        # luminance in [0..1]; black_point/white_point map to 1..0 alpha respectively.
        bp = self._black_point
        wp = self._white_point
        gm = self._gamma

        mask_img = QImage(src_img.size(), QImage.Format_ARGB32_Premultiplied)
        mask_img.fill(Qt.transparent)

        # Per-pixel loop (fast enough for icons; fine at 25 FPS)
        for y in range(src_img.height()):
            for x in range(src_img.width()):
                c = src_img.pixelColor(x, y)
                a = c.alphaF()               # respect original transparency
                if a <= 0.0:
                    continue
                # Rec.709 luminance
                lum = (0.2126 * c.redF() + 0.7152 * c.greenF() + 0.0722 * c.blueF())
                # Map lum to mask alpha: lum ≤ bp => 1; lum ≥ wp => 0; linear in-between
                if lum <= bp:
                    t = 1.0
                elif lum >= wp:
                    t = 0.0
                else:
                    t = (wp - lum) / (wp - bp)  # 0..1
                # gamma curve + source alpha
                alpha = (t ** gm) * a
                if alpha <= 0.0:
                    continue
                mask_img.setPixelColor(x, y, QColor(255, 255, 255, int(alpha * 255)))

        # tint image: fill with color then apply source alpha as mask
        tint = self._color_for(getattr(self, "_value", 0.0))
        tinted = QImage(mask_img.size(), QImage.Format_ARGB32_Premultiplied)
        tinted.fill(tint)
        tp = QPainter(tinted)
        tp.setCompositionMode(QPainter.CompositionMode_DestinationIn)
        tp.drawImage(0, 0, mask_img)  # keep only the alpha from mask
        tp.end()

        # draw (with rotation & opacity)
        p.setOpacity(self._opacity)
        if abs(self._rotation) > 0.1:
            cx = im_rect.center().x()
            cy = im_rect.center().y()
            p.translate(QPointF(cx, cy))
            p.rotate(self._rotation)
            p.translate(QPointF(-cx, -cy))

        p.drawImage(im_rect.topLeft(), tinted)
        p.end()
