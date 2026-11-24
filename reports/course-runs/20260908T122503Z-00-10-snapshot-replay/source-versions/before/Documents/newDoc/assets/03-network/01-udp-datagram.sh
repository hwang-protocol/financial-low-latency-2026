#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-03-udp-datagram"; ASSET="Documents/newDoc/assets/03-network/01-udp-datagram.sh"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\nsource_asset=%s\nsource_sha256=%s\nhost=%s\npython=%s\n' "$RUN_ID" "$ASSET" "$(sha256sum "$ASSET" | cut -d' ' -f1)" "$(hostname)" "$(python3 --version 2>&1)" >"$OUT/run.env"

ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
  python3 -u - <<'PY' >"$OUT/raw/receiver.txt" 2>&1 &
import socket, struct
header = struct.Struct("!HBBHHIQQI"); tick = struct.Struct("!H4sHIII")
def decode(data):
    if len(data) != 52: raise ValueError("BAD_PACKET_SIZE")
    head = header.unpack(data[:32]); body = tick.unpack(data[32:])
    if head[:6] != (0x464C, 1, 1, 0, 32, 20): raise ValueError("BAD_HEADER")
    if body[0] != 0x4D44 or body[5] != head[8]: raise ValueError("BAD_TICK")
    return head, body
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.settimeout(3); s.bind(("20.1.1.2", 42101))
for unused in range(5):
    data, peer = s.recvfrom(2048); head, body = decode(data)
    print("bytes=%d magic=0x%04x version=%d session=%d sequence=%d symbol=%s" %
          (len(data), head[0], head[1], head[6], head[8], body[1].decode()), flush=True)
PY
receiver_pid=$!
trap 'kill "$receiver_pid" 2>/dev/null || true' EXIT
sleep 0.5

printf '===== root@10.1.1.1 · UDP sender =====\n'; ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.1 \
  python3 - <<'PY' 2>&1 | tee "$OUT/raw/sender.txt"
import socket, struct
header = struct.Struct("!HBBHHIQQI"); tick = struct.Struct("!H4sHIII")
def make(sequence):
    body = tick.pack(0x4D44, b"AAPL", 0, 1234501, 10, sequence)
    return header.pack(0x464C, 1, 1, 0, 32, 20, 7, 701, sequence) + body
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.bind(("20.1.1.1", 0))
for sequence in range(5): s.sendto(make(sequence), ("20.1.1.2", 42101))
print("sent_sequences=0,1,2,3,4")
PY
wait "$receiver_pid"; trap - EXIT
printf '===== root@10.1.1.2 · UDP receiver =====\n'; cat "$OUT/raw/receiver.txt"
(cd "$OUT" && sha256sum raw/*.txt run.env >SHA256SUMS); printf 'evidence=%s\n' "$OUT"
