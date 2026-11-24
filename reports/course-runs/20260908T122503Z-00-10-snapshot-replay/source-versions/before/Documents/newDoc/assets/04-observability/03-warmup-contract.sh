#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-04-warmup-contract"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
SOURCE="$(find Documents/reports/course-runs -maxdepth 1 -type d \
  -name '*-04-raw-samples' | sort | tail -1)/raw/latency.csv"

printf '===== jump host · python3 warmup view =====\n'; python3 - "$SOURCE" "$OUT/raw/samples.csv" <<'PY' 2>&1 | tee "$OUT/raw/result.txt"
import sys
rows = []
with open(sys.argv[1], "r", encoding="utf-8") as source:
    for line in source:
        sequence, elapsed_ns = line.strip().split(",")
        rows.append((int(sequence), int(elapsed_ns)))
with open(sys.argv[2], "w", encoding="utf-8") as target:
    target.write("sequence,elapsed_ns,phase,eligible\n")
    for sequence, elapsed_ns in rows:
        phase = "warmup" if sequence < 10 else "measured"
        eligible = "false" if sequence < 10 else "true"
        target.write("%d,%d,%s,%s\n" % (sequence, elapsed_ns, phase, eligible))
warmup = [row for row in rows if row[0] < 10]
eligible = [row for row in rows if row[0] >= 10]
print("raw_count=%d" % len(rows))
print("warmup_count=%d" % len(warmup))
print("eligible_count=%d" % len(eligible))
PY
printf '$ sed -n 1,13p %s\n' "$OUT/raw/samples.csv"
sed -n '1,13p' "$OUT/raw/samples.csv"
(cd "$OUT" && sha256sum raw/*.csv raw/result.txt run.env >SHA256SUMS); printf 'evidence=%s\n' "$OUT"
