#!/usr/bin/env bash
# Invoked from .111 as: ssh ... bash -s -- /absolute/path/dev.env < this-file
set -Eeuo pipefail
FLLE_PHASE='3.5 综合寄存器电路'
FLLE_LAST_LOG=''
FLLE_LAST_COMMAND=''
fail() {
  local rc="$1" line="$2" command="$3"
  trap - ERR
  printf '\n[执行中止] 阶段=%s 退出码=%s 行号=%s\n' "$FLLE_PHASE" "$rc" "$line" >&2
  printf '[失败命令] %s\n' "${FLLE_LAST_COMMAND:-$command}" >&2
  if [[ -n "$FLLE_LAST_LOG" && -f "$FLLE_LAST_LOG" ]]; then
    printf '[完整日志] %s\n$ tail -n 30 %q\n' "$FLLE_LAST_LOG" "$FLLE_LAST_LOG" >&2
    tail -n 30 "$FLLE_LAST_LOG" >&2 || :
  fi
  exit "$rc"
}
trap 'fail "$?" "$LINENO" "$BASH_COMMAND"' ERR
section() {
  printf '\n%s / %s\n===== %s =====\n[%s] 对: %s  证: %s\n' \
    "$(hostname)" "$FLLE_PHASE" "$1" "$2" "$3" "$4"
}
run() {
  printf -v FLLE_LAST_COMMAND '%q ' "$@"
  printf '$ %s\n' "${FLLE_LAST_COMMAND% }"
  "$@"
  FLLE_LAST_COMMAND=''
}
logged() {
  FLLE_LAST_LOG="$1"
  shift
  printf -v FLLE_LAST_COMMAND '%q ' "$@"
  printf '$ %s > %q 2>&1\n' "${FLLE_LAST_COMMAND% }" "$FLLE_LAST_LOG"
  "$@" >"$FLLE_LAST_LOG" 2>&1
  FLLE_LAST_COMMAND=''
}
: "${1:?pass the absolute dev.env path for this run}"
[[ "$1" = /* && -r "$1" ]]
source "$1"
: "${RUN_ID:?missing RUN_ID}" "${FLLE_DEV:?missing FLLE_DEV}" "${FLLE_CORE:?missing FLLE_CORE}"
section '查执行主机与本轮目录' '开发机' '管理地址为 10.1.1.101；目录与本轮 RUN_ID 一致' '保护安装和生成文件的目标位置'
run ip -4 -o address show
ip -4 -o address show | grep -Fq ' 10.1.1.101/'
run cat "$1"
[[ "$RUN_ID" =~ ^[[:alnum:]_.-]+$ ]]
[[ "$FLLE_DEV" == "/opt/flle-ch08-dev/$RUN_ID" ]]
[[ "$FLLE_CORE" == "$FLLE_DEV/core" && "$1" == "$FLLE_DEV/dev.env" ]]
[[ -d "$FLLE_CORE" && -d "$FLLE_DEV/tools" ]]

# Stage 3.4 creates this directory and copies this run's RTL into it.
cd "$FLLE_DEV/work/core-synthesis"
rm -f control-regs-netlist.json control-regs-netlist.sha256

section '查 3.4 留下的寄存器源码' 'control_regs.sv' '本轮综合目录中存在该文件' '沿用 3.4 已复制的同一批 RTL 源码'
run ls -l control_regs.sv

section '把寄存器电路综合成通用网表' 'Yosys' '查看 check 的实际问题数和 stat 的电路统计' '验证寄存器描述可生成通用逻辑与连接；PDI 构建仍在后续板卡工程中进行'
printf '本步作用: 控制寄存器是独立模块，3.4的过滤顶层没有包含它，需要单独综合。\n'
logged "$PWD/control-regs-synthesis.log" "$FLLE_DEV/venv/bin/yowasp-yosys" -Q -T -p '
  read_verilog -sv control_regs.sv;
  synth -top control_regs -noabc;
  check -assert;
  stat;
  write_json control-regs-netlist.json
'
run grep 'Found and reported' control-regs-synthesis.log
run tail -n 20 control-regs-synthesis.log

section '查寄存器网表文件与指纹' 'JSON 网表' '生成 control-regs-netlist.json 并记录 SHA-256' '保存本次寄存器综合产物'
run ls -lh control-regs-netlist.json
printf '$ sha256sum control-regs-netlist.json > control-regs-netlist.sha256\n'
sha256sum control-regs-netlist.json > control-regs-netlist.sha256
run cat control-regs-netlist.sha256
printf '读数: 0 problems表示寄存器结构检查通过；两份网表分别检查，还未接成板卡工程。\n'
printf '\n[下一步] 各卡日志已自动保存到 .111；接着阅读第4步，将已验证的源码接入板卡工程。\n'
