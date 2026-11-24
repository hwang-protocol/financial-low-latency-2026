#!/usr/bin/env bash
# Sourced by the two Chapter 06 QoS experiments. Scope: the selected order socket.
QOS_TRANSPORT="${FLLE_QOS_TRANSPORT:-SOCKET}"
case "$QOS_TRANSPORT" in SOCKET|OPENONLOAD) ;; *) echo 'FLLE_QOS_TRANSPORT must be SOCKET or OPENONLOAD' >&2; exit 2;; esac
QOS_TOOL=apps/flle-trading-lab/scripts/order-dscp.py
QOS_CHANGED=0
QOS_ORIGINAL_DSCP=0
QOS_PID=''
QOS_CTL=apps/flle-trading-lab/scripts/transport_labctl.sh

qos_validate_platform() {
  python3 - "$1" "$2" "$QOS_TRANSPORT" "$QOS_PID" <<'PY'
import json, sys
path, phase, transport, expected_pid = sys.argv[1:]
s = json.load(open(path))
if not (s.get('mode') == 'SFC' and s.get('transition') == 'READY'
        and s.get('owner') == 'sfc' and s.get('data_ip_present') is True):
    raise SystemExit('[平台未就绪] 需要 SFC / READY、sfc 驱动及数据口地址；'
                     f"当前 mode={s.get('mode')} transition={s.get('transition')} "
                     f"owner={s.get('owner')} data_ip_present={s.get('data_ip_present')}；记录：{path}")
r = s.get('hardware_receipts', {}).get('socket' if transport == 'SOCKET' else 'onload', {})
if r.get('launch_verified') is not True:
    raise SystemExit(f'[客户端未就绪] {transport} 的当前进程身份未通过核验；请检查第五章准备 B。记录：{path}')
if phase == 'path':
    if r.get('verified') is not True:
        raise SystemExit(f'[路径未确认] {transport} 已启动，但订单连接尚未通过路径核验。记录：{path}')
    if str(r.get('pid')) != expected_pid:
        raise SystemExit(f'[客户端已变化] 路径记录 PID={r.get("pid")}，打标客户端 PID={expected_pid}；停止实验。')
    print(f'[路径检查通过] {transport} · PID={expected_pid} · 当前订单连接已核验。')
else:
    print(f'[平台检查通过] {transport} 已启动；接下来检查订单连接。')
PY
}

qos_check_platform() {
  printf '===== 检查平台与订单客户端 =====\n'
  bash "$QOS_CTL" status "$PARENT_RUN_ID" >"$RAW/platform-before.json"
  qos_validate_platform "$RAW/platform-before.json" launch
}

qos_verify_path() {
  printf '===== 核对当前订单连接的实际路径 =====\n'
  if ! bash "$QOS_CTL" attest "$PARENT_RUN_ID" "$QOS_TRANSPORT" \
      >"$RAW/order-path-status.json" 2>"$RAW/order-path-error.txt"; then
    printf '[路径检查失败] %s；记录：%s/order-path-error.txt\n' "$QOS_TRANSPORT" "$RAW" >&2
    tail -n 20 "$RAW/order-path-error.txt" >&2
    return 1
  fi
  qos_validate_platform "$RAW/order-path-status.json" path
}

qos_preflight() {
  python3 "$QOS_TOOL" --transport "$QOS_TRANSPORT" --expect 0 --json GET >"$RAW/order-dscp-before.json"
  read -r QOS_ORIGINAL_DSCP QOS_PID SOURCE_PORT < <(python3 - "$RAW/order-dscp-before.json" <<'PY'
import json,sys
s=json.load(open(sys.argv[1])); print(s['dscp'],s['pid'],s['local_port'])
PY
  )
  [[ "$QOS_PID" =~ ^[0-9]+$ && "$SOURCE_PORT" =~ ^[0-9]+$ ]]
  if test "$SOURCE_PORT" = 0; then
    printf '[连接准备] 当前客户端尚未建连，先完成两笔方向相反的预热单；不计入 QoS 对比。\n'
    qos_connect >"$RAW/qos-connect-summary.txt"
    python3 "$QOS_TOOL" --transport "$QOS_TRANSPORT" --expect-pid "$QOS_PID" --connected --expect 0 --json GET >"$RAW/order-dscp-before.json"
    SOURCE_PORT="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["local_port"])' "$RAW/order-dscp-before.json")"
  fi
  python3 "$QOS_TOOL" --transport "$QOS_TRANSPORT" --expect-pid "$QOS_PID" --connected --expect 0 GET
}

qos_mark() {
  # Set before issuing the command: a lost reply must still trigger restoration.
  QOS_CHANGED=1
  python3 "$QOS_TOOL" --transport "$QOS_TRANSPORT" --expect-pid "$QOS_PID" --connected 46 | tee "$RAW/order-dscp-active.txt"
}

qos_restore() {
  test "$QOS_CHANGED" -eq 1 || return 0
  python3 "$QOS_TOOL" --transport "$QOS_TRANSPORT" --expect-pid "$QOS_PID" "$QOS_ORIGINAL_DSCP" | tee "$RAW/order-dscp-restored.txt" || return 1
  QOS_CHANGED=0
}

qos_verify_restored() {
  python3 "$QOS_TOOL" --transport "$QOS_TRANSPORT" --expect-pid "$QOS_PID" --expect "$QOS_ORIGINAL_DSCP" --json GET >"$RAW/order-dscp-after.json"
}
