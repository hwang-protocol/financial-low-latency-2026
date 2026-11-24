#!/usr/bin/env bash
set -euo pipefail
cd /financial-low-latency
REPO_ROOT=/financial-low-latency
SELF="$REPO_ROOT/Documents/newDoc/assets/03-live-traffic/01-capture-live-market.sh"
TOOLS="$REPO_ROOT/Documents/newDoc/assets/03-live-traffic"
STATE="$REPO_ROOT/Documents/reports/run-state/02-trading-baseline.env"
LABCTL="$REPO_ROOT/apps/flle-trading-lab/scripts/labctl.sh"
source "$STATE"
BASE_RUN_ID="$RUN_ID"
CHAPTER_RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-03-live-market"
OUT="$REPO_ROOT/Documents/reports/$CHAPTER_RUN_ID"
REMOTE="/var/tmp/$CHAPTER_RUN_ID-market.pcap"
API="${WEB_URL%/}"
mkdir -p "$OUT/raw"
# ~~~~~先确认第二章基础业务服务还在线（此处不逐路验收加速）~~~~~
bash "$LABCTL" verify "$BASE_RUN_ID" >"$OUT/raw/verify.txt"
# ~~~~~记下当前行情模式；EXIT 时只恢复它，并删掉 .2 上的临时 pcap~~~~~
ORIGINAL_MODE="$(curl -fsS "$API/api/state" | python3 -c 'import json,sys;print(json.load(sys.stdin)["market_mode"])')"
cleanup() {
  curl -fsS -X POST -H 'Content-Type: application/json' -d "{\"market_mode\":\"$ORIGINAL_MODE\"}" "$API/api/market" >/dev/null || true
  ssh root@10.1.1.2 "rm -f '$REMOTE'" || true
}
trap cleanup EXIT
# ~~~~~只切 MULTICAST；不切 UNICAST/DUAL，也不用点网页~~~~~
curl -fsS -X POST -H 'Content-Type: application/json' -d '{"market_mode":"MULTICAST"}' "$API/api/market" >/dev/null
# ~~~~~在 .2 ens64np1 抓 200 个组播 UDP：-nn 不反解名字，-s 0 整帧，-c 200 够数就停~~~~~
ssh root@10.1.1.2 "rm -f '$REMOTE'; timeout 8 tcpdump -i ens64np1 -nn -s 0 -c 200 -w '$REMOTE' 'udp dst port 42120 and dst host 239.20.1.20'" 2>&1 | tee "$OUT/raw/tcpdump.txt"
# ~~~~~拉回管理机后按 Ethernet → IPv4 → UDP → MoldUDP64 → ITCH 5.0 拆同一帧~~~~~
scp "root@10.1.1.2:$REMOTE" "$OUT/raw/live-market.pcap" >/dev/null
python3 "$TOOLS/inspect_market_pcap.py" "$OUT/raw/live-market.pcap" | tee "$OUT/raw/decoded.txt"
# ~~~~~写 run.env 与 SHA；trap EXIT 会把 market_mode 切回 ORIGINAL_MODE~~~~~
{
  printf 'CHAPTER_RUN_ID=%s\nBASE_RUN_ID=%s\n' "$CHAPTER_RUN_ID" "$BASE_RUN_ID"
  printf 'CAPTURE_HOST=10.1.1.2\nCAPTURE_INTERFACE=ens64np1\nORIGINAL_MODE=%s\n' "$ORIGINAL_MODE"
} >"$OUT/run.env"
sha256sum "$SELF" "$TOOLS/pcap_tools.py" "$TOOLS/inspect_market_pcap.py" \
  "$OUT/raw/live-market.pcap" "$OUT/raw/tcpdump.txt" "$OUT/raw/decoded.txt" "$OUT/run.env" >"$OUT/SHA256SUMS"
sha256sum -c "$OUT/SHA256SUMS" >/dev/null
echo "evidence=$OUT"
