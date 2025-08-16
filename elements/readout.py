# elements/readout.py
from __future__ import annotations
import math
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QFont, QColor
from PySide6.QtWidgets import QWidget
from elements.element import Element  # your base

_ALIGN_MAP = {
    "left":   Qt.AlignLeft   | Qt.AlignVCenter,
    "right":  Qt.AlignRight  | Qt.AlignVCenter,
    "top":    Qt.AlignTop    | Qt.AlignHCenter,
    "bottom": Qt.AlignBottom | Qt.AlignHCenter,
    "center": Qt.AlignCenter,
}

def _qcolor(c):
    if isinstance(c, QColor): return c
    if isinstance(c, (tuple, list)): return QColor(*c)
    return QColor(str(c))

class Readout(Element):
    """
    Two-line numeric readout:
      [ LABEL ]          (top)
      [ VALUE (channel) ](bottom, larger)
    - Independent colors/fonts for label/value
    - Optional scale/offset and format string
    - Geometry supports centered=True|False like your other elements
    """
    def __init__(self,
                 x: int, y: int, width: int, height: int,
                 centered: bool = False,
                 *,
                 label: str = "LABEL",
                 channel: str | None = None,
                 fmt: str = "{value}",
                 units: str = "",
                 scale: float = 1.0,
                 offset: float = 0.0,
                 # colors
                 label_color=Qt.gray,
                 value_color=Qt.white,
                 bg_color=Qt.transparent,
                 # fonts
                 label_font_family: str = "DejaVu Sans",
                 value_font_family: str = "DejaVu Sans",
                 label_font_px: int = 18,
                 value_font_px: int = 42,
                 label_bold: bool = True,
                 value_bold: bool = True,
                 label_italic: bool = False,
                 value_italic: bool = False,
                 # layout
                 align: str = "center",
                 padding: int = 8,
                 spacing: int = 4,
                 label_ratio: float = 0.40,   # portion of height for label
                 parent: QWidget | None = None):
        # convert center → top-left, then call base with keywords (safe order)
        if centered:
            x, y = int(x - width/2), int(y - height/2)

        super().__init__(x=x, y=y, width=int(width), height=int(height),
                         bg_color=bg_color, parent=parent)

        # model
        self._label = str(label)
        self._channel = channel
        self._fmt = str(fmt)
        self._units = str(units)
        self._scale = float(scale)
        self._offset = float(offset)

        # style
        self._label_color = _qcolor(label_color)
        self._value_color = _qcolor(value_color)
        self._label_font_family = label_font_family
        self._value_font_family = value_font_family
        self._label_font_px = int(label_font_px)
        self._value_font_px = int(value_font_px)
        self._label_bold = bool(label_bold)
        self._value_bold = bool(value_bold)
        self._label_italic = bool(label_italic)
        self._value_italic = bool(value_italic)
        self._align = _ALIGN_MAP.get(align.lower(), Qt.AlignCenter)
        self._padding = int(padding)
        self._spacing = int(spacing)
        self._label_ratio = max(0.05, min(0.95, float(label_ratio)))

        # cached text
        self._value_text = ""
        self._last_value_text = None

    # -------- public setters (optional) --------
    def set_label(self, text: str):
        if text != self._label:
            self._label = text
            self.update()

    def set_channel(self, name: str | None):
        self._channel = name

    def set_format(self, fmt: str, units: str = None):
        self._fmt = fmt
        if units is not None:
            self._units = units
        self._last_value_text = None  # force redraw

    def set_colors(self, *, label=None, value=None):
        if label is not None: self._label_color = _qcolor(label)
        if value is not None: self._value_color = _qcolor(value)
        self.update()

    def set_scale_offset(self, scale: float | None = None, offset: float | None = None):
        if scale is not None: self._scale = float(scale)
        if offset is not None: self._offset = float(offset)

    # -------- channel update hook --------
    def update_val(self, store):
        if not self._channel:
            return
        raw = store.get(self._channel)
        if raw is None:
            return
        try:
            v = float(raw)
        except Exception:
            # non-numeric; show as text
            new_text = str(raw)
        else:
            v = self._offset + self._scale * v
            try:
                new_text = self._fmt.format(value=v)
            except Exception:
                new_text = f"{v}"
        if self._units:
            new_text = f"{new_text}{self._units}"

        if new_text != self._last_value_text:
            self._last_value_text = new_text
            self._value_text = new_text
            self.update()

    # -------- painting --------
    def paintEvent(self, e):
        # base fills background (supports transparent)
        super().paintEvent(e)

        p = QPainter(self)
        p.setRenderHint(QPainter.TextAntialiasing, True)

        # layout rects
        r = self.rect().adjusted(self._padding, self._padding,
                                 -self._padding, -self._padding)
        if r.width() <= 0 or r.height() <= 0:
            p.end(); return

        label_h = int(r.height() * self._label_ratio)
        value_h = max(0, r.height() - label_h - self._spacing)

        label_rect = QRectF(r.left(), r.top(), r.width(), label_h)
        value_rect = QRectF(r.left(), r.top() + label_h + self._spacing, r.width(), value_h)

        # label
        lf = QFont(self._label_font_family, self._label_font_px)
        lf.setBold(self._label_bold); lf.setItalic(self._label_italic)
        p.setFont(lf)
        p.setPen(self._label_color)
        p.drawText(label_rect, self._align | Qt.TextWordWrap, self._label)

        # value
        vf = QFont(self._value_font_family, self._value_font_px)
        vf.setBold(self._value_bold); vf.setItalic(self._value_italic)
        p.setFont(vf)
        p.setPen(self._value_color)
        txt = self._value_text if self._value_text else "--"
        p.drawText(value_rect, self._align | Qt.TextWordWrap, txt)

        p.end()
