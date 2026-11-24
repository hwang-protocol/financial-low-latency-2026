#!/usr/bin/env bash
# Run 2: one OpenOnload order; all diagnostic receipts stay in raw.
set -Eeuo pipefail
cd /qyt-fll
. reports/run-state/02-trading-baseline.env
OUT="reports/course-runs/$RUN_ID"
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
engine=lab["clients"]["trader_onload"]["software"]["network_engine"]
if row["result"] != "ORDER_EXECUTED" or int(row["order_rtt_ns"]) <= 0 or engine != "ONLOAD_USER_STACK":
    raise SystemExit("订单结果、往返时间或收发引擎未通过检查")
print("===== 运行 ② · Onload 单笔验证 =====")
print("[1/3 成交结果]")
print("result="+row["result"]+"  # Exchange 已确认成交")
print("client_order_id="+str(oid)+"  # 按此编号查询本笔订单")
print("\n[2/3 实际收发路径]")
print("engine="+engine+"  # Onload 用户态 TCP 栈收发")
print("\n[3/3 订单往返耗时]")
print("order_rtt_ns="+str(row["order_rtt_ns"])+f"  # {int(row['order_rtt_ns']) / 1000:.3f} µs（微秒）")
print("计时范围：调用发送前 → 最终成交回报解码完成；1000 ns = 1 µs。")
print("\n[结论] 本笔成交与实际路径检查通过。")
print("scope=单笔路径验证；四路快慢看运行 ⑤ 的批量比较")
print("\n本步通过；接着执行运行 ③。")
PY
(printf '# 完整订单、路径记录及校验文件保存在：\nevidence=%s\n' "$STEP" | tee -a "$RAW/result.txt")
(cd "$STEP" && find native-receipts -type f -print0 | sort -z | xargs -0 sha256sum >native-receipts.SHA256SUMS)
(cd "$STEP" && sha256sum raw/* native-receipts.SHA256SUMS run.env >SHA256SUMS)
