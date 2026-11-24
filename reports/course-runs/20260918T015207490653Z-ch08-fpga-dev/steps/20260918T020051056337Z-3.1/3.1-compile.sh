#!/usr/bin/env bash
# Invoked from .111 as: ssh ... bash -s -- /absolute/path/dev.env < this-file
set -Eeuo pipefail
FLLE_PHASE='3.1 编译仿真程序'
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

mkdir -p "$FLLE_DEV/work/simulation"
cd "$FLLE_DEV/work/simulation"
rm -f filter.vvp compile.sha256

section '把电路源码与测试台编成仿真程序' 'iverilog' '编译无错误退出，并产生 filter.vvp' '-g2012 启用 SystemVerilog；-s 指定测试台入口'
printf '本步作用: 把四个电路模块和测试台编译成 filter.vvp；测试台负责产生时钟、报文并核对输出。\n'
logged "$PWD/compile.log" iverilog -g2012 -s filter_tb -o filter.vvp \
  "$FLLE_CORE/nvda_match.sv" "$FLLE_CORE/drop_once.sv" \
  "$FLLE_CORE/frame_filter.sv" "$FLLE_CORE/control_regs.sv" "$FLLE_CORE/filter_tb.sv"
run cat compile.log

section '查仿真程序与源码指纹' '编译产物' 'filter.vvp 为本轮生成的非空文件；源码与产物各有 SHA-256' '下一步用同一份程序和源码执行测试'
run ls -l filter.vvp
printf '$ sha256sum filter.vvp %q/*.sv > compile.sha256\n' "$FLLE_CORE"
sha256sum filter.vvp "$FLLE_CORE/"*.sv > compile.sha256
run cat compile.sha256
printf '\n[下一步] 运行 3.2，让 vvp 执行 filter.vvp。\n'
printf '读数: filter.vvp 是在电脑上运行的仿真程序；编译完成后，还要运行测试才知道行为是否正确。\n'
