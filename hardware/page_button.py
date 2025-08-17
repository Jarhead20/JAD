# hardware/page_buttons.py
from __future__ import annotations
import time
from typing import List, Sequence, Dict, Union
from PySide6.QtCore import QObject, QTimer, Signal
import gpiod
from gpiod.line import Direction, Bias, Value

class ButtonChannel(QObject):
    pressed  = Signal()
    released = Signal()
    clicked  = Signal()

class PageButtons(QObject):
    # any-button signals (index, name)
    pressed  = Signal(int, str)
    released = Signal(int, str)
    clicked  = Signal(int, str)

    def __init__(
        self,
        *,
        pins: Sequence[int],
        names: Sequence[str] | None = None,
        chip: str = "/dev/gpiochip0",
        active_low: Union[bool, Sequence[bool]] = True,
        debounce_ms: Union[int, Sequence[int]] = 50,
        store=None,                 # <-- pass your channels singleton here
        prefix: str = "btn_",       # channels prefix
        parent=None
    ):
        super().__init__(parent)
        if not pins:
            raise ValueError("pins must be a non-empty list")

        self.store = store
        self.prefix = prefix

        self.pins: List[int] = list(pins)
        self.names: List[str] = list(names) if names else [f"{i}" for i in range(len(pins))]

        def norm(opt, n, default):
            if isinstance(opt, (list, tuple)):
                if len(opt) != n: raise ValueError("per-button option length mismatch")
                return list(opt)
            return [opt] * n

        self.active_low: List[bool] = norm(active_low, len(self.pins), True)
        self.debounce_s: List[float] = [max(0, int(ms))/1000.0 for ms in norm(debounce_ms, len(self.pins), 50)]

        cfg: Dict[int, gpiod.LineSettings] = {}
        for pin, al in zip(self.pins, self.active_low):
            cfg[pin] = gpiod.LineSettings(direction=Direction.INPUT, bias=Bias.PULL_UP if al else Bias.PULL_DOWN)
        self.req = gpiod.request_lines(chip, consumer="PAGE_BUTTONS", config=cfg)

        self._last_val   = [None] * len(self.pins)
        self._stable_val = [False] * len(self.pins)
        self._last_t     = [time.monotonic()] * len(self.pins)

        self._by_index: List[ButtonChannel] = [ButtonChannel(self) for _ in self.pins]
        self._by_name = dict(zip(self.names, self._by_index))

        self._timer = QTimer(self); self._timer.setInterval(10); self._timer.timeout.connect(self._poll); self._timer.start()

    def button(self, key: Union[int, str]) -> ButtonChannel:
        return self._by_index[key] if isinstance(key, int) else self._by_name[key]

    # ---- internals ----
    def _read_pressed(self, i: int) -> bool:
        v = self.req.get_value(self.pins[i])
        return (v == Value.INACTIVE) if self.active_low[i] else (v == Value.ACTIVE)

    def _ch_name(self, name: str, suffix: str) -> str:
        return f"{self.prefix}{name}{suffix}"

    def _publish(self, name: str, pressed: bool):
        if not self.store:
            return
        # pressed state
        self.store.set(self._ch_name(name, "_pressed"), 1 if pressed else 0)

    def _pulse_click(self, name: str):
        if not self.store:
            return
        # boolean pulse
        self.store.set(self._ch_name(name, "_click"), 1)
        QTimer.singleShot(50, lambda: self.store.set(self._ch_name(name, "_click"), 0))
        # token for edge detection
        ts = int(time.time() * 1000)
        self.store.set(self._ch_name(name, "_click_ts"), ts)

    def _poll(self):
        now = time.monotonic()
        for i, name in enumerate(self.names):
            val = self._read_pressed(i)
            if self._last_val[i] is None:
                self._last_val[i] = val
                self._stable_val[i] = val
                self._last_t[i] = now
                self._publish(name, val)
                continue

            if val != self._last_val[i]:
                self._last_val[i] = val
                self._last_t[i] = now

            if (now - self._last_t[i]) >= self.debounce_s[i] and val != self._stable_val[i]:
                self._stable_val[i] = val
                ch = self._by_index[i]
                self._publish(name, val)
                if val:
                    ch.pressed.emit(); self.pressed.emit(i, name)
                    ch.clicked.emit(); self.clicked.emit(i, name)
                    self._pulse_click(name)
                else:
                    ch.released.emit(); self.released.emit(i, name)

    def close(self):
        try: self._timer.stop()
        except Exception: pass
        try: self.req.release()
        except Exception: pass
