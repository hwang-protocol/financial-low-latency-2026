#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT=/qyt-fll; cd "$REPO_ROOT"
TOOLS="$REPO_ROOT/assets/03-live-traffic"
source "$REPO_ROOT/reports/run-state/02-trading-baseline.env"
BASE_RUN_ID="$RUN_ID"; API="${WEB_URL%/}"
CHAPTER_RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-03-market-paths"; OUT="$REPO_ROOT/reports/course-runs/$CHAPTER_RUN_ID"; mkdir -p "$OUT/raw"
{
  python3 assets/common/eos_cli.py --mode show --plan "assets/02-trading-baseline/igmp-show.plan" --output "$OUT/raw/switch-igmp.txt" >/dev/null
  python3 assets/02-trading-baseline/inspect-igmp.py "$OUT/raw/switch-igmp.txt" --members --ab --display
  curl -fsS --max-time 10 "$API/api/state" | python3 -c 'import json,sys; s=json.load(sys.stdin); assert s.get("market_network",{}).get("market_schema")=="udp-multicast-ab-v1", "请先升级第二章 A/B 平台"'
  curl -fsS --max-time 10 "$API/api/state" >"$OUT/raw/comparison-start.json"
  ORIGINAL_MODE="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["market_mode"])' "$OUT/raw/comparison-start.json")"
  read_state() {
    curl -fsS --max-time 10 "$API/api/state" >"$OUT/raw/$1.json" || return
    python3 "$TOOLS/check-comparison-state.py" "$OUT/raw/comparison-start.json" "$OUT/raw/$1.json"
  }
  set_mode() {
    case "$1" in UNICAST|MULTICAST|MULTICAST_A|MULTICAST_B|DUAL) ;; *) echo 'Invalid market mode' >&2; return 2;; esac
    python3 "$TOOLS/classroom-output.py" mode transports "$API" "$1"
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
  capture() {
    set_mode "$1"; read_state "$1-before" >/dev/null; remote="/var/tmp/$CHAPTER_RUN_ID-$1.pcap"
    python3 "$TOOLS/classroom-output.py" capture transports "$remote" "$1"
    ssh root@10.1.1.2 "rm -f '$remote'; timeout 8 tcpdump -i ens64np1 -nn -s 0 -c 120 -w '$remote' 'udp and src host 20.1.1.1'" 2>&1 | tee "$OUT/raw/$1-tcpdump.txt"
    scp "root@10.1.1.2:$remote" "$OUT/raw/$1.pcap" >/dev/null
    read_state "$1-after" >/dev/null
  }
  for mode in MULTICAST_A MULTICAST_B; do capture "$mode"; done
  set_mode DUAL; BEFORE="$(read_state duplicates-before)"
  capture DUAL; for _ in $(seq 1 20); do
    AFTER="$(read_state duplicates-after)"; [ "$AFTER" -gt "$BEFORE" ] && break; sleep 0.2
  done
  read_state comparison-final >/dev/null; FINAL="$(cat "$OUT/raw/comparison-final.json")"; read -r PENDING GAPS < <(python3 -c 'import json,sys;d=json.load(sys.stdin)["feed"];print(d["pending"], d["gaps"])' <<<"$FINAL")
  ssh root@10.1.1.2 'ip maddr show dev ens64np1' >"$OUT/raw/membership.txt"
  USERS="$(awk '$1=="inet" && $2=="233.74.125.32" {print ($3=="users" ? $4 : 1)}' "$OUT/raw/membership.txt")"
  USERS_B="$(awk '$1=="inet" && $2=="233.74.125.33" {print ($3=="users" ? $4 : 1)}' "$OUT/raw/membership.txt")"
  python3 "$TOOLS/classroom-output.py" decode transports "$OUT" "$BEFORE" "$AFTER" "$USERS" "$USERS_B" "$PENDING" "$GAPS"
  python3 "$TOOLS/inspect_transport_pcaps.py" "$OUT/raw/MULTICAST_A.pcap" "$OUT/raw/MULTICAST_B.pcap" "$OUT/raw/DUAL.pcap" --duplicates-before "$BEFORE" --duplicates-after "$AFTER" --membership-users "$USERS" --membership-users-b "$USERS_B" --pending "$PENDING" --gaps "$GAPS" | tee "$OUT/raw/decoded.txt" | python3 "$TOOLS/classroom-output.py" annotate transports
  restore_market_mode; trap - EXIT; cleanup_capture; printf 'CHAPTER_RUN_ID=%s\nBASE_RUN_ID=%s\nORIGINAL_MODE=%s\n' "$CHAPTER_RUN_ID" "$BASE_RUN_ID" "$ORIGINAL_MODE" >"$OUT/run.env"
  sha256sum "$TOOLS/02-compare-market-transports.sh" "$TOOLS/classroom-output.py" "$TOOLS/check-comparison-state.py" "$TOOLS/pcap_tools.py" "$TOOLS/inspect_transport_pcaps.py" "$OUT"/raw/* "$OUT/run.env" >"$OUT/SHA256SUMS"
  sha256sum -c "$OUT/SHA256SUMS" >/dev/null
} 2>&1 | tee "$OUT/classroom.txt"
sha256sum "$OUT/classroom.txt" "$OUT/SHA256SUMS" >"$OUT/CLASSROOM_SHA256SUMS"
