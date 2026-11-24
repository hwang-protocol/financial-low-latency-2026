#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-02-fail-closed"
OUT="Documents/reports/course-runs/$RUN_ID"
mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"

printf '===== root@10.1.1.101 · python3 =====\n'; ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.101 \
  python3 - <<'PY' 2>&1 | tee "$OUT/raw/result.txt"
import struct

header = struct.Struct("!HBBHHIQQI")
tick = struct.Struct("!H4sHIII")
body = tick.pack(0x4D44, b"AAPL", 0, 1234501, 10, 1)
good = header.pack(0x464C, 1, 1, 0, 32, 20, 7, 701, 1) + body

def decode(packet):
    if len(packet) != 52:
        raise ValueError("BAD_PACKET_SIZE")
    fields = header.unpack(packet[:32])
    if fields[0] != 0x464C:
        raise ValueError("BAD_MAGIC")
    if fields[1] != 1:
        raise ValueError("BAD_VERSION")
    if fields[4] != 32 or fields[5] != 20:
        raise ValueError("BAD_LENGTH")
    return "ACCEPTED"

cases = [
    ("good", good, "ACCEPTED"),
    ("magic", bytes([0, 0]) + good[2:], "BAD_MAGIC"),
    ("version", good[:2] + bytes([9]) + good[3:], "BAD_VERSION"),
    ("length", good[:8] + bytes([0, 0, 0, 19]) + good[12:], "BAD_LENGTH"),
]
for name, packet, expected in cases:
    try:
        result = decode(packet)
    except ValueError as error:
        result = str(error)
    assert result == expected, (name, result, expected)
    print(name + "=" + result)
PY

(cd "$OUT" && sha256sum raw/result.txt run.env >SHA256SUMS); printf 'evidence=%s\n' "$OUT"
