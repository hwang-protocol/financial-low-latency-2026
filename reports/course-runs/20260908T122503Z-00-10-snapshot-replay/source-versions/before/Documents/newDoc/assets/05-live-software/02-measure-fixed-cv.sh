#!/usr/bin/env bash
set -euo pipefail
cd /financial-low-latency
REPO_ROOT=/financial-low-latency
SELF="$REPO_ROOT/Documents/newDoc/assets/05-live-software/02-measure-fixed-cv.sh"
HELPER="$REPO_ROOT/apps/flle-trading-lab/tests/software_measurement.py"
source "$REPO_ROOT/Documents/reports/run-state/02-trading-baseline.env"
APP_RUN_ID="$RUN_ID"
# ~~~~~读取运行 ① 的 DEQUE 摘要~~~~~
source "$REPO_ROOT/Documents/reports/run-state/05-deque-cv.env"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-05-fixed-cv"
OUT="$REPO_ROOT/Documents/reports/course-runs/$RUN_ID"
mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\nAPP_RUN_ID=%s\nBASELINE_RUN_ID=%s\nPROFILE=DEQUE_FIXED_ABBA_ISOLATED_AUTO_SENTINEL_V14\n' "$RUN_ID" "$APP_RUN_ID" "$DEQUE_RUN_ID" >"$OUT/run.env"
# ~~~~~DEQUE↔FIXED 配平，只换储存~~~~~
python3 "$HELPER" --profiles DEQUE_CV:dedicated,FIXED_CV:dedicated --repeat 8 --control-port 48121 --treatment-cpu 2 --control-cpu 3 --housekeeping-cpus 0-1 --precondition-samples 1000 --warmup 40 \
  --samples 400 --interval-us 20000 --control-every 5 --stability-limit-pct 20 \
  --environment-equivalence-pct 40 --direction-consistency-pct 87.5 --single-profile-spread-limit 1.5 \
  --bootstrap-resamples 4000 --bootstrap-seed 20260828 --output "$OUT/raw/software.csv" \
  2>&1 | tee "$OUT/raw/result.txt"
# ~~~~~封 SHA~~~~~
sha256sum "$SELF" "$HELPER" "$OUT/raw/software.csv" \
  "$OUT/raw/software.summary.json" "$OUT/raw/result.txt" "$OUT/run.env" >"$OUT/SHA256SUMS"
printf 'FIXED_RUN_ID=%s\nFIXED_SUMMARY=%s\n' "$RUN_ID" "$OUT/raw/software.summary.json" >Documents/reports/run-state/05-fixed-cv.env
printf 'evidence=%s\n' "$OUT"
