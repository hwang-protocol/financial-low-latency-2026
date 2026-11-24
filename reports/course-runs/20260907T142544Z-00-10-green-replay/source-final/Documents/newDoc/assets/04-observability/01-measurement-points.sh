#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-04-measurement-points"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"

printf '===== root@10.1.1.101 · python3 =====\n'; ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.101 \
  python3 - <<'PY' 2>&1 | tee "$OUT/raw/result.txt"
import time
t0 = time.monotonic_ns()
total = 0
for number in range(10000):
    total += number
t1 = time.monotonic_ns()
elapsed = t1 - t0
print("t0_ns=%d" % t0)
print("t1_ns=%d" % t1)
print("elapsed_ns=%d" % elapsed)
print("total=%d" % total)
PY
(cd "$OUT" && sha256sum raw/result.txt run.env >SHA256SUMS); printf 'evidence=%s\n' "$OUT"
