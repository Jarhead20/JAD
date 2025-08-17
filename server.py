# Windows sender (runs on your gaming PC)
import mmap, ctypes, socket, json, time

class UDPSink:
    def __init__(self, host: str, port: int, *, allow_broadcast=False):
        self.host = host
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if allow_broadcast:
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.fail_count = 0
        self._last_warn = 0.0

    def send(self, payload: dict):
        buf = json.dumps(payload).encode("utf-8")
        try:
            self.sock.sendto(buf, (self.host, self.port))
            self.fail_count = 0
        except OSError as e:
            # Network unreachable, no route, etc. → don’t crash; back off a bit
            self.fail_count += 1
            # exponential backoff up to ~2s
            delay = min(2.0, 0.05 * (2 ** min(self.fail_count, 6)))
            now = time.monotonic()
            if now - self._last_warn > 2.0:  # throttle logs
                print(f"[UDP] send failed ({e}); will keep trying...")
                self._last_warn = now
            time.sleep(delay)  # brief pause to avoid busy-loop
            # keep going (don’t re-raise)

# --- Static page (unchanged) ---
class SPageFileStatic(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ('smVersion', ctypes.c_wchar * 15),
        ('acVersion', ctypes.c_wchar * 15),
        ('numberOfSessions', ctypes.c_int),
        ('numCars', ctypes.c_int),
        ('carModel', ctypes.c_wchar * 33),
        ('track', ctypes.c_wchar * 33),
        ('playerName', ctypes.c_wchar * 33),
        ('playerSurname', ctypes.c_wchar * 33),
        ('playerNick', ctypes.c_wchar * 33),
        ('sectorCount', ctypes.c_int),
        ('maxTorque', ctypes.c_float),
        ('maxPower', ctypes.c_float),
        ('maxRpm', ctypes.c_int),
        ('maxFuel', ctypes.c_float),
    ]

mm_static = mmap.mmap(-1, ctypes.sizeof(SPageFileStatic), tagname="acpmf_static")
stat = SPageFileStatic.from_buffer(mm_static)
MAX_RPM = int(stat.maxRpm) or 8000
TANK_L  = float(stat.maxFuel) or 60.0
REDLINE_RPM = int(0.95 * MAX_RPM)

c_int32 = ctypes.c_int32
c_float = ctypes.c_float
c_wchar = ctypes.c_wchar

class SPageFileGraphic(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ('packetId', c_int32),
        ('status',   c_int32),     # AC_STATUS
        ('session',  c_int32),     # AC_SESSION_TYPE
        ('currentTime', c_wchar * 15),
        ('lastTime',    c_wchar * 15),
        ('bestTime',    c_wchar * 15),
        ('split',       c_wchar * 15),
        ('completedLaps', c_int32),
        ('position',      c_int32),
        ('iCurrentTime',  c_int32),   # ms
        ('iLastTime',     c_int32),   # ms
        ('iBestTime',     c_int32),   # ms
        ('sessionTimeLeft',  c_float),
        ('distanceTraveled', c_float),
        ('isInPit',         c_int32),
        ('currentSectorIndex', c_int32),
        ('lastSectorTime',     c_int32),
        ('numberOfLaps',       c_int32),
        ('tyreCompound', c_wchar * 33),
        ('replayTimeMultiplier', c_float),
        ('normalizedCarPosition', c_float),
        ('carCoordinates', c_float * 3),
        ('penaltyTime',    c_float),
        ('flag',           c_int32),
        ('idealLineOn',    c_int32),
        ('isInPitLane',    c_int32),
        ('surfaceGrip',    c_float),
    ]

mm_graph = mmap.mmap(-1, ctypes.sizeof(SPageFileGraphic), tagname="acpmf_graphics")
gfx = SPageFileGraphic.from_buffer(mm_graph)

c_int32 = ctypes.c_int32
c_float = ctypes.c_float

class SPageFilePhysics(ctypes.Structure):
    _pack_ = 4
    _fields_ = [
        ('packetId', c_int32),
        ('gas',      c_float),
        ('brake',    c_float),
        ('fuel',     c_float),
        ('gear',     c_int32),
        ('rpms',     c_int32),
        ('steerAngle', c_float),
        ('speedKmh',   c_float),
        ('velocity',   c_float * 3),
        ('accG',       c_float * 3),
        ('wheelSlip',        c_float * 4),
        ('wheelLoad',        c_float * 4),
        ('wheelsPressure',   c_float * 4),
        ('wheelAngularSpeed',c_float * 4),
        ('tyreWear',         c_float * 4),
        ('tyreDirtyLevel',   c_float * 4),
        ('tyreCoreTemperature', c_float * 4),
        ('camberRAD',        c_float * 4),
        ('suspensionTravel', c_float * 4),
        ('drs',        c_float),
        ('tc',         c_float),
        ('heading',    c_float),
        ('pitch',      c_float),
        ('roll',       c_float),
        ('cgHeight',   c_float),
        ('carDamage',  c_float * 5),     # <— ADD THIS
        # (you can extend further if you want the rest)
    ]

mm_phys = mmap.mmap(-1, ctypes.sizeof(SPageFilePhysics), tagname="acpmf_physics")
phys = SPageFilePhysics.from_buffer(mm_phys)

PI_IP = "172.20.10.15"
PORT  = 5005
udp = UDPSink(PI_IP, PORT)

while True:
    # Read live values
    rpm     = int(phys.rpms)
    gear    = int(phys.gear)
    gas     = float(phys.gas)
    fuel_l  = float(phys.fuel)
    speed = float(phys.speedKmh)
    wear4   = [float(x) for x in phys.tyreWear]  # 4 corners
    pres4   = [float(x) for x in phys.wheelsPressure]  # 4 corners
    brake = float(phys.brake)
    damage5 = [float(x) for x in phys.carDamage]   # <— NEW
    lap = int(gfx.numberOfLaps)

    gx, gy, gz = float(phys.accG[0]), float(phys.accG[1]), float(phys.accG[2])


    payload = {
        "rpm": rpm,
        "gear": gear,
        "throttle": gas,
        "fuel_l": round(fuel_l, 2),
        "fuel_capacity_l": round(TANK_L, 2),
        "max_rpm": MAX_RPM,
        "redline_rpm": REDLINE_RPM,
        # tyre wear, array order is typically FL, FR, RL, RR:
        "tyre_wear": wear4,
        "tyre_pres": pres4,
        "speed": speed,
        "brake": brake,
        "gas": gas,

        "accG": [gx, gy, gz],         # raw array
        "acc_long_g": gx,             # convenience fields
        "acc_lat_g":  gz,
        "car_damage": damage5,
        "lap": lap
    }

    lap_cur_ms  = int(gfx.iCurrentTime)
    lap_last_ms = int(gfx.iLastTime)
    lap_best_ms = int(gfx.iBestTime)
    laps_done   = int(gfx.completedLaps)


    payload.update({
        "lap_current_ms": lap_cur_ms if lap_cur_ms >= 0 else 0,
        "lap_last_ms":    lap_last_ms if lap_last_ms >= 0 else 0,
        "lap_best_ms":    lap_best_ms if lap_best_ms >= 0 else 0,
        "laps_completed": laps_done
    })
    # sock.sendto(json.dumps(payload).encode("utf-8"), (PI_IP, PORT))
    udp.send(payload)
    time.sleep(0.05)  # ~20 Hz
