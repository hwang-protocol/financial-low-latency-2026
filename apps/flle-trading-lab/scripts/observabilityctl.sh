#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd -- "$APP_DIR/../.." && pwd)"
OBSERVER_HOST="${FLLE_OBSERVER_HOST:-root@10.1.1.101}"
STAGE=/var/tmp/flle-observability-stage
PROM_DEB="$REPO_ROOT/artifacts/blobs/observability/prometheus/2.31.2/prometheus_2.31.2+ds1-1ubuntu1.22.04.3_amd64.deb"
GRAFANA_DEB="$REPO_ROOT/artifacts/blobs/observability/grafana/13.1.0/grafana_13.1.0_amd64.deb"
PROM_SHA=e9cdd14fd49950215e10ca8b467ba678b7a80369e7df79ce79b913173f30a0e1
GRAFANA_SHA=75412533c4f8c57c3d14a7f11cc048249012e24e2046f19453bacc7d70462215

preflight() {
  test "$(sha256sum "$PROM_DEB" | awk '{print $1}')" = "$PROM_SHA"
  test "$(sha256sum "$GRAFANA_DEB" | awk '{print $1}')" = "$GRAFANA_SHA"
  ssh "$OBSERVER_HOST" "set -eu; test \"\$(. /etc/os-release; echo \$ID:\$VERSION_ID)\" = ubuntu:22.04; curl -fsS http://10.1.1.101:8088/metrics >/dev/null"
}

install_stack() {
  preflight
  ssh "$OBSERVER_HOST" "install -d -m 0755 '$STAGE'"
  if ! ssh "$OBSERVER_HOST" "test \"\$(sha256sum '$STAGE/prometheus.deb' 2>/dev/null | awk '{print \$1}')\" = '$PROM_SHA'"; then
    scp "$PROM_DEB" "$OBSERVER_HOST:$STAGE/prometheus.deb"
  fi
  if ! ssh "$OBSERVER_HOST" "test \"\$(sha256sum '$STAGE/grafana.deb' 2>/dev/null | awk '{print \$1}')\" = '$GRAFANA_SHA'"; then
    scp "$GRAFANA_DEB" "$OBSERVER_HOST:$STAGE/grafana.deb"
  fi
  scp "$APP_DIR/observability/prometheus.yml" "$APP_DIR/observability/grafana.ini" \
      "$APP_DIR/observability/grafana-datasource.yml" \
      "$APP_DIR/observability/grafana-dashboard-provider.yml" \
      "$APP_DIR/observability/flle-trading-baseline.json" "$OBSERVER_HOST:$STAGE/"
  if ! ssh "$OBSERVER_HOST" 'test "$(dpkg-query -W prometheus 2>/dev/null | awk "{print \$2}")" = "2.31.2+ds1-1ubuntu1.22.04.3" && test "$(dpkg-query -W grafana 2>/dev/null | awk "{print \$2}")" = "13.1.0"'; then
    python3 "$REPO_ROOT/assets/common/install-offline-packages.py" "${OBSERVER_HOST#root@}" observability
  fi
  ssh "$OBSERVER_HOST" "set -eu; systemctl stop prometheus grafana-server; install -m 0644 '$STAGE/prometheus.yml' /etc/prometheus/prometheus.yml; install -m 0644 '$STAGE/grafana.ini' /etc/grafana/grafana.ini; install -d -o grafana -g grafana -m 0755 /var/lib/grafana/dashboards/flle; install -m 0644 '$STAGE/grafana-datasource.yml' /etc/grafana/provisioning/datasources/flle.yml; install -m 0644 '$STAGE/grafana-dashboard-provider.yml' /etc/grafana/provisioning/dashboards/flle.yml; install -o grafana -g grafana -m 0644 '$STAGE/flle-trading-baseline.json' /var/lib/grafana/dashboards/flle/flle-trading-baseline.json; systemctl enable --now prometheus grafana-server"
}

verify_stack() {
  ssh "$OBSERVER_HOST" 'set -eu; for _ in $(seq 1 60); do query=$(curl -fsS "http://10.1.1.101:9090/api/v1/query?query=up%7Bjob%3D%22flle-trading%22%7D" 2>/dev/null || true); case "$query" in *"\"value\":["*",\"1\"]"*) curl -fsS http://10.1.1.101:3000/api/health >/dev/null 2>&1 && break;; esac; sleep 1; done; prometheus --version 2>&1 | head -1; /usr/sbin/grafana-server -v; systemctl is-active prometheus grafana-server; curl -fsS http://10.1.1.101:9090/-/ready; curl -fsS http://10.1.1.101:3000/api/health; curl -fsS "http://10.1.1.101:9090/api/v1/query?query=up%7Bjob%3D%22flle-trading%22%7D"; curl -fsS "http://10.1.1.101:3000/api/search?query=FLLE"'
}

case "$ACTION" in
  preflight) preflight ;;
  install) install_stack; verify_stack ;;
  verify) preflight; verify_stack ;;
  *) echo "usage: $0 {preflight|install|verify}" >&2; exit 2 ;;
esac
