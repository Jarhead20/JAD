from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QPainter, QFont, QColor
from PySide6.QtWidgets import QWidget
from elements.element import Element

class TextElement(Element):
    def __init__(self,
                 x: int, y: int, width: int, height: int, centered: bool,
                 text: str = "",
                 color=Qt.white,
                 bg_color=Qt.black,
                 align=Qt.AlignCenter,
                 font_family: str = "DejaVu Sans",
                 font_px: int = 24,
                 bold: bool = False,
                 italic: bool = False,
                 wrap: bool = True,
                 padding: int | tuple[int,int,int,int] = 0,
                 autoscale: bool = False,
                 min_px: int = 8,
                 max_px: int | None = None,
                 parent: QWidget | None = None,
                 **kwargs):
        super().__init__(x, y, width, height, centered, bg_color, parent)
        self._text = text
        self._color = self._to_qcolor(color)
        self._align = align
        self._font_family = font_family
        self._font_px = int(font_px)
        self._bold = bool(bold)
        self._italic = bool(italic)
        self._wrap = bool(wrap)
        self._autoscale = bool(autoscale)
        self._min_px = int(min_px)
        self._max_px = int(max_px) if max_px is not None else max(self._font_px, self._min_px)
        self._padding = self._normalize_padding(padding)

        self._channel = kwargs.get("channel", None)
        self._fmt     = kwargs.get("fmt", "{value}")   # e.g. "{value:.0f} rpm"
        self._prefix  = kwargs.get("prefix", "")
        self._suffix  = kwargs.get("suffix", "")

    # ---------- helpers / setters ----------
    def set_text(self, text: str):
        if text != self._text:
            self._text = text
            self.update()

    def append_text(self, extra: str):
        self.set_text(self._text + extra)

    def set_color(self, color):
        c = self._to_qcolor(color)
        if c != self._color:
            self._color = c
            self.update()

    def set_align(self, align_flags: Qt.AlignmentFlag):
        self._align = align_flags
        self.update()

    def set_font(self, family: str | None = None, px: int | None = None,
                 *, bold: bool | None = None, italic: bool | None = None):
        if family is not None: self._font_family = family
        if px is not None:     self._font_px = int(px)
        if bold is not None:   self._bold = bool(bold)
        if italic is not None: self._italic = bool(italic)
        self.update()

    def set_padding(self, padding: int | tuple[int,int,int,int]):
        self._padding = self._normalize_padding(padding)
        self.update()

    def set_wrap(self, wrap: bool):
        self._wrap = bool(wrap)
        self.update()

    def set_autoscale(self, enabled: bool, min_px: int | None = None, max_px: int | None = None):
        self._autoscale = bool(enabled)
        if min_px is not None: self._min_px = int(min_px)
        if max_px is not None: self._max_px = int(max_px)
        self.update()

    # ---------- painting ----------
    def paintEvent(self, e):
        # Let Element paint the background
        super().paintEvent(e)

        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)

        # Compute padded drawing rect
        l,t,r,b = self._padding
        rect = self.rect().adjusted(l, t, -r, -b)

        # Choose/fit font
        if self._autoscale:
            f = self._fit_font(p, rect, self._font_family, self._text, self._max_px, self._min_px, self._wrap)
        else:
            f = QFont(self._font_family, self._font_px)

        f.setBold(self._bold)
        f.setItalic(self._italic)
        p.setFont(f)
        p.setPen(self._color)

        flags = self._align
        if self._wrap:
            flags |= Qt.TextWordWrap

        p.drawText(QRectF(rect), flags, self._text)
        p.end()

    def update_val(self, store):
        if not self._channel:
            return
        v = store.get(self._channel)
        if v is None:
            return
        try:
            s = self._fmt.format(value=v)
        except Exception:
            s = str(v)
        if self._prefix or self._suffix:
            s = f"{self._prefix}{s}{self._suffix}"
        self.set_text(s)

    # ---------- internals ----------
    def _fit_font(self, painter: QPainter, rect: QRectF, family: str, text: str,
                  max_px: int, min_px: int, wrap: bool) -> QFont:
        flags = self._align | (Qt.TextWordWrap if wrap else Qt.TextDontClip)
        f = QFont(family)
        for size in range(max_px, min_px - 1, -1):
            f.setPixelSize(size)
            painter.setFont(f)
            br = painter.fontMetrics().boundingRect(rect.toRect(), flags, text)
            if br.width() <= rect.width() and br.height() <= rect.height():
                return f
        f.setPixelSize(min_px)
        return f

    def _normalize_padding(self, p):
        if isinstance(p, int):
            return (p, p, p, p)
        if isinstance(p, tuple) and len(p) == 4:
            return tuple(int(x) for x in p)
        return (0,0,0,0)

    def _to_qcolor(self, c) -> QColor:
        if isinstance(c, QColor): return c
        if isinstance(c, tuple) and len(c) in (3,4):
            return QColor(*c)
        return QColor(c)  # Qt.GlobalColor or CSS string
