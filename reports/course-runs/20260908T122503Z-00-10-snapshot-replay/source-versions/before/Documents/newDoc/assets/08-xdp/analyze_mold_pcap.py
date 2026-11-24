#!/usr/bin/env python3
"""Count course MoldUDP64/ITCH packets in an XDP before/after capture."""

from __future__ import annotations

import argparse
import collections
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "03-live-traffic"))
from pcap_tools import parse_ethernet_ipv4, parse_udp, read_pcap, text  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pcap")
    parser.add_argument("--expect-nvda", choices=("present", "absent"))
    args = parser.parse_args()
    _, linktype, packets = read_pcap(args.pcap)
    assert linktype == 1, f"expected Ethernet linktype, got {linktype}"
    types: collections.Counter[str] = collections.Counter()
    stocks: collections.Counter[str] = collections.Counter()
    sequences: list[int] = []
    short = 0
    for captured in packets:
        ip = parse_ethernet_ipv4(captured.data)
        if not ip:
            continue
        udp = parse_udp(ip)
        if not udp or ip.source != "20.1.1.1" or ip.destination != "233.74.125.32":
            continue
        if udp.destination_port != 31032 or len(udp.payload) < 20:
            continue
        sequence, count = struct.unpack_from("!QH", udp.payload, 10)
        cursor = 20
        for index in range(count if count != 0xFFFF else 0):
            if cursor + 2 > len(udp.payload):
                short += 1
                break
            length = struct.unpack_from("!H", udp.payload, cursor)[0]
            cursor += 2
            if not length or cursor + length > len(udp.payload):
                short += 1
                break
            message = udp.payload[cursor:cursor + length]
            cursor += length
            kind = chr(message[0])
            types[kind] += 1
            sequences.append(sequence + index)
            if kind in "AFP" and len(message) >= 32:
                stocks[text(message[24:32])] += 1
    print(f"pcap={args.pcap} packets={len(packets)} itch={sum(types.values())} short={short}")
    print("types=" + ",".join(f"{key}:{types[key]}" for key in sorted(types)))
    print("stocks=" + ",".join(f"{key}:{stocks[key]}" for key in sorted(stocks)))
    if sequences:
        print(f"sequence_min={min(sequences)} sequence_max={max(sequences)}")
    nvda = stocks["NVDA"]
    if args.expect_nvda == "present":
        assert nvda > 0, "expected an NVDA A/F/P message after XDP"
    if args.expect_nvda == "absent":
        assert nvda == 0, f"expected XDP to hide NVDA A/F/P, got {nvda}"
    print(f"nvda_stock={nvda} verdict=PASS")


if __name__ == "__main__":
    main()
