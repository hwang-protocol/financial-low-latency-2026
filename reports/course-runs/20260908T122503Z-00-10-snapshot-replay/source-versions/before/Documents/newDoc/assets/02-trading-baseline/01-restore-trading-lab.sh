#!/usr/bin/env bash
# Deploy all course trading capabilities once; later chapters only select profiles.
set -Eeuo pipefail
cd /financial-low-latency
REPO_ROOT=/financial-low-latency
SELF="$REPO_ROOT/Documents/newDoc/assets/02-trading-baseline/01-restore-trading-lab.sh"
CTL="$REPO_ROOT/apps/flle-trading-lab/scripts/transport_labctl.sh"
STATE="$REPO_ROOT/Documents/reports/run-state/02-trading-baseline.env"
exec 9>/run/lock/flle-platform-deploy.lock; flock -n 9
if test -s "$STATE.pending"; then
  PENDING_RUN="$(sed -n 's/^RUN_ID=//p' "$STATE.pending")"
  [[ "$PENDING_RUN" =~ ^[A-Za-z0-9._-]+-02-trading-platform$ ]]
  PENDING_OUT="$REPO_ROOT/Documents/reports/course-runs/$PENDING_RUN"
  echo "Recovering interrupted deployment: $PENDING_RUN"
  bash "$CTL" stop "$PENDING_RUN" 2>&1 | tee "$PENDING_OUT/raw/interrupted-cleanup-$(date -u +%Y%m%dT%H%M%S.%NZ).txt"
  mv "$STATE.pending" "$PENDING_OUT/aborted-deploy.env"
fi
if test -s "$STATE"; then
  OLD_RUN_ID="$(sed -n 's/^RUN_ID=//p' "$STATE")"
  case "$OLD_RUN_ID" in
    *-02-trading-platform)
      if bash "$CTL" verify "$OLD_RUN_ID"; then
        echo "platform=ALREADY_DEPLOYED run_id=$OLD_RUN_ID"; exit
      fi
      if test "$(bash "$CTL" reuse-state "$OLD_RUN_ID")" != CLEAN; then
        bash "$CTL" retire-snapshot-controller "$OLD_RUN_ID" 2>&1 | tee "$REPO_ROOT/Documents/reports/course-runs/$OLD_RUN_ID/raw/snapshot-retire-$(date -u +%Y%m%dT%H%M%S.%NZ).txt"
      fi
      test "$(bash "$CTL" reuse-state "$OLD_RUN_ID")" = CLEAN
      mv "$STATE" "$REPO_ROOT/Documents/reports/course-runs/$OLD_RUN_ID/retired-platform.env"
      ;;
    *-02-trading-baseline) bash apps/flle-trading-lab/scripts/labctl.sh stop "$OLD_RUN_ID" ;;
    *) echo 'Unrecognized platform state; refusing to overwrite it' >&2; exit 2 ;;
  esac
fi
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-02-trading-platform"
OUT="$REPO_ROOT/Documents/reports/course-runs/$RUN_ID"
mkdir -p "$OUT/raw" "${STATE%/*}"
# Persist identity before the first mutation so interrupted deployment is recoverable.
printf 'RUN_ID=%s\nRUN_DIR=/var/tmp/flle-trading-lab-%s\nWEB_URL=http://10.1.1.101:8088/\nPROFILE=UNIFIED_TRADING_PLATFORM\n' "$RUN_ID" "$RUN_ID" >"$OUT/run.env"
cp "$OUT/run.env" "$STATE.pending"
{
  bash "$CTL" preflight "$RUN_ID"
  bash Documents/newDoc/assets/06-kernel-bypass/four-path-build-contract-audit.sh "$OUT/raw/code-contract"
  bash "$CTL" deploy "$RUN_ID"
  bash "$CTL" baseline "$RUN_ID"
  bash "$CTL" verify "$RUN_ID"
} 2>&1 | tee "$OUT/raw/restore.txt"
cp "$OUT/run.env" "$STATE.tmp.$BASHPID"; mv "$STATE.tmp.$BASHPID" "$STATE"
rm -f "$STATE.pending"
sha256sum "$SELF" "$CTL" "$OUT/raw/restore.txt" "$OUT/run.env" >"$OUT/SHA256SUMS"
echo "platform=READY profile=SOFTWARE capabilities=Socket,Onload,TCPDirect,DPDK,FeedGuardian"
echo "evidence=$OUT"
