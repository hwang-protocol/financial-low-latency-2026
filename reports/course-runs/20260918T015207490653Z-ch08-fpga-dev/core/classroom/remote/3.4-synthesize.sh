#!/usr/bin/env bash
# Invoked from .111 as: ssh ... bash -s -- /absolute/path/dev.env < this-file
set -Eeuo pipefail
FLLE_PHASE='3.4 综合过滤电路'
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

mkdir -p "$FLLE_DEV/work/core-synthesis"
cp "$FLLE_CORE/"*.sv "$FLLE_DEV/work/core-synthesis/"
cd "$FLLE_DEV/work/core-synthesis"
rm -f frame-filter-netlist.json frame-filter-netlist.sha256

section '把过滤电路描述综合成通用网表' 'Yosys' '查看 check 的实际问题数和 stat 的电路统计' '网表描述逻辑单元与连接；本步尚未映射到具体 FPGA'
logged "$PWD/frame-filter-synthesis.log" "$FLLE_DEV/venv/bin/yowasp-yosys" -Q -T -p '
  read_verilog -sv nvda_match.sv drop_once.sv frame_filter.sv;
  synth -top frame_filter -noabc;
  check -assert;
  stat;
  write_json frame-filter-netlist.json
'
run grep 'Found and reported' frame-filter-synthesis.log
run tail -n 20 frame-filter-synthesis.log

section '查过滤网表文件与指纹' 'JSON 网表' '生成 frame-filter-netlist.json 并记录 SHA-256' '保存本次通用综合产物，供后续检查或比较'
run ls -lh frame-filter-netlist.json
printf '$ sha256sum frame-filter-netlist.json > frame-filter-netlist.sha256\n'
sha256sum frame-filter-netlist.json > frame-filter-netlist.sha256
run cat frame-filter-netlist.sha256
printf '\n[下一步] 3.5 使用本步已复制到 core-synthesis 的源码，综合寄存器电路。\n'
