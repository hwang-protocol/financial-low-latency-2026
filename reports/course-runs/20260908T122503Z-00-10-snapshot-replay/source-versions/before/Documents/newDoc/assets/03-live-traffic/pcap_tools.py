#!/usr/bin/env python3
"""Small, dependency-free readers for the chapter 03 Ethernet pcaps."""

from __future__ import annotations

import ipaddress
import struct
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Packet:
    timestamp_ns: int
    data: bytes


@dataclass(frozen=True)
class IPv4Packet:
    source: str
    destination: str
    protocol: int
    payload: bytes


@dataclass(frozen=True)
class UDPDatagram:
    source_port: int
    destination_port: int
    payload: bytes


@dataclass(frozen=True)
class TCPSegment:
    source_port: int
    destination_port: int
    sequence: int
    flags: int
    payload: bytes


def read_pcap(path: str | Path) -> tuple[str, int, list[Packet]]:
    raw = Path(path).read_bytes()
    if len(raw) < 24:
        raise ValueError("pcap global header is truncated")
    formats = {
        b"\xd4\xc3\xb2\xa1": ("<", 1_000),
        b"\xa1\xb2\xc3\xd4": (">", 1_000),
        b"\x4d\x3c\xb2\xa1": ("<", 1),
        b"\xa1\xb2\x3c\x4d": (">", 1),
    }
    if raw[:4] not in formats:
        raise ValueError(f"unsupported pcap magic {raw[:4].hex()}")
    endian, fraction_to_ns = formats[raw[:4]]
    _, _, _, _, _, linktype = struct.unpack_from(endian + "HHIIII", raw, 4)
    cursor = 24
    packets: list[Packet] = []
    while cursor < len(raw):
        if cursor + 16 > len(raw):
            raise ValueError("pcap record header is truncated")
        seconds, fraction, captured, original = struct.unpack_from(endian + "IIII", raw, cursor)
        cursor += 16
        if captured > original or cursor + captured > len(raw):
            raise ValueError("pcap record data is truncated")
        packets.append(Packet(seconds * 1_000_000_000 + fraction * fraction_to_ns,
                              raw[cursor:cursor + captured]))
        cursor += captured
    return raw[:4].hex(), linktype, packets


def parse_ethernet_ipv4(frame: bytes) -> IPv4Packet | None:
    if len(frame) < 14:
        return None
    ethertype = struct.unpack_from("!H", frame, 12)[0]
    cursor = 14
    while ethertype in (0x8100, 0x88A8, 0x9100):
        if len(frame) < cursor + 4:
            return None
        ethertype = struct.unpack_from("!H", frame, cursor + 2)[0]
        cursor += 4
    if ethertype != 0x0800 or len(frame) < cursor + 20:
        return None
    first = frame[cursor]
    version, ihl = first >> 4, (first & 0x0F) * 4
    if version != 4 or ihl < 20 or len(frame) < cursor + ihl:
        return None
    total_length = struct.unpack_from("!H", frame, cursor + 2)[0]
    if total_length < ihl or len(frame) < cursor + total_length:
        return None
    fragment = struct.unpack_from("!H", frame, cursor + 6)[0]
    if fragment & 0x3FFF:
        return None
    return IPv4Packet(
        str(ipaddress.ip_address(frame[cursor + 12:cursor + 16])),
        str(ipaddress.ip_address(frame[cursor + 16:cursor + 20])),
        frame[cursor + 9],
        frame[cursor + ihl:cursor + total_length],
    )


def parse_udp(packet: IPv4Packet) -> UDPDatagram | None:
    raw = packet.payload
    if packet.protocol != 17 or len(raw) < 8:
        return None
    source, destination, length = struct.unpack_from("!HHH", raw, 0)
    if length < 8 or length > len(raw):
        return None
    return UDPDatagram(source, destination, raw[8:length])


def parse_tcp(packet: IPv4Packet) -> TCPSegment | None:
    raw = packet.payload
    if packet.protocol != 6 or len(raw) < 20:
        return None
    source, destination, sequence = struct.unpack_from("!HHI", raw, 0)
    header_length = (raw[12] >> 4) * 4
    if header_length < 20 or header_length > len(raw):
        return None
    return TCPSegment(source, destination, sequence, raw[13], raw[header_length:])


def reassemble(segments: list[tuple[int, bytes]]) -> bytes:
    """Reassemble one short capture direction, tolerating retransmitted bytes."""
    byte_at: dict[int, int] = {}
    for sequence, payload in segments:
        for offset, value in enumerate(payload):
            byte_at.setdefault(sequence + offset, value)
    if not byte_at:
        return b""
    cursor = min(byte_at)
    output = bytearray()
    while cursor in byte_at:
        output.append(byte_at[cursor])
        cursor += 1
    return bytes(output)


def text(raw: bytes) -> str:
    return raw.decode("ascii", errors="replace").rstrip(" \0")
