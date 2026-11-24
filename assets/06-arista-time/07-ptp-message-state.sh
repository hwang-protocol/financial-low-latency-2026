#!/usr/bin/env bash
set -Eeuo pipefail
cd /qyt-fll
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-07-ptp-messages"
OUT="reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"

printf '$ python3 - < assets/06-arista-time/ptp_message_model.py\n' \
  | tee "$OUT/raw/result.txt"
python3 - < assets/06-arista-time/ptp_message_model.py \
  2>&1 | tee -a "$OUT/raw/result.txt"
(cd "$OUT" && sha256sum raw/result.txt run.env >SHA256SUMS)
echo "evidence=$OUT"
