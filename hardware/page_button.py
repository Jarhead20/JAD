# hardware/page_buttons.py
from __future__ import annotations
import time
from typing import List, Sequence, Dict, Union
from PySide6.QtCore import QObject, QTimer, Signal
import gpiod
from gpiod.line import Direction, Bias, Value

class ButtonChannel(QObject):
    """Signals for a single button."""
    pressed  = Signal()
    released = Signal()
    clicked  = Signal()

class PageButtons(QObject):
    """
    Manage multiple GPIO buttons at once (default 5). Debounced.
    - Connect per-button: buttons.button("page").clicked.connect(...)
    - Or catch any: buttons.clicked.connect(lambda idx,name: ...)
    """
    # any-button signals (index, name)
    pressed  = Signal(int, str)
    released = Signal(int, str)
    clicked  = Signal(int, str)

    def __init__(
        self,
        *,
        pins: Sequence[int],                     # e.g. [27, 17, 22, 5, 6]
        names: Sequence[str] | None = None,      # e.g. ["page","A","B","C","D"]
        chip: str = "/dev/gpiochip0",
        active_low: Union[bool, Sequence[bool]] = True,
        debounce_ms: Union[int, Sequence[int]] = 50,
        parent=None
    ):
        super().__init__(parent)
        if not pins:
            raise ValueError("pins must be a non-empty list")
        self.pins: List[int] = list(pins)
        self.names: List[str] = list(names) if names else [f"btn{i}" for i in range(len(pins))]

        # normalize per-button options
        def norm_opt(opt, default):
            if isinstance(opt, (list, tuple)):
                if len(opt) != len(self.pins): raise ValueError("per-button option length mismatch")
                return list(opt)
            return [opt] * len(self.pins)

        self.active_low: List[bool] = norm_opt(active_low, True)
        self.debounce_s: List[float] = [max(0, int(ms))/1000.0 for ms in norm_opt(debounce_ms, 50)]

        # request all lines at once with suitable bias per polarity
        cfg: Dict[int, gpiod.LineSettings] = {}
        for pin, al in zip(self.pins, self.active_low):
            cfg[pin] = gpiod.LineSettings(
                direction=Direction.INPUT,
                bias=Bias.PULL_UP if al else Bias.PULL_DOWN
            )
        self.req = gpiod.request_lines(chip, consumer="PAGE_BUTTONS", config=cfg)

        # per-button state for debouncing
        self._last_val   = [None] * len(self.pins)   # raw (possibly bouncing)
        self._stable_val = [False] * len(self.pins)  # debounced
        self._last_t     = [time.monotonic()] * len(self.pins)

        # per-button QObject channels for convenient hookup
        self._by_index: List[ButtonChannel] = [ButtonChannel(self) for _ in self.pins]
        self._by_name: Dict[str, ButtonChannel] = dict(zip(self.names, self._by_index))

        # poll timer (10 ms)
        self._timer = QTimer(self)
        self._timer.setInterval(10)
        self._timer.timeout.connect(self._poll)
        self._timer.start()

    # ----- public helpers -----
    def button(self, key: Union[int, str]) -> ButtonChannel:
        """Get a ButtonChannel by index (0..N-1) or by name string."""
        if isinstance(key, int):
            return self._by_index[key]
        return self._by_name[key]

    # ----- internals -----
    def _read_pressed(self, i: int) -> bool:
        v = self.req.get_value(self.pins[i])
        return (v == Value.INACTIVE) if self.active_low[i] else (v == Value.ACTIVE)

    def _poll(self):
        now = time.monotonic()
        for i, name in enumerate(self.names):
            val = self._read_pressed(i)
            if self._last_val[i] is None:
                self._last_val[i] = val
                self._stable_val[i] = val
                self._last_t[i] = now
                continue

            if val != self._last_val[i]:
                self._last_val[i] = val
                self._last_t[i] = now

            if (now - self._last_t[i]) >= self.debounce_s[i] and val != self._stable_val[i]:
                self._stable_val[i] = val
                ch = self._by_index[i]
                if val:
                    ch.pressed.emit()
                    self.pressed.emit(i, name)
                    ch.clicked.emit()           # edge = click
                    self.clicked.emit(i, name)
                else:
                    ch.released.emit()
                    self.released.emit(i, name)

    def close(self):
        try: self._timer.stop()
        except Exception: pass
        try: self.req.release()
        except Exception: pass
