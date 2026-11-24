#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-04-prometheus-up-cycle"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"

printf '===== root@10.1.1.101 · Prometheus up cycle =====\n'; ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.101 \
  bash -s <<'REMOTE' 2>&1 | tee "$OUT/raw/result.txt"
set -Eeuo pipefail
cd /opt/flle/observability
trap 'docker compose start node-exporter >/dev/null 2>&1 || true' EXIT
query() {
  curl -fsSG --data-urlencode 'query=up{job="node-exporter"}' \
    http://127.0.0.1:9090/api/v1/query
  printf '\n'
}
printf '$ Prometheus instant query · exporter running\n'; query
docker compose stop node-exporter
sleep 3
printf '$ Prometheus instant query · exporter stopped\n'; query
docker compose start node-exporter
sleep 3
printf '$ Prometheus instant query · exporter restarted\n'; query
REMOTE
(cd "$OUT" && sha256sum raw/result.txt run.env >SHA256SUMS); printf 'evidence=%s\n' "$OUT"
