#!/usr/bin/env python3

"""Summarize tcpdump's one-line PTPv2 decode and correction fields."""

from __future__ import annotations

import argparse
import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path


TYPE_RE = re.compile(r"msg type : ([^,]+)")
CORRECTION_RE = re.compile(r"NS correction : ([+-]?\d+), sub NS correction : (\d+)")
DOMAIN_RE = re.compile(r"domain : (\d+)")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("decode", type=Path)
    args = parser.parse_args()

    counts: Counter[str] = Counter()
    domains: Counter[int] = Counter()
    corrections: dict[str, list[float]] = defaultdict(list)
    bad_checksum_lines = 0
    two_step_syncs = 0

    for line in args.decode.read_text(encoding="utf-8", errors="replace").splitlines():
        type_match = TYPE_RE.search(line)
        if not type_match:
            continue
        message_type = type_match.group(1).strip()
        counts[message_type] += 1
        if "bad udp cksum" in line:
            bad_checksum_lines += 1
        if message_type == "sync msg" and "Flags [two step]" in line:
            two_step_syncs += 1
        domain_match = DOMAIN_RE.search(line)
        if domain_match:
            domains[int(domain_match.group(1))] += 1
        correction_match = CORRECTION_RE.search(line)
        if correction_match:
            whole = int(correction_match.group(1))
            fraction = int(correction_match.group(2)) / 65536.0
            corrections[message_type].append(whole + fraction)

    correction_summary = {}
    for message_type, values in sorted(corrections.items()):
        correction_summary[message_type] = {
            "count": len(values),
            "nonzero_count": sum(value != 0 for value in values),
            "min_ns": min(values),
            "median_ns": statistics.median(values),
            "max_ns": max(values),
        }

    print(
        json.dumps(
            {
                "source": str(args.decode),
                "message_counts": dict(sorted(counts.items())),
                "domain_counts": dict(sorted(domains.items())),
                "two_step_sync_count": two_step_syncs,
                "bad_udp_checksum_decode_lines": bad_checksum_lines,
                "correction_fields": correction_summary,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
