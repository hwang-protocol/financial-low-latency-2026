#!/usr/bin/env bash
# Run 2: one OpenOnload order; all diagnostic receipts stay in raw.
set -Eeuo pipefail
cd /financial-low-latency
. Documents/reports/run-state/02-trading-baseline.env
OUT="Documents/reports/course-runs/$RUN_ID"
STEP="$OUT/classroom-runs/$(date -u +%Y%m%dT%H%M%S.%NZ)-run02-onload"
RAW="$STEP/raw"; mkdir -p "$RAW"
printf 'PARENT_RUN_ID=%s\nSTEP=RUN02_OPENONLOAD\n' "$RUN_ID" >"$STEP/run.env"
API=http://10.1.1.101:8088
reply="$(curl -fsS -X POST -H 'Content-Type: application/json' \
  -d '{"symbol":"AAPL","side":"SELL","quantity":1,"limit_price_x10000":1,"transport":"OPENONLOAD"}' \
  "$API/api/order")"
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
lab="$(curl -fsS "$API/api/transport-lab")"; printf '%s\n' "$lab" >"$RAW/transport-lab.json"
bash apps/flle-trading-lab/scripts/transport_labctl.sh attest "$RUN_ID" OPENONLOAD \
  "$PWD/$STEP/native-receipts" >"$RAW/path-receipt.json"
python3 - "$oid" "$RAW/order-state.json" "$RAW/transport-lab.json" <<'PY' | tee "$RAW/result.txt"
import json,sys
oid=int(sys.argv[1]); app=json.load(open(sys.argv[2])); lab=json.load(open(sys.argv[3]))
row=next(o for o in app["orders"] if int(o.get("client_order_id",0))==oid)
print("===== 运行 ② · OpenOnload 真单 =====")
print("task=用 OpenOnload 发送一笔 AAPL 1 股可成交 IOC")
print("result="+row["result"]); print("client_order_id="+str(oid))
print("order_rtt_ns="+str(row["order_rtt_ns"]))
print("engine="+lab["clients"]["trader_onload"]["software"]["network_engine"])
print("scope=单笔路径验证；正式延迟比较看运行 ⑤")
PY
(printf 'evidence=%s\n' "$STEP" | tee -a "$RAW/result.txt")
(cd "$STEP" && find native-receipts -type f -print0 | sort -z | xargs -0 sha256sum >native-receipts.SHA256SUMS)
(cd "$STEP" && sha256sum raw/* native-receipts.SHA256SUMS run.env >SHA256SUMS)
