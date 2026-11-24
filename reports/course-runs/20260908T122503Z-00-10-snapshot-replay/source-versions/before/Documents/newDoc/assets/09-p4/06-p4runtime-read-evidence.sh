#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-09-p4runtime-read"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
SOURCE="Documents/newDoc/assets/09-p4/evidence/p4runtime-rw.log"

cp "$SOURCE" "$OUT/raw/p4runtime.txt"
printf '===== 2026-08-20 现场 P4Runtime 客户端标准输出 =====\n' | tee "$OUT/raw/transcript.txt"
printf '$ INSERT -> READ -> DELETE -> READ(empty)\n' | tee -a "$OUT/raw/transcript.txt"
cat "$OUT/raw/p4runtime.txt" 2>&1 | tee -a "$OUT/raw/transcript.txt"
(cd "$OUT" && sha256sum raw/*.txt run.env >SHA256SUMS)
printf 'evidence=%s\n' "$OUT"
