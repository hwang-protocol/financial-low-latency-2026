"""Synthetic A/B packets used only by local tests; never classroom evidence."""
from pathlib import Path
import socket
import struct


def packet(group, port, sequence, message=b'S' + bytes(10) + b'O', session=b'LOCALTEST1'):
    mold = struct.pack('!10sQH', session, sequence, 1) + struct.pack('!H', len(message)) + message
    udp = struct.pack('!HHHH', 45000, port, len(mold) + 8, 0) + mold
    ip = bytearray(struct.pack('!BBHHHBBH4s4s', 0x45, 0, len(udp) + 20, 1, 0, 1, 17, 0,
                              socket.inet_aton('20.1.1.1'), socket.inet_aton(group)))
    total = sum(struct.unpack('!10H', ip))
    while total >> 16: total = (total & 65535) + (total >> 16)
    struct.pack_into('!H', ip, 10, (~total) & 65535)
    mac = b'\x01\x00\x5e' + (int.from_bytes(socket.inet_aton(group), 'big') & 0x7fffff).to_bytes(3, 'big')
    return mac + bytes.fromhex('0200000000010800') + ip + udp


def write_pcap(path, packets):
    raw = struct.pack('<IHHIIII', 0xa1b2c3d4, 2, 4, 0, 0, 65535, 1)
    for i, p in enumerate(packets):
        raw += struct.pack('<IIII', 1, i, len(p), len(p)) + p
    Path(path).write_bytes(raw)


def build(raw):
    raw = Path(raw)
    a, b = ('233.74.125.32', 31032), ('233.74.125.33', 31033)
    for mode, packets in (
        ('MULTICAST_A', [packet(*a, i) for i in range(1, 121)]),
        ('MULTICAST_B', [packet(*b, i) for i in range(121, 241)]),
        ('DUAL', [packet(*dest, i) for i in range(241, 301) for dest in (a, b)]),
    ):
        write_pcap(raw / (mode + '.pcap'), packets)
        (raw / (mode + '-tcpdump.txt')).write_text('120 packets captured\n0 packets dropped by kernel\n')
    (raw / 'membership.txt').write_text('inet 233.74.125.32\ninet 233.74.125.33\n')
