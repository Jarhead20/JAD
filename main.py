import os, sys, json, signal, time
from PySide6.QtCore import Qt, QTimer, QFileSystemWatcher, QTimer
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout
from PySide6.QtNetwork import QUdpSocket, QHostAddress
import glob

import gpiod
from gpiod.line import Direction, Bias, Value
import re

from controller.page import Page
from controller.page_controller import PageCycler
from controller.channels import channels
from hardware.shift_lights import ShiftLights

# ---- Qt / display env (Pi screen) ----
os.environ["DISPLAY"] = ":0"
os.environ["XAUTHORITY"] = "/home/jad/.Xauthority"
os.environ["QT_QPA_PLATFORM"] = "xcb"

signal.signal(signal.SIGINT, signal.SIG_DFL)

PINS = [6, 5, 22, 27, 17, 16, 12, 25, 24, 23]  # BCM offsets, pick your 10

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
PAGES_DIR = os.path.join(BASE_DIR, "pages")

def _natural_key(path: str):
    name = os.path.basename(path).lower()
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", name)]

def discover_pages():
    files = glob.glob(os.path.join(PAGES_DIR, "*.json"))
    files.sort(key=_natural_key)
    return files



# ---- App start ----
if __name__ == "__main__":
    page_paths = discover_pages()

    app = QApplication(sys.argv)

    # Root container that we keep; we swap Page children inside it
    root = QWidget()
    root.setObjectName("root")
    root.setCursor(Qt.BlankCursor)
    
    root.setAttribute(Qt.WA_StyledBackground, True)  # only root paints bg
    root.setStyleSheet("#root { background: #000; }")  # scoped to root only
    root.setFixedSize(1024, 600)
    root.showFullScreen()

    cycler = PageCycler(root=root, paths=page_paths)

    sl = ShiftLights(PINS, mode="bar",active_high=True, flash_at=0.95, flash_hz=8.0)

    
    

    watcher = QFileSystemWatcher()
    def _reset_watches():
        # clear old
        for f in watcher.files(): watcher.removePath(f)
        for d in watcher.directories(): watcher.removePath(d)
        # (re)add current dir + files
        watcher.addPath(PAGES_DIR)
        if page_paths:
            watcher.addPaths(page_paths)

    _reset_watches()

    # Debounced reloads (avoid reloading on half-written files)
    _pending = {}

    def _reload_path(path):
        # Re-add file to watch (Qt may drop it if editor rewrites the file)
        if os.path.exists(path) and path not in watcher.files():
            watcher.addPath(path)
        try:
            # If the changed file is the current page, reload it
            if path == cycler.current_path():
                cycler.reload_current()
            # Always refresh the page list in case new files appeared/vanished
            _refresh_pages()
        except Exception as e:
            print("hot-reload failed:", e)
            # Try again shortly (file might still be being written)
            QTimer.singleShot(300, lambda: _reload_path(path))

    def _schedule_reload(path):
        # coalesce bursts from some editors
        if path in _pending:
            return
        _pending[path] = True
        QTimer.singleShot(150, lambda: (_pending.pop(path, None), _reload_path(path)))

    def _refresh_pages():
        global page_paths
        new_paths = discover_pages()
        if new_paths != page_paths:
            page_paths = new_paths
            cycler.set_pages(page_paths)
            _reset_watches()

    # Signals
    watcher.fileChanged.connect(_schedule_reload)
    watcher.directoryChanged.connect(lambda _p: (_reset_watches(), _refresh_pages()))

    

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
                wear = msg.get("tyre_wear", [None, None, None, None])
                pres = msg.get("tyre_pres", [None, None, None, None])

                # NEW: acceleration (lat/long) in g
                acc = msg.get("accG") or [msg.get("acc_long_g", 0.0), msg.get("acc_lat_g", 0.0), 0.0]
                try:
                    gx, gy = float(acc[0]), float(acc[2])
                except Exception:
                    gx = gy = 0.0

                dmg = msg.get("car_damage", [0, 0, 0, 0, 0])
                try:
                    dmg = [float(d/100 or 0.0) for d in dmg]
                except Exception:
                    dmg = [0.0, 0.0, 0.0, 0.0, 0.0]

                ch = {
                    "rpm": msg.get("rpm", 0),
                    "rpm_k": msg.get("rpm", 0) / 1000.0,
                    "fuel_l": fuel_l,
                    "fuel_pct": (fuel_l / cap) if cap else 0.0,
                    "gear": msg.get("gear", 0),
                    "speed": msg.get("speed", 0.0),

                    "tyre_wear_fl": (wear[0] or 0)/100,
                    "tyre_wear_fr": (wear[1] or 0)/100,
                    "tyre_wear_rl": (wear[2] or 0)/100,
                    "tyre_wear_rr": (wear[3] or 0)/100,
                    "wheel_pressure_fl": pres[0],
                    "wheel_pressure_fr": pres[1],
                    "wheel_pressure_rl": pres[2],
                    "wheel_pressure_rr": pres[3],
                    "brake": msg.get("brake", 0.0),
                    "gas": msg.get("gas", 0.0),

                    # NEW: channels for GG element
                    "acc_long_g": gx,
                    "acc_lat_g":  gy,
                    "car_damage": dmg,
                    "car_damage_0": dmg[0],
                    "car_damage_1": dmg[1],
                    "car_damage_2": dmg[2],
                    "car_damage_3": dmg[3],
                    "car_damage_4": dmg[4],
                    "car_damage_max": max(dmg),
                    "car_damage_avg": max(dmg)/5.0,
                }
                channels.update(ch)

                

                rpm = msg.get("rpms") or msg.get("rpm") or 0
                max_rpm = msg.get("max_rpm", 9000)
                min_rpm = int(0.60 * max_rpm)
                sl.update_rpm(rpm, min_rpm=min_rpm, max_rpm=max_rpm)

            except Exception as e:
                print("bad packet:", e)

    sock.readyRead.connect(on_ready)

    BTN = 27   # BCM27 (pin 13) -> button to GND (active-low)

    # req = gpiod.request_lines(
    #     "/dev/gpiochip0",
    #     consumer="PAGE_CYCLE",
    #     config={
    #         BTN: gpiod.LineSettings(direction=Direction.INPUT,
    #                                 bias=Bias.PULL_UP),
    #     }
    # )

    # DEBOUNCE_S = 0.05  # 50 ms debounce
    # state = {"pressed": False, "t": 0.0}

    # def poll_button():
    #     v = req.get_value(BTN)
    #     now = time.monotonic()
    #     pressed = (v == Value.INACTIVE)  # pull-up: LOW means pressed
    #     if pressed != state["pressed"] and (now - state["t"]) >= DEBOUNCE_S:
    #         state["pressed"] = pressed
    #         state["t"] = now
    #         if pressed:
    #             cycler.next_page()

    # btn_timer = QTimer()
    # btn_timer.setInterval(10)  # 10 ms poll
    # btn_timer.timeout.connect(poll_button)
    # btn_timer.start()


    # ---- Clean up on exit ----
    def cleanup():
        sl.close()
        try:
            req.release()
        except Exception:
            pass

    app.aboutToQuit.connect(cleanup)

    sys.exit(app.exec())

