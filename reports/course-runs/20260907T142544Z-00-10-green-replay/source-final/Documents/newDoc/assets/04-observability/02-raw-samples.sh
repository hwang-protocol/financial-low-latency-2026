#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-04-raw-samples"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"

printf '===== root@10.1.1.101 · python3 =====\n'; ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.101 \
  python3 - <<'PY' 2> >(tee "$OUT/raw/latency.stderr" >&2) | tee "$OUT/raw/latency.csv"
import time
for sequence in range(100):
    start = time.monotonic_ns()
    payload = sequence.to_bytes(4, "big")
    decoded = int.from_bytes(payload, "big")
    elapsed = time.monotonic_ns() - start
    print("%d,%d" % (sequence, elapsed))
PY
printf '$ wc -l %s\n' "$OUT/raw/latency.csv"
wc -l "$OUT/raw/latency.csv"
(cd "$OUT" && sha256sum raw/* run.env >SHA256SUMS); printf 'evidence=%s\n' "$OUT"
