#!/usr/bin/env python3
"""Print per-key deltas between two bpftool dumps of the PERCPU counters map."""
import json
import sys

NAMES = ["COURSE_UDP", "MOLD_HEARTBEAT", "AAPL_STOCK", "NVDA_STOCK", "OTHER_ITCH", "SHORT_INPUT", "POLICY_DROP"]


def load(path):
    out = {}
    for row in json.load(open(path)):
        f = row.get("formatted", row)
        key = f["key"] if isinstance(f["key"], int) else int.from_bytes(bytes(int(b, 16) for b in f["key"]), "little")
        total = 0
        for item in f["values"]:
            v = item["value"]
            total += v if isinstance(v, int) else int.from_bytes(bytes(int(b, 16) for b in v), "little")
        out[key] = total
    return out


a, b = load(sys.argv[1]), load(sys.argv[2])
for k, name in enumerate(NAMES):
    print(f"{name:15s} total={b.get(k, 0):8d}  delta={b.get(k, 0) - a.get(k, 0):6d}")
