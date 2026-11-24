#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-04-observability-services-compose"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"

printf '===== root@10.1.1.101 · observability Compose =====\n'; ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.101 bash -s <<'REMOTE' 2>&1 | tee "$OUT/raw/result.txt"
set -Eeuo pipefail
root=/opt/flle/observability; install -d -m 755 "$root"
cat >"$root/prometheus.yml" <<'YAML'
global:
  scrape_interval: 1s
scrape_configs:
  - job_name: prometheus
    static_configs: [{targets: ["prometheus:9090"]}]
  - job_name: node-exporter
    static_configs: [{targets: ["node-exporter:9100"]}]
YAML
cat >"$root/compose.yaml" <<'YAML'
name: flle-observability
services:
  prometheus:
    image: quay.io/prometheus/prometheus:v2.31.2
    pull_policy: never
    command: ["--config.file=/etc/prometheus/prometheus.yml"]
    ports: ["9090:9090"]
    volumes: ["./prometheus.yml:/etc/prometheus/prometheus.yml:ro"]
    restart: unless-stopped
  node-exporter: {image: "quay.io/prometheus/node-exporter:v1.3.1", pull_policy: never, ports: ["9100:9100"], restart: unless-stopped}
  loki: {image: "grafana/loki:3.7.2", pull_policy: never, ports: ["3100:3100"], restart: unless-stopped}
  grafana: {image: "grafana/grafana:13.1.0", pull_policy: never, ports: ["3000:3000"], restart: unless-stopped}
YAML
cd "$root"; docker compose config; docker compose up -d --pull never
for try in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:9090/-/ready >/dev/null 2>&1 &&
     curl -fsS http://127.0.0.1:9100/metrics >/dev/null 2>&1 &&
     curl -fsS http://127.0.0.1:3100/ready >/dev/null 2>&1 &&
     curl -fsS http://127.0.0.1:3000/api/health >/dev/null 2>&1; then break; fi
  sleep 1
done
printf '$ docker compose ps\n'; docker compose ps
printf '$ curl -fsS http://127.0.0.1:9090/-/ready\n'; curl -fsS http://127.0.0.1:9090/-/ready
printf '$ curl node-exporter /metrics HTTP status\n'; curl -fsS -o /dev/null -w 'HTTP %{http_code}\n' http://127.0.0.1:9100/metrics
printf '$ curl -fsS http://127.0.0.1:3100/ready\n'; curl -fsS http://127.0.0.1:3100/ready
printf '$ curl -fsS http://127.0.0.1:3000/api/health\n'; curl -fsS http://127.0.0.1:3000/api/health; echo
REMOTE
(cd "$OUT" && sha256sum raw/result.txt run.env >SHA256SUMS); printf 'evidence=%s\n' "$OUT"
