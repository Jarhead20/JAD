# Pi 5 / libgpiod v2.x
import time, gpiod
from gpiod.line import Direction, Bias, Value

LED = 17   # BCM17 (pin 11)
BTN = 27   # BCM27 (pin 13) -> wire to GND via button

# Request both lines in one go:
req = gpiod.request_lines(
    "/dev/gpiochip0",
    consumer="LED_BUTTON",
    config={
        LED: gpiod.LineSettings(direction=Direction.OUTPUT,
                                output_value=Value.INACTIVE),  # LED off initially
        BTN: gpiod.LineSettings(direction=Direction.INPUT,
                                bias=Bias.PULL_UP)              # internal pull-up
    }
)

print("Press Ctrl+C to quit")
try:
    prev = None
    while True:
        # With pull-up: released = HIGH (= ACTIVE), pressed to GND = LOW (= INACTIVE)
        pressed = (req.get_value(BTN) == Value.INACTIVE)
        if pressed != prev:
            req.set_value(LED, Value.ACTIVE if pressed else Value.INACTIVE)
            prev = pressed
        time.sleep(0.01)  # 10 ms poll (acts as debounce)
        print(pressed)
except KeyboardInterrupt:
    pass
finally:
    # ensure LED off and release
    req.set_value(LED, Value.INACTIVE)
    req.release()
