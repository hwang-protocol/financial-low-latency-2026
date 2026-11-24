#!/usr/bin/env bash
set -Eeuo pipefail
run() { printf '$'; printf ' %q' "$@"; printf '\n'; "$@"; }
trap 'rc=$?; printf "分发失败，退出码=%s，位置=%s\n" "$rc" "$LINENO"; exit "$rc"' ERR
ip -4 -o address show | grep -q '10.1.1.111/'
FLLE_REPO=/qyt-fll
FLLE_ASSET="$FLLE_REPO/assets/08-arista-fpga-draft"
FLLE_CACHE="$FLLE_REPO/artifacts/blobs/ch08-fpga-dev"
RUN_ID="${FLLE_CH08_RUN_ID:?请使用课堂入口执行}"
FLLE_RESULT="$FLLE_REPO/reports/course-runs/$RUN_ID"
FLLE_DEV="/opt/flle-ch08-dev/$RUN_ID"
FLLE_SSH=(-o BatchMode=yes -o ConnectTimeout=10)
printf '\n===== 1/5 校验 .111 的离线材料 =====\n'
printf '准备: Icarus 和 Python 安装包，相当于本章的离线安装盘；先检查文件是否完整。\n'
printf '[安装材料] 对: 所有摘要为 OK  证: 清单和安装包与课前固定版本一致\n'
cd "$FLLE_CACHE"
printf '46640355f35963cd3a31ae0d57450e2ff263b5c2a456a3333a9f3f129590d471  SHA256SUMS\n' | sha256sum -c -
run sha256sum -c SHA256SUMS
printf '\n===== 2/5 在 .101 建立本轮开发目录 =====\n'
printf '准备: 自动连接开发机，新建本轮目录；恢复快照后重跑也从新目录开始。\n'
printf '[目标环境] 对: Ubuntu 22.04 / amd64，地址 .101  证: 系统、地址和新目录实际返回\n'
run ssh "${FLLE_SSH[@]}" root@10.1.1.101 bash -s -- "$FLLE_DEV" <<'REMOTE'
set -euo pipefail
printf '$ hostname\n'; hostname
printf '$ ip -4 -o address show\n'; ip -4 -o address show
ip -4 -o address show | grep -q '10.1.1.101/'
. /etc/os-release
printf 'os=%s version=%s architecture=%s\n' "$ID" "$VERSION_ID" "$(dpkg --print-architecture)"
test "$ID:$VERSION_ID:$(dpkg --print-architecture)" = ubuntu:22.04:amd64
mkdir -p /opt/flle-ch08-dev
mkdir -- "$1"
printf '$ ls -ld %s\n' "$1"; ls -ld "$1"
REMOTE
mkdir -p "$FLLE_RESULT" "$(dirname "$FLLE_CH08_STATE")"
printf '\n===== 3/5 从已有缓存安装共享编译工具 =====\n'
printf '准备: Verilator 把电路描述转换为仿真模型；g++ 和 make 用于构建下一章的仿真程序。\n'
printf '[下一章工具] 对: Verilator、g++、make 可用  证: 离线安装器实际检查与安装返回\n'
printf '完整安装记录: %s/verilator-install.log\n' "$FLLE_RESULT"
printf '$ python3 %q 10.1.1.101 verilator > %q 2>&1\n' \
  "$FLLE_REPO/assets/common/install-offline-packages.py" "$FLLE_RESULT/verilator-install.log"
if run python3 "$FLLE_REPO/assets/common/install-offline-packages.py" \
  10.1.1.101 verilator > "$FLLE_RESULT/verilator-install.log" 2>&1; then
  run tail -n 8 "$FLLE_RESULT/verilator-install.log"
else
  rc=$?
  run tail -n 30 "$FLLE_RESULT/verilator-install.log"
  exit "$rc"
fi
printf '\n===== 4/5 复制源码和安装包，保存输入归档 =====\n'
printf '准备: core 是本章源码，ch09 是下一章源码，tools 是本章安装包。\n'
printf 'inputs.tgz 只是传输用的压缩包；第6步的 .swix 才是 EOS 安装包。\n'
printf '[本轮输入] 对: core / ch09 / tools 三个目录  证: 归档文件清单与摘要\n'
run cp -a "$FLLE_ASSET" "$FLLE_RESULT/core"
run cp -a "$FLLE_REPO/assets/09-verilator" "$FLLE_RESULT/ch09"
run cp -a "$FLLE_CACHE" "$FLLE_RESULT/tools"
cd "$FLLE_RESULT"
run tar --exclude=__pycache__ -czf inputs.tgz core tools ch09
sha256sum inputs.tgz > inputs.sha256
run cat inputs.sha256
printf 'RUN_ID 是本轮编号；保存到 dev.env，后续卡片自动读取目录。\n'
printf 'RUN_ID=%q\nFLLE_DEV=%q\nFLLE_CORE=%q\nCH09_SRC=%q\nRESULT_DIR=%q\nSTARTED_AT_UTC=%q\nPURPOSE=ch08-fpga-development\nPROFILE_ID=vm101-ubuntu22.04-offline\nSTATUS=ACTIVE\n' \
  "$RUN_ID" "$FLLE_DEV" "$FLLE_DEV/core" "$FLLE_DEV/ch09" "$FLLE_RESULT" "$(date -u +%FT%TZ)" > dev.env
run cat dev.env
printf '\n===== 5/5 传到 .101，再次校验并解压 =====\n'
printf '准备: 把项目文件和安装盘送到开发机；.111 保留原件和本轮日志。\n'
printf '[开发机副本] 对: inputs.tgz 校验 OK，源码和工具目录存在  证: 远端校验及目录清单\n'
run scp "${FLLE_SSH[@]}" inputs.tgz inputs.sha256 dev.env "root@10.1.1.101:$FLLE_DEV/"
run ssh "${FLLE_SSH[@]}" root@10.1.1.101 bash -s -- "$FLLE_DEV" "$FLLE_CH08_PUBLISH_CURRENT" <<'REMOTE'
set -euo pipefail
cd "$1"
printf '$ sha256sum -c inputs.sha256\n'; sha256sum -c inputs.sha256
printf '$ tar -xzf inputs.tgz\n'; tar -xzf inputs.tgz
if [ "$2" = 1 ]; then cp dev.env /opt/flle-ch08-dev/current.env; fi
printf '$ ls -ld core ch09 tools\n'; ls -ld core ch09 tools
REMOTE
run cp dev.env "$FLLE_CH08_STATE"
printf 'development_host=10.1.1.101\nRUN_ID=%s\nworkspace=%s\n' "$RUN_ID" "$FLLE_DEV"
printf '本步完成: 两章材料已就位，共享编译工具已备齐；1.2核对环境，1.3安装本章工具。\n'
