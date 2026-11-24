#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-10-fifo-backpressure"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"

printf '===== jump-host =====\n$ python3 -\n' | tee "$OUT/raw/result.txt"
python3 - <<'PY' 2>&1 | tee -a "$OUT/raw/result.txt"
fifo = [10, 11, 12, 13]
candidate = 14
print('cycle=0 fifo=%s level=%d output_ready=0' % (fifo, len(fifo)))
input_ready = int(len(fifo) < 4)
print('cycle=1 candidate=%d input_ready=%d fifo=%s' %
      (candidate, input_ready, fifo))
output = fifo.pop(0)
fifo.append(candidate)
print('cycle=2 output_ready=1 pop=%d push=%d fifo=%s level=%d' %
      (output, candidate, fifo, len(fifo)))
PY
(cd "$OUT" && sha256sum raw/result.txt run.env >SHA256SUMS)
printf 'evidence=%s\n' "$OUT"
