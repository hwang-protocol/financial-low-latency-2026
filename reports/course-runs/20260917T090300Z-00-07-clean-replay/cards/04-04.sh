#!/usr/bin/env bash
set -euo pipefail
cd /financial-low-latency
REPO_ROOT=/financial-low-latency
SELF="$REPO_ROOT/Documents/newDoc/assets/04-live-software/04-measure-spsc-shared-cpu.sh"
HELPER="$REPO_ROOT/apps/flle-trading-lab/tests/software_measurement.py"
RESTORE="$REPO_ROOT/apps/flle-trading-lab/tests/restore_software_profile.py"
source "$REPO_ROOT/Documents/reports/run-state/02-trading-baseline.env"
APP_RUN_ID="$RUN_ID"
# ~~~~~读取运行 ③ 的 SPSC 摘要；退出时恢复 CPU 角色~~~~~
source "$REPO_ROOT/Documents/reports/run-state/05-spsc-spin.env"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-05-spsc-shared-cpu"
OUT="$REPO_ROOT/Documents/reports/course-runs/$RUN_ID"
mkdir -p "$OUT/raw"
restore_profile() { python3 "$RESTORE" >"$OUT/raw/restore.txt"; }
trap restore_profile EXIT
printf 'RUN_ID=%s\nAPP_RUN_ID=%s\nPREVIOUS_RUN_ID=%s\nPROFILE=SPSC_DEDICATED_SHARED_ABBA_AUTO_SENTINEL_V14\n' "$RUN_ID" "$APP_RUN_ID" "$SPSC_RUN_ID" >"$OUT/run.env"
# ~~~~~SPSC 隔离核 ↔ 共享核配平~~~~~
python3 "$HELPER" --profiles SPSC_SPIN:dedicated,SPSC_SPIN:shared --repeat 8 --control-port 48121 --treatment-cpu 2 --control-cpu 3 --shared-cpu 0 --housekeeping-cpus 0 --precondition-samples 1000 --warmup 40 \
  --samples 400 --interval-us 20000 --control-every 5 --stability-limit-pct 20 \
  --environment-equivalence-pct 40 --direction-consistency-pct 87.5 --single-profile-spread-limit 1.5 \
  --bootstrap-resamples 4000 --bootstrap-seed 20260828 --output "$OUT/raw/software.csv" \
  2>&1 | tee "$OUT/raw/result.txt"
restore_profile
trap - EXIT
# ~~~~~封 SHA~~~~~
sha256sum "$SELF" "$HELPER" "$RESTORE" "$OUT/raw/software.csv" \
  "$OUT/raw/software.market.json" "$OUT/raw/software.summary.json" "$OUT/raw/result.txt" "$OUT/raw/restore.txt" "$OUT/run.env" >"$OUT/SHA256SUMS"
printf 'SOFTWARE_RUN_ID=%s\nSOFTWARE_PROFILE=SPSC_DEDICATED_SHARED_ABBA_AUTO_SENTINEL_V14\nSOFTWARE_SUMMARY=%s\n' "$RUN_ID" "$OUT/raw/software.summary.json" >Documents/reports/run-state/05-software-current.env
printf '本轮证据目录：%s\n' "$OUT"
