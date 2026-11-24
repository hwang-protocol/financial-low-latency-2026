#!/usr/bin/env bash
set -euo pipefail
cd /financial-low-latency
REPO_ROOT=/financial-low-latency
SELF="$REPO_ROOT/Documents/newDoc/assets/04-live-observability/02-query-prometheus.sh"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-04-prometheus-query"
OUT="$REPO_ROOT/Documents/reports/course-runs/$RUN_ID"
mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\nPROMETHEUS_URL=http://10.1.1.101:9090\n' "$RUN_ID" >"$OUT/run.env"
# ~~~~~等两个 scrape 周期，再保存完整 /metrics~~~~~
sleep 2
curl -fsS http://10.1.1.101:8088/metrics >"$OUT/raw/exposition.txt"
# ~~~~~promtool 校验 exposition，再查 ready / up / p99 / rate~~~~~
ssh root@10.1.1.101 'promtool check metrics' <"$OUT/raw/exposition.txt" 2>&1 | tee "$OUT/raw/promtool.txt"
curl -fsS http://10.1.1.101:9090/-/ready | tee "$OUT/raw/ready.txt"; echo
curl -fsSG --data-urlencode 'query=up{job="flle-trading"}' http://10.1.1.101:9090/api/v1/query | tee "$OUT/raw/up.json"; echo
curl -fsSG --data-urlencode 'query=flle_baseline_order_rtt_seconds{client="manual",stat="p99"}' http://10.1.1.101:9090/api/v1/query | tee "$OUT/raw/p99.json"; echo
curl -fsSG --data-urlencode 'query=rate(flle_market_messages_total[30s])' http://10.1.1.101:9090/api/v1/query | tee "$OUT/raw/rate.json"; echo
# ~~~~~封 SHA~~~~~
sha256sum "$SELF" "$OUT/raw/exposition.txt" "$OUT/raw/promtool.txt" \
  "$OUT/raw/ready.txt" "$OUT/raw/up.json" "$OUT/raw/p99.json" \
  "$OUT/raw/rate.json" "$OUT/run.env" >"$OUT/SHA256SUMS"
printf 'evidence=%s\n' "$OUT"
