import socket, struct

header = struct.Struct("!HBBHHIQQI")
tick = struct.Struct("!H4sHIII")
BODY = tick.pack(0x4D44, b"AAPL", 0, 1234501, 10, 1)

def frame(magic=0x464C, version=1, header_len=32, body_len=20):
    """按 wire-v1 打包一条 Tick；只改一个参数就得到一条只坏一处的包。"""
    return header.pack(magic, version, 1, 0, header_len, body_len, 7, 701, 1) + BODY

def decode(packet):
    """按固定顺序检查四项结构合同；它只看信封，不解析 Body。"""
    if len(packet) != 52:
        raise ValueError("BAD_PACKET_SIZE")
    fields = header.unpack(packet[:32])
    if fields[0] != 0x464C:
        raise ValueError("BAD_MAGIC")
    if fields[1] != 1:
        raise ValueError("BAD_VERSION")
    if fields[4] != 32 or fields[5] != 20:
        raise ValueError("BAD_LENGTH")
    return "HEADER_GATE_PASSED"

receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
receiver.bind(("127.0.0.1", 42103)); receiver.settimeout(5)
sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
for label, packet in [("legal", frame()), ("truncated", frame()[:40]),
        ("bad-magic", frame(magic=0x4646)), ("bad-version", frame(version=2)),
        ("bad-header-len", frame(header_len=33))]:
    sender.sendto(packet, ("127.0.0.1", 42103))
    print("sent case=%-15s bytes=%d head8=%s" % (label, len(packet), packet[:8].hex()))
print("---- 接收端逐条过门禁 ----")
for unused in range(5):
    data, peer = receiver.recvfrom(2048)
    try:
        verdict = decode(data)
    except ValueError as err:
        verdict = str(err)
    print("recv bytes=%d head8=%s verdict=%s" % (len(data), data[:8].hex(), verdict))
