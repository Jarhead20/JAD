import os, sys, math, signal
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout
from elements.gauge import Gauge

os.environ["DISPLAY"] = ":0"
os.environ["XAUTHORITY"] = "/home/jad/.Xauthority"
os.environ["QT_QPA_PLATFORM"] = "xcb"

signal.signal(signal.SIGINT, signal.SIG_DFL)



class Display(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("JAD")

        self.gauge = Gauge(
            label="RPM x1000",
            font_size=20
        )

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.gauge, 1)

        self.t = QTimer(self)
        self.t.timeout.connect(self.animate)
        self.t.start(40)
        self.phase = 0.0

    def animate(self):
        self.phase += 0.04
        v = (math.sin(self.phase) + 1.0) / 2.0
        self.gauge.set_value(v)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = Display()
    w.setCursor(Qt.BlankCursor)
    w.showFullScreen()
    sys.exit(app.exec())
