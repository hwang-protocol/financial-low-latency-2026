#!/usr/bin/env bash
set -euo pipefail
cd /financial-low-latency
REPO_ROOT=/financial-low-latency
SELF="$REPO_ROOT/Documents/newDoc/assets/03-live-traffic/02-compare-market-transports.sh"
TOOLS="$REPO_ROOT/Documents/newDoc/assets/03-live-traffic"
source "$REPO_ROOT/Documents/reports/run-state/02-trading-baseline.env"
BASE_RUN_ID="$RUN_ID"; API="${WEB_URL%/}"
CHAPTER_RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-03-market-paths"
OUT="$REPO_ROOT/Documents/reports/$CHAPTER_RUN_ID"; mkdir -p "$OUT/raw"
# ~~~~~记下当前行情模式；EXIT 时只恢复它，并删掉 .2 上的临时 pcap~~~~~
ORIGINAL_MODE="$(curl -fsS "$API/api/state" | python3 -c 'import json,sys;print(json.load(sys.stdin)["market_mode"])')"
cleanup() {
  curl -fsS -X POST -H 'Content-Type: application/json' -d "{\"market_mode\":\"$ORIGINAL_MODE\"}" "$API/api/market" >/dev/null || true
  ssh root@10.1.1.2 "rm -f /var/tmp/$CHAPTER_RUN_ID-*.pcap" || true
}
trap cleanup EXIT
# ~~~~~切模式后等 state 回读到同一值；三种模式都抓 udp 42120-42122~~~~~
set_mode() {
  curl -fsS -X POST -H 'Content-Type: application/json' -d "{\"market_mode\":\"$1\"}" "$API/api/market" >/dev/null
  for _ in $(seq 1 20); do
    [ "$(curl -fsS "$API/api/state" | python3 -c 'import json,sys;print(json.load(sys.stdin)["market_mode"])')" = "$1" ] && return; sleep 0.1
  done; return 1
}
capture() {
  set_mode "$1"; remote="/var/tmp/$CHAPTER_RUN_ID-$1.pcap"
  ssh root@10.1.1.2 "rm -f '$remote'; timeout 8 tcpdump -i ens64np1 -nn -s 0 -c 120 -w '$remote' 'udp dst portrange 42120-42122'" 2>&1 | tee "$OUT/raw/$1-tcpdump.txt"
  scp "root@10.1.1.2:$remote" "$OUT/raw/$1.pcap" >/dev/null
}
# ~~~~~先抓 UNICAST，再抓 MULTICAST；BPF 相同，差别只在 Exchange 发往哪~~~~~
capture UNICAST
capture MULTICAST
# ~~~~~DUAL 先记下 duplicate，抓完再等 counter 增加~~~~~
set_mode DUAL
BEFORE="$(curl -fsS "$API/api/state" | python3 -c 'import json,sys;print(json.load(sys.stdin)["feed"]["duplicates"])')"
capture DUAL
for _ in $(seq 1 20); do
  AFTER="$(curl -fsS "$API/api/state" | python3 -c 'import json,sys;print(json.load(sys.stdin)["feed"]["duplicates"])')"; [ "$AFTER" -gt "$BEFORE" ] && break; sleep 0.2
done
FINAL="$(curl -fsS "$API/api/state")"
read -r PENDING GAPS < <(python3 -c 'import json,sys;d=json.load(sys.stdin)["feed"];print(d["pending"], d["gaps"])' <<<"$FINAL")
ssh root@10.1.1.2 'ip maddr show dev ens64np1' >"$OUT/raw/membership.txt"
USERS="$(awk '$1=="inet" && $2=="239.20.1.20" {print $4}' "$OUT/raw/membership.txt")"
# ~~~~~对照三份目的端点、membership 与 duplicate；写 run.env 与 SHA~~~~~
python3 "$TOOLS/inspect_transport_pcaps.py" "$OUT/raw/UNICAST.pcap" "$OUT/raw/MULTICAST.pcap" "$OUT/raw/DUAL.pcap" --duplicates-before "$BEFORE" --duplicates-after "$AFTER" --membership-users "$USERS" --pending "$PENDING" --gaps "$GAPS" | tee "$OUT/raw/decoded.txt"
printf 'CHAPTER_RUN_ID=%s\nBASE_RUN_ID=%s\nORIGINAL_MODE=%s\n' "$CHAPTER_RUN_ID" "$BASE_RUN_ID" "$ORIGINAL_MODE" >"$OUT/run.env"
sha256sum "$SELF" "$TOOLS/pcap_tools.py" "$TOOLS/inspect_transport_pcaps.py" "$OUT"/raw/* "$OUT/run.env" >"$OUT/SHA256SUMS"
sha256sum -c "$OUT/SHA256SUMS" >/dev/null
echo "evidence=$OUT"
