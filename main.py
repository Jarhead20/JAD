import os, sys, math, signal
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout
from PySide6.QtNetwork import QUdpSocket, QHostAddress
from elements.gauge import Gauge
import socket, json


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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = Display()
    w.setCursor(Qt.BlankCursor)
    w.showFullScreen()

    sock = QUdpSocket()
    PORT = 5005

    if not sock.bind(QHostAddress.Any, PORT):
        print(f"Failed to bind UDP {PORT}")
        sys.exit(1)

    def on_ready():
        while sock.hasPendingDatagrams():
            d = sock.receiveDatagram()
            payload = bytes(d.data())
            try:
                msg = json.loads(payload.decode("utf-8"))
                rpm = msg.get("rpm", 0)
                w.gauge.set_value(max(0.0, min(1.0, rpm / 8000.0)))
            except Exception as e:
                print("bad packet:", e)

    sock.readyRead.connect(on_ready)

    tick = QTimer()
    tick.start(100)
    tick.timeout.connect(lambda: None)

    sys.exit(app.exec())
    
    

        
