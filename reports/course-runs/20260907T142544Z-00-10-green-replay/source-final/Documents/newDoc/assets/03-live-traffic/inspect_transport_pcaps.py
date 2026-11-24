#!/usr/bin/env python3
"""Compare live UNICAST, MULTICAST and DUAL market captures."""

from __future__ import annotations

import argparse
import collections
import struct

from pcap_tools import parse_ethernet_ipv4, parse_udp, read_pcap


def summarize(path: str) -> tuple[collections.Counter[tuple[str, int]], dict[tuple[str, int], set[int]], int]:
    _, linktype, packets = read_pcap(path)
    assert linktype == 1
    counts: collections.Counter[tuple[str, int]] = collections.Counter()
    sequences: dict[tuple[str, int], set[int]] = collections.defaultdict(set)
    for captured in packets:
        ip = parse_ethernet_ipv4(captured.data)
        if not ip or ip.source != "20.1.1.1":
            continue
        udp = parse_udp(ip)
        if not udp or udp.destination_port not in (42120, 42121, 42122) or len(udp.payload) < 20:
            continue
        first, count = struct.unpack_from("!QH", udp.payload, 10)
        key = (ip.destination, udp.destination_port)
        counts[key] += 1
        sequences[key].update(range(first, first + count))
    return counts, sequences, len(packets)


def line(mode: str, counts: collections.Counter[tuple[str, int]], packets: int) -> str:
    return (f"mode={mode} captured={packets} multicast={counts[('239.20.1.20', 42120)]} "
            f"auto_unicast={counts[('20.1.1.2', 42121)]} manual_unicast={counts[('20.1.1.2', 42122)]}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("unicast")
    parser.add_argument("multicast")
    parser.add_argument("dual")
    parser.add_argument("--duplicates-before", type=int, required=True)
    parser.add_argument("--duplicates-after", type=int, required=True)
    parser.add_argument("--membership-users", type=int, required=True)
    parser.add_argument("--pending", type=int, required=True)
    parser.add_argument("--gaps", type=int, required=True)
    args = parser.parse_args()
    unicast, u_seq, u_packets = summarize(args.unicast)
    multicast, m_seq, m_packets = summarize(args.multicast)
    dual, d_seq, d_packets = summarize(args.dual)
    assert unicast[("239.20.1.20", 42120)] == 0 and unicast[("20.1.1.2", 42121)] > 0 and unicast[("20.1.1.2", 42122)] > 0
    assert multicast[("239.20.1.20", 42120)] > 0 and multicast[("20.1.1.2", 42121)] == 0 and multicast[("20.1.1.2", 42122)] == 0
    keys = (("239.20.1.20", 42120), ("20.1.1.2", 42121), ("20.1.1.2", 42122))
    assert all(dual[key] > 0 for key in keys)
    overlap = len(d_seq[keys[0]] & d_seq[keys[1]]) + len(d_seq[keys[0]] & d_seq[keys[2]])
    duplicate_delta = args.duplicates_after - args.duplicates_before
    assert args.membership_users == 2 and overlap > 0 and duplicate_delta > 0
    assert args.pending == 0 and args.gaps == 0
    print(line("UNICAST", unicast, u_packets))
    print(line("MULTICAST", multicast, m_packets))
    print(line("DUAL", dual, d_packets))
    print(f"membership=239.20.1.20 users={args.membership_users} dual_sequence_overlap={overlap} duplicate_delta={duplicate_delta} pending={args.pending} gaps={args.gaps}")
    print("verdict=THREE_TRANSPORT_MODES_PASS")


if __name__ == "__main__":
    main()
