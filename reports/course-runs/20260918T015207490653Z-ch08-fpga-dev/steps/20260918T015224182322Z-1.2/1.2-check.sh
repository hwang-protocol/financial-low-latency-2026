#!/usr/bin/env bash
# Invoked from .111 as: ssh ... bash -s -- /absolute/path/dev.env < this-file
set -Eeuo pipefail
FLLE_PHASE='1.2 检查开发机'
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

section '查主机名、系统与架构' '系统基线' 'vm-monitor；Ubuntu 22.04；amd64' '确认本轮开发材料位于可恢复快照的课堂虚拟机'
run hostname
run grep -E '^(NAME|VERSION_ID)=' /etc/os-release
run dpkg --print-architecture
[[ "$(hostname)" == vm-monitor ]]
source /etc/os-release
[[ "$ID:$VERSION_ID:$(dpkg --print-architecture)" == ubuntu:22.04:amd64 ]]

section '查分发后的输入文件' '源码与工具' '源码、工具和清单均存在；压缩包校验返回 OK' '后续安装与仿真读取这批输入'
run ls -ld "$FLLE_DEV" "$FLLE_CORE" "$FLLE_DEV/tools"
run ls -l "$FLLE_CORE/nvda_match.sv" "$FLLE_CORE/frame_filter.sv" \
  "$FLLE_CORE/filter_tb.sv" "$FLLE_CORE/test_eos_control.py" \
  "$FLLE_DEV/tools/requirements.txt" "$FLLE_DEV/tools/SHA256SUMS"
cd "$FLLE_DEV"
run sha256sum -c inputs.sha256
printf '\n本步完成: 开发机身份、系统和输入包均通过核对；继续1.3安装工具。\n'
