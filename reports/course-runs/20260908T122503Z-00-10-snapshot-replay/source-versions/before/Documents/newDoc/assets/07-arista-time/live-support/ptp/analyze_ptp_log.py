#!/usr/bin/env python3

"""Summarize linuxptp master-offset samples without changing test state."""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
from pathlib import Path


SAMPLE_RE = re.compile(
    r"master offset\s+([+-]?\d+)\s+s([012])\s+freq\s+([+-]?\d+)\s+path delay\s+([+-]?\d+)"
)


def percentile(values: list[int], probability: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = (len(ordered) - 1) * probability
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return float(ordered[lower])
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (rank - lower)


def stats(values: list[int]) -> dict[str, float | int | None]:
    return {
        "count": len(values),
        "min": min(values) if values else None,
        "median": statistics.median(values) if values else None,
        "max": max(values) if values else None,
        "mean": statistics.fmean(values) if values else None,
        "p95": percentile(values, 0.95),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    parser.add_argument("--tail", type=int, default=20)
    args = parser.parse_args()

    samples: list[dict[str, int]] = []
    for line in args.log.read_text(encoding="utf-8", errors="replace").splitlines():
        match = SAMPLE_RE.search(line)
        if match:
            offset, state, frequency, delay = map(int, match.groups())
            samples.append(
                {
                    "offset_ns": offset,
                    "state": state,
                    "frequency_ppb": frequency,
                    "path_delay_ns": delay,
                }
            )

    locked = [sample for sample in samples if sample["state"] == 2]
    tail = locked[-args.tail :]
    output = {
        "source": str(args.log),
        "all_sample_count": len(samples),
        "state_counts": {
            f"s{state}": sum(sample["state"] == state for sample in samples)
            for state in (0, 1, 2)
        },
        "locked_sample_count": len(locked),
        "locked_all": {
            "offset_ns": stats([sample["offset_ns"] for sample in locked]),
            "abs_offset_ns": stats([abs(sample["offset_ns"]) for sample in locked]),
            "path_delay_ns": stats([sample["path_delay_ns"] for sample in locked]),
            "frequency_ppb": stats([sample["frequency_ppb"] for sample in locked]),
        },
        "locked_tail": {
            "requested_count": args.tail,
            "actual_count": len(tail),
            "offset_ns": stats([sample["offset_ns"] for sample in tail]),
            "abs_offset_ns": stats([abs(sample["offset_ns"]) for sample in tail]),
            "path_delay_ns": stats([sample["path_delay_ns"] for sample in tail]),
            "frequency_ppb": stats([sample["frequency_ppb"] for sample in tail]),
        },
    }
    print(json.dumps(output, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
