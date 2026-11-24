#!/usr/bin/env bash
# Sourced by the two Chapter 06 QoS experiments. Scope: the selected order socket.
QOS_TRANSPORT="${FLLE_QOS_TRANSPORT:-SOCKET}"
case "$QOS_TRANSPORT" in SOCKET|OPENONLOAD) ;; *) echo 'FLLE_QOS_TRANSPORT must be SOCKET or OPENONLOAD' >&2; exit 2;; esac
QOS_TOOL=apps/flle-trading-lab/scripts/order-dscp.py
QOS_CHANGED=0
QOS_ORIGINAL_DSCP=0
QOS_PID=''

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
