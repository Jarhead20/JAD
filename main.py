import sys
import signal
from PySide6.QtWidgets import QApplication, QLabel
from PySide6.QtCore import Qt

# Allow Ctrl+C to kill the app
signal.signal(signal.SIGINT, signal.SIG_DFL)

app = QApplication(sys.argv)

label = QLabel("Hello World")
label.setAlignment(Qt.AlignCenter)
label.setStyleSheet("font-size: 32px; background: black; color: lime;")

label.showFullScreen()  # Fullscreen mode

sys.exit(app.exec())
