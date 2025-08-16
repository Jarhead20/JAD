import os, sys, json, signal, time
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout
from PySide6.QtNetwork import QUdpSocket, QHostAddress

import gpiod
from gpiod.line import Direction, Bias, Value

from elements.page import Page
from controller.channels import channels

# ---- Qt / display env (Pi screen) ----
os.environ["DISPLAY"] = ":0"
os.environ["XAUTHORITY"] = "/home/jad/.Xauthority"
os.environ["QT_QPA_PLATFORM"] = "xcb"

signal.signal(signal.SIGINT, signal.SIG_DFL)

# ---- Pages to cycle through (add your files here) ----
PAGE_PATHS = [
    "pages/page1.json",
    "pages/page2.json",
]

# ---- Small page cycler that swaps the Page widget ----
class PageCycler:
    def __init__(self, container: QWidget, paths: list[str]):
        self.container = container
        self.paths = [p for p in paths if p] or []
        if not self.paths:
            raise RuntimeError("No page JSON paths configured.")
        self.layout = QVBoxLayout(container)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.current = None
        self.index = -1
        self.next_page()  # show first page

    def next_page(self):
        self.index = (self.index + 1) % len(self.paths)
        path = self.paths[self.index]
        new_page = Page(path)
        if self.current:
            self.layout.removeWidget(self.current)
            self.current.hide()
            self.current.deleteLater()
        self.layout.addWidget(new_page)
        new_page.show()
        self.current = new_page
        print(f"[ui] Showing {path}")

# ---- App start ----
if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Root container that we keep; we swap Page children inside it
    root = QWidget()
    root.setCursor(Qt.BlankCursor)
    cycler = PageCycler(root, PAGE_PATHS)
    root.showFullScreen()
    root.setAttribute(Qt.WA_StyledBackground, True)
    root.setStyleSheet("background:#000;")

    ui_tick = QTimer()
    ui_tick.setInterval(40)  # ~25 FPS
    def on_ui_tick():
        if cycler.current is not None:
            cycler.current.tick_channels(channels)
    ui_tick.timeout.connect(on_ui_tick)
    ui_tick.start()

    # ---- UDP receiver → channels ----
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
                fuel_l = msg.get("fuel_l", 0.0)
                cap = msg.get("fuel_capacity_l", 0.0)
                fuel_pct = (fuel_l / cap) if cap else 0.0
                channels.update({
                    "rpm": msg.get("rpm", 0),
                    "rpm_k": msg.get("rpm", 0) / 1000.0,
                    "fuel_l": fuel_l,
                    "fuel_pct": fuel_pct,
                    "gear": msg.get("gear", 0),
                    "max_rpm": msg.get("max_rpm", 0),
                    "fuel_capacity_l": cap,
                })
            except Exception as e:
                print("bad packet:", e)

    sock.readyRead.connect(on_ready)

    # ---- GPIO: button cycles pages; LED mirrors press ----
    LED = 17   # BCM17 (pin 11)
    BTN = 27   # BCM27 (pin 13) -> button to GND (active-low)

    req = gpiod.request_lines(
        "/dev/gpiochip0",
        consumer="PAGE_CYCLE",
        config={
            LED: gpiod.LineSettings(direction=Direction.OUTPUT,
                                    output_value=Value.INACTIVE),
            BTN: gpiod.LineSettings(direction=Direction.INPUT,
                                    bias=Bias.PULL_UP),
        }
    )

    DEBOUNCE_S = 0.05  # 50 ms debounce
    state = {"pressed": False, "t": 0.0}

    def poll_button():
        v = req.get_value(BTN)
        now = time.monotonic()
        pressed = (v == Value.INACTIVE)  # pull-up: LOW means pressed
        if pressed != state["pressed"] and (now - state["t"]) >= DEBOUNCE_S:
            state["pressed"] = pressed
            state["t"] = now
            # LED mirrors button state
            req.set_value(LED, Value.ACTIVE if pressed else Value.INACTIVE)
            if pressed:
                cycler.next_page()

    btn_timer = QTimer()
    btn_timer.setInterval(10)  # 10 ms poll
    btn_timer.timeout.connect(poll_button)
    btn_timer.start()


    # ---- Clean up on exit ----
    def cleanup():
        try:
            req.set_value(LED, Value.INACTIVE)
        except Exception:
            pass
        try:
            req.release()
        except Exception:
            pass

    app.aboutToQuit.connect(cleanup)

    sys.exit(app.exec())
