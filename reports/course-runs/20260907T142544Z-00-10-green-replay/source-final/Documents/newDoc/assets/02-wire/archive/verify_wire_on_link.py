"""从 pcap 逐层剥出 wire-v1 payload，并对每一层的合同做断言。

第二部分运行 ① 调用本脚本：正文绿色卡把它从 stdin 送到 `.2` 执行，
命令行参数是远端 pcap 路径，远端不留副本。

逐层断言的目的是让「payload 落在 offset 42、长度 52」成为推导结果而不是硬编码常数。
长度链是本脚本 fail-closed 的重点：捕获长度、IPv4 total length、IHL 和 UDP length
必须互相自证，任何一环对不上就退出，而不是把错位的 bytes 继续喂给 wire-v1 解码。
Python 切片越界不会报错，所以每次截取前都先断言源 bytes 真的够长。
"""

import struct
import sys

# wire-v1 合同：32-byte Header + 20-byte Tick Body，前缀 ! 表示网络字节序。
HEADER = struct.Struct("!HBBHHIQQI")
TICK = struct.Struct("!H4sHIII")

EXPECTED_HEADER = (0x464C, 1, 1, 0, 32, 20, 7, 701, 1)
EXPECTED_TICK = (0x4D44, b"AAPL", 0, 1234501, 10, 1)
EXPECTED_DST_PORT = 42102
EXPECTED_PAYLOAD_BYTES = 52
LINKTYPE_ETHERNET = 1
ETH_HEADER_BYTES = 14
UDP_HEADER_BYTES = 8
IP_MIN_HEADER_BYTES = 20
PCAP_GLOBAL_HEADER_BYTES = 24
PCAP_RECORD_HEADER_BYTES = 16


def read_first_frame(pcap_path):
    """读取 pcap 第一条记录，并断言这条记录是完整捕获的。

    Args:
        pcap_path: 远端 pcap 文件路径。

    Returns:
        tuple: `(magic_hex, linktype, frame)`，frame 是捕获到的以太帧 bytes。
    """
    raw = open(pcap_path, "rb").read()
    magic = raw[:4]
    # pcap 文件自己也有字节序合同：magic 0xa1b2c3d4 在小端机器上落成 d4 c3 b2 a1。
    assert magic == b"\xd4\xc3\xb2\xa1", "unexpected pcap byte order: %s" % magic.hex()
    linktype = struct.unpack("<I", raw[20:24])[0]
    # linktype 决定下面能不能按 14-byte Ethernet 头往下剥。
    assert linktype == LINKTYPE_ETHERNET, "expected Ethernet, got linktype %d" % linktype
    record = PCAP_GLOBAL_HEADER_BYTES
    assert len(raw) >= record + PCAP_RECORD_HEADER_BYTES, "pcap has no complete record header"
    # 记录头后 8 bytes 是 incl_len 与 orig_len：前者是文件里真存了多少，后者是线上原始长度。
    incl_len, orig_len = struct.unpack("<II", raw[record + 8:record + 16])
    # snaplen 截断会让后面所有长度推导失去意义，所以截断的捕获直接拒绝。
    assert incl_len == orig_len, "truncated capture: incl_len=%d orig_len=%d" % (incl_len, orig_len)
    start = record + PCAP_RECORD_HEADER_BYTES
    frame = raw[start:start + incl_len]
    # 文件也可能被写坏或被人为改短：实际读到的 bytes 必须等于 incl_len 声明的长度。
    assert len(frame) == incl_len, "pcap record shorter than declared incl_len %d" % incl_len
    return magic.hex(), linktype, frame


