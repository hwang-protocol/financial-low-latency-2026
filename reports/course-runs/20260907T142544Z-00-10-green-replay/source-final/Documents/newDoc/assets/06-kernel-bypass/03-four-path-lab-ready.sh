#!/usr/bin/env bash
# Select the already-deployed comparison clients; keep the same platform and GUI.
set -Eeuo pipefail
cd /financial-low-latency
test -s Documents/reports/run-state/02-trading-baseline.env || { echo "Missing platform state: run Chapter 02 deployment first" >&2; exit 2; }
source Documents/reports/run-state/02-trading-baseline.env
[[ "$RUN_ID" =~ ^[A-Za-z0-9._-]+-02-trading-platform$ ]] || { echo "Legacy platform state: run Chapter 02 deployment before Chapter 06" >&2; exit 2; }
CTL=apps/flle-trading-lab/scripts/transport_labctl.sh
OUT="Documents/reports/course-runs/$RUN_ID/profile-switches/$(date -u +%Y%m%dT%H%M%S.%NZ)"
mkdir -p "$OUT/raw"
identity(){
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.1 "cat '$RUN_DIR/exchange.identity'; sha256sum '$RUN_DIR/transport.deployed.sha256'"
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.101 "cat '$RUN_DIR/gateway.identity'; sha256sum '$RUN_DIR/source.sha256'"
}
identity >"$OUT/raw/before.txt"
bash "$CTL" start "$RUN_ID" >"$OUT/raw/start.txt" 2>&1
bash "$CTL" verify "$RUN_ID" >"$OUT/raw/verify.txt" 2>&1
identity >"$OUT/raw/after.txt"
cmp "$OUT/raw/before.txt" "$OUT/raw/after.txt"
ready=0
for _ in $(seq 1 60); do
  curl -fsS http://10.1.1.101:8088/api/transport-lab >"$OUT/raw/transport-lab.json"
  if python3 - "$OUT/raw/transport-lab.json" <<'PY'
import json,sys
x=json.load(open(sys.argv[1]))
ready=(x['mode']=='SFC' and x['transition']=='READY' and x['owner']=='sfc'
       and all(x['clients'][n]['health']['status']=='ONLINE'
               for n in ('trader_manual','trader_onload','trader_tcpdirect')))
raise SystemExit(0 if ready else 1)
PY
  then ready=1; break; fi
  sleep 0.5
done
test "$ready" -eq 1
printf '===== 固定路径测试配置 =====\nplatform_run=%s\nresult=READY\nprofile=TRANSPORT\nclients=Socket, Onload, TCPDirect ONLINE; DPDK WAITING\nqueue_mode=DEQUE_CV\nexchange_and_gui=UNCHANGED\nevidence=%s\n' "$RUN_ID" "$OUT" | tee "$OUT/raw/result.txt"
(cd "$OUT" && sha256sum raw/* >SHA256SUMS)
