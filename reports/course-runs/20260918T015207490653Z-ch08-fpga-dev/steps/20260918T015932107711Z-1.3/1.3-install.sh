#!/usr/bin/env bash
# Invoked from .111 as: ssh ... bash -s -- /absolute/path/dev.env < this-file
set -Eeuo pipefail
FLLE_PHASE='1.3 安装开发工具'
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

section '核对两章共享材料' '准备版本' '本轮包含 ch09 源码目录' '先确认1.1已分发两章材料，再安装工具'
if [[ "${CH09_SRC:-}" != "$FLLE_DEV/ch09" ||
      ! -s "$FLLE_DEV/ch09/market_filter.sv" ||
      ! -s "$FLLE_DEV/ch09/offline-selftest.sh" ]]; then
  printf '[准备未完成] 本轮缺少第九章材料或 CH09_SRC 路径；旧版1.1创建的目录需要重新准备。\n' >&2
  printf '[处理方法] 无需恢复快照；在 .111 依次重跑1.1、1.2、1.3。1.1会创建新目录，保留旧结果。\n' >&2
  exit 1
fi
run ls -l "$CH09_SRC/market_filter.sv" "$CH09_SRC/offline-selftest.sh"

cd "$FLLE_DEV/tools"
mkdir -p "$FLLE_DEV/work"

section '查离线安装包' 'SHA-256' '清单中的每份文件均返回 OK' '安装前确认离线材料与已登记的内容一致'
run sha256sum -c SHA256SUMS

section '安装 Icarus 仿真工具' 'Icarus' 'dpkg 安装完成，无错误退出' 'iverilog 编译电路仿真程序；vvp 执行该程序'
logged "$FLLE_DEV/work/iverilog-install.log" dpkg -i deb/iverilog_11.0-1.1_amd64.deb
run tail -n 12 "$FLLE_DEV/work/iverilog-install.log"

section '安装独立 Python 工具环境' 'Python 与 Yosys' '本地 wheel 安装完成，无依赖冲突' '管理测试与通用综合使用本轮独立环境'
run python3 -m venv --without-pip "$FLLE_DEV/venv"
logged "$FLLE_DEV/work/python-install.log" \
  env "PYTHONPATH=$FLLE_DEV/tools/wheels/pip-25.2-py3-none-any.whl" \
  "$FLLE_DEV/venv/bin/python" -m pip install --no-index \
  "--find-links=$FLLE_DEV/tools/wheels" -r "$FLLE_DEV/tools/requirements.txt"
run tail -n 4 "$FLLE_DEV/work/python-install.log"

section '查工具版本与依赖' '本章和下一章工具' 'Icarus 可查版本；pip 无损坏依赖；Yosys、Verilator、g++、make 均可显示版本' '本章使用 Icarus/Python/Yosys；下一章复用 Verilator/C++ 编译工具'
FLLE_LAST_LOG="$FLLE_DEV/work/tools.txt"
{
  run dpkg-query -W '-f=${Package} ${Version}\n' iverilog
  run "$FLLE_DEV/venv/bin/python" -m pip check
  run "$FLLE_DEV/venv/bin/yowasp-yosys" -V
  run verilator --version
  run g++ --version
  run make --version
} 2>&1 | tee "$FLLE_LAST_LOG"
printf '\n本步完成: Icarus、Python/Yosys 和下一章共享工具已就绪；第2步看源码，第3步编译与测试。\n'
