#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-10-vcd-evidence"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
SRC="Documents/newDoc/assets/09-verilator/evidence"

cp "$SRC/vcd-audit.json" "$OUT/raw/"
cp "$SRC/vcd-sha256.txt" "$OUT/raw/"
{
  printf '===== 2026-08-20 现场 VCD 审计器标准输出 =====\n'
  printf '$ python3 audit_vcd.py market_pipeline-run1.vcd\n'
  cat "$OUT/raw/vcd-audit.json"
  printf '===== 2026-08-20 现场 sha256sum 标准输出 =====\n'
  printf '$ sha256sum market_pipeline-run1.vcd market_pipeline-run2.vcd\n'
  cat "$OUT/raw/vcd-sha256.txt"
} 2>&1 | tee "$OUT/raw/transcript.txt"
(cd "$OUT" && sha256sum raw/* run.env >SHA256SUMS)
printf 'evidence=%s\n' "$OUT"
