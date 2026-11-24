#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-09-p4-dst-exact"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
SOURCE="Documents/newDoc/assets/09-p4/evidence"

cp "$SOURCE"/counter-{hit,miss}-lr-{before,after}.txt "$OUT/raw/"
printf '===== 2026-08-20 现场 simple_switch_CLI 原生输出 =====\n' | tee "$OUT/raw/transcript.txt"
for file in "$OUT"/raw/counter-*.txt; do
  tag="${file##*/counter-}"; tag="${tag%.txt}"
  printf '$ cat %s # window=%s\n' "${file#"$OUT/"}" "$tag"
  cat "$file"
done 2>&1 | tee -a "$OUT/raw/transcript.txt"
(cd "$OUT" && sha256sum raw/* run.env >SHA256SUMS)
printf 'evidence=%s\n' "$OUT"
