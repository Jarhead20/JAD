from controller.element_list import ElementList
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout
from PySide6.QtNetwork import QUdpSocket, QHostAddress
from PySide6.QtGui import QPainter, QPen, QFont, QColor
from elements.gauge import RoundGauge, LinearGauge
from controller.channels import channels

class Page(QWidget):
    def __init__(self, layout_path: str):
        super().__init__()
        self._elist = ElementList()
        meta = self._elist.parse(layout_path, parent=self)
        bg = (meta or {}).get("bg_color", None)
        if bg is not None:
            self.setStyleSheet(f"background: {self._css_color(bg)};")
        

    def tick_channels(self, store):
        for e in self._elist.get_elements():
            upd = getattr(e, "update_val", None)
            if upd:
                upd(store)
            vis = getattr(e, "evaluate_visibility", None)
            if vis: 
                vis(store)

    def elements(self):
        return self._elist.get_elements()
    
    def _css_color(self, c):
        if isinstance(c, str): return c
        if isinstance(c, (list, tuple)):
            if len(c) == 3: r,g,b = c; return f"rgb({r},{g},{b})"
            if len(c) == 4: r,g,b,a = c; return f"rgba({r},{g},{b},{a})"
        if isinstance(c, QColor):
            return f"rgba({c.red()},{c.green()},{c.blue()},{c.alpha()})"
        return "black"
