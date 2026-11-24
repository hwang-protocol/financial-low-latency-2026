#!/usr/bin/env bash
# Called once per green card by stage-session.py. Never advances to another card.
set -Eeuo pipefail
cd /financial-low-latency
source Documents/newDoc/assets/common/flle-remote.sh
ROOT=/financial-low-latency
ASSET="$ROOT/Documents/newDoc/assets/09-p4"
COMMON="$ROOT/Documents/newDoc/assets/common"
EOS="$COMMON/eos_cli.py"
: "${RUN_ID:?}" "${OUT:?}" "${ORIGINAL_MODE:?}"
[[ "$RUN_ID" =~ ^[0-9]{8}T[0-9]{6}Z-09-p4-drop-live$ ]]
test "$OUT" = "$ROOT/Documents/reports/course-runs/$RUN_ID"
REMOTE="/var/tmp/$RUN_ID"
API=http://10.1.1.101:8088
remote11(){ ssh -n "${FLLE_SSH_OPTS[@]}" root@10.1.1.11 "$@"; }
remote11_cli(){ ssh "${FLLE_SSH_OPTS[@]}" root@10.1.1.11 "$@"; }
replay_control(){
  python3 - "$API" "$1" "$OUT/raw/replay-$1.json" <<'PY'
import json, sys, time, urllib.request
api, action, output = sys.argv[1:]
request = urllib.request.Request(api+'/api/replay', data=json.dumps({'action':action}).encode(), headers={'Content-Type':'application/json'})
with urllib.request.urlopen(request, timeout=5) as response:
    assert json.load(response).get('ok') is True
expected = {'PAUSE':'PAUSED', 'RESUME':'PLAYING'}[action]
deadline = time.monotonic()+5
while time.monotonic() < deadline:
    with urllib.request.urlopen(api+'/api/state', timeout=5) as response:
        state = json.load(response)
    if state['replay']['status'] == expected:
        with open(output, 'w') as out: json.dump(state, out)
        break
    time.sleep(0.1)
else:
    raise SystemExit('replay state did not become '+expected)
PY
}
cli_step(){
  local receipt="$1" command="$2" purpose="$3" interpretation="$4"
  printf '%s\n' '' "RuntimeCmd: $command" "# 作用：$purpose" '# 本条命令的原生输出：'
  printf '%s\n' "$command" | remote11_cli "simple_switch_CLI --thrift-port 9090" | tee -a "$receipt"
  if grep -Eq 'Error:|Invalid (table|register|counter|command)' "$receipt"; then
    printf 'CLI返回错误，停止本步。\n' >&2; return 1
  fi
  printf '%s\n' "# 输出解读：$interpretation"
}

