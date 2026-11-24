#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-03-feed-recovery"; ASSET="Documents/newDoc/assets/03-network/07-feed-recovery.sh"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\nsource_asset=%s\nsource_sha256=%s\nhost=%s\npython=%s\n' "$RUN_ID" "$ASSET" "$(sha256sum "$ASSET" | cut -d' ' -f1)" "$(hostname)" "$(python3 --version 2>&1)" >"$OUT/run.env"
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
  python3 -u - <<'PY' >"$OUT/raw/handler.txt" 2>&1 &
import select, socket, struct
header = struct.Struct("!HBBHHIQQI"); tick = struct.Struct("!H4sHIII")
def decode(data):
    if len(data) != 52: raise ValueError("BAD_PACKET_SIZE")
    head = header.unpack(data[:32]); body = tick.unpack(data[32:])
    if head[:6] != (0x464C, 1, 1, 0, 32, 20) or head[6] != 7 or body[0] != 0x4D44 or body[5] != head[8]: raise ValueError("BAD_WIRE_V1")
    return head[8]
feeds = [("A", "239.20.2.1", 42109), ("B", "239.20.2.2", 42110)]
sockets = []; names = {}
for name, group, port in feeds:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); s.bind(("", port))
    s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
                 socket.inet_aton(group) + socket.inet_aton("20.1.1.2"))
    sockets.append(s); names[s] = name
accepted = {}; duplicates = receipts = 0
while receipts < 11:
    ready = select.select(sockets, [], [], 3)[0]
    if not ready: raise TimeoutError("no feed datagram")
    for s in ready:
        sequence = decode(s.recv(2048)); receipts += 1
        if sequence in accepted: duplicates += 1
        else: accepted[sequence] = names[s]
print("receipts=%d sequence4_source=%s accepted=%s duplicates=%d" % (receipts, accepted[4], sorted(accepted), duplicates), flush=True)
PY
handler_pid=$!; trap 'kill "$handler_pid" 2>/dev/null || true' EXIT; sleep 0.5
printf '===== root@10.1.1.1 · Feed sender =====\n'; ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.1 \
  python3 - <<'PY' 2>&1 | tee "$OUT/raw/sender.txt"
import socket, struct
header = struct.Struct("!HBBHHIQQI"); tick = struct.Struct("!H4sHIII")
def make(sequence):
    body = tick.pack(0x4D44, b"AAPL", 0, 1234501, 10, sequence)
    return header.pack(0x464C, 1, 1, 0, 32, 20, 7, 701, sequence) + body
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton("20.1.1.1"))
for sequence in [0, 1, 2, 3, 5]: s.sendto(make(sequence), ("239.20.2.1", 42109))
for sequence in range(6): s.sendto(make(sequence), ("239.20.2.2", 42110))
print("feed_A=0,1,2,3,5 feed_B=0,1,2,3,4,5")
PY
wait "$handler_pid"; trap - EXIT
printf '===== root@10.1.1.2 · Feed handler =====\n'; cat "$OUT/raw/handler.txt"
(cd "$OUT" && sha256sum raw/*.txt run.env >SHA256SUMS); printf 'evidence=%s\n' "$OUT"
