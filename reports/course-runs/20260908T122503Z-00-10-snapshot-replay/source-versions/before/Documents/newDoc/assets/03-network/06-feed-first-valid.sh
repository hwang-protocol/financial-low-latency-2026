#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-03-feed-first-valid"; ASSET="Documents/newDoc/assets/03-network/06-feed-first-valid.sh"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\nsource_asset=%s\nsource_sha256=%s\nhost=%s\npython=%s\n' "$RUN_ID" "$ASSET" "$(sha256sum "$ASSET" | cut -d' ' -f1)" "$(hostname)" "$(python3 --version 2>&1)" >"$OUT/run.env"
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 python3 -u - <<'PY' >"$OUT/raw/handler.txt" 2>&1 &
import select, socket, struct; header = struct.Struct("!HBBHHIQQI"); tick = struct.Struct("!H4sHIII")
def decode(data):
    if len(data) != 52: raise ValueError("BAD_PACKET_SIZE")
    head = header.unpack(data[:32]); body = tick.unpack(data[32:])
    if head[:6] != (0x464C, 1, 1, 0, 32, 20) or head[6] != 7 or body[0] != 0x4D44 or body[5] != head[8]: raise ValueError("BAD_WIRE_V1")
    return head[6], head[8]
feeds = [("A", "239.20.1.1", 42107), ("B", "239.20.1.2", 42108)]
sockets = []; names = {}
for name, group, port in feeds:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); s.bind(("", port))
    s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, socket.inet_aton(group) + socket.inet_aton("20.1.1.2"))
    sockets.append(s); names[s] = name
accepted = {}; rejected = duplicates = receipts = 0
while receipts < 3:
    ready = select.select(sockets, [], [], 3)[0]
    if not ready: raise TimeoutError("no feed datagram")
    for s in ready:
        data = s.recv(2048); source = names[s]; receipts += 1
        try: key = decode(data)
        except ValueError as error:
            rejected += 1; print("source=%s event=REJECTED reason=%s" % (source, error), flush=True); continue
        if key in accepted:
            duplicates += 1; print("source=%s event=DUPLICATE sequence=%d" % (source, key[1]), flush=True)
        else:
            accepted[key] = source; print("source=%s event=ACCEPTED sequence=%d" % (source, key[1]), flush=True)
print("accepted_source=%s rejected=%d duplicates=%d" % (accepted[(7, 0)], rejected, duplicates), flush=True)
PY
handler_pid=$!; trap 'kill "$handler_pid" 2>/dev/null || true' EXIT; sleep 0.5
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.1 python3 - <<'PY' >"$OUT/raw/sender.txt" 2>&1
import socket, struct, time
header = struct.Struct("!HBBHHIQQI"); tick = struct.Struct("!H4sHIII")
def make(sequence):
    body = tick.pack(0x4D44, b"AAPL", 0, 1234501, 10, sequence)
    return header.pack(0x464C, 1, 1, 0, 32, 20, 7, 701, sequence) + body
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton("20.1.1.1"))
bad = bytearray(make(0)); bad[32:34] = b"\x00\x00"
for payload, target in [(bad, ("239.20.1.1", 42107)), (make(0), ("239.20.1.2", 42108)), (make(0), ("239.20.1.1", 42107))]:
    s.sendto(payload, target); time.sleep(0.1)
print("sent=A_BAD,B_VALID,A_VALID")
PY
wait "$handler_pid"; trap - EXIT; cat "$OUT/raw/handler.txt"
(cd "$OUT" && sha256sum raw/*.txt run.env >SHA256SUMS); printf 'evidence=%s\n' "$OUT"
