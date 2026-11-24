#!/usr/bin/env bash
set -euo pipefail
cd /financial-low-latency
REPO_ROOT=/financial-low-latency
SELF="$REPO_ROOT/Documents/newDoc/assets/04-live-observability/00-restore-observability.sh"
CTL="$REPO_ROOT/apps/flle-trading-lab/scripts/observabilityctl.sh"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-04-observability-restore"
OUT="$REPO_ROOT/Documents/reports/course-runs/$RUN_ID"
mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\nPROFILE=HOST_NATIVE_PROMETHEUS_GRAFANA\n' "$RUN_ID" >"$OUT/run.env"
# ~~~~~装或同步 .101 上的宿主机 Prometheus / Grafana，不用 Docker~~~~~
"$CTL" install 2>&1 | tee "$OUT/raw/restore.txt"
# ~~~~~读两项 systemd 状态；封 SHA，并写出观测栈 URL~~~~~
ssh root@10.1.1.101 'systemctl show prometheus grafana-server -p Id -p ActiveState -p SubState -p MainPID' >"$OUT/raw/services.txt"
sha256sum "$SELF" "$CTL" \
  "$REPO_ROOT/apps/flle-trading-lab/observability/prometheus.yml" \
  "$REPO_ROOT/apps/flle-trading-lab/observability/grafana.ini" \
  "$REPO_ROOT/apps/flle-trading-lab/observability/grafana-datasource.yml" \
  "$REPO_ROOT/apps/flle-trading-lab/observability/grafana-dashboard-provider.yml" \
  "$REPO_ROOT/apps/flle-trading-lab/observability/flle-trading-baseline.json" \
  "$OUT/raw/restore.txt" "$OUT/raw/services.txt" "$OUT/run.env" >"$OUT/SHA256SUMS"
printf 'STACK_RUN_ID=%s\nPROMETHEUS_URL=http://10.1.1.101:9090/\nGRAFANA_URL=http://10.1.1.101:3000/d/flle-trading-baseline/\n' "$RUN_ID" >Documents/reports/run-state/04-observability-stack.env
printf 'evidence=%s\n' "$OUT"
