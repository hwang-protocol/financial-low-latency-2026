#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-03-tcp-framing"; ASSET="Documents/newDoc/assets/03-network/02-tcp-framing.sh"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\nsource_asset=%s\nsource_sha256=%s\nhost=%s\npython=%s\n' "$RUN_ID" "$ASSET" "$(sha256sum "$ASSET" | cut -d' ' -f1)" "$(hostname)" "$(python3 --version 2>&1)" >"$OUT/run.env"

ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.1 \
  python3 -u - <<'PY' >"$OUT/raw/server.txt" 2>&1 &
import socket, struct
s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("20.1.1.1", 42103)); s.listen(1)
c, peer = s.accept()
a = b"ACK"; b = b"EXECUTION"
c.sendall(struct.pack("!I", len(a)) + a + struct.pack("!I", len(b)) + b)
print("sent_frames=ACK,EXECUTION", flush=True)
c.close(); s.close()
PY
server_pid=$!; trap 'kill "$server_pid" 2>/dev/null || true' EXIT; sleep 0.5
printf '===== root@10.1.1.2 · TCP client =====\n'; ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
  python3 -u - <<'PY' 2>&1 | tee "$OUT/raw/client.txt"
import socket, struct
def read_exact(sock, size):
    data = b""
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk: raise RuntimeError("early EOF")
        data += chunk
    return data
def read_frame(sock):
    size = struct.unpack("!I", read_exact(sock, 4))[0]
    return read_exact(sock, size)
s = socket.create_connection(("20.1.1.1", 42103), timeout=3)
first = read_frame(s); second = read_frame(s)
print("frame1=%s frame2=%s" % (first.decode(), second.decode()))
PY
wait "$server_pid"; trap - EXIT; printf '===== root@10.1.1.1 · TCP server =====\n'; cat "$OUT/raw/server.txt"
(cd "$OUT" && sha256sum raw/*.txt run.env >SHA256SUMS); printf 'evidence=%s\n' "$OUT"
