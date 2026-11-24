#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-10-assert-scoreboard"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
SRC="Documents/newDoc/assets/09-verilator/evidence"

cp "$SRC/assert-mutant.log" "$OUT/raw/"
cp "$SRC/scoreboard-mutant.log" "$OUT/raw/"
{
  printf '===== 2026-08-20 现场 RTL assertion 标准错误 =====\n'
  printf '$ ./obj_assert_mutant/Vmarket_pipeline 0x00000001 4096 coverage-assert-mutant.dat\n'
  cat "$OUT/raw/assert-mutant.log"
  printf '===== 2026-08-20 现场 scoreboard 标准错误 =====\n'
  printf '$ ./obj_scoreboard_mutant/Vmarket_pipeline 0x00000001 4096 coverage-scoreboard-mutant.dat\n'
  cat "$OUT/raw/scoreboard-mutant.log"
} 2>&1 | tee "$OUT/raw/transcript.txt"
(cd "$OUT" && sha256sum raw/* run.env >SHA256SUMS)
printf 'evidence=%s\n' "$OUT"
