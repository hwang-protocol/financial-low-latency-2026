#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-03-order-responses"; ASSET="Documents/newDoc/assets/03-network/03-order-responses.sh"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\nsource_asset=%s\nsource_sha256=%s\nhost=%s\npython=%s\n' "$RUN_ID" "$ASSET" "$(sha256sum "$ASSET" | cut -d' ' -f1)" "$(hostname)" "$(python3 --version 2>&1)" >"$OUT/run.env"

ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.1 \
  python3 -u - <<'PY' >"$OUT/raw/server.txt" 2>&1 &
import socket, struct
def frame(text): return struct.pack("!I", len(text)) + text
def read_exact(sock, size):
    data = b""
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk: raise RuntimeError("early EOF")
        data += chunk
    return data
s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
s.bind(("20.1.1.1", 42104)); s.listen(1); c, peer = s.accept()
size = struct.unpack("!I", read_exact(c, 4))[0]; order = read_exact(c, size).decode()
print("received=" + order, flush=True)
correlation = order.split(":")[1]
c.sendall(frame(("ACK:" + correlation).encode()))
c.sendall(frame(("EXECUTION:" + correlation).encode()))
c.close(); s.close()
PY
server_pid=$!; trap 'kill "$server_pid" 2>/dev/null || true' EXIT; sleep 0.5
printf '===== root@10.1.1.2 · Trader client =====\n'; ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
  python3 -u - <<'PY' 2>&1 | tee "$OUT/raw/client.txt"
import socket, struct
def frame(text): return struct.pack("!I", len(text)) + text
def read_exact(sock, size):
    data = b""
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk: raise RuntimeError("early EOF")
        data += chunk
    return data
def read_frame(sock):
    size = struct.unpack("!I", read_exact(sock, 4))[0]
    return read_exact(sock, size).decode()
s = socket.create_connection(("20.1.1.1", 42104), timeout=3)
s.sendall(frame(b"ORDER:7001")); ack = read_frame(s); execution = read_frame(s)
print(ack); print(execution)
PY
wait "$server_pid"; trap - EXIT; printf '===== root@10.1.1.1 · Exchange server =====\n'; cat "$OUT/raw/server.txt"
(cd "$OUT" && sha256sum raw/*.txt run.env >SHA256SUMS); printf 'evidence=%s\n' "$OUT"
