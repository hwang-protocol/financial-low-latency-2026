#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-10-reset-boundary"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
SRC="Documents/newDoc/assets/09-verilator/evidence/reset-boundary.json"

cp "$SRC" "$OUT/raw/result.json"
printf '===== 2026-08-20 现场 midstream reset 结果 =====\n' | tee "$OUT/raw/transcript.txt"
printf '$ ./obj_clean/Vmarket_pipeline_reset clean run1-result.json run1.vcd run1.coverage.dat >run1.stdout\n' | tee -a "$OUT/raw/transcript.txt"
printf '$ cat run1-result.json\n' | tee -a "$OUT/raw/transcript.txt"
cat "$OUT/raw/result.json" 2>&1 | tee -a "$OUT/raw/transcript.txt"
(cd "$OUT" && sha256sum raw/* run.env >SHA256SUMS)
printf 'evidence=%s\n' "$OUT"
