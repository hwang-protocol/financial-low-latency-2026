#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-05-per-message-allocation"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"

ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.101 \
  'tmp=$(mktemp -d); trap '"'"'rm -rf "$tmp"'"'"' EXIT;
   g++-11 -std=c++17 -O2 -x c++ -o "$tmp/lab" - && "$tmp/lab"' \
  < Documents/newDoc/assets/05-software/allocation_lab.cpp \
  2>&1 | tee "$OUT/raw/result.txt"
(cd "$OUT" && sha256sum raw/result.txt run.env >SHA256SUMS)
echo "evidence=$OUT"
