#!/usr/bin/env python3
"""Compare A-only, B-only and A/B UDP multicast captures."""
from __future__ import annotations
import argparse
import collections
import struct
from pcap_tools import parse_ethernet_ipv4, parse_udp, read_pcap

A = ("233.74.125.32", 31032)
B = ("233.74.125.33", 31033)
UNICAST = ("20.1.1.2", 42121)


def summarize(path):
    _, linktype, packets = read_pcap(path)
    assert linktype == 1, "Ethernet pcap required"
    counts, messages = collections.Counter(), collections.defaultdict(dict)
    for captured in packets:
        ip = parse_ethernet_ipv4(captured.data)
        assert ip and ip.source == "20.1.1.1", "unexpected source in market capture"
        udp = parse_udp(ip)
        assert udp and len(udp.payload) >= 20, "invalid Mold datagram"
        endpoint = (ip.destination, udp.destination_port)
        assert endpoint in (A, B, UNICAST), "unexpected market endpoint"
        counts[endpoint] += 1
        session = udp.payload[:10]
        first, count = struct.unpack_from("!QH", udp.payload, 10)
        assert 0 < count < 65535, "this capture requires data messages"
        cursor = 20
        for index in range(count):
            assert cursor + 2 <= len(udp.payload), "truncated message length"
            size = struct.unpack_from("!H", udp.payload, cursor)[0]
            cursor += 2
            assert size and cursor + size <= len(udp.payload), "truncated message"
            key = (session, first + index)
            payload = udp.payload[cursor:cursor + size]
            previous = messages[endpoint].setdefault(key, payload)
            assert previous == payload, "same session/sequence has conflicting payloads"
            cursor += size
        assert cursor == len(udp.payload), "trailing Mold bytes"
    return counts, messages, len(packets)


def line(mode, counts, packets):
    return f"mode={mode} captured={packets} multicast_a={counts[A]} multicast_b={counts[B]}"


def main():
    parser = argparse.ArgumentParser()
    for name in ("a", "b", "dual"):
        parser.add_argument(name)
    for name in ("duplicates-before", "duplicates-after", "membership-users", "membership-users-b", "pending", "gaps"):
        parser.add_argument("--" + name, type=int, required=True)
    args = parser.parse_args()
    a, am, ap = summarize(args.a)
    b, bm, bp = summarize(args.b)
    dual, dm, dp = summarize(args.dual)
    assert ap > 0 and a[A] == ap and not a[B] and not a[UNICAST], "A-only capture contains another path"
    assert bp > 0 and b[B] == bp and not b[A] and not b[UNICAST], "B-only capture contains another path"
    assert dual[A] > 0 and dual[B] > 0 and not dual[UNICAST], "DUAL requires two multicast paths"
    overlap = dm[A].keys() & dm[B].keys()
    assert overlap and all(dm[A][key] == dm[B][key] for key in overlap), "A/B copies must carry identical messages"
    sessions = {session for data in (am[A], bm[B], dm[A], dm[B]) for session, _ in data}
    assert len(sessions) == 1, "the three windows must stay in the same replay session"
    delta = args.duplicates_after - args.duplicates_before
    assert args.membership_users == args.membership_users_b == 1 and delta > 0
    assert args.pending == 0 and args.gaps == 0
    print(line("MULTICAST_A", a, ap))
    print(line("MULTICAST_B", b, bp))
    print(line("DUAL", dual, dp))
    print(f"membership_a={args.membership_users} membership_b={args.membership_users_b} dual_sequence_overlap={len(overlap)} duplicate_delta={delta} pending={args.pending} gaps={args.gaps}")
    print("verdict=THREE_TRANSPORT_MODES_PASS")


if __name__ == "__main__":
    main()
