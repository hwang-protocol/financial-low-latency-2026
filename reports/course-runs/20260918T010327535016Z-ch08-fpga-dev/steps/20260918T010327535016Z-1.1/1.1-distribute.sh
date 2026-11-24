#!/usr/bin/env bash
set -Eeuo pipefail
run() { printf '$'; printf ' %q' "$@"; printf '\n'; "$@"; }
trap 'rc=$?; printf "分发失败，退出码=%s，位置=%s\n" "$rc" "$LINENO"; exit "$rc"' ERR
ip -4 -o address show | grep -q '10.1.1.111/'
FLLE_REPO=/financial-low-latency
FLLE_ASSET="$FLLE_REPO/Documents/newDoc/assets/08-arista-fpga-draft"
FLLE_CACHE="$FLLE_REPO/artifacts/blobs/ch08-fpga-dev"
RUN_ID="${FLLE_CH08_RUN_ID:?请使用课堂入口执行}"
FLLE_RESULT="$FLLE_REPO/Documents/reports/course-runs/$RUN_ID"
FLLE_DEV="/opt/flle-ch08-dev/$RUN_ID"
FLLE_SSH=(-o BatchMode=yes -o ConnectTimeout=10)
printf '\n===== 校验 .111 的离线材料 =====\n'
printf '[安装材料] 对: 所有摘要为 OK  证: 清单和安装包与课前固定版本一致\n'
cd "$FLLE_CACHE"
printf '46640355f35963cd3a31ae0d57450e2ff263b5c2a456a3333a9f3f129590d471  SHA256SUMS\n' | sha256sum -c -
run sha256sum -c SHA256SUMS
printf '\n===== 在 .101 建立本轮开发目录 =====\n'
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
printf '\n===== 从已有缓存安装共享编译工具 =====\n'
printf '[下一章工具] 对: Verilator、g++、make 可用  证: 离线安装器实际检查与安装返回\n'
run python3 "$FLLE_REPO/Documents/newDoc/assets/common/install-offline-packages.py" \
  10.1.1.101 verilator 2>&1 | tee "$FLLE_RESULT/verilator-install.log"
printf '\n===== 复制源码和安装包，保存输入归档 =====\n'
printf '[本轮输入] 对: core / ch09 / tools 三个目录  证: 归档文件清单与摘要\n'
run cp -a "$FLLE_ASSET" "$FLLE_RESULT/core"
run cp -a "$FLLE_REPO/Documents/newDoc/assets/09-verilator" "$FLLE_RESULT/ch09"
run cp -a "$FLLE_CACHE" "$FLLE_RESULT/tools"
cd "$FLLE_RESULT"
run tar --exclude=__pycache__ -czf inputs.tgz core tools ch09
sha256sum inputs.tgz > inputs.sha256
run cat inputs.sha256
printf 'RUN_ID=%q\nFLLE_DEV=%q\nFLLE_CORE=%q\nCH09_SRC=%q\nRESULT_DIR=%q\nSTARTED_AT_UTC=%q\nPURPOSE=ch08-fpga-development\nPROFILE_ID=vm101-ubuntu22.04-offline\nSTATUS=ACTIVE\n' \
  "$RUN_ID" "$FLLE_DEV" "$FLLE_DEV/core" "$FLLE_DEV/ch09" "$FLLE_RESULT" "$(date -u +%FT%TZ)" > dev.env
run cat dev.env
printf '\n===== 传到 .101，再次校验并解压 =====\n'
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
