#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-03-multicast-membership"; ASSET="Documents/newDoc/assets/03-network/04-multicast-membership.sh"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\nsource_asset=%s\nsource_sha256=%s\nhost=%s\npython=%s\n' "$RUN_ID" "$ASSET" "$(sha256sum "$ASSET" | cut -d' ' -f1)" "$(hostname)" "$(python3 --version 2>&1)" >"$OUT/run.env"

ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
  python3 -u - <<'PY' >"$OUT/raw/receiver.txt" 2>&1 &
import socket, struct
header = struct.Struct("!HBBHHIQQI"); tick = struct.Struct("!H4sHIII")
def decode(data):
    if len(data) != 52: raise ValueError("BAD_PACKET_SIZE")
    head = header.unpack(data[:32]); body = tick.unpack(data[32:])
    if head[:6] != (0x464C, 1, 1, 0, 32, 20) or body[0] != 0x4D44 or body[5] != head[8]: raise ValueError("BAD_WIRE_V1")
    return head[8]
group = "239.20.0.5"; port = 42105
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); s.bind(("", port))
membership = socket.inet_aton(group) + socket.inet_aton("20.1.1.2")
s.settimeout(0.7)
try: decode(s.recvfrom(2048)[0]); pre = 1
except socket.timeout: pre = 0
s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, membership)
s.settimeout(2); joined = decode(s.recvfrom(2048)[0])
s.setsockopt(socket.IPPROTO_IP, socket.IP_DROP_MEMBERSHIP, membership)
s.settimeout(0.7)
try: decode(s.recvfrom(2048)[0]); post = 1
except socket.timeout: post = 0
print("pre=%d joined_sequence=%d post=%d" % (pre, joined, post), flush=True)
PY
receiver_pid=$!; trap 'kill "$receiver_pid" 2>/dev/null || true' EXIT; sleep 0.2
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.1 python3 - <<'PY' >"$OUT/raw/sender.txt" 2>&1
import socket, struct, time
header = struct.Struct("!HBBHHIQQI"); tick = struct.Struct("!H4sHIII")
def make(sequence):
    body = tick.pack(0x4D44, b"AAPL", 0, 1234501, 10, sequence)
    return header.pack(0x464C, 1, 1, 0, 32, 20, 7, 701, sequence) + body
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton("20.1.1.1"))
for delay, sequence in [(0.1, 0), (0.8, 1), (0.2, 2)]:
    time.sleep(delay); s.sendto(make(sequence), ("239.20.0.5", 42105))
print("sent_sequences=0,1,2")
PY
wait "$receiver_pid"; trap - EXIT
cat "$OUT/raw/sender.txt"; cat "$OUT/raw/receiver.txt"
(cd "$OUT" && sha256sum raw/*.txt run.env >SHA256SUMS); printf 'evidence=%s\n' "$OUT"
