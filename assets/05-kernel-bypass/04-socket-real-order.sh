#!/usr/bin/env bash
# Run 1: one Kernel Socket order; all diagnostic receipts stay in raw.
set -Eeuo pipefail
cd /qyt-fll
. reports/run-state/02-trading-baseline.env
OUT="reports/course-runs/$RUN_ID"
STEP="$OUT/classroom-runs/$(date -u +%Y%m%dT%H%M%S.%NZ)-run01-socket"
RAW="$STEP/raw"; mkdir -p "$RAW"
printf 'PARENT_RUN_ID=%s\nSTEP=RUN01_SOCKET\n' "$RUN_ID" >"$STEP/run.env"
API=http://10.1.1.101:8088
STAGE='检查第五章测试配置'
oid=''
report_failure(){
  local rc=$?
  trap - ERR
  printf '\n[运行①未完成] %s；退出码=%s\n[记录目录] %s\n' "$STAGE" "$rc" "$STEP" >&2
  if test -n "$oid"; then printf '[订单已提交] 编号=%s，请按编号查看结果；重跑会提交新订单。\n' "$oid" >&2; fi
  if test -s "$RAW/path-receipt-error.txt"; then tail -n 20 "$RAW/path-receipt-error.txt" >&2; fi
  exit "$rc"
}
trap report_failure ERR
printf '[1/3] 检查测试配置\n'
curl -fsS --connect-timeout 2 --max-time 10 "$API/api/state" >"$RAW/pre-state.json"
curl -fsS --connect-timeout 2 --max-time 10 "$API/api/transport-lab" >"$RAW/pre-lab.json"
python3 - "$RAW/pre-state.json" "$RAW/pre-lab.json" <<'PY'
import json, sys
app, lab = [json.load(open(p)) for p in sys.argv[1:]]
client = lab.get('clients', {}).get('trader_manual', {})
software = client.get('software', {})
ready = (app.get('experiment_profile') == 'TRANSPORT'
         and (lab.get('mode'), lab.get('transition'), lab.get('owner')) == ('SFC', 'READY', 'sfc')
         and client.get('health', {}).get('status') == 'ONLINE'
         and software.get('queue_locked') is True
         and software.get('queue_mode') == 'DEQUE_CV'
         and software.get('network_engine') == 'KERNEL_SOCKET')
if not ready:
    print('[尚未下单] 当前不是就绪的第五章 Kernel Socket 测试配置。', file=sys.stderr)
    print('请先执行准备 B：bash assets/05-kernel-bypass/03-four-path-lab-ready.sh', file=sys.stderr)
    raise SystemExit(2)
PY
STAGE='提交订单并等待成交'
printf '[2/3] 提交 1 股模拟订单并等待成交\n'
reply="$(curl -fsS -X POST -H 'Content-Type: application/json' \
  -d '{"symbol":"AAPL","side":"BUY","quantity":1,"limit_price_x10000":999999999999,"transport":"SOCKET"}' \
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
STAGE='核验实际收发路径'
printf '[3/3] 核验实际收发路径\n'
bash apps/flle-trading-lab/scripts/transport_labctl.sh attest "$RUN_ID" SOCKET \
  "$PWD/$STEP/native-receipts" >"$RAW/path-receipt.json" 2>"$RAW/path-receipt-error.txt"
python3 - "$oid" "$RAW/order-state.json" "$RAW/transport-lab.json" <<'PY' | tee "$RAW/result.txt"
import json,sys
oid=int(sys.argv[1]); app=json.load(open(sys.argv[2])); lab=json.load(open(sys.argv[3]))
row=next(o for o in app["orders"] if int(o.get("client_order_id",0))==oid)
engine=lab["clients"]["trader_manual"]["software"]["network_engine"]
if row["result"] != "ORDER_EXECUTED" or int(row["order_rtt_ns"]) <= 0 or engine != "KERNEL_SOCKET":
    raise SystemExit("订单结果、往返时间或收发引擎未通过检查")
print("===== 运行 ① · Kernel Socket 单笔验证 =====")
print("[1/3 成交结果]")
print("result="+row["result"]+"  # Exchange 已确认成交")
print("client_order_id="+str(oid)+"  # 按此编号查询本笔订单")
print("\n[2/3 实际收发路径]")
print("engine="+engine+"  # Linux 内核 Socket 收发")
print("\n[3/3 订单往返耗时]")
print("order_rtt_ns="+str(row["order_rtt_ns"])+f"  # {int(row['order_rtt_ns']) / 1000:.3f} µs（微秒）")
print("计时范围：调用发送前 → 最终成交回报解码完成；1000 ns = 1 µs。")
print("\n[结论] 本笔成交与实际路径检查通过。")
print("scope=单笔路径验证；四路快慢看运行 ⑤ 的批量比较")
print("\n本步通过；接着执行运行 ②。")
PY
(printf '# 完整订单、路径记录及校验文件保存在：\nevidence=%s\n' "$STEP" | tee -a "$RAW/result.txt")
(cd "$STEP" && find native-receipts -type f -print0 | sort -z | xargs -0 sha256sum >native-receipts.SHA256SUMS)
(cd "$STEP" && sha256sum raw/* native-receipts.SHA256SUMS run.env >SHA256SUMS)
