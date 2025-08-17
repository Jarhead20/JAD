import time
from typing import Iterable, List, Optional

import gpiod
from gpiod.line import Direction, Value


class ShiftLights:
    """
    Drive N shift lights using GPIO via libgpiod v2.x.

    pins:         list of BCM line offsets (e.g., [5,6,13,19,26,16,20,21,12,25])
    chip:         gpiochip path (default '/dev/gpiochip0' on Pi 5)
    active_high:  True if LED turns on when line is HIGH; False for active-low drivers
    mode:         'bar' (fill up to current level) or 'dot' (only one LED lit)
    thresholds:   optional list of N floats in 0..1 for each LED's trigger point
                  (if omitted, thresholds are evenly spaced)
    flash_at:     ratio (0..1) above which lights will flash
    flash_hz:     flash frequency in Hz
    """

    def __init__(
        self,
        pins: Iterable[int],
        *,
        chip: str = "/dev/gpiochip0",
        active_high: bool = True,
        mode: str = "bar",
        thresholds: Optional[Iterable[float]] = None,
        flash_at: Optional[float] = None,
        flash_hz: float = 6.0,
        consumer: str = "SHIFT_LIGHTS",
    ):
        self.pins: List[int] = list(pins)
        if not self.pins:
            raise ValueError("pins must be a non-empty list of BCM offsets")

        self.chip = chip
        self.active_high = bool(active_high)
        self.mode = mode.lower()
        if self.mode not in ("bar", "dot"):
            raise ValueError("mode must be 'bar' or 'dot'")

        self.N = len(self.pins)
        if thresholds is None:
            # Evenly spaced, e.g. for 10 LEDs: 0.1, 0.2, ..., 1.0
            self.thresholds = [(i + 1) / self.N for i in range(self.N)]
        else:
            t = [float(x) for x in thresholds]
            if len(t) != self.N:
                raise ValueError("thresholds length must match pins length")
            self.thresholds = t

        self.flash_at = None if flash_at is None else float(flash_at)
        self.flash_hz = float(flash_hz)

        # Request all lines as outputs in one go
        cfg = {}
        for off in self.pins:
            # Start OFF
            cfg[off] = gpiod.LineSettings(direction=Direction.OUTPUT, output_value=Value.INACTIVE)
        self.req = gpiod.request_lines(self.chip, consumer=consumer, config=cfg)

        # cache of current on/off states (bools)
        self._states = {off: False for off in self.pins}

    # --- helpers ---
    def _to_value(self, on: bool) -> Value:
        # ACTIVE = logic 1. If wiring is active-low, invert.
        if self.active_high:
            return Value.ACTIVE if on else Value.INACTIVE
        else:
            return Value.INACTIVE if on else Value.ACTIVE

    def _apply_states(self, new_states: List[bool]):
        # Build a dict {offset: Value}
        mapping = {off: self._to_value(on) for off, on in zip(self.pins, new_states)}
        self.req.set_values(mapping)
        for off, on in zip(self.pins, new_states):
            self._states[off] = on

    def update_ratio(self, ratio: float):
        """
        Update lights from a 0..1 ratio.
        Normal:
        - 'bar': fill up to threshold
        - 'dot': highest reached LED only
        Flash mode (r >= flash_at and flash_hz > 0):
        - ALL LEDs flash together; during the on phase, ALL are ON.
        """
        r = max(0.0, min(1.0, float(ratio)))

        flashing = (self.flash_at is not None and r >= self.flash_at and self.flash_hz > 0)
        if flashing:
            blink_on = (int(time.monotonic() * self.flash_hz * 2.0) & 1) == 1
            states = [bool(blink_on)] * self.N   # all on during on-phase, all off during off-phase
            self._apply_states(states)
            return

        # --- normal (non-flash) behavior ---
        if self.mode == "bar":
            states = [r >= thr for thr in self.thresholds]
        else:  # 'dot'
            idx = -1
            for i, thr in enumerate(self.thresholds):
                if r >= thr:
                    idx = i
            states = [(i == idx) for i in range(self.N)]

        self._apply_states(states)


    def update_rpm(self, rpm: float, *, min_rpm: float, max_rpm: float):
        """
        Map RPM to 0..1 and call update_ratio(). Values below min_rpm light nothing.
        """
        if max_rpm <= min_rpm:
            raise ValueError("max_rpm must be > min_rpm")
        rrpm = (float(rpm) - float(min_rpm)) / (float(max_rpm) - float(min_rpm))
        self.update_ratio(rrpm)

    def set_raw_count(self, count: int):
        """
        Directly light the first 'count' LEDs (bar-style), no flashing, no thresholds.
        """
        c = max(0, min(self.N, int(count)))
        states = [i < c for i in range(self.N)]
        self._apply_states(states)

    def all_off(self):
        self._apply_states([False] * self.N)

    def all_on(self):
        self._apply_states([True] * self.N)

    def close(self):
        try:
            self.all_off()
        except Exception:
            pass
        try:
            self.req.release()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()