configure(){
bash "$COMMON/check-filter-handoff.sh" bridge >"$OUT/raw/handoff-before.txt"
bash "$COMMON/feed-guardianctl.sh" direct >"$OUT/raw/feed-guardian.txt"
curl -fsS "$API/api/state" >"$OUT/raw/state-before.json"
python3 "$EOS" --plan "$ASSET/p4-trading-show.plan" --output "$OUT/raw/eos-before.txt" --mode show >/dev/null
grep -q 'VLAN 100 not found' "$OUT/raw/eos-before.txt"
grep -q 'VLAN 200 not found' "$OUT/raw/eos-before.txt"
# Only this marker authorizes automatic restoration: the ownership gates passed.
touch "$OUT/armed"
remote11 "mkdir '$REMOTE'"
SOURCE_SHA="$(sha256sum "$ASSET/trading_bridge_nvda_drop.p4" | awk '{print $1}')"
printf 'RUN_ID=%s\nSOURCE_SHA256=%s\nORIGINAL_MODE=%s\n' "$RUN_ID" "$SOURCE_SHA" "$ORIGINAL_MODE" >"$OUT/run.env"
scp -q "${FLLE_SSH_OPTS[@]}" "$ASSET/trading_bridge_nvda_drop.p4" root@10.1.1.101:"$REMOTE.p4"
ssh -n "${FLLE_SSH_OPTS[@]}" root@10.1.1.101 "p4c-bm2-ss --p4v 16 --p4runtime-files '$REMOTE.p4info.txt' -o '$REMOTE.json' '$REMOTE.p4'"
scp -q "${FLLE_SSH_OPTS[@]}" root@10.1.1.101:"$REMOTE.json" "$OUT/artifacts/trading_bridge_nvda_drop.json"
test "$(ssh -n "${FLLE_SSH_OPTS[@]}" root@10.1.1.101 "sha256sum '$REMOTE.p4'" | awk '{print $1}')" = "$SOURCE_SHA"
printf 'JSON_SHA256=%s\n' "$(sha256sum "$OUT/artifacts/trading_bridge_nvda_drop.json" | awk '{print $1}')" >>"$OUT/run.env"
cp "$ASSET/trading_bridge_nvda_drop.p4" "$ASSET/live-support/stage-session.py" "$0" \
  "$COMMON/feed-guardianctl.sh" "$COMMON/wait-feed-state.py" \
  "$COMMON/assert-feed-order-gate.py" "$COMMON/assert-feed-gap-ui.py" \
  "$COMMON/prove-trading-recovered.py" \
  "$OUT/source/"
scp -q "${FLLE_SSH_OPTS[@]}" "$OUT/artifacts/trading_bridge_nvda_drop.json" root@10.1.1.11:"$REMOTE/"

python3 "$EOS" --plan "$ASSET/p4-trading-isolate-tools.plan" --output "$OUT/raw/eos-isolate-tools.txt" --mode controlled-config
remote11 "set -Eeuo pipefail; ip link set dev ens64f0np0 up; ip link set dev ens64f1np1 up; cd '$REMOTE'; nohup simple_switch --log-console --log-level warn --interface 1@ens64f0np0 --interface 2@ens64f1np1 --thrift-port 9090 trading_bridge_nvda_drop.json >simple_switch.log 2>&1 </dev/null & echo \$! >simple_switch.pid; sleep 2; kill -0 \$(cat simple_switch.pid)"
# CLI 逐条演示：table-install
: >"$OUT/raw/table-install.txt"
cli_step "$OUT/raw/table-install.txt" \
  'table_add IngressImpl.unicast_dst IngressImpl.forward 00:0f:53:d3:af:20 => 1' \
  '配置去往 Exchange 的二层转发：目的 MAC 命中后走 BMv2 端口1。' \
  '出现Entry has been added表示表项已写入；runtime data的00:01对应出口1。'
cli_step "$OUT/raw/table-install.txt" \
  'table_add IngressImpl.unicast_dst IngressImpl.forward 00:0f:53:d3:af:21 => 2' \
  '配置去往 Trader 的二层转发：目的 MAC 命中后走 BMv2 端口2。' \
  '出现Entry has been added表示表项已写入；runtime data的00:02对应出口2。'
cli_step "$OUT/raw/table-install.txt" \
  'table_add IngressImpl.market_policy IngressImpl.select_policy 0x14010101 0xef140114 0x41 8095 0x4e56444120202020 =>' \
  '装入行情规则：源20.1.1.1、目的239.20.1.20、Type A、Locate8095、NVDA；命中只标记policy_hit。' \
  'match key列出五个匹配值，action是select_policy；这里只装规则，尚未给丢包额度。'
cli_step "$OUT/raw/table-install.txt" \
  'register_write IngressImpl.remaining_drops 0 0' \
  '把一次性丢包额度设为0，先验证放行。' \
  '这条写命令通常只返回提示符；后面用register_read读回额度。'
cli_step "$OUT/raw/table-install.txt" \
  'register_write IngressImpl.dropped_sequence 0 0' \
  '清空本次丢包序号记录。' \
  '这条写命令通常只返回提示符；丢包发生后再读取记录的序号。'
cli_step "$OUT/raw/table-install.txt" \
  'table_dump IngressImpl.market_policy' \
  '查看实际装入的五个匹配值和动作；不是只看P4表结构。' \
  'Match key是表内实际匹配值；Action entry是命中动作；默认NoAction表示不命中这条策略。'
cli_step "$OUT/raw/table-install.txt" \
  'register_read IngressImpl.remaining_drops 0' \
  '读回索引0的额度，确认初始值为0。' \
  'remaining_drops[0]=0表示初始未武装；它不代表已经丢过包。'
python3 "$EOS" --plan "$ASSET/p4-trading-cut-endpoints.plan" --output "$OUT/raw/eos-cut-endpoints.txt" --mode controlled-config
ssh -n "${FLLE_SSH_OPTS[@]}" root@10.1.1.1 'ping -c 3 -W 2 20.1.1.2' >"$OUT/raw/ping-allow-all.txt"
curl -fsS -X POST -H 'Content-Type: application/json' -d '{"market_mode":"MULTICAST"}' "$API/api/market" >/dev/null

session_before="$(curl -fsS "$API/api/state" | python3 -c 'import json,sys; print(json.load(sys.stdin)["session"])')"
curl -fsS -X POST -H 'Content-Type: application/json' -d '{"action":"RESTART"}' "$API/api/replay" >/dev/null
printf '%s\n' '' '10.1.1.11 / verify' '===== 查行情放行基线 =====' '[Feed] 对: 新 Session / HEALTHY  证: 未武装时原行情可以穿过当前路径' '$ python3 "$COMMON/wait-feed-state.py" "$API/api/state" HEALTHY --timeout 25 --session-not "$session_before"'
python3 "$COMMON/wait-feed-state.py" "$API/api/state" HEALTHY --timeout 25 --session-not "$session_before" | tee "$OUT/raw/feed-baseline.json"
replay_control PAUSE
sleep 1
python3 "$COMMON/wait-feed-state.py" "$API/api/state" HEALTHY --timeout 25 | tee "$OUT/raw/feed-baseline.json"
curl -fsS "$API/api/state" >"$OUT/raw/state-allow-all.json"

printf 'step=CONFIGURE result=PASS; path=VLAN100-BMv2-VLAN200; feed=HEALTHY\n'
}

