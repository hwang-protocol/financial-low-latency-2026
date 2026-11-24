#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-03-host-igmp-state"; ASSET="Documents/newDoc/assets/03-network/05-host-igmp-state.sh"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\nsource_asset=%s\nsource_sha256=%s\nhost=%s\npython=%s\n' "$RUN_ID" "$ASSET" "$(sha256sum "$ASSET" | cut -d' ' -f1)" "$(hostname)" "$(python3 --version 2>&1)" >"$OUT/run.env"

ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
  python3 -u - <<'PY' >"$OUT/raw/joiner.txt" 2>&1 &
import socket, time
group = "239.20.0.6"
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1); s.bind(("", 42106))
m = socket.inet_aton(group) + socket.inet_aton("20.1.1.2")
s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, m)
print("JOIN_ACTIVE " + group, flush=True); time.sleep(3)
s.setsockopt(socket.IPPROTO_IP, socket.IP_DROP_MEMBERSHIP, m)
PY
joiner_pid=$!; trap 'kill "$joiner_pid" 2>/dev/null || true' EXIT; sleep 0.5
printf '===== root@10.1.1.2 · membership state =====\n$ cat /proc/net/igmp\n'
ssh -n -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
  cat /proc/net/igmp 2>&1 | tee "$OUT/raw/proc-net-igmp.txt"
printf '$ ip maddr show dev ens64np1\n'
ssh -n -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
  ip maddr show dev ens64np1 2>&1 | tee "$OUT/raw/ip-maddr.txt"
wait "$joiner_pid"; trap - EXIT; printf '$ joiner stdout/stderr\n'; cat "$OUT/raw/joiner.txt"
(cd "$OUT" && sha256sum raw/*.txt run.env >SHA256SUMS); printf 'evidence=%s\n' "$OUT"
