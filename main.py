import sys
import os
import signal
from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtCore import Qt

os.environ["DISPLAY"] = ":0"
os.environ["XAUTHORITY"] = "/home/jad/.Xauthority"
os.environ["QT_QPA_PLATFORM"] = "xcb"

# Allow Ctrl+C to kill the app
signal.signal(signal.SIGINT, signal.SIG_DFL)

app = QApplication(sys.argv)

central_widget = QWidget()
layout = QVBoxLayout(central_widget)

svg_widget = QSvgWidget("/home/jad/JAD/assets/BMW.svg")
layout.addWidget(svg_widget)


central_widget.showFullScreen()

sys.exit(app.exec())
