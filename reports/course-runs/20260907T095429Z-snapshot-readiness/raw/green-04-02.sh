#!/usr/bin/env bash
set -euo pipefail
cd /financial-low-latency
REPO_ROOT=/financial-low-latency
SELF="$REPO_ROOT/Documents/newDoc/assets/04-live-observability/01-capture-order-rtt-baseline.sh"
HELPER="$REPO_ROOT/apps/flle-trading-lab/tests/baseline_measurement.py"
source "$REPO_ROOT/Documents/reports/run-state/02-trading-baseline.env"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-04-order-rtt-baseline"
OUT="$REPO_ROOT/Documents/reports/course-runs/$RUN_ID"
mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\nAPP_RUN_ID=%s\nPROFILE=HOST_NATIVE_ORDER_RTT_50HZ_V1\n' "$RUN_ID" "$RUN_DIR" >"$OUT/run.env"
# ~~~~~记下 MANUAL PID 与 CPU 座位；不改绑定~~~~~
ssh root@10.1.1.2 "set -eu; pid=\$(cat '$RUN_DIR/trader-manual.pid'); hostname; uname -r; taskset -pc \"\$pid\"; chrt -p \"\$pid\"; grep '^Cpus_allowed_list' /proc/\$pid/status" >"$OUT/raw/host-profile.txt"
# ~~~~~50 Hz 采 20 warmup + 200 measured；不暂停行情、不关 AUTO~~~~~
python3 "$HELPER" --warmup 20 --samples 200 --interval-us 20000 \
  --output "$OUT/raw/order-rtt.csv" 2>&1 | tee "$OUT/raw/result.txt"
# ~~~~~封 SHA，并把 raw CSV 路径交给后续卡~~~~~
sha256sum "$SELF" "$HELPER" "$OUT/raw/host-profile.txt" \
  "$OUT/raw/order-rtt.csv" "$OUT/raw/order-rtt.summary.json" \
  "$OUT/raw/result.txt" "$OUT/run.env" >"$OUT/SHA256SUMS"
printf 'BASELINE_RUN_ID=%s\nBASELINE_PROFILE=HOST_NATIVE_ORDER_RTT_50HZ_V1\nRAW_CSV=%s\n' "$RUN_ID" "$OUT/raw/order-rtt.csv" >Documents/reports/run-state/04-order-rtt-baseline.env
printf 'evidence=%s\n' "$OUT"
