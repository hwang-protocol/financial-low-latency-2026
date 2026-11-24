#!/usr/bin/env bash
set -euo pipefail
cd /financial-low-latency
REPO_ROOT=/financial-low-latency
SELF="$REPO_ROOT/Documents/newDoc/assets/02-trading-baseline/01-restore-trading-lab.sh"
LABCTL="$REPO_ROOT/apps/flle-trading-lab/scripts/labctl.sh"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-02-trading-baseline"
OUT="$REPO_ROOT/Documents/reports/$RUN_ID"
STATE="$REPO_ROOT/Documents/reports/run-state/02-trading-baseline.env"
mkdir -p "$OUT/raw" "$(dirname -- "$STATE")"

if [ -s "$STATE" ]; then
  OLD_RUN_ID="$(sed -n 's/^RUN_ID=//p' "$STATE")"
  case "$OLD_RUN_ID" in ""|*[!A-Za-z0-9._-]*) exit 2;; esac
  bash "$LABCTL" stop "$OLD_RUN_ID"
fi

{
  echo "run_id=$RUN_ID"
  bash "$LABCTL" preflight "$RUN_ID"
  bash "$LABCTL" deploy "$RUN_ID"
  bash "$LABCTL" start "$RUN_ID"
  bash "$LABCTL" verify "$RUN_ID"
} 2>&1 | tee "$OUT/raw/restore.txt"

{
  printf 'RUN_ID=%s\n' "$RUN_ID"
  printf 'RUN_DIR=/var/tmp/flle-trading-lab-%s\n' "$RUN_ID"
  printf 'WEB_URL=http://10.1.1.101:8088/\n'
  printf 'PROFILE=HOST_NATIVE_REGULAR_SESSION_OFFICIAL_REPLAY\n'
  printf 'MARKET_DATE=2026-06-12\n'
  printf 'REPLAY_WINDOW=09:30:00-16:00:00\n'
  printf 'REPLAY_SHA256=82e1d74f961803e0646e1f09329f080d72f21f581540344ed8da605a7641ef2b\n'
} >"$OUT/run.env"
cp "$OUT/run.env" "$STATE"
sha256sum "$SELF" "$LABCTL" "$OUT/raw/restore.txt" "$OUT/run.env" >"$OUT/SHA256SUMS"
sha256sum -c "$OUT/SHA256SUMS" >/dev/null
echo "evidence=$OUT"
