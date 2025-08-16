from time import sleep
from hardware.shift_lights import ShiftLights

PINS = [6, 5, 22, 27, 17, 16, 12, 25, 24, 23]  # BCM offsets, pick your 10
with ShiftLights(PINS, mode="bar", active_high=True, flash_at=0.98, flash_hz=8.0) as sl:
    # Demo sweep
    for k in list(range(0, 110)):
        sl.update_ratio(k/100.0)
        sleep(0.1)
    sl.close()