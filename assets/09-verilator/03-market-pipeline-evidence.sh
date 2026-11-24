#!/usr/bin/env bash
set -Eeuo pipefail
cd /qyt-fll
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-10-rtl-pipeline-evidence"
OUT="reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
SRC="assets/09-verilator/evidence/market-pipeline.log"

cp "$SRC" "$OUT/raw/result.txt"
printf '===== 2026-08-20 现场 Verilator testbench 标准输出 =====\n' | tee "$OUT/raw/transcript.txt"
printf '$ ./obj_dir/Vmarket_pipeline market_pipeline-run1.vcd\n' | tee -a "$OUT/raw/transcript.txt"
cat "$OUT/raw/result.txt" 2>&1 | tee -a "$OUT/raw/transcript.txt"
(cd "$OUT" && sha256sum raw/* run.env >SHA256SUMS)
printf 'evidence=%s\n' "$OUT"
