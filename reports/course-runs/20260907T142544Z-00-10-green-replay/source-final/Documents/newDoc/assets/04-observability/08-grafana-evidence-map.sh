#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-04-grafana-evidence-map"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"

printf '===== root@10.1.1.101 · Grafana health =====\n'; ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.101 \
  bash -s <<'REMOTE' 2>&1 | tee "$OUT/raw/health.json"
set -Eeuo pipefail
cd /opt/flle/observability
printf '$ docker compose ps grafana\n'; docker compose ps grafana
printf '$ curl -fsS http://127.0.0.1:3000/api/health\n'
curl -fsS http://127.0.0.1:3000/api/health
REMOTE
printf '===== jump host · dashboard asset =====\n'; cp Documents/newDoc/assets/04-observability/tail-latency-dashboard.json \
  "$OUT/raw/dashboard.json"
printf '$ cat Documents/newDoc/assets/04-observability/tail-latency-dashboard.json\n'
cat "$OUT/raw/dashboard.json"
printf '===== jump host · dashboard mappings =====\n'; python3 - <<'PY' 2>&1 | tee "$OUT/raw/result.txt"
import json
path = "Documents/newDoc/assets/04-observability/tail-latency-dashboard.json"
with open(path, "r", encoding="utf-8") as source:
    dashboard = json.load(source)
panels = dashboard["panels"]
for panel in panels:
    target = panel["targets"][0]
    print("%s -> type=%s uid=%s expr=%s" %
          (panel["title"], panel["datasource"]["type"],
           panel["datasource"]["uid"], target["expr"]))
PY
(cd "$OUT" && sha256sum raw/*.json raw/*.txt run.env >SHA256SUMS); printf 'evidence=%s\n' "$OUT"
