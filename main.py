import os, sys, math, signal
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout
from elements.gauge import Gauge
import socket, json


os.environ["DISPLAY"] = ":0"
os.environ["XAUTHORITY"] = "/home/jad/.Xauthority"
os.environ["QT_QPA_PLATFORM"] = "xcb"

signal.signal(signal.SIGINT, signal.SIG_DFL)

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind(("0.0.0.0", 5005))

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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = Display()
    
    w.setCursor(Qt.BlankCursor)
    w.showFullScreen()
    while True:
        data, _ = sock.recvfrom(1024)
        msg = json.loads(data.decode())
        rpm = msg["rpm"]
        w.gauge.set_value(rpm/8000)
        sys.exit(app.exec())
