#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-04-tail-vs-mean"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"

printf '===== jump host · python3 tail statistics =====\n'; python3 - <<'PY' 2>&1 | tee "$OUT/raw/result.txt"
import math
import statistics
def p99(values):
    ordered = sorted(values)
    return ordered[math.ceil(0.99 * len(ordered)) - 1]
steady = [100] * 100
spiky = [80] * 98 + [1080, 1080]
print("steady mean=%d p99=%d max=%d" %
      (statistics.mean(steady), p99(steady), max(steady)))
print("spiky  mean=%d p99=%d max=%d" %
      (statistics.mean(spiky), p99(spiky), max(spiky)))
PY
(cd "$OUT" && sha256sum raw/result.txt run.env >SHA256SUMS); printf 'evidence=%s\n' "$OUT"
