#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-04-metric-types"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"

printf '%s\n' \
  '# HELP flle_messages_total Accepted messages.' \
  '# TYPE flle_messages_total counter' \
  'flle_messages_total 100' \
  '# HELP flle_feed_gap Current sequence gap count.' \
  '# TYPE flle_feed_gap gauge' \
  'flle_feed_gap 0' \
  '# HELP flle_latency_seconds Message latency distribution.' \
  '# TYPE flle_latency_seconds histogram' \
  'flle_latency_seconds_bucket{le="0.001"} 98' \
  'flle_latency_seconds_bucket{le="+Inf"} 100' \
  'flle_latency_seconds_sum 0.02' \
  'flle_latency_seconds_count 100' >"$OUT/raw/metrics.txt"
printf '===== jump host · metric exposition =====\n$ cat %s\n' "$OUT/raw/metrics.txt"
cat "$OUT/raw/metrics.txt"
printf '===== root@10.1.1.101 · Prometheus container =====\n$ promtool check metrics < metrics.txt\n'
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.101 \
  'cd /opt/flle/observability && docker compose exec -T prometheus promtool check metrics' \
  <"$OUT/raw/metrics.txt" 2>&1 | tee "$OUT/raw/promtool.txt"
(cd "$OUT" && sha256sum raw/*.txt run.env >SHA256SUMS); printf 'evidence=%s\n' "$OUT"
