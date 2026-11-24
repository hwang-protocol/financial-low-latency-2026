#!/usr/bin/env bash
# 教师/审计入口。学生正文运行 ③ 改为打开浏览器，不再粘贴本脚本。
set -euo pipefail
cd /financial-low-latency
REPO_ROOT=/financial-low-latency
SELF="$REPO_ROOT/Documents/newDoc/assets/04-live-observability/03-verify-grafana-dashboard.sh"
DASHBOARD="$REPO_ROOT/apps/flle-trading-lab/observability/flle-trading-baseline.json"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-04-grafana-dashboard"
OUT="$REPO_ROOT/Documents/reports/course-runs/$RUN_ID"
mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\nGRAFANA_URL=http://10.1.1.101:3000/d/flle-trading-baseline/\n' "$RUN_ID" >"$OUT/run.env"
# ~~~~~读 Grafana health，并按 UID 取回已部署 dashboard~~~~~
curl -fsS http://10.1.1.101:3000/api/health | tee "$OUT/raw/health.json"; echo
curl -fsS 'http://10.1.1.101:3000/api/search?query=FLLE' | tee "$OUT/raw/search.json"; echo
curl -fsS http://10.1.1.101:3000/api/dashboards/uid/flle-trading-baseline >"$OUT/raw/dashboard.json"
# ~~~~~匿名打开课程页面，确认 HTTP 200~~~~~
curl -fsS -o /dev/null -w 'dashboard_http=%{http_code} content_type=%{content_type}\n' \
  http://10.1.1.101:3000/d/flle-trading-baseline/ | tee "$OUT/raw/http.txt"
printf 'dashboard=http://10.1.1.101:3000/d/flle-trading-baseline/\n' | tee "$OUT/raw/url.txt"
# ~~~~~封 SHA~~~~~
sha256sum "$SELF" "$DASHBOARD" "$OUT/raw/health.json" "$OUT/raw/search.json" \
  "$OUT/raw/dashboard.json" "$OUT/raw/http.txt" "$OUT/raw/url.txt" "$OUT/run.env" >"$OUT/SHA256SUMS"
printf 'evidence=%s\n' "$OUT"
