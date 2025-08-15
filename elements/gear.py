# elements/gear.py
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
import inspect

# Reuse your TextElement (centered text box)
from elements.text import TextElement

class GearElement(TextElement):
    """
    Displays gear as text, converting raw integers:
      0 -> 'R', 1 -> 'N', 2 -> '1', 3 -> '2', ...
    Reads from a channel (default 'gear'); you can also set the text manually.
    """

    def __init__(self,
                 x: int, y: int, width: int, height: int,
                 centered: bool = True,                  # kept for compatibility with your constructor style
                 *,
                 channel: str = "gear",
                 color=Qt.white,
                 bg_color=Qt.black,
                 font_family: str = "DejaVu Sans",
                 font_px: int = 72,
                 bold: bool = True,
                 italic: bool = False,
                 align=Qt.AlignCenter,
                 wrap: bool = False,
                 parent=None):
        # Support both of your TextElement signatures:
        #  - TextElement(x,y,w,h, centered, text, ...)
        #  - TextElement(x,y,w,h, text=..., ...)   (center-is-default)
        needs_centered = "centered" in inspect.signature(TextElement.__init__).parameters

        if needs_centered:
            super().__init__(x, y, width, height, centered, "",
                             color=color, bg_color=bg_color, align=align,
                             font_family=font_family, font_px=font_px,
                             bold=bold, italic=italic, wrap=wrap, parent=parent)
        else:
            super().__init__(x, y, width, height, "",
                             color=color, bg_color=bg_color, align=align,
                             font_family=font_family, font_px=font_px,
                             bold=bold, italic=italic, wrap=wrap, parent=parent)

        self._channel = channel

    # Map raw value -> display label
    @staticmethod
    def map_gear(raw) -> str:
        try:
            v = int(raw)
        except Exception:
            # If it isn't an int, show as-is (useful for 'P' or '?')
            return str(raw) if raw is not None else "?"

        if v <= 0:
            return "R"   # user mapping request: 0 (and negatives) => Reverse
        if v == 1:
            return "N"
        
        print(v)
        return str(v - 1)

    def update_val(self, store):
        if not self._channel:
            return
        val = store.get(self._channel, None)
        label = self.map_gear(val)
        # Only update if it changed (avoids extra repaints)
        if label != getattr(self, "_last_label", None):
            self._last_label = label
            self.set_text(label)
