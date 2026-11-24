#!/usr/bin/env bash
# Invoked from .111 as: ssh ... bash -s -- /absolute/path/dev.env < this-file
set -Eeuo pipefail
FLLE_PHASE='3.3 测试管理程序'
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

cd "$FLLE_CORE/test-support/openfdk"

section '查公开库测试依赖' 'OpenFDK 文件' '清单中的文件均返回 OK' '管理测试使用已登记的公开库副本'
run sha256sum -c SHA256SUMS

section '执行 Python 管理测试' 'unittest' '逐项读取测试名称与结果，以及结尾的实际测试数' '测试管理参数、寄存器访问和命令处理；设备接口由测试替身提供'
logged "$FLLE_DEV/work/management.log" "$FLLE_DEV/venv/bin/python" -B "$FLLE_CORE/test_eos_control.py" "$PWD"
run cat "$FLLE_DEV/work/management.log"
printf '读数: 每项ok和末尾OK表示对应测试通过；Ran 16 tests是测试数量，耗时随运行变化。\n'
printf '范围: 本步用模拟设备接口检查装载等待、发放/撤销额度和读数，没有向真实FPGA装载镜像。\n'
printf '\n[下一步] 读完 unittest 结果，运行 3.4 生成过滤电路的通用网表。\n'
