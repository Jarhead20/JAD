import os, sys, math, signal
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout
from PySide6.QtNetwork import QUdpSocket, QHostAddress
from elements.gauge import RoundGauge, LinearGauge
from elements.page import Page
from elements.element_list import ElementList
import socket, json
import gpiod, time
from controller.channels import channels


os.environ["DISPLAY"] = ":0"
os.environ["XAUTHORITY"] = "/home/jad/.Xauthority"
os.environ["QT_QPA_PLATFORM"] = "xcb"

signal.signal(signal.SIGINT, signal.SIG_DFL)



if __name__ == "__main__":
    app = QApplication(sys.argv)


    w = Page("pages/page1.json")
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
                # e.g. {"rpm": 6421, "fuel_l": 31.5, "gear": 3, "max_rpm": 9000}
                # derive channels you want to expose:
                fuel_l = msg.get("fuel_l", 0)
                fuel_pct = fuel_l/msg.get("fuel_capacity_l", 0.0)
                ch = {"rpm": msg.get("rpm", 0),
                    "rpm_k": msg.get("rpm", 0)/1000.0,
                    "fuel_l": fuel_l,
                    "fuel_pct": fuel_pct,
                    "gear": msg.get("gear", 0)}
                channels.update(ch)
            except Exception as e:
                print("bad packet:", e)

    sock.readyRead.connect(on_ready)

    tick = QTimer()
    tick.start(100)
    tick.timeout.connect(lambda: None)

    sys.exit(app.exec())
    
    

        
