#!/usr/bin/env bash
set -Eeuo pipefail
cd /qyt-fll
TOOLS=assets/02-trading-baseline
source reports/run-state/02-trading-baseline.env
BASE_RUN_ID="$RUN_ID"; API="${WEB_URL%/}"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-02-igmp-feed"
OUT="reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\nBASE_RUN_ID=%s\n' "$RUN_ID" "$BASE_RUN_ID" >"$OUT/run.env"
# Keep the original mode, and restore it even when capture or verification fails.
printf '===== 记下当前行情模式 =====\n$ curl -fsS --max-time 10 %q\n' "$API/api/state"
curl -fsS --max-time 10 "$API/api/state" >"$OUT/raw/before.json"
ORIGINAL_MODE="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["market_mode"])' "$OUT/raw/before.json")"
case "$ORIGINAL_MODE" in UNICAST|MULTICAST|MULTICAST_A|MULTICAST_B|DUAL) ;; *) exit 2;; esac
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
  set_mode DUAL
  filter='udp and src host 20.1.1.1 and ((dst host 233.74.125.32 and dst port 31032) or (dst host 233.74.125.33 and dst port 31033))'
  printf '10.1.1.2 / capture\n===== 同时看 A、B 两路行情包 =====\n[报文] 同一窗口共抓十包，两组都应出现；各路包数不要求相等。\n$ ssh root@10.1.1.2 timeout 12 tcpdump -p -i ens64np1 -nn -c 10 %q\n' "$filter"
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 "timeout 12 tcpdump -p -i ens64np1 -nn -c 10 '$filter'" 2>&1 | tee "$OUT/raw/packets.txt"
  count='import pathlib,sys; s=pathlib.Path(sys.argv[1]).read_text(); a=s.count("> 233.74.125.32.31032:"); b=s.count("> 233.74.125.33.31033:"); print("A 路=%s 包，B 路=%s 包，共 %s 包" % (a,b,a+b),flush=True); sys.exit(0 if a>0 and b>0 and a+b==10 else "两路抓包检查未通过：应共十包且两组都有包。")'
  printf '===== 核对两路都收到 =====\n$ python3 -c %q %q\n' "$count" "$OUT/raw/packets.txt"
  python3 -c "$count" "$OUT/raw/packets.txt"
  printf '===== 查应用接收状态 =====\n$ python3 assets/common/wait-feed-state.py %s HEALTHY --timeout 25\n' "$API/api/state"
  if python3 assets/common/wait-feed-state.py "$API/api/state" HEALTHY --timeout 25 >"$OUT/raw/feed.json" 2>"$OUT/raw/feed-error.txt"; then :; else
    rc=$?; printf '应用接收检查失败，退出码 %s；以下为最后状态与错误，随后恢复原行情模式。\n' "$rc"; cat "$OUT/raw/feed.json" "$OUT/raw/feed-error.txt"; exit "$rc"
  fi
  summary='import json,sys; s=json.load(open(sys.argv[1])); print("market_mode=%s integrity=%s next_expected=%s" % (s["market_mode"],s["feed"]["integrity"],s["feed"]["next_expected"]))'
  printf '$ python3 -c %q %q\n' "$summary" "$OUT/raw/feed.json"
  python3 -c "$summary" "$OUT/raw/feed.json"
  printf '===== 恢复检查前的行情模式 =====\n'; set_mode "$ORIGINAL_MODE"; trap - EXIT
} 2>&1 | tee "$OUT/raw/classroom.txt"
sha256sum "$TOOLS/01c-check-multicast-feed.sh" "$OUT"/raw/* "$OUT/run.env" >"$OUT/SHA256SUMS"
