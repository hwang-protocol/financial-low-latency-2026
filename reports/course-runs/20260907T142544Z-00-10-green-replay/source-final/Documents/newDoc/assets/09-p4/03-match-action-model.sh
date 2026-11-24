#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-09-p4-match-action"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"

printf '===== jump-host =====\n$ python3 -\n' | tee "$OUT/raw/result.txt"
python3 - <<'PY' 2>&1 | tee -a "$OUT/raw/result.txt"
table = {"00:0f:53:d3:af:21": 2}
packets = ["00:0f:53:d3:af:21", "00:11:22:33:44:55", "ff:ff:ff:ff:ff:ff"]
for destination in packets:
    if destination in table:
        result = "FORWARD_PORT_%d" % table[destination]
    else:
        result = "DEFAULT_DROP"
    print("dst=%s result=%s" % (destination, result))
PY
(cd "$OUT" && sha256sum raw/result.txt run.env >SHA256SUMS)
printf 'evidence=%s\n' "$OUT"
