#!/usr/bin/env python3
"""Create the audit manifest for a byte-preserving filtered ITCH file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--output-sha256", required=True)
    parser.add_argument("--stats", required=True)
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()
    source = Path(args.source).resolve()
    output = Path(args.output).resolve()
    stats = json.loads(Path(args.stats).read_text(encoding="utf-8"))
    manifest = {
        "schema": "flle.itch-replay-manifest.v1",
        "source": "NASDAQ_PUBLIC_ITCH_SAMPLE",
        "source_url": "https://emi.nasdaq.com/ITCH/Nasdaq%20ITCH/S061226-v50.txt.gz",
        "source_file": source.name,
        "source_compressed_bytes": source.stat().st_size,
        "source_sha256": args.source_sha256,
        "market_date": "2026-06-12",
        "protocol": "Nasdaq TotalView-ITCH 5.0 / BinaryFILE",
        "symbols": ["AAPL", "NVDA"],
        "byte_preserving_filter": True,
        "truncated_input": False,
        "output_file": output.name,
        "output_sha256": args.output_sha256,
        **stats,
    }
    if int(manifest["output_bytes"]) != output.stat().st_size:
        raise SystemExit("filter stats/output size mismatch")
    Path(args.manifest).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
