from elements.element_list import ElementList
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout
from PySide6.QtNetwork import QUdpSocket, QHostAddress
from PySide6.QtGui import QPainter, QPen, QFont
from elements.gauge import RoundGauge, LinearGauge
from controller.channels import channels

class Page(QWidget):
    def __init__(self, layout_path: str):
        super().__init__()
        self.setWindowTitle("JAD")
        self.setStyleSheet("background:black;")
        self._elist = ElementList()
        self._elist.parse(layout_path, parent=self)

        self._poll = QTimer(self)
        self._poll.setInterval(40)          # ~25 FPS
        self._poll.timeout.connect(self._tick)
        self._poll.start()

    def _tick(self):
        for e in self._elist.get_elements():
            upd = getattr(e, "update_val", None)
            if upd: upd(channels)

    def elements(self):
        return self._elist.get_elements()
