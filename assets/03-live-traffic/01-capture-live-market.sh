#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT=/qyt-fll; cd "$REPO_ROOT"
TOOLS="$REPO_ROOT/assets/03-live-traffic"
LABCTL="$REPO_ROOT/apps/flle-trading-lab/scripts/transport_labctl.sh"
source "$REPO_ROOT/reports/run-state/02-trading-baseline.env"
BASE_RUN_ID="$RUN_ID"; API="${WEB_URL%/}"
CHAPTER_RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-03-live-market"
OUT="$REPO_ROOT/reports/course-runs/$CHAPTER_RUN_ID"; mkdir -p "$OUT/raw"
REMOTE="/var/tmp/$CHAPTER_RUN_ID-market.pcap"
{
  python3 "$TOOLS/classroom-output.py" verify market "$LABCTL" "$BASE_RUN_ID"
  bash "$LABCTL" verify "$BASE_RUN_ID" >"$OUT/raw/verify.txt" 2>&1 || { rc=$?; tail -n 20 "$OUT/raw/verify.txt"; exit "$rc"; }
  ORIGINAL_MODE="$(curl -fsS --max-time 10 "$API/api/state" | python3 -c 'import json,sys;print(json.load(sys.stdin)["market_mode"])')"
  set_mode() {
    case "$1" in UNICAST|MULTICAST|MULTICAST_A|MULTICAST_B|DUAL) ;; *) echo 'Invalid market mode' >&2; return 2;; esac
    python3 "$TOOLS/classroom-output.py" mode market "$API" "$1"
    curl -fsS --max-time 10 -X POST -H 'Content-Type: application/json' -d "{\"market_mode\":\"$1\"}" "$API/api/market" >"$OUT/raw/set-$1.json" || return $?
    printf '回读确认：$ curl -fsS --max-time 10 %q\n' "$API/api/state"
    for _ in {1..30}; do
      curl -fsS --max-time 10 "$API/api/state" >"$OUT/raw/mode-state.json" || return $?
      if python3 -c 'import json,sys;sys.exit(json.load(open(sys.argv[1]))["market_mode"] != sys.argv[2])' "$OUT/raw/mode-state.json" "$1"; then printf 'market_mode=%s\n' "$1"; return 0; fi
      sleep 0.1
    done; echo "Market mode readback did not become $1" >&2; return 1
  }
  restore_market_mode() { printf '===== 恢复检查前的行情模式 =====\n'
    set_mode "$ORIGINAL_MODE" || { echo '行情模式恢复失败，退出码125；暂停后续下单并检查网页状态。' >&2; return 125; }
  }
  cleanup_capture() { ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=5 root@10.1.1.2 "rm -f /var/tmp/$CHAPTER_RUN_ID-*.pcap"; }
  trap 'rc=$?; trap - EXIT; restore_market_mode || rc=125; cleanup_capture || true; exit "$rc"' EXIT
  set_mode MULTICAST_A
  python3 "$TOOLS/classroom-output.py" capture market "$REMOTE"
  ssh root@10.1.1.2 "rm -f '$REMOTE'; timeout 8 tcpdump -i ens64np1 -nn -s 0 -c 200 -w '$REMOTE' 'udp dst port 31032 and dst host 233.74.125.32'" 2>&1 | tee "$OUT/raw/tcpdump.txt"
  scp "root@10.1.1.2:$REMOTE" "$OUT/raw/live-market.pcap" >/dev/null
  python3 "$TOOLS/classroom-output.py" decode market "$OUT"
  python3 "$TOOLS/inspect_market_pcap.py" "$OUT/raw/live-market.pcap" | tee "$OUT/raw/decoded.txt" | python3 "$TOOLS/classroom-output.py" annotate market
  restore_market_mode; trap - EXIT; cleanup_capture
  printf 'CHAPTER_RUN_ID=%s\nBASE_RUN_ID=%s\nCAPTURE_HOST=10.1.1.2\nCAPTURE_INTERFACE=ens64np1\nORIGINAL_MODE=%s\n' "$CHAPTER_RUN_ID" "$BASE_RUN_ID" "$ORIGINAL_MODE" >"$OUT/run.env"
  sha256sum "$TOOLS/01-capture-live-market.sh" "$TOOLS/classroom-output.py" "$TOOLS/pcap_tools.py" "$TOOLS/inspect_market_pcap.py" "$OUT"/raw/* "$OUT/run.env" >"$OUT/SHA256SUMS"
  sha256sum -c "$OUT/SHA256SUMS" >/dev/null
} 2>&1 | tee "$OUT/classroom.txt"
sha256sum "$OUT/classroom.txt" "$OUT/SHA256SUMS" >"$OUT/CLASSROOM_SHA256SUMS"
