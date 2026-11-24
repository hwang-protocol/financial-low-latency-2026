#!/usr/bin/env bash
# Run 4: safe DPDK ownership switch, one order, then immediate SFC restore.
set -Eeuo pipefail
cd /financial-low-latency
. Documents/reports/run-state/02-trading-baseline.env
OUT="Documents/reports/course-runs/$RUN_ID"
STEP="$OUT/classroom-runs/$(date -u +%Y%m%dT%H%M%S.%NZ)-run04-dpdk"
RAW="$STEP/raw"; mkdir -p "$RAW"
printf 'PARENT_RUN_ID=%s\nSTEP=RUN04_DPDK\n' "$RUN_ID" >"$STEP/run.env"
API=http://10.1.1.101:8088
post_mode(){ curl --max-time 620 -fsS -X POST -H 'Content-Type: application/json' -d '{"mode":"'"$1"'"}' "$API/api/data-plane"; }
restore(){ rc=$?; trap - EXIT; if test "$rc" -ne 0; then bash apps/flle-trading-lab/scripts/transport_labctl.sh sfc "$RUN_ID" >"$RAW/emergency-restore.json" 2>&1 || exit 125; fi; exit "$rc"; }
trap restore EXIT
switch="$(post_mode DPDK)"; printf '%s\n' "$switch" >"$RAW/dpdk-switch.json"
python3 -c 'import json,sys; x=json.load(sys.stdin); raise SystemExit(not(x.get("mode")=="DPDK" and x.get("transition")=="READY" and x.get("owner")=="vfio-pci"))' <<<"$switch"
reply="$(curl -fsS -X POST -H 'Content-Type: application/json' \
  -d '{"symbol":"AAPL","side":"SELL","quantity":1,"limit_price_x10000":1,"transport":"DPDK"}' "$API/api/order")"
printf '%s\n' "$reply" >"$RAW/order-reply.json"
oid="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["client_order_id"])' <<<"$reply")"
executed=0
for _ in $(seq 1 40); do
  state="$(curl -fsS "$API/api/state")"
  python3 -c 'import json,sys; oid=int(sys.argv[1]); rows=[o for o in json.loads(sys.argv[2]).get("orders",[]) if int(o.get("client_order_id",0))==oid]; raise SystemExit(not(rows and rows[0].get("result")=="ORDER_EXECUTED" and int(rows[0].get("order_rtt_ns",0))>0))' "$oid" "$state" && { executed=1; break; }
  sleep 0.25
done
test "$executed" -eq 1
printf '%s\n' "$state" >"$RAW/order-state.json"
bash apps/flle-trading-lab/scripts/transport_labctl.sh attest "$RUN_ID" DPDK "$PWD/$STEP/native-receipts" >"$RAW/path-receipt.json"
restored="$(post_mode SFC)"; printf '%s\n' "$restored" >"$RAW/sfc-restore.json"
python3 -c 'import json,sys; x=json.load(sys.stdin); raise SystemExit(not(x.get("mode")=="SFC" and x.get("transition")=="READY" and x.get("owner")=="sfc"))' <<<"$restored"
trap - EXIT
python3 - "$oid" "$RAW/order-state.json" "$RAW/path-receipt.json" <<'PY' | tee "$RAW/result.txt"
import json,sys; from pathlib import Path
oid=int(sys.argv[1]); app=json.load(open(sys.argv[2])); receipt=json.load(open(sys.argv[3]))
states=list(Path(receipt["local_directory"]).glob("standalone-native-receipts/standalone-*/evidence/state.json"))
if len(states) != 1: raise SystemExit("native DPDK receipt must contain exactly one state.json")
software=json.load(states[0].open())["software_latency"]; engine=software.get("network_engine", software.get("network_reactor"))
if engine != "FSTACK_POLL": raise SystemExit("native DPDK receipt lacks FSTACK_POLL")
row=next(o for o in app["orders"] if int(o.get("client_order_id",0))==oid)
print("===== 运行 ④ · DPDK + F-Stack 真单 =====")
print("task=切到 DPDK 后发送一笔 AAPL 1 股可成交 IOC，并恢复 SFC")
print("result="+row["result"]); print("client_order_id="+str(oid))
print("order_rtt_ns="+str(row["order_rtt_ns"]))
print("engine="+engine); print("restored=SFC/READY/sfc")
print("scope=单笔路径验证；正式延迟比较看运行 ⑤")
PY
(printf 'evidence=%s\n' "$STEP" | tee -a "$RAW/result.txt")
(cd "$STEP" && find native-receipts -type f -print0 | sort -z | xargs -0 sha256sum >native-receipts.SHA256SUMS)
(cd "$STEP" && sha256sum raw/* native-receipts.SHA256SUMS run.env >SHA256SUMS)
