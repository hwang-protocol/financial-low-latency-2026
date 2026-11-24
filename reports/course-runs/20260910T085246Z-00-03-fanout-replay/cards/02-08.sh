#!/usr/bin/env bash
set -euo pipefail
cd /financial-low-latency
REPO_ROOT=/financial-low-latency
SELF="$REPO_ROOT/Documents/newDoc/assets/02-trading-baseline/02-first-trade.sh"
STATE="$REPO_ROOT/Documents/reports/run-state/02-trading-baseline.env"
LABCTL="$REPO_ROOT/apps/flle-trading-lab/scripts/transport_labctl.sh"
TRADE_TEST="$REPO_ROOT/apps/flle-trading-lab/tests/first_trade.py"
test -s "$STATE"
source "$STATE"
case "$RUN_ID" in ""|*[!A-Za-z0-9._-]*) exit 2;; esac
OUT="$REPO_ROOT/Documents/reports/course-runs/$RUN_ID"
mkdir -p "$OUT/raw"

{
  printf '\n%s / first-trade\n===== ① 查下单前的平台状态 =====\n核对当前配置与进程；通过后才发送订单。完整状态写入日志。\n$ bash %q verify %q\n' "$(hostname)" "$LABCTL" "$RUN_ID"
  if bash "$LABCTL" verify "$RUN_ID" >"$OUT/raw/verify-before-trade.txt" 2>&1; then rc=0; else rc=$?; fi
  if test "$rc" -ne 0; then
    printf '检查失败，退出码 %s；本次不下单。\n$ tail -n 20 %q\n' "$rc" "$OUT/raw/verify-before-trade.txt"
    tail -n 20 "$OUT/raw/verify-before-trade.txt"; exit "$rc"
  fi
  printf '检查命令退出码：0；完整输出：%s\n' "$OUT/raw/verify-before-trade.txt"
  filter='/^[A-Za-z][A-Za-z0-9_-]*=/ && length($0)<=240 { if(++n<=8) print }'
  printf '$ awk %q %q\n' "$filter" "$OUT/raw/verify-before-trade.txt"
  awk "$filter" "$OUT/raw/verify-before-trade.txt"
  printf '\n===== ② 完成一笔手动纸面交易 =====\n[本单] 对: 成交 1 股、持仓变化一致、两端都有记录  证: 下单到成交的链路通了\n$ python3 %q --base-url %q\n' "$TRADE_TEST" "$WEB_URL"
  python3 "$TRADE_TEST" --base-url "$WEB_URL" 2>&1 | tee "$OUT/raw/first-trade.txt"
} 2>&1 | tee "$OUT/raw/first-trade-classroom.txt"
sha256sum "$SELF" "$TRADE_TEST" "$OUT/raw/verify-before-trade.txt" \
  "$OUT/raw/first-trade.txt" "$OUT/raw/first-trade-classroom.txt" >"$OUT/FIRST_TRADE_SHA256SUMS"
sha256sum -c "$OUT/FIRST_TRADE_SHA256SUMS" >/dev/null
echo "evidence=$OUT"
