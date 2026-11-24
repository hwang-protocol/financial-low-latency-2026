#!/usr/bin/env bash
set -euo pipefail
cd /qyt-fll
REPO_ROOT=/qyt-fll
SELF="$REPO_ROOT/assets/04-live-software/03-measure-spsc-spin.sh"
HELPER="$REPO_ROOT/apps/flle-trading-lab/tests/software_measurement.py"
source "$REPO_ROOT/reports/run-state/02-trading-baseline.env"
APP_RUN_ID="$RUN_ID"
# ~~~~~读取运行 ② 的 FIXED 摘要~~~~~
source "$REPO_ROOT/reports/run-state/05-fixed-cv.env"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-05-spsc-spin"
OUT="$REPO_ROOT/reports/course-runs/$RUN_ID"
mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\nAPP_RUN_ID=%s\nPREVIOUS_RUN_ID=%s\nPROFILE=FIXED_SPSC_ABBA_BUSY_SPIN_ISOLATED_AUTO_SENTINEL_V14\n' "$RUN_ID" "$APP_RUN_ID" "$FIXED_RUN_ID" >"$OUT/run.env"
# ~~~~~FIXED↔SPSC 配平，只换同步~~~~~
python3 "$HELPER" --profiles FIXED_CV:dedicated,SPSC_SPIN:dedicated --repeat 8 --control-port 48121 --treatment-cpu 2 --control-cpu 3 --housekeeping-cpus 0-1 --precondition-samples 1000 --warmup 40 \
  --samples 400 --interval-us 20000 --control-every 5 --stability-limit-pct 20 \
  --environment-equivalence-pct 40 --direction-consistency-pct 87.5 --single-profile-spread-limit 1.5 \
  --bootstrap-resamples 4000 --bootstrap-seed 20260828 --output "$OUT/raw/software.csv" \
  2>&1 | tee "$OUT/raw/result.txt"
# ~~~~~封 SHA~~~~~
sha256sum "$SELF" "$HELPER" "$OUT/raw/software.csv" \
  "$OUT/raw/software.market.json" "$OUT/raw/software.summary.json" "$OUT/raw/result.txt" "$OUT/run.env" >"$OUT/SHA256SUMS"
printf 'SPSC_RUN_ID=%s\nSPSC_SUMMARY=%s\n' "$RUN_ID" "$OUT/raw/software.summary.json" >reports/run-state/05-spsc-spin.env
printf '本轮证据目录：%s\n' "$OUT"
