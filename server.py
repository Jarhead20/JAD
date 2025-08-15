# Windows only (shared memory tagname)
import mmap, ctypes, struct, time, socket, json

PI_IP = "172.20.10.15"
PORT = 5005
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# ---- Static page (capacity & max RPM) ----
class SPageFileStatic(ctypes.Structure):
    _pack_ = 4  # matches AC's #pragma pack(4)
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
        ('maxFuel', ctypes.c_float)
    ]

mm_static = mmap.mmap(-1, ctypes.sizeof(SPageFileStatic), tagname="acpmf_static")
stat = SPageFileStatic.from_buffer(mm_static)
MAX_RPM   = int(stat.maxRpm) or 8000   # fallback if 0
TANK_L    = float(stat.maxFuel) or 60  # fallback if 0

print(f"Car max RPM: {MAX_RPM}, Tank capacity: {TANK_L:.1f} L")

REDLINE_RPM = int(0.95 * MAX_RPM)

# ---- Physics page (live values) ----
# Layout beginning of SPageFilePhysics:
# int packetId; float gas; float brake; float fuel; int gear; int rpms;
fmt = "<ifffii"
size = struct.calcsize(fmt)
mm_phys = mmap.mmap(-1, 4096, tagname="acpmf_physics")

while True:
    mm_phys.seek(0)
    packetId, gas, brake, fuel_l, gear, rpm = struct.unpack(fmt, mm_phys.read(size))

    payload = {
        "rpm": rpm,
        "gear": gear,
        "throttle": gas,
        "fuel_l": round(fuel_l, 2),
        "fuel_capacity_l": round(TANK_L, 2),
        "max_rpm": MAX_RPM,
        "redline_rpm": REDLINE_RPM
    }
    sock.sendto(json.dumps(payload).encode("utf-8"), (PI_IP, PORT))
    time.sleep(0.05)   # ~20 Hz
