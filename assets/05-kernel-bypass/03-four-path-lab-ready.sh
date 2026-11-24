#!/usr/bin/env bash
# Select the already-deployed comparison clients; keep the same platform and GUI.
set -Eeuo pipefail
cd /qyt-fll
test -s reports/run-state/02-trading-baseline.env || { echo "Missing platform state: run Chapter 02 deployment first" >&2; exit 2; }
source reports/run-state/02-trading-baseline.env
[[ "$RUN_ID" =~ ^[A-Za-z0-9._-]+-02-trading-platform$ ]] || { echo "Legacy platform state: run Chapter 02 deployment before Chapter 05" >&2; exit 2; }
CTL=apps/flle-trading-lab/scripts/transport_labctl.sh
if pgrep -af "measure_four_transports.py --run-id $RUN_ID" >/dev/null \
  || pgrep -af "transport_labctl.sh measure $RUN_ID" >/dev/null \
  || pgrep -af "transport_labctl.sh dpdk $RUN_ID" >/dev/null; then
  echo "正式比较正在使用这个平台，等它结束后再跑准备 B。" >&2
  exit 3
fi
OUT="reports/course-runs/$RUN_ID/profile-switches/$(date -u +%Y%m%dT%H%M%S.%NZ)"
mkdir -p "$OUT/raw"
STAGE='读取当前平台身份'; LOG="$OUT/raw/before.txt"
STAGE_ACTIVE=0
finish_stage(){
  printf '[完成] %s（%s 秒）\n' "$STAGE" "$((SECONDS - STAGE_STARTED))" >&2
  STAGE_ACTIVE=0
}
begin_stage(){
  if test "$STAGE_ACTIVE" -eq 1; then finish_stage; fi
  STAGE="$2"; LOG="$OUT/raw/$3"; STAGE_STARTED=$SECONDS
  STAGE_ACTIVE=1
  printf '\n[%s/7] %s\n[日志] %s\n' "$1" "$STAGE" "$LOG" >&2
}
report_failure(){
  local rc=$?
  trap - ERR
  printf '\n[准备 B 未完成] 阶段：%s；退出码：%s\n' "$STAGE" "$rc" >&2
  if test -s "$LOG"; then
    printf '[日志末尾]\n' >&2
    tail -n 35 "$LOG" >&2
  fi
  printf '[完整记录] %s\n' "$OUT" >&2
  exit "$rc"
}
trap report_failure ERR
identity(){
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.1 \
    "set -eu; cat '$RUN_DIR/exchange.identity'; sha256sum '$RUN_DIR/transport.deployed.sha256'"
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.101 bash -s -- "$RUN_DIR" <<'REMOTE'
run_dir="$1"
set -eu
if test -s "$run_dir/gateway.identity"; then cat "$run_dir/gateway.identity"
else printf 'gateway.identity=ABSENT\n'; fi
sha256sum "$run_dir/source.sha256"
REMOTE
}
printf '===== 准备 B · 切换测试配置 =====\n使用第二章备好的程序；各阶段完成后显示耗时。\n' >&2
begin_stage 1 '读取当前平台身份' before.txt
identity >"$OUT/raw/before.txt"
begin_stage 2 '核对第二章准备的测试客户端' posix-qos-prep.txt
bash apps/flle-trading-lab/scripts/prepare-posix-qos.sh "$RUN_ID" --check >"$LOG" 2>&1
begin_stage 3 '切换到路径测试客户端' start.txt
bash "$CTL" start "$RUN_ID" >"$OUT/raw/start.txt" 2>&1
begin_stage 4 '核对客户端默认打标' order-dscp.txt
python3 apps/flle-trading-lab/scripts/order-dscp.py --transport SOCKET --expect 0 GET >"$LOG"
python3 apps/flle-trading-lab/scripts/order-dscp.py --transport OPENONLOAD --expect 0 GET >>"$LOG"
begin_stage 5 '核验测试环境' verify.txt
bash "$CTL" verify "$RUN_ID" >"$OUT/raw/verify.txt" 2>&1
begin_stage 6 '核对 Exchange 与网页是否保持原进程' after.txt
identity >"$OUT/raw/after.txt"
python3 - "$OUT/raw/before.txt" "$OUT/raw/after.txt" <<'PY'
import sys
before = open(sys.argv[1]).read().splitlines()
after = open(sys.argv[2]).read().splitlines()

def sha(rows, name):
    for line in rows:
        parts = line.split()
        if len(parts) >= 2 and parts[-1].endswith(name):
            return parts[0]
    raise SystemExit(f"缺少 {name} 校验值")

def pids(rows):
    return [line for line in rows if line.startswith("pid=")]

def gateway(rows):
    found = [line for line in rows if line == "gateway.identity=ABSENT"]
    values = pids(rows)
    if found:
        return "ABSENT"
    if len(values) >= 2:
        return values[1]
    raise SystemExit("缺少网页进程身份")

if pids(before)[:1] != pids(after)[:1]:
    raise SystemExit("Exchange 进程身份已变化，停止准备 B。")
if sha(before, "transport.deployed.sha256") != sha(after, "transport.deployed.sha256"):
    raise SystemExit("Exchange 部署清单已变化，停止准备 B。")
if sha(before, "source.sha256") != sha(after, "source.sha256"):
    raise SystemExit("网页文件清单已变化，停止准备 B。")
was, now = gateway(before), gateway(after)
if was != "ABSENT" and was != now:
    raise SystemExit("网页进程已被替换，停止准备 B。")
if now == "ABSENT":
    raise SystemExit("切换后仍没有网页进程身份。")
PY
ready=0
begin_stage 7 '等待三路客户端就绪' transport-lab.json
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
finish_stage
{
  cat <<EOF
准备 B：停掉普通客户端，换上测试客户端
# 本步只换客户端，不下单。Exchange 和网页保持原进程。

# 1. 沿用的平台
platform_run=$RUN_ID
# 第 02 章已经部署的交易平台，不另起一套系统。

# 2. 切换结果
result=READY
# 前三路测试客户端已就绪。

# 3. 当前配置
profile=TRANSPORT
# 已停掉普通 AUTO / MANUAL，换上路径测试客户端。

# 4. 四路客户端
clients=Kernel Socket, Onload, TCPDirect ONLINE; DPDK WAITING
# 前三路在线；DPDK 等运行 ④ 再独占网卡。

# 5. 订单队列
queue_mode=DEQUE_CV
# 四路都用第 04 章的 deque + 互斥锁 + 条件变量。

# 6. Exchange 与网页
exchange_and_gui=UNCHANGED
# 进程身份和文件清单与切换前一致。

# 7. 订单打标
order_dscp=0
# Socket / Onload 默认不打标；第 06 章才临时设为 DSCP 46。

# 可以进入运行 ① 下单。
# 完整校验记录保存在下方 evidence 目录。
evidence=$OUT
EOF
} | tee "$OUT/raw/result.txt"
(cd "$OUT" && sha256sum raw/* >SHA256SUMS)
