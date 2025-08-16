from PySide6.QtCore import Qt, QSize, QRectF
from PySide6.QtGui import QPainter, QColor
from PySide6.QtWidgets import QWidget
from controller.channels import channels

class Element(QWidget):
    """
    Minimal positioned widget with a background color and helper methods.
    Requires x, y, width, height, bg_color.
    """
    def __init__(self, x: int, y: int, width: int, height: int, centered=False,
                 bg_color=Qt.black, parent: QWidget | None = None):
        super().__init__(parent)
        self._bg_color = bg_color
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self._centered = centered
        if(self._centered):
            self.setGeometry(int(x-(width/2)), int(y-(height/2)), int(width), int(height))
        else:
            self.setGeometry(int(x), int(y), int(width), int(height))

    # ----- Helpers -----
    def set_bg(self, color):
        self._bg_color = color
        self.update()

    def bg(self):
        return self._bg_color

    def set_pos(self, x: int, y: int):
        self.setGeometry(int(x), int(y), self.width(), self.height())

    def set_size(self, w: int, h: int):
        self.setGeometry(self.x(), self.y(), int(w), int(h))

    def set_geometry(self, x: int, y: int, w: int, h: int):
        self.setGeometry(int(x), int(y), int(w), int(h))

    def add(self, child: QWidget, *, x: int | None = None, y: int | None = None,
            w: int | None = None, h: int | None = None):
        """Adopt child and optionally place it."""
        child.setParent(self)
        if None not in (x, y, w, h):
            child.setGeometry(int(x), int(y), int(w), int(h))
        child.show()
        return child

    def center_xy(self) -> tuple[int, int]:
        c = self.rect().center()
        return c.x(), c.y()

    def refresh(self):
        self.update()

    def update_val(self, store):
        pass

    def paintEvent(self, _):
        p = QPainter(self)
        # Only fill if bg is a valid QColor with alpha > 0
        if isinstance(self._bg_color, QColor) and self._bg_color.isValid() and self._bg_color.alpha() > 0:
            p.fillRect(self.rect(), self._bg_color)
        p.end()
