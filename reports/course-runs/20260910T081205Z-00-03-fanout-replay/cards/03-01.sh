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
OUT="$REPO_ROOT/Documents/reports/course-runs/$CHAPTER_RUN_ID"
REMOTE="/var/tmp/$CHAPTER_RUN_ID-market.pcap"
API="${WEB_URL%/}"
mkdir -p "$OUT/raw"
{
  python3 "$TOOLS/classroom-output.py" verify market "$LABCTL" "$BASE_RUN_ID"
  bash "$LABCTL" verify "$BASE_RUN_ID" >"$OUT/raw/verify.txt" 2>&1 || { rc=$?; tail -n 20 "$OUT/raw/verify.txt"; exit "$rc"; }
  ORIGINAL_MODE="$(curl -fsS --max-time 10 "$API/api/state" | python3 -c 'import json,sys;print(json.load(sys.stdin)["market_mode"])')"
  source "$TOOLS/market-mode.sh"
  trap cleanup_market EXIT
  python3 "$TOOLS/classroom-output.py" mode market "$API" MULTICAST
  set_mode MULTICAST
  python3 "$TOOLS/classroom-output.py" capture market "$REMOTE"
  ssh root@10.1.1.2 "rm -f '$REMOTE'; timeout 8 tcpdump -i ens64np1 -nn -s 0 -c 200 -w '$REMOTE' 'udp dst port 31032 and dst host 233.74.125.32'" 2>&1 | tee "$OUT/raw/tcpdump.txt"
  scp "root@10.1.1.2:$REMOTE" "$OUT/raw/live-market.pcap" >/dev/null
  python3 "$TOOLS/classroom-output.py" decode market "$OUT"
  python3 "$TOOLS/inspect_market_pcap.py" "$OUT/raw/live-market.pcap" | tee "$OUT/raw/decoded.txt" | python3 "$TOOLS/classroom-output.py" annotate market
  restore_market_mode; trap - EXIT; cleanup_capture
  {
    printf 'CHAPTER_RUN_ID=%s\nBASE_RUN_ID=%s\n' "$CHAPTER_RUN_ID" "$BASE_RUN_ID"
    printf 'CAPTURE_HOST=10.1.1.2\nCAPTURE_INTERFACE=ens64np1\nORIGINAL_MODE=%s\n' "$ORIGINAL_MODE"
  } >"$OUT/run.env"
  sha256sum "$SELF" "$TOOLS/market-mode.sh" "$TOOLS/classroom-output.py" "$TOOLS/pcap_tools.py" "$TOOLS/inspect_market_pcap.py" \
    "$OUT/raw/"*.json \
    "$OUT/raw/"*-native.txt "$OUT/raw/live-market.pcap" "$OUT/raw/tcpdump.txt" "$OUT/raw/decoded.txt" "$OUT/run.env" >"$OUT/SHA256SUMS"
  sha256sum -c "$OUT/SHA256SUMS" >/dev/null
} 2>&1 | tee "$OUT/classroom.txt"
sha256sum "$OUT/classroom.txt" "$OUT/SHA256SUMS" >"$OUT/CLASSROOM_SHA256SUMS"