inspect(){
python3 "$EOS" --plan "$ASSET/p4-trading-inspect.plan" --output "$OUT/raw/eos-inspect.txt" --mode show
: >"$OUT/raw/cli-inspect.txt"
cli_step "$OUT/raw/cli-inspect.txt" 'show_tables' '查看P4程序的表。' '列表应包含market_policy与unicast_dst。'
cli_step "$OUT/raw/cli-inspect.txt" 'table_dump IngressImpl.market_policy' '查看实际NVDA规则。' '五字段同时匹配，动作select_policy。'
cli_step "$OUT/raw/cli-inspect.txt" 'register_read IngressImpl.remaining_drops 0' '查看丢包额度。' '此时应为0，保持放行。'
cli_step "$OUT/raw/cli-inspect.txt" 'counter_read IngressImpl.policy_drop_packets 0' '查看实际丢包数。' '此时应为0 packets。'
grep -Eq 'remaining_drops\[0\]= *0$' "$OUT/raw/cli-inspect.txt"
grep -Eq 'policy_drop_packets\[0\]= \([0-9]+ bytes, 0 packets\)$' "$OUT/raw/cli-inspect.txt"
python3 "$COMMON/wait-feed-state.py" "$API/api/state" HEALTHY --timeout 25 | tee "$OUT/raw/feed-inspect.json"
curl -fsS "$API/api/state" >"$OUT/raw/state-inspect.json"
printf 'step=INSPECT result=PASS; rules=NVDA; drops=0; feed=HEALTHY\n'
}

