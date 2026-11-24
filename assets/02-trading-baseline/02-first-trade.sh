#!/usr/bin/env bash
set -euo pipefail
cd /qyt-fll
REPO_ROOT=/qyt-fll
SELF="$REPO_ROOT/assets/02-trading-baseline/02-first-trade.sh"
FORMATTER="$REPO_ROOT/assets/02-trading-baseline/format_first_trade.py"
STATE="$REPO_ROOT/reports/run-state/02-trading-baseline.env"
LABCTL="$REPO_ROOT/apps/flle-trading-lab/scripts/transport_labctl.sh"
TRADE_TEST="$REPO_ROOT/apps/flle-trading-lab/tests/first_trade.py"
test -s "$STATE"
source "$STATE"
case "$RUN_ID" in ""|*[!A-Za-z0-9._-]*) exit 2;; esac
OUT="$REPO_ROOT/reports/course-runs/$RUN_ID"
mkdir -p "$OUT/raw"

{
  printf '\n%s / first-trade\n===== ① 查下单前的平台状态 =====\n核对当前配置与进程；通过后才发送订单。\n$ bash apps/flle-trading-lab/scripts/transport_labctl.sh verify %s\n' "$(hostname)" "$RUN_ID"
  if bash "$LABCTL" verify "$RUN_ID" >"$OUT/raw/verify-before-trade.txt" 2>&1; then rc=0; else rc=$?; fi
  if test "$rc" -ne 0; then
    printf '检查失败，退出码 %s；本次不下单。\n$ tail -n 20 %q\n' "$rc" "$OUT/raw/verify-before-trade.txt"
    tail -n 20 "$OUT/raw/verify-before-trade.txt"; exit "$rc"
  fi
  python3 "$FORMATTER" --verify "$OUT/raw/verify-before-trade.txt"
  printf '\n===== ② 完成一笔手动纸面交易 =====\n$ python3 apps/flle-trading-lab/tests/first_trade.py --base-url %s\n' "$WEB_URL"
  if python3 "$TRADE_TEST" --base-url "$WEB_URL" >"$OUT/raw/first-trade.txt" 2>&1; then rc=0; else rc=$?; fi
  if test "$rc" -ne 0; then
    printf '下单失败，退出码 %s。\n$ tail -n 20 %q\n' "$rc" "$OUT/raw/first-trade.txt"
    tail -n 20 "$OUT/raw/first-trade.txt"; exit "$rc"
  fi
  if grep -qx 'verdict=FIRST_TRADE_PASS' "$OUT/raw/first-trade.txt"; then
    python3 "$FORMATTER" --trade "$OUT/raw/first-trade.txt"
  else
    cat "$OUT/raw/first-trade.txt"
  fi
} 2>&1 | tee "$OUT/raw/first-trade-classroom.txt"
sha256sum "$SELF" "$TRADE_TEST" "$FORMATTER" "$OUT/raw/verify-before-trade.txt" \
  "$OUT/raw/first-trade.txt" "$OUT/raw/first-trade-classroom.txt" >"$OUT/FIRST_TRADE_SHA256SUMS"
sha256sum -c "$OUT/FIRST_TRADE_SHA256SUMS" >/dev/null
echo "evidence=$OUT"
