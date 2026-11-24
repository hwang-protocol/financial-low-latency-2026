#!/usr/bin/env bash
set -euo pipefail
cd /qyt-fll
REPO_ROOT=/qyt-fll
SELF="$REPO_ROOT/assets/03-live-traffic/03-capture-live-order.sh"
TOOLS="$REPO_ROOT/assets/03-live-traffic"
TRADE_TEST="$REPO_ROOT/apps/flle-trading-lab/tests/first_trade.py"
source "$REPO_ROOT/reports/run-state/02-trading-baseline.env"
BASE_RUN_ID="$RUN_ID"; API="${WEB_URL%/}"
CHAPTER_RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-03-live-order"
OUT="$REPO_ROOT/reports/course-runs/$CHAPTER_RUN_ID"; mkdir -p "$OUT/raw"
{
  REMOTE="/var/tmp/$CHAPTER_RUN_ID-order.pcap"
  cleanup() { rc=$?; trap - EXIT; test -z "${CAPTURE_PID:-}" || wait "$CAPTURE_PID" || true; ssh root@10.1.1.2 "rm -f '$REMOTE'" || true; exit "$rc"; }
  trap cleanup EXIT
  python3 "$TOOLS/classroom-output.py" capture order "$REMOTE"
  ssh root@10.1.1.2 "rm -f '$REMOTE'; timeout -s INT 4 tcpdump -i ens64np1 -nn -s 0 -U -w '$REMOTE' 'tcp port 43120'" >"$OUT/raw/tcpdump.txt" 2>&1 &
  CAPTURE_PID=$!
  sleep 0.5
  python3 "$TOOLS/classroom-output.py" trade order "$TRADE_TEST" "$API"
  python3 "$TRADE_TEST" --base-url "$API" >"$OUT/raw/first-trade.txt" 2>&1 || { rc=$?; tail -n 20 "$OUT/raw/first-trade.txt"; exit "$rc"; }
  python3 "$TOOLS/classroom-output.py" sessions order "$RUN_DIR"
  ssh root@10.1.1.2 "printf 'auto_pid='; cat '$RUN_DIR/trader-auto.pid'; printf 'manual_pid='; cat '$RUN_DIR/trader-manual.pid'; ss -ntpH state established '( dport = :43120 )'" >"$OUT/raw/sessions.txt"
  cat "$OUT/raw/sessions.txt"
  RC=0; wait "$CAPTURE_PID" || RC=$?
  python3 "$TOOLS/classroom-output.py" capture-result order "$OUT"
  [ "$RC" -eq 0 ] || [ "$RC" -eq 124 ]
  scp "root@10.1.1.2:$REMOTE" "$OUT/raw/live-order.pcap" >/dev/null
  python3 "$TOOLS/classroom-output.py" decode order "$OUT"
  python3 "$TOOLS/inspect_order_pcap.py" "$OUT/raw/live-order.pcap" "$OUT/raw/sessions.txt" --first-trade "$OUT/raw/first-trade.txt" | tee "$OUT/raw/decoded.txt" | python3 "$TOOLS/classroom-output.py" annotate order
  printf 'CHAPTER_RUN_ID=%s\nBASE_RUN_ID=%s\nWEB_URL=%s\n' "$CHAPTER_RUN_ID" "$BASE_RUN_ID" "$WEB_URL" >"$OUT/run.env"
  sha256sum "$SELF" "$TOOLS/classroom-output.py" "$TOOLS/pcap_tools.py" "$TOOLS/inspect_order_pcap.py" "$TRADE_TEST" \
    "$OUT/raw/"*-native.txt "$OUT/raw/live-order.pcap" "$OUT/raw/tcpdump.txt" "$OUT/raw/sessions.txt" "$OUT/raw/first-trade.txt" "$OUT/raw/decoded.txt" "$OUT/run.env" >"$OUT/SHA256SUMS"
  sha256sum -c "$OUT/SHA256SUMS" >/dev/null
} 2>&1 | tee "$OUT/classroom.txt"
sha256sum "$OUT/classroom.txt" "$OUT/SHA256SUMS" >"$OUT/CLASSROOM_SHA256SUMS"