drop(){
POLICY_DEADMAN_PID=
trap 'if test -n "$POLICY_DEADMAN_PID"; then kill "$POLICY_DEADMAN_PID" 2>/dev/null || true; fi' EXIT
# CLI 逐条演示：register-block
: >"$OUT/raw/register-block.txt"
cli_step "$OUT/raw/register-block.txt" \
  'register_write IngressImpl.remaining_drops 0 1' \
  '给策略一次丢包额度；下一个命中目标包可以消费它。' \
  '这条写命令通常只返回提示符；下一条读额度，后续用计数和GAP确认效果。'
replay_control RESUME
( sleep 5; printf '%s\n' 'register_write IngressImpl.remaining_drops 0 0' | remote11_cli "simple_switch_CLI --thrift-port 9090" ) >"$OUT/raw/policy-deadman.log" 2>&1 & POLICY_DEADMAN_PID=$!
cli_step "$OUT/raw/register-block.txt" \
  'register_read IngressImpl.remaining_drops 0' \
  '立即读回额度：可能为1，也可能已被到达的目标包消费成0。' \
  '1表示额度尚未消费；0也可能是目标包已经到达并消费了额度，继续看丢包计数与GAP。'
printf '%s\n' '' '10.1.1.11 / verify' '===== 查行情缺口 =====' '[Feed] 对: GAP / gap_size=1 / 闸门关闭  证: 策略执行后接收器自己发现序号缺失' '$ python3 "$COMMON/wait-feed-state.py" "$API/api/state" GAP --timeout 12'
python3 "$COMMON/wait-feed-state.py" "$API/api/state" GAP --timeout 12 | tee "$OUT/raw/feed-gap.json"
replay_control PAUSE
kill "$POLICY_DEADMAN_PID" 2>/dev/null || true; wait "$POLICY_DEADMAN_PID" 2>/dev/null || true; POLICY_DEADMAN_PID=
curl -fsS "$API/api/state" >"$OUT/raw/state-gap.json"
printf '%s\n' '' '10.1.1.11 / verify' '===== 查缺口期间拒单 =====' '[订单 API] 对: HTTP 400 / FEED_NOT_HEALTHY  证: 行情不完整时交易闸门确实拒绝下单' '$ python3 "$COMMON/assert-feed-order-gate.py" "$API"'
python3 "$COMMON/assert-feed-order-gate.py" "$API" | tee "$OUT/raw/order-gate.json"
printf '%s\n' '' '10.1.1.11 / verify' '===== 查界面与 GAP 状态合同 =====' '[GUI] 对: 红条、灰簿、按钮合同通过  证: 页面源与 live 状态一致；不是浏览器截图' '$ python3 "$COMMON/assert-feed-gap-ui.py" "$API" "$OUT/raw"'
python3 "$COMMON/assert-feed-gap-ui.py" "$API" "$OUT/raw" | tee "$OUT/raw/gui-gap-contract.json"
printf '%s\n' '' '10.1.1.11 / verify' '===== 查P4 额度、序号与计数 =====' '[Thrift] 对: 额度0 / policy_drop_packets为1 / 同一Sequence  证: 清策略并用板外软件target的原生读数对账' '$ simple_switch_CLI --thrift-port 9090（输入 register_write/read 与 counter_read）'
# CLI 逐条演示：register-clear
: >"$OUT/raw/register-clear.txt"
cli_step "$OUT/raw/register-clear.txt" \
  'register_write IngressImpl.remaining_drops 0 0' \
  '主动清零额度，撤销后续策略丢包。' \
  '这条写命令通常只返回提示符；下一条读取确认已经撤销额度。'
cli_step "$OUT/raw/register-clear.txt" \
  'register_read IngressImpl.remaining_drops 0' \
  '确认撤销后的额度为0；这一个0不能单独证明发生过丢包。' \
  'remaining_drops[0]=0表示当前已撤销；刚才执行过清零，这个0不能单独证明丢包。'
cli_step "$OUT/raw/register-clear.txt" \
  'register_read IngressImpl.dropped_sequence 0' \
  '读出P4记录的被丢行情序号，与Feed next_expected对照。' \
  '输出值是P4记录的丢弃序号，必须与当次Feed next_expected一致。'
cli_step "$OUT/raw/register-clear.txt" \
  'counter_read IngressImpl.policy_drop_packets 0' \
  '读取策略实际丢包计数；本次预期1 packets。' \
  '括号中的packets是实际策略丢包数，本次预期1；bytes是该计数器记录的字节量。'
cli_step "$OUT/raw/register-clear.txt" \
  'counter_read IngressImpl.stock_packets 1' \
  '读取NVDA识别计数（索引1），用于观察识别到的NVDA包数量。' \
  '索引1对应NVDA；packets是识别到的NVDA包数，不是丢包数。'
grep -Eq 'policy_drop_packets\[0\]= \([0-9]+ bytes, 1 packets\)$' "$OUT/raw/register-clear.txt"
printf '%s\n' '' '跳板机 / verify' '===== 查P4 序号对账 =====' '[Sequence] 对: dropped_sequence 等于 Feed next_expected  证: P4 丢弃与行情缺口指向同一包' '$ python3 - "$OUT/raw/register-clear.txt" "$OUT/raw/feed-gap.json"'
python3 - "$OUT/raw/register-clear.txt" "$OUT/raw/feed-gap.json" <<'PY'
import json, re, sys
receipt = open(sys.argv[1], encoding="utf-8").read()
match = re.search(r"dropped_sequence\[0\]=\s*([0-9]+)", receipt)
assert match, receipt
sequence = int(match.group(1))
gap = json.load(open(sys.argv[2], encoding="utf-8"))["feed"]
assert gap["gap_size"] == 1, gap
assert sequence == gap["next_expected"], (sequence, gap)
print(f"p4_drop_sequence={sequence} matches_feed_next_expected")
PY

printf 'step=DROP result=PASS; drops=1; sequence=MATCH; feed=GAP\n'
}

