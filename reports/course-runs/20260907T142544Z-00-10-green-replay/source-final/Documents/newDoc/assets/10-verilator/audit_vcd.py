#!/usr/bin/env python3

"""Audit required signals and activity in a Verilator VCD trace."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path


REQUIRED = (
    "clk",
    "rst_n",
    "s_valid",
    "s_ready",
    "m_valid",
    "m_ready",
    "fifo_level",
    "m_timestamp",
    "accepted_count",
    "matched_count",
    "bad_magic_count",
    "nonmatch_count",
    "stall_count",
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("vcd", type=Path)
    args = parser.parse_args()

    scopes: list[str] = []
    names_by_code: dict[str, list[str]] = defaultdict(list)
    transitions: dict[str, int] = defaultdict(int)
    in_header = True

    with args.vcd.open("r", encoding="utf-8", errors="replace") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if in_header:
                fields = line.split()
                if fields[:1] == ["$scope"] and len(fields) >= 3:
                    scopes.append(fields[2])
                elif fields[:1] == ["$upscope"] and scopes:
                    scopes.pop()
                elif fields[:1] == ["$var"] and len(fields) >= 6:
                    code = fields[3]
                    reference = fields[4]
                    names_by_code[code].append(".".join(scopes + [reference]))
                elif fields[:1] == ["$enddefinitions"]:
                    in_header = False
                continue

            code = None
            if line[:1] in {"0", "1", "x", "X", "z", "Z"}:
                code = line[1:]
            elif line[:1] in {"b", "B", "r", "R"}:
                fields = line.split()
                if len(fields) == 2:
                    code = fields[1]
            if code in names_by_code:
                transitions[code] += 1

    selected = {}
    missing = []
    inactive = []
    for required in REQUIRED:
        candidates = [
            (code, name)
            for code, names in names_by_code.items()
            for name in names
            if name == required or name.endswith("." + required)
        ]
        if not candidates:
            missing.append(required)
            continue
        code, full_name = max(candidates, key=lambda item: transitions[item[0]])
        count = transitions[code]
        selected[required] = {"full_name": full_name, "transitions": count}
        if count == 0:
            inactive.append(required)

    if in_header:
        raise SystemExit("VCD_AUDIT_FAIL enddefinitions_missing")
    if missing:
        raise SystemExit("VCD_AUDIT_FAIL missing=" + ",".join(missing))
    if inactive:
        raise SystemExit("VCD_AUDIT_FAIL inactive=" + ",".join(inactive))

    digest = hashlib.sha256(args.vcd.read_bytes()).hexdigest()
    print(
        json.dumps(
            {
                "status": "VCD_AUDIT_PASS",
                "path": str(args.vcd),
                "bytes": args.vcd.stat().st_size,
                "sha256": digest,
                "required_signals": selected,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

