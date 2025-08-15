import time, gpiod
from gpiod.line import Direction, Value

LED = 17

req = gpiod.request_lines(
    "/dev/gpiochip0",
    consumer="LED",
    config={LED: gpiod.LineSettings(direction=Direction.OUTPUT,
                                    output_value=Value.INACTIVE)}
)

for _ in range(5):
    req.set_value(LED, Value.ACTIVE)
    time.sleep(0.5)
    req.set_value(LED, Value.INACTIVE)
    time.sleep(0.5)

req.release()