cleanup(){
# Restore endpoints successfully before stopping the inline target.
python3 "$EOS" --plan "$ASSET/p4-trading-restore-endpoints.plan" --output "$OUT/raw/eos-restore-endpoints.txt" --mode controlled-config
printf '%s\n' 'register_write IngressImpl.remaining_drops 0 0' | remote11_cli "simple_switch_CLI --thrift-port 9090" >/dev/null 2>&1 || true
remote11 "set -Eeuo pipefail; if test -s '$REMOTE/simple_switch.pid'; then pid=\$(cat '$REMOTE/simple_switch.pid'); if kill -0 \"\$pid\" 2>/dev/null; then test \"\$(readlink /proc/\$pid/cwd)\" = '$REMOTE'; kill \"\$pid\"; for n in 1 2 3 4 5; do kill -0 \"\$pid\" 2>/dev/null || break; sleep 1; done; ! kill -0 \"\$pid\" 2>/dev/null; fi; fi; ip link set dev ens64f0np0 down; ip link set dev ens64f1np1 down"
python3 "$EOS" --plan "$ASSET/p4-trading-restore-final.plan" --output "$OUT/raw/eos-restore-final.txt" --mode controlled-config
curl -fsS -X POST -H 'Content-Type: application/json' -d "{\"market_mode\":\"$ORIGINAL_MODE\"}" "$API/api/market" >/dev/null
curl -fsS -X POST -H 'Content-Type: application/json' -d '{"action":"RESTART"}' "$API/api/replay" >/dev/null
bash "$COMMON/feed-guardianctl.sh" direct >"$OUT/raw/feed-guardian-restored.txt" 2>&1
bash "$COMMON/check-filter-handoff.sh" bridge >"$OUT/raw/handoff-after.txt"
if test "${ORIGINAL_PLAYBACK:-PLAYING}" = PAUSED; then replay_control PAUSE; fi
remote11 "if test -d '$REMOTE'; then find '$REMOTE' -mindepth 1 -delete; rmdir '$REMOTE'; fi"
printf 'path=VLAN20; tools=DOWN; cleanup=PASS\n'
}

restore(){
cleanup
grep -q 'VLAN 100 not found' "$OUT/raw/eos-restore-final.txt"
grep -q 'VLAN 200 not found' "$OUT/raw/eos-restore-final.txt"
final_old_session="$(curl -fsS "$API/api/state" | python3 -c 'import json,sys; print(json.load(sys.stdin)["session"])')"
curl -fsS -X POST -H 'Content-Type: application/json' -d '{"action":"RESTART"}' "$API/api/replay" >/dev/null
printf '%s\n' '' '10.1.1.11 / verify' '===== 查清理后的行情 =====' '[Feed] 对: 新 Session / HEALTHY  证: 卸载过滤层后原订阅路径恢复' '$ python3 "$COMMON/wait-feed-state.py" "$API/api/state" HEALTHY --timeout 25 --session-not "$final_old_session"'
python3 "$COMMON/wait-feed-state.py" "$API/api/state" HEALTHY --timeout 25 --session-not "$final_old_session" | tee "$OUT/raw/feed-final.json"
printf '%s\n' '' '10.1.1.11 / verify' '===== 查恢复后两笔订单 =====' '[OUCH] 对: 两笔成交 / AAPL 净持仓不变  证: 业务恢复覆盖真实协议下单与回执' '$ python3 "$COMMON/prove-trading-recovered.py" "$API" "$OUT/raw/post-restore-orders"'
python3 "$COMMON/prove-trading-recovered.py" "$API" "$OUT/raw/post-restore-orders" | tee "$OUT/raw/post-restore-orders.json"
if test "${ORIGINAL_PLAYBACK:-PLAYING}" = PAUSED; then replay_control PAUSE; fi
curl -fsS "$API/api/state" >"$OUT/raw/state-after.json"
remote11 "! pgrep -x simple_switch; ! ip -details link show dev ens64f0np0 | grep -q prog/xdp; test \"\$(cat /sys/class/net/ens64f0np0/operstate)\" = down"
printf 'ORIGINAL_MODE=%s\n' "$ORIGINAL_MODE" >>"$OUT/run.env"
bash "$COMMON/check-filter-handoff.sh" bridge >"$OUT/raw/handoff-after.txt"
printf 'step=RESTORE result=PASS; feed=HEALTHY; post_restore_orders=2/2; evidence=%s\n' "$OUT"
}

case "${1:?stage required}" in
  configure) configure ;;
  inspect) inspect ;;
  drop) drop ;;
  cleanup) cleanup ;;
  restore) restore ;;
  *) printf 'unknown stage\n' >&2; exit 2 ;;
esac
