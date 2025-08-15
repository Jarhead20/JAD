import mmap, struct, time
import socket, json
PI_IP = "jad@jad.local"
PORT = 5005

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Map the physics page (4KB is plenty; we only read the first few fields)
mm = mmap.mmap(-1, 4096, tagname="acpmf_physics")

# Struct layout for the first fields of SPageFilePhysics:
# int packetId; float gas; float brake; float fuel; int gear; int rpm;
fmt = "<ifffii"           # little-endian: i f f f i i
size = struct.calcsize(fmt)

while True:
    mm.seek(0)
    packetId, gas, brake, fuel, gear, rpm = struct.unpack(fmt, mm.read(size))
    print(f"RPM: {rpm}  Gear: {gear}  Throttle: {gas:.2f}")
    time.sleep(0.05)      # ~20 Hz
    payload = json.dumps({"rpm": rpm}).encode()
    sock.sendto(payload, (PI_IP, PORT))




