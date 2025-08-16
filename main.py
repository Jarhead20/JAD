import os, sys, json, signal, time
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout
from PySide6.QtNetwork import QUdpSocket, QHostAddress
import glob

import gpiod
from gpiod.line import Direction, Bias, Value

from controller.page import Page
from controller.page_controller import PageCycler
from controller.channels import channels

# ---- Qt / display env (Pi screen) ----
os.environ["DISPLAY"] = ":0"
os.environ["XAUTHORITY"] = "/home/jad/.Xauthority"
os.environ["QT_QPA_PLATFORM"] = "xcb"

signal.signal(signal.SIGINT, signal.SIG_DFL)

# ---- Pages to cycle through (add your files here) ----
# PAGE_PATHS = [
#     "pages/page1.json",
#     "pages/page2.json",
# ]

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
PAGES_DIR = os.path.join(BASE_DIR, "pages")


# ---- App start ----
if __name__ == "__main__":

    page_paths = glob.glob(os.path.join(PAGES_DIR, "*.json"))

    app = QApplication(sys.argv)

    # Root container that we keep; we swap Page children inside it
    root = QWidget()
    root.setCursor(Qt.BlankCursor)
    cycler = PageCycler(root, page_paths)
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
                wear = msg.get("tyre_wear", [None, None, None, None])
                # Assume [FL, FR, RL, RR]
                ch = {
                    "rpm": msg.get("rpm", 0),
                    "rpm_k": msg.get("rpm", 0)/1000.0,
                    "fuel_l": msg.get("fuel_l", 0.0),
                    "fuel_pct": (msg.get("fuel_l", 0.0) / msg.get("fuel_capacity_l", 0.0)) if msg.get("fuel_capacity_l") else 0.0,
                    "gear": msg.get("gear", 0),
                    "speed": msg.get("speed", 0.0)/3.6,
                    # Tyre wear raw values
                    "tyre_wear_fl": wear[0]/100,
                    "tyre_wear_fr": wear[1]/100,
                    "tyre_wear_rl": wear[2]/100,
                    "tyre_wear_rr": wear[3]/100,
                    "brake": msg.get("brake", 0.0),
                    "gas": msg.get("gas", 0.0),
                }
                channels.update(ch)

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
