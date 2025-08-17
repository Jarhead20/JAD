# elements/image.py
from __future__ import annotations
import os
from PySide6.QtCore import Qt, QRectF, QSizeF
from PySide6.QtGui import QPainter, QPixmap, QColor, QTransform
from PySide6.QtWidgets import QWidget
import os

# SVG renderer (install pyside6-addons if you don't have QtSvg)
from PySide6.QtSvg import QSvgRenderer

# Reuse your Element base
from elements.element import Element

from pathlib import Path
APP_ROOT = Path("/home/jad/JAD")

_ALIGN_MAP = {
    "left": Qt.AlignLeft | Qt.AlignVCenter,
    "right": Qt.AlignRight | Qt.AlignVCenter,
    "top": Qt.AlignTop | Qt.AlignHCenter,
    "bottom": Qt.AlignBottom | Qt.AlignHCenter,
    "center": Qt.AlignCenter,
    "center_left": Qt.AlignLeft | Qt.AlignVCenter,
    "center_right": Qt.AlignRight | Qt.AlignVCenter,
    "center_top": Qt.AlignHCenter | Qt.AlignTop,
    "center_bottom": Qt.AlignHCenter | Qt.AlignBottom,
}

def _qcolor(c):
    if isinstance(c, QColor): return c
    if isinstance(c, (tuple, list)): return QColor(*c)
    return QColor(str(c))

class ImageElement(Element):
    """
    Image widget supporting SVG/PNG/JPG.
    Geometry uses your new `centered=` style:
      - pass x,y, width, height, centered=True/False
    Options:
      - mode: "contain" | "cover" | "stretch" (default: contain)
      - align: one of _ALIGN_MAP keys (default: "center")
      - opacity: 0..1
      - rotation: degrees (clockwise)
    """

    def __init__(self,
                 x: int, y: int, width: int, height: int,
                 centered: bool = False,
                 *,
                 path: str = "",
                 mode: str = "contain",
                 align: str = "center",
                 opacity: float = 1.0,
                 rotation: float = 0.0,
                 bg_color=Qt.transparent,
                 parent: QWidget | None = None):
        # Convert center coords to top-left if needed
        if centered:
            tlx = int(x - width/2)
            tly = int(y - height/2)
        else:
            tlx, tly = int(x), int(y)

        super().__init__(
            x=tlx,
            y=tly,
            width=int(width),
            height=int(height),
            bg_color=bg_color,
            parent=parent,
        )

        p = Path(path)
        self._path = str(p if p.is_absolute() else (APP_ROOT / p).resolve())

        self._mode = mode.lower()
        self._align = _ALIGN_MAP.get(align.lower(), Qt.AlignCenter)
        self._opacity = max(0.0, min(1.0, float(opacity)))
        self._rotation = float(rotation)

        # Image holders
        self._pixmap: QPixmap | None = None
        self._svg: QSvgRenderer | None = None
        self._intrinsic_size = QSizeF(0, 0)

        if path:
            self.set_image(path)

    # ----- public setters -----
    def set_image(self, path: str):
        self._path = path
        self._pixmap = None
        self._svg = None
        self._intrinsic_size = QSizeF(0, 0)

        ext = os.path.splitext(path)[1].lower()
        if ext in (".svg", ".svgz"):
            renderer = QSvgRenderer(path)
            if not renderer.isValid():
                print(f"[ImageElement] Invalid SVG: {path}")
            else:
                self._svg = renderer
                sz = renderer.defaultSize()
                self._intrinsic_size = QSizeF(sz.width(), sz.height())
        else:
            pm = QPixmap(path)
            if pm.isNull():
                print(f"[ImageElement] Could not load image: {path}")
            else:
                self._pixmap = pm
                self._intrinsic_size = QSizeF(pm.width(), pm.height())
        self.update()

    def set_mode(self, mode: str):
        self._mode = str(mode).lower()
        self.update()

    def set_align(self, align: str):
        self._align = _ALIGN_MAP.get(align.lower(), Qt.AlignCenter)
        self.update()

    def set_opacity(self, opacity: float):
        self._opacity = max(0.0, min(1.0, float(opacity)))
        self.update()

    def set_rotation(self, deg: float):
        self._rotation = float(deg)
        self.update()

    # ----- painting -----
    def paintEvent(self, e):
        # Let Element draw the background (supports transparent)
        super().paintEvent(e)

        if self._intrinsic_size.width() <= 0 or self._intrinsic_size.height() <= 0:
            return  # nothing to draw

        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform, True)
        p.setOpacity(self._opacity)

        target = QRectF(self.rect())

        # Compute destination rect based on mode + align
        iw, ih = self._intrinsic_size.width(), self._intrinsic_size.height()
        tw, th = target.width(), target.height()

        if self._mode == "stretch":
            dest = target
        else:
            # contain/cover preserve aspect ratio
            sx = tw / iw
            sy = th / ih
            scale = min(sx, sy) if self._mode == "contain" else max(sx, sy)
            dw, dh = iw * scale, ih * scale

            # alignment inside target
            if self._align & Qt.AlignLeft:
                dx = target.left()
            elif self._align & Qt.AlignRight:
                dx = target.right() - dw
            else:  # center horizontally
                dx = target.left() + (tw - dw) / 2.0

            if self._align & Qt.AlignTop:
                dy = target.top()
            elif self._align & Qt.AlignBottom:
                dy = target.bottom() - dh
            else:  # center vertically
                dy = target.top() + (th - dh) / 2.0

            dest = QRectF(dx, dy, dw, dh)

            if self._mode == "cover":
                # clip to target for the overflow
                p.save()
                p.setClipRect(target)

        # rotation around widget center (optional)
        if self._rotation:
            p.save()
            c = target.center()
            tr = QTransform()
            tr.translate(c.x(), c.y())
            tr.rotate(self._rotation)
            tr.translate(-c.x(), -c.y())
            p.setTransform(tr, combine=True)

        # draw
        if self._svg is not None:
            self._svg.render(p, dest)
        elif self._pixmap is not None:
            p.drawPixmap(dest, self._pixmap, QRectF(0, 0, iw, ih))

        # restore rotation clip states
        if self._rotation:
            p.restore()
        if self._mode == "cover":
            p.restore()

        p.end()
