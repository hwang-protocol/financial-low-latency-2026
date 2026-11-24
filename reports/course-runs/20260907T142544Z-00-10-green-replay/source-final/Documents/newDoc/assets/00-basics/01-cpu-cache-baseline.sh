#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-00-cpu-cache-baseline"
OUT="Documents/reports/course-runs/$RUN_ID"
mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"

printf '===== root@10.1.1.101 · CPU cache baseline =====\n'
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.101 \
  bash -s <<'REMOTE' 2>&1 | tee "$OUT/raw/result.txt"
set -Eeuo pipefail
printf '$ lscpu\n'; lscpu
printf '\n$ getconf PAGE_SIZE\n'; getconf PAGE_SIZE
printf '\n$ /sys/devices/system/cpu/cpu0/cache/index*/...\n'
for d in /sys/devices/system/cpu/cpu0/cache/index*; do
  printf '%s ' "$(basename "$d")"
  printf 'level='; tr -d '\n' <"$d/level"
  printf ' type='; tr -d '\n' <"$d/type"
  printf ' size='; tr -d '\n' <"$d/size"
  printf ' line='; cat "$d/coherency_line_size"
done
REMOTE
(cd "$OUT" && sha256sum raw/result.txt run.env >SHA256SUMS); printf 'evidence=%s\n' "$OUT"
