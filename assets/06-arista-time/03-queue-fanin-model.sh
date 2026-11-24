#!/usr/bin/env bash
set -Eeuo pipefail
cd /qyt-fll
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-07-queue-fanin"
OUT="reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"

python3 - <<'PY' 2>&1 | tee "$OUT/raw/result.txt"
egress_capacity = 10
profiles = [("one_ingress", 8), ("two_ingress", 16)]
for name, arrival in profiles:
    queued = max(0, arrival - egress_capacity)
    print("%s arrival=%d capacity=%d queued=%d" %
          (name, arrival, egress_capacity, queued))
PY
(cd "$OUT" && sha256sum raw/result.txt run.env >SHA256SUMS)
echo "evidence=$OUT"
