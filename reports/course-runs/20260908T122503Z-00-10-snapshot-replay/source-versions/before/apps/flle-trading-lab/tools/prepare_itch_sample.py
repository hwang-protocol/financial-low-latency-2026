#!/usr/bin/env python3
"""Filter a Nasdaq BinaryFILE stream to AAPL/NVDA without changing ITCH bytes.

This is an offline data-preparation tool, not part of the measured trading path.
The output remains BinaryFILE: a two-byte big-endian length followed by the
original, byte-for-byte ITCH 5.0 message.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import struct
import sys
from collections import Counter
from pathlib import Path


TARGETS = {"AAPL", "NVDA"}
SYMBOL_OFFSETS = {
    ord("R"): 11,
    ord("H"): 11,
    ord("Y"): 11,
    ord("L"): 11,
    ord("N"): 11,
    ord("A"): 24,
    ord("F"): 24,
    ord("P"): 24,
    ord("Q"): 19,
    ord("I"): 28,
}


def symbol_at(message: bytes, offset: int) -> str:
    if len(message) < offset + 8:
        return ""
    return message[offset : offset + 8].decode("ascii", "strict").rstrip(" ")


def u32(message: bytes, offset: int) -> int:
    return struct.unpack_from("!I", message, offset)[0]


def u64(message: bytes, offset: int) -> int:
    return struct.unpack_from("!Q", message, offset)[0]


def timestamp_ns(message: bytes) -> int | None:
    if len(message) < 11:
        return None
    return int.from_bytes(message[5:11], "big")


def should_keep(message: bytes, orders: dict[int, tuple[str, int]]) -> bool:
    kind = message[0]
    if kind == ord("S"):
        return True
    if kind in SYMBOL_OFFSETS:
        symbol = symbol_at(message, SYMBOL_OFFSETS[kind])
        if symbol not in TARGETS:
            return False
        if kind in (ord("A"), ord("F")) and len(message) >= 36:
            orders[u64(message, 11)] = (symbol, u32(message, 20))
        return True
    if kind in (ord("E"), ord("C"), ord("X"), ord("D")):
        if len(message) < 19:
            return False
        reference = u64(message, 11)
        current = orders.get(reference)
        if current is None:
            return False
        if kind == ord("D"):
            orders.pop(reference, None)
        elif len(message) >= 23:
            remaining = max(0, current[1] - u32(message, 19))
            if remaining:
                orders[reference] = (current[0], remaining)
            else:
                orders.pop(reference, None)
        return True
    if kind == ord("U") and len(message) == 35:
        old_reference = u64(message, 11)
        current = orders.pop(old_reference, None)
        if current is None:
            return False
        orders[u64(message, 19)] = (current[0], u32(message, 27))
        return True
    return False


def run(args: argparse.Namespace) -> dict[str, object]:
    source = Path(args.input).resolve()
    destination = Path(args.output).resolve()
    manifest = Path(args.manifest).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    orders: dict[int, tuple[str, int]] = {}
    input_counts: Counter[str] = Counter()
    output_counts: Counter[str] = Counter()
    output_digest = hashlib.sha256()
    input_messages = 0
    output_messages = 0
    first_timestamp: int | None = None
    last_timestamp: int | None = None
    truncated = False

    try:
        with gzip.open(source, "rb") as reader, temporary.open("wb") as writer:
            while True:
                prefix = reader.read(2)
                if not prefix:
                    break
                if len(prefix) != 2:
                    raise EOFError("truncated BinaryFILE length prefix")
                length = struct.unpack("!H", prefix)[0]
                if length == 0:
                    continue
                message = reader.read(length)
                if len(message) != length:
                    raise EOFError("truncated BinaryFILE message")
                input_messages += 1
                kind = chr(message[0])
                input_counts[kind] += 1
                if not should_keep(message, orders):
                    continue
                record = prefix + message
                writer.write(record)
                output_digest.update(record)
                output_messages += 1
                output_counts[kind] += 1
                timestamp = timestamp_ns(message)
                if timestamp is not None:
                    first_timestamp = timestamp if first_timestamp is None else first_timestamp
                    last_timestamp = timestamp
    except (EOFError, gzip.BadGzipFile) as error:
        if not args.allow_truncated:
            temporary.unlink(missing_ok=True)
            raise
        truncated = True
        print(f"warning: accepted truncated gzip stream: {error}", file=sys.stderr)

    os.replace(temporary, destination)
    result: dict[str, object] = {
        "schema": "flle.itch-replay-manifest.v1",
        "source": "NASDAQ_PUBLIC_ITCH_SAMPLE",
        "source_url": "https://emi.nasdaq.com/ITCH/Nasdaq%20ITCH/S061226-v50.txt.gz",
        "source_file": source.name,
        "source_compressed_bytes": source.stat().st_size,
        "source_sha256": args.source_sha256 or None,
        "market_date": "2026-06-12",
        "protocol": "Nasdaq TotalView-ITCH 5.0 / BinaryFILE",
        "symbols": sorted(TARGETS),
        "byte_preserving_filter": True,
        "truncated_input": truncated,
        "input_messages_seen": input_messages,
        "output_messages": output_messages,
        "output_bytes": destination.stat().st_size,
        "output_sha256": output_digest.hexdigest(),
        "first_timestamp_ns": first_timestamp,
        "last_timestamp_ns": last_timestamp,
        "input_type_counts": dict(sorted(input_counts.items())),
        "output_type_counts": dict(sorted(output_counts.items())),
    }
    manifest.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--allow-truncated", action="store_true")
    parser.add_argument("--source-sha256", default="")
    args = parser.parse_args()
    if args.source_sha256 and (
        len(args.source_sha256) != 64
        or any(character not in "0123456789abcdefABCDEF" for character in args.source_sha256)
    ):
        parser.error("--source-sha256 must be 64 hexadecimal characters")
    result = run(args)
    print(json.dumps(result, separators=(",", ":"), sort_keys=True))


if __name__ == "__main__":
    main()
