#!/usr/bin/env bash
set -euo pipefail
cd /financial-low-latency
REPO_ROOT=/financial-low-latency
SELF="$REPO_ROOT/Documents/newDoc/assets/05-live-software/00-install-hot-path-dashboard.sh"
DASHBOARD="$REPO_ROOT/apps/flle-trading-lab/observability/flle-software-hot-path.json"
source "$REPO_ROOT/Documents/reports/run-state/04-observability-stack.env"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-05-software-dashboard"
OUT="$REPO_ROOT/Documents/reports/course-runs/$RUN_ID"
mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\nDASHBOARD_URL=http://10.1.1.101:3000/d/flle-software-hot-path/\n' "$RUN_ID" >"$OUT/run.env"
# ~~~~~校验 dashboard JSON，再同步到 .101 Grafana~~~~~
python3 -m json.tool "$DASHBOARD" >/dev/null
scp -q "$DASHBOARD" root@10.1.1.101:/var/tmp/flle-software-hot-path.json
ssh root@10.1.1.101 "set -eu; install -o grafana -g grafana -m 0644 /var/tmp/flle-software-hot-path.json /var/lib/grafana/dashboards/flle/flle-software-hot-path.json; rm -f /var/tmp/flle-software-hot-path.json; systemctl is-active grafana-server" | tee "$OUT/raw/service.txt"
# ~~~~~等 UID 可取回，确认 8 块 panel~~~~~
for _ in $(seq 1 15); do curl -fsS http://10.1.1.101:3000/api/dashboards/uid/flle-software-hot-path >"$OUT/raw/dashboard.json" 2>/dev/null && break; sleep 1; done
python3 - "$OUT/raw/dashboard.json" <<'PY' | tee "$OUT/raw/result.txt"
import json,sys
value=json.load(open(sys.argv[1], encoding="utf-8"))
assert value["dashboard"]["uid"] == "flle-software-hot-path"
assert len(value["dashboard"]["panels"]) == 8
print("dashboard_uid=flle-software-hot-path panels=8")
print("grafana_service=active access=anonymous_viewer")
print("dashboard=http://10.1.1.101:3000/d/flle-software-hot-path/")
PY
# ~~~~~封 SHA，写出驾驶舱 URL~~~~~
sha256sum "$SELF" "$DASHBOARD" "$OUT/raw/service.txt" "$OUT/raw/dashboard.json" "$OUT/raw/result.txt" "$OUT/run.env" >"$OUT/SHA256SUMS"
printf 'DASHBOARD_RUN_ID=%s\nDASHBOARD_URL=http://10.1.1.101:3000/d/flle-software-hot-path/\n' "$RUN_ID" >Documents/reports/run-state/05-software-dashboard.env
printf 'evidence=%s\n' "$OUT"
