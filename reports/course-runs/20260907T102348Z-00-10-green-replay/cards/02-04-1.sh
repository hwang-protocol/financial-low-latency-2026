#!/usr/bin/env bash
set -euo pipefail
cd /financial-low-latency
REPO_ROOT=/financial-low-latency
SELF="$REPO_ROOT/Documents/newDoc/assets/02-trading-baseline/02-first-trade.sh"
STATE="$REPO_ROOT/Documents/reports/run-state/02-trading-baseline.env"
LABCTL="$REPO_ROOT/apps/flle-trading-lab/scripts/labctl.sh"
TRADE_TEST="$REPO_ROOT/apps/flle-trading-lab/tests/first_trade.py"
test -s "$STATE"
source "$STATE"
case "$RUN_ID" in ""|*[!A-Za-z0-9._-]*) exit 2;; esac
OUT="$REPO_ROOT/Documents/reports/course-runs/$RUN_ID"
mkdir -p "$OUT/raw"

bash "$LABCTL" verify "$RUN_ID" >"$OUT/raw/verify-before-trade.txt"
python3 "$TRADE_TEST" --base-url "$WEB_URL" | tee "$OUT/raw/first-trade.txt"
sha256sum "$SELF" "$TRADE_TEST" "$OUT/raw/verify-before-trade.txt" \
  "$OUT/raw/first-trade.txt" >"$OUT/FIRST_TRADE_SHA256SUMS"
sha256sum -c "$OUT/FIRST_TRADE_SHA256SUMS" >/dev/null
echo "evidence=$OUT"
