#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
TOOLS=Documents/newDoc/assets/02-trading-baseline
source Documents/reports/run-state/02-trading-baseline.env
BASE_RUN_ID="$RUN_ID"; API="${WEB_URL%/}"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-02-igmp-feed"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\nBASE_RUN_ID=%s\n' "$RUN_ID" "$BASE_RUN_ID" >"$OUT/run.env"
# Keep the original mode, and restore it even when capture or verification fails.
printf '===== 记下当前行情模式 =====\n$ curl -fsS --max-time 10 %q\n' "$API/api/state"
curl -fsS --max-time 10 "$API/api/state" >"$OUT/raw/before.json"
ORIGINAL_MODE="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["market_mode"])' "$OUT/raw/before.json")"
case "$ORIGINAL_MODE" in UNICAST|MULTICAST|DUAL) ;; *) exit 2;; esac
printf 'market_mode=%s\n' "$ORIGINAL_MODE"
precheck='import json,sys; s=json.load(open(sys.argv[1])); f=s.get("feed") or {}; print("integrity=%s next_expected=%s trading_gate=%s" % (f.get("integrity"),f.get("next_expected"),f.get("trading_gate")),flush=True); sys.exit(0 if f.get("integrity")=="HEALTHY" else "检查前行情已非 HEALTHY；本次不切换模式、不抓包。先处理行情缺口，再重试；不要继续下单。")'
printf '$ python3 -c %q %q\n' "$precheck" "$OUT/raw/before.json"; python3 -c "$precheck" "$OUT/raw/before.json"
set_mode() {
  printf '$ curl -fsS --max-time 10 -X POST -H %q -d %q %q\n' 'Content-Type: application/json' "{\"market_mode\":\"$1\"}" "$API/api/market"
  curl -fsS --max-time 10 -X POST -H 'Content-Type: application/json' -d "{\"market_mode\":\"$1\"}" "$API/api/market" >"$OUT/raw/set-$1.json" || return $?
  printf '轮询确认模式已切换：$ curl -fsS --max-time 10 %q\n' "$API/api/state"
  for _ in {1..30}; do
    curl -fsS --max-time 10 "$API/api/state" >"$OUT/raw/state.json" || return $?
    if python3 -c 'import json,sys;assert json.load(open(sys.argv[1]))["market_mode"]==sys.argv[2]' "$OUT/raw/state.json" "$1" 2>/dev/null; then printf 'market_mode=%s\n' "$1"; return 0; fi
    sleep 0.1
  done; return 1
}
cleanup() {
  rc=$?; trap - EXIT
  printf '===== 恢复检查前的行情模式 =====\n'
  if ! set_mode "$ORIGINAL_MODE"; then echo '行情模式恢复失败，请停止后续下单并检查网页状态。' >&2; exit 125; fi
  exit "$rc"
}
{
  trap cleanup EXIT
  printf '10.1.1.1 / market\n===== 临时发送组播行情 =====\n只切换行情目的地址；检查结束恢复原模式。\n'
  set_mode MULTICAST
  printf '10.1.1.2 / capture\n===== 在 Trader 数据口看五个行情包 =====\n[报文] 对: 源 20.1.1.1，目的 233.74.125.32.31032  证: 行情到了 Et2 对应的数据口\n$ ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 timeout 12 tcpdump -p -i ens64np1 -nn -c 5 %q\n' 'udp and src host 20.1.1.1 and dst host 233.74.125.32 and dst port 31032'
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 "timeout 12 tcpdump -p -i ens64np1 -nn -c 5 'udp and src host 20.1.1.1 and dst host 233.74.125.32 and dst port 31032'" 2>&1 | tee "$OUT/raw/packets.txt"
  printf '===== 查应用接收状态 =====\n$ python3 Documents/newDoc/assets/common/wait-feed-state.py %s HEALTHY --timeout 25\n' "$API/api/state"
  if python3 Documents/newDoc/assets/common/wait-feed-state.py "$API/api/state" HEALTHY --timeout 25 >"$OUT/raw/feed.json" 2>"$OUT/raw/feed-error.txt"; then :; else
    rc=$?; printf '应用接收检查失败，退出码 %s；以下为最后状态与错误，随后恢复原行情模式。\n' "$rc"; cat "$OUT/raw/feed.json" "$OUT/raw/feed-error.txt"; exit "$rc"
  fi
  summary='import json,sys; s=json.load(open(sys.argv[1])); print("market_mode=%s integrity=%s next_expected=%s" % (s["market_mode"],s["feed"]["integrity"],s["feed"]["next_expected"]))'
  printf '$ python3 -c %q %q\n' "$summary" "$OUT/raw/feed.json"
  python3 -c "$summary" "$OUT/raw/feed.json"
  printf '===== 恢复检查前的行情模式 =====\n'; set_mode "$ORIGINAL_MODE"; trap - EXIT
} 2>&1 | tee "$OUT/raw/classroom.txt"
sha256sum "$TOOLS/01c-check-multicast-feed.sh" "$OUT"/raw/* "$OUT/run.env" >"$OUT/SHA256SUMS"
