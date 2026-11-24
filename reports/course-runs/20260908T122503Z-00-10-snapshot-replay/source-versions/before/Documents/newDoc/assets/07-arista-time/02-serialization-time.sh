#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-07-serialization"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"

python3 - <<'PY' 2>&1 | tee "$OUT/raw/result.txt"
rate = 10_000_000_000
small_bytes = 64
large_bytes = 1514
small_ns = small_bytes * 8 * 1_000_000_000 / rate
large_ns = large_bytes * 8 * 1_000_000_000 / rate
difference_ns = large_ns - small_ns
print("64B_ns=%.1f" % small_ns)
print("1514B_ns=%.1f" % large_ns)
print("difference_ns=%.1f" % difference_ns)
PY
(cd "$OUT" && sha256sum raw/result.txt run.env >SHA256SUMS)
echo "evidence=$OUT"
