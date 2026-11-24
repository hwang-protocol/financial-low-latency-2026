"""从 pcap 逐层剥出 wire-v1 payload，并对每一层的合同做断言。

第二部分运行 ① 调用本脚本：正文绿色卡把它从 stdin 送到 `.2` 执行，
命令行参数是远端 pcap 路径，远端不留副本。

逐层断言的目的是让「payload 落在 offset 42」成为推导结果而不是硬编码常数：
pcap 字节序、linktype、EtherType、IPv4 version、protocol、UDP 端口和
UDP length 任何一层不符合预期，都在这里立刻失败，而不是把错位的
bytes 继续喂给 wire-v1 解码。
"""

import struct
import sys

# wire-v1 合同：32-byte Header + 20-byte Tick Body，前缀 ! 表示网络字节序。
HEADER = struct.Struct("!HBBHHIQQI")
TICK = struct.Struct("!H4sHIII")

EXPECTED_HEADER = (0x464C, 1, 1, 0, 32, 20, 7, 701, 1)
EXPECTED_TICK = (0x4D44, b"AAPL", 0, 1234501, 10, 1)
EXPECTED_DST_PORT = 42102
LINKTYPE_ETHERNET = 1


def read_first_frame(pcap_path):
    """读取 pcap 第一条记录。

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
    # 24-byte 全局头之后是 16-byte 记录头，本条帧的 incl_len 落在 offset 32。
    incl_len = struct.unpack("<I", raw[32:36])[0]
    return magic.hex(), linktype, raw[40:40 + incl_len]


def extract_udp_payload(frame):
    """逐层剥掉 Ethernet、IPv4 与 UDP 头，按 UDP length 截出业务 payload。

    Args:
        frame: 捕获到的完整以太帧 bytes。

    Returns:
        tuple: `(ip_header_bytes, dst_port, udp_length, payload)`。
    """
    ethertype = struct.unpack("!H", frame[12:14])[0]
    # access VLAN 上抓到的是不带 802.1Q tag 的帧，所以 EtherType 直接是 IPv4。
    assert ethertype == 0x0800, "expected IPv4 EtherType, got 0x%04x" % ethertype
    assert frame[14] >> 4 == 4, "expected IPv4, got version %d" % (frame[14] >> 4)
    # IPv4 头长度由 IHL 给出，不是固定 20，所以 UDP 头偏移必须算出来。
    ip_header_bytes = (frame[14] & 0x0F) * 4
    assert frame[23] == 17, "expected UDP, got IP protocol %d" % frame[23]
    udp = frame[14 + ip_header_bytes:]
    dst_port, udp_length = struct.unpack("!HH", udp[2:6])
    assert dst_port == EXPECTED_DST_PORT, "unexpected dst port %d" % dst_port
    # UDP length 含 8-byte 头；按它截断，避免把以太网填充算进 payload。
    return ip_header_bytes, dst_port, udp_length, udp[8:udp_length]


def decode_wire_v1(payload):
    """按 wire-v1 合同把 payload 解回字段，并断言与发送端约定一致。

    Args:
        payload: 剥完外层头的 52-byte 业务载荷。

    Returns:
        tuple: `(head, body)` 两个已解包的字段元组。
    """
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