def extract_udp_payload(frame):
    """逐层剥掉 Ethernet、IPv4 与 UDP 头，按互相自证的长度截出业务 payload。

    Args:
        frame: 捕获到的完整以太帧 bytes。

    Returns:
        tuple: `(ip_header_bytes, dst_port, udp_length, payload)`。
    """
    ethertype = struct.unpack("!H", frame[12:14])[0]
    # access VLAN 上抓到的是不带 802.1Q tag 的帧，所以 EtherType 直接是 IPv4。
    assert ethertype == 0x0800, "expected IPv4 EtherType, got 0x%04x" % ethertype
    ip = ETH_HEADER_BYTES
    assert len(frame) >= ip + IP_MIN_HEADER_BYTES, "frame too short for a 20-byte IPv4 header"
    assert frame[ip] >> 4 == 4, "expected IPv4, got version %d" % (frame[ip] >> 4)
    # IPv4 头长度由 IHL 给出，不是固定 20，所以 UDP 头偏移必须算出来。
    ip_header_bytes = (frame[ip] & 0x0F) * 4
    assert ip_header_bytes >= IP_MIN_HEADER_BYTES, "illegal IHL: %d bytes" % ip_header_bytes
    assert len(frame) >= ip + ip_header_bytes, "frame does not cover the full IPv4 header"
    ip_total_length = struct.unpack("!H", frame[ip + 2:ip + 4])[0]
    # 分片包的 payload 不完整。MF 位与 fragment offset 都必须为 0；DF 位允许置起。
    assert struct.unpack("!H", frame[ip + 6:ip + 8])[0] & 0x3FFF == 0, "fragmented IPv4 rejected"
    assert frame[ip + 9] == 17, "expected UDP, got IP protocol %d" % frame[ip + 9]
    assert ip_total_length >= ip_header_bytes + UDP_HEADER_BYTES, \
        "IP total length %d cannot hold a UDP header" % ip_total_length
    # 以太帧可能带填充，所以用 IP total length 而不是帧尾界定 IP 包，并要求捕获覆盖它。
    assert len(frame) >= ip + ip_total_length, "frame does not cover the full IP packet"
    udp = frame[ip + ip_header_bytes:ip + ip_total_length]
    dst_port, udp_length = struct.unpack("!HH", udp[2:6])
    assert dst_port == EXPECTED_DST_PORT, "unexpected dst port %d" % dst_port
    assert udp_length >= UDP_HEADER_BYTES, "UDP length %d smaller than its own header" % udp_length
    # 关键交叉校验：UDP 自报长度必须与 IPv4 推出的长度一致，否则两层互相矛盾。
    assert udp_length == ip_total_length - ip_header_bytes, \
        "UDP length %d disagrees with IP payload length %d" % (udp_length, ip_total_length - ip_header_bytes)
    assert len(udp) == udp_length, "capture does not cover the full UDP segment"
    return ip_header_bytes, dst_port, udp_length, udp[UDP_HEADER_BYTES:]


def decode_wire_v1(payload):
    """按 wire-v1 合同把 payload 解回字段，并断言与发送端约定一致。

    Args:
        payload: 剥完外层头的 52-byte 业务载荷。

    Returns:
        tuple: `(head, body)` 两个已解包的字段元组。
    """
    # 先断言总长度，再解字段：长度不对时报「52 bytes 不符」比报 struct 错误更容易定位。
    assert len(payload) == EXPECTED_PAYLOAD_BYTES, \
        "wire-v1 payload must be %d bytes, got %d" % (EXPECTED_PAYLOAD_BYTES, len(payload))
    head = HEADER.unpack(payload[:32])
    body = TICK.unpack(payload[32:])
    assert head == EXPECTED_HEADER, "header mismatch: %r" % (head,)
    assert body == EXPECTED_TICK, "tick body mismatch: %r" % (body,)
    return head, body


def verify_capture(pcap_path):
    """按 pcap → 以太帧 → UDP payload → wire-v1 字段的顺序验证并打印证据行。"""
    magic_hex, linktype, frame = read_first_frame(pcap_path)
    ip_header_bytes, dst_port, udp_length, payload = extract_udp_payload(frame)
    head, body = decode_wire_v1(payload)
    print("pcap_magic=%s linktype=%d" % (magic_hex, linktype))
    print("captured_frame_bytes=%d ip_header_bytes=%d dst_port=%d udp_length=%d payload_bytes=%d"
          % (len(frame), ip_header_bytes, dst_port, udp_length, len(payload)))
    print("wire_hex=%s" % payload.hex())
    print("wire_decoded=symbol:%s price:%d quantity:%d sequence:%d"
          % (body[1].decode(), body[3], body[4], head[8]))


if __name__ == "__main__":
    verify_capture(sys.argv[1])
