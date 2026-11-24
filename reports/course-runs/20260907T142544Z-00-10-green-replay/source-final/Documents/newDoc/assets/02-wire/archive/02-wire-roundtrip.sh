#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-02-wire-roundtrip"
OUT="Documents/reports/course-runs/$RUN_ID"
mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"

printf '===== root@10.1.1.101 · python3 =====\n'; ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.101 \
  python3 - <<'PY' 2>&1 | tee "$OUT/raw/result.txt"
import struct

# Header 是前 32 bytes：magic/version/type/length/session/correlation/sequence。
header = struct.Struct("!HBBHHIQQI")

# Tick Body 是后 20 bytes：body magic、4-byte symbol、flags、price、quantity、tick sequence。
tick = struct.Struct("!H4sHIII")

# 先打包正文。b"AAPL"表示线上固定写入 4 个 ASCII 字节。
body = tick.pack(0x4D44, b"AAPL", 0, 1234501, 10, 1)

# 再打包 Header，并把 Header + Body 拼成一条完整 52-byte packet。
packet = header.pack(0x464C, 1, 1, 0, 32, len(body), 7, 701, 1) + body

# 接收端按固定偏移切片：前 32 bytes 解 Header，后 20 bytes 解 Tick Body。
head_fields = header.unpack(packet[:32])
tick_fields = tick.unpack(packet[32:])

# 全字段自检，并锁住 Tick 的双 sequence 合同。
expected_head = (0x464C, 1, 1, 0, 32, 20, 7, 701, 1)
expected_tick = (0x4D44, b"AAPL", 0, 1234501, 10, 1)
assert head_fields == expected_head
assert tick_fields == expected_tick
assert head_fields[8] == tick_fields[5]

print("packet_bytes=%d" % len(packet))
print("packet_hex=%s" % packet.hex())
print("header=magic:0x%04x version:%d type:%d reserved:%d "
      "header_length:%d body_length:%d session:%d correlation:%d sequence:%d" %
      head_fields)
print("body=magic:0x%04x symbol:%s flags:%d price:%d quantity:%d tick_sequence:%d" %
      (tick_fields[0], tick_fields[1].decode(), *tick_fields[2:]))
PY

(cd "$OUT" && sha256sum raw/result.txt run.env >SHA256SUMS); printf 'evidence=%s\n' "$OUT"
