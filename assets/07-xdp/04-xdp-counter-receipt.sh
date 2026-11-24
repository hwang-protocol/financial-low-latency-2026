#!/usr/bin/env bash
set -Eeuo pipefail
cd /qyt-fll
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-08-xdp-counters"
OUT="reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
SOURCE="assets/07-xdp/xdp-map-native-20260820.txt"
{
  printf '$ sha256sum %s\n' "$SOURCE"; sha256sum "$SOURCE"
  printf '\n$ cat %s\n' "$SOURCE"; cat "$SOURCE"
} 2>&1 | tee "$OUT/raw/result.txt"
(cd "$OUT" && sha256sum raw/result.txt run.env >SHA256SUMS)
echo "evidence=$OUT"
