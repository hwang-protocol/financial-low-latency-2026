#!/usr/bin/env python3
"""Decode the live MoldUDP64/ITCH packet captured by run 01."""

from __future__ import annotations

import argparse
import collections
import struct

from pcap_tools import parse_ethernet_ipv4, parse_udp, read_pcap, text

ITCH_TYPE = {
    "A": "Add Order",
    "D": "Order Delete",
    "E": "Order Executed",
    "P": "Trade",
    "U": "Order Replace",
}


def mold(payload: bytes) -> tuple[str, int, list[bytes]]:
    """拆开 MoldUDP64：Session、Sequence Number、Message Count 和各条 ITCH。"""
    if len(payload) < 20:
        raise ValueError("short MoldUDP64 header")
    session = text(payload[:10])
    sequence, count = struct.unpack_from("!QH", payload, 10)
    if not session or count == 0xFFFF:
        raise ValueError("unsupported MoldUDP64 control packet")
    cursor, messages = 20, []
    for _ in range(count):
        if cursor + 2 > len(payload):
            raise ValueError("truncated MoldUDP64 message length")
        length = struct.unpack_from("!H", payload, cursor)[0]
        cursor += 2
        if not length or cursor + length > len(payload):
            raise ValueError("truncated MoldUDP64 message")
        messages.append(payload[cursor:cursor + length])
        cursor += length
    if cursor != len(payload):
        raise ValueError("trailing MoldUDP64 bytes")
    return session, sequence, messages


def format_mac(raw: bytes) -> str:
    """把 6 字节 MAC 写成冒号分隔的十六进制。"""
    return ":".join(f"{byte:02x}" for byte in raw)


def print_packet_details(sample: dict) -> None:
    """按 Wireshark Packet Details 树打印样例帧，字段名用官方英文。"""
    frame = sample["frame"]
    ip = sample["ip"]
    udp = sample["udp"]
    message = sample["message"]
    kind = chr(message[0])
    print(f"Frame {sample['number']}: {len(frame)} bytes on wire, {len(frame)} bytes captured")
    print(f"Ethernet II, Src: {format_mac(frame[6:12])}, Dst: {format_mac(frame[0:6])}")
    print(f"Internet Protocol Version 4, Src: {ip.source}, Dst: {ip.destination}")
    print(f"User Datagram Protocol, Src Port: {udp.source_port}, Dst Port: {udp.destination_port}")
    print("MoldUDP64")
    print(f"    Session: {sample['session']}")
    print(f"    Sequence Number: {sample['sequence']}")
    print(f"    Message Count: {sample['count']}")
    print(f"    Message Length: {len(message)}")
    print(f"Nasdaq TotalView-ITCH 5.0")
    print(f"    Message Type: {kind} ({ITCH_TYPE.get(kind, kind)})")
    print(f"    Stock Locate: {struct.unpack_from('!H', message, 1)[0]}")
    print(f"    Tracking Number: {struct.unpack_from('!H', message, 3)[0]}")
    print(f"    Timestamp: {int.from_bytes(message[5:11], 'big')}")
    print(f"    Order Reference Number: {struct.unpack_from('!Q', message, 11)[0]}")
    print(f"    Buy/Sell Indicator: {chr(message[19])}")
    print(f"    Shares: {struct.unpack_from('!I', message, 20)[0]}")
    print(f"    Stock: {text(message[24:32])}")
    print(f"    Price: {struct.unpack_from('!I', message, 32)[0]}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pcap")
    args = parser.parse_args()
    magic, linktype, packets = read_pcap(args.pcap)
    assert linktype == 1, f"expected Ethernet linktype, got {linktype}"
    molds, counts, types, samples = [], [], collections.Counter(), []
    for captured in packets:
        ip = parse_ethernet_ipv4(captured.data)
        if not ip:
            continue
        udp = parse_udp(ip)
        if not udp or ip.source != "20.1.1.1" or ip.destination != "233.74.125.32" or udp.destination_port != 31032:
            continue
        session, first, messages = mold(udp.payload)
        molds.append((session, first, len(messages), udp.source_port))
        counts.append(len(messages))
        for index, message in enumerate(messages):
            kind = chr(message[0]) if message else "?"
            types[kind] += 1
            if kind in "AF" and len(message) >= 36 and text(message[24:32]) in {"AAPL", "NVDA"}:
                samples.append({
                    "number": len(molds),
                    "frame": captured.data,
                    "ip": ip,
                    "udp": udp,
                    "session": session,
                    "sequence": first + index,
                    "count": len(messages),
                    "message": message,
                })
    assert len(packets) == len(molds) == 200 and samples, "capture is not 200 live MoldUDP64 packets"
    sessions = {entry[0] for entry in molds}
    assert len(sessions) == 1
    all_sequences = [entry[1] + index for entry in molds for index in range(entry[2])]
    assert all(count > 0 for count in counts)
    assert len(set(all_sequences)) == len(all_sequences)
    assert max(all_sequences) - min(all_sequences) + 1 == len(all_sequences), "captured Mold sequence is not continuous"
    summary = ",".join(f"{kind}:{amount}" for kind, amount in sorted(types.items()))
    print(f"pcap_magic={magic} linktype={linktype} packets={len(packets)} mold_packets={len(molds)}")
    print(f"path=20.1.1.1:{molds[0][3]}->233.74.125.32:31032 session={next(iter(sessions))}")
    print(f"sequence={min(all_sequences)}..{max(all_sequences)} message_count={min(counts)}..{max(counts)} itch_types={summary}")
    print_packet_details(samples[0])
    print("verdict=LIVE_MARKET_FLOW_PASS")


if __name__ == "__main__":
    main()
