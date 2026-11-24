#!/usr/bin/env bash
set -Eeuo pipefail
run() { printf '$'; printf ' %q' "$@"; printf '\n'; "$@"; }
trap 'rc=$?; printf "收回失败，退出码=%s，位置=%s\n" "$rc" "$LINENO"; exit "$rc"' ERR
ip -4 -o address show | grep -q '10.1.1.111/'
source "${FLLE_CH08_STATE:?请使用课堂入口执行}"
FLLE_SSH=(-o BatchMode=yes -o ConnectTimeout=10)
printf '\n===== 在 .101 归档完整 work 目录 =====\n'
printf '[待收回文件] 对: 仿真日志、管理日志及两份网表存在  证: 实际文件大小；内容结论仍看前面各卡\n'
run ssh "${FLLE_SSH[@]}" root@10.1.1.101 bash -s -- "$FLLE_DEV" <<'REMOTE'
set -euo pipefail
cd "$1"
test -s work/simulation/simulation.log
test -s work/management.log
test -s work/core-synthesis/frame-filter-netlist.json
test -s work/core-synthesis/control-regs-netlist.json
printf '$ ls -lh work/simulation/simulation.log work/management.log work/core-synthesis/*-netlist.json\n'
ls -lh work/simulation/simulation.log work/management.log work/core-synthesis/*-netlist.json
printf '$ tar -czf results.tgz work\n'; tar -czf results.tgz work
sha256sum results.tgz > results.sha256
printf '$ cat results.sha256\n'; cat results.sha256
REMOTE
printf '\n===== 收回 .111 并核对摘要 =====\n'
printf '[最终归档] 对: results.tgz 校验 OK  证: 传输后字节完整，可在 .101 恢复快照后保留\n'
run scp "${FLLE_SSH[@]}" "root@10.1.1.101:$FLLE_DEV/results.tgz" \
  "root@10.1.1.101:$FLLE_DEV/results.sha256" "$RESULT_DIR/"
cd "$RESULT_DIR"
run sha256sum -c results.sha256
run tar -tzf results.tgz
printf 'STATUS=COLLECTED\n' >> "$FLLE_CH08_STATE"
printf 'results_saved=%s\n' "$RESULT_DIR"
