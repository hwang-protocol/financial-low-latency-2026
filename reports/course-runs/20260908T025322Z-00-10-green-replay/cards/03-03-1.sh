#!/usr/bin/env bash
set -euo pipefail
cd /financial-low-latency
REPO_ROOT=/financial-low-latency
SELF="$REPO_ROOT/Documents/newDoc/assets/03-live-traffic/03-capture-live-order.sh"
TOOLS="$REPO_ROOT/Documents/newDoc/assets/03-live-traffic"
TRADE_TEST="$REPO_ROOT/apps/flle-trading-lab/tests/first_trade.py"
source "$REPO_ROOT/Documents/reports/run-state/02-trading-baseline.env"
BASE_RUN_ID="$RUN_ID"; API="${WEB_URL%/}"
CHAPTER_RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-03-live-order"
OUT="$REPO_ROOT/Documents/reports/$CHAPTER_RUN_ID"; mkdir -p "$OUT/raw"
REMOTE="/var/tmp/$CHAPTER_RUN_ID-order.pcap"
cleanup() { ssh root@10.1.1.2 "rm -f '$REMOTE'" || true; }
trap cleanup EXIT
# ~~~~~记下 AUTO/MANUAL PID 和两条已建立的 43120 会话~~~~~
ssh root@10.1.1.2 "printf 'auto_pid='; cat '$RUN_DIR/trader-auto.pid'; printf 'manual_pid='; cat '$RUN_DIR/trader-manual.pid'; ss -ntpH state established '( dport = :43120 )'" >"$OUT/raw/sessions.txt"
# ~~~~~在 .2 ens64np1 后台抓 4 秒 tcp 43120~~~~~
ssh root@10.1.1.2 "rm -f '$REMOTE'; timeout -s INT 4 tcpdump -i ens64np1 -nn -s 0 -U -w '$REMOTE' 'tcp port 43120'" >"$OUT/raw/tcpdump.txt" 2>&1 &
CAPTURE_PID=$!
sleep 0.5
# ~~~~~窗口内发一笔 MANUAL IOC；AUTO 和行情继续跑~~~~~
python3 "$TRADE_TEST" --base-url "$API" >"$OUT/raw/first-trade.txt"
RC=0; wait "$CAPTURE_PID" || RC=$?
[ "$RC" -eq 0 ] || [ "$RC" -eq 124 ]
# ~~~~~拉回后按 Ethernet → IPv4 → TCP → SoupBinTCP → OUCH 拆同一帧~~~~~
scp "root@10.1.1.2:$REMOTE" "$OUT/raw/live-order.pcap" >/dev/null
python3 "$TOOLS/inspect_order_pcap.py" "$OUT/raw/live-order.pcap" "$OUT/raw/sessions.txt" | tee "$OUT/raw/decoded.txt"
# ~~~~~写 run.env 与 SHA；trap EXIT 会删掉 .2 上的临时 pcap~~~~~
printf 'CHAPTER_RUN_ID=%s\nBASE_RUN_ID=%s\nWEB_URL=%s\n' "$CHAPTER_RUN_ID" "$BASE_RUN_ID" "$WEB_URL" >"$OUT/run.env"
sha256sum "$SELF" "$TOOLS/pcap_tools.py" "$TOOLS/inspect_order_pcap.py" "$TRADE_TEST" \
  "$OUT/raw/live-order.pcap" "$OUT/raw/tcpdump.txt" "$OUT/raw/sessions.txt" "$OUT/raw/first-trade.txt" "$OUT/raw/decoded.txt" "$OUT/run.env" >"$OUT/SHA256SUMS"
sha256sum -c "$OUT/SHA256SUMS" >/dev/null
echo "evidence=$OUT"
