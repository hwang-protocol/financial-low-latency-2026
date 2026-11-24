#!/usr/bin/env bash
# Called by Chapter 02 for fresh deployment and an existing Chapter 04 snapshot.
set -Eeuo pipefail
HERE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
RUN_ID="${1:?platform RUN_ID required}"
[[ "$RUN_ID" =~ ^[A-Za-z0-9._-]+-02-trading-platform$ ]] || exit 2
printf '===== 准备后续实验程序 =====\n'
printf '[1/2] Socket / Onload 测试客户端：使用已编译程序，默认 DSCP 0。\n'
bash "$HERE/prepare-posix-qos.sh" "$RUN_ID"
printf '[2/2] Arista 官方 LANZ 读取工具：部署到 .101，第六章再启动采集。\n'
bash "$HERE/prepare-lanz-reader.sh"
bash "$HERE/prepare-posix-qos.sh" "$RUN_ID" --check
bash "$HERE/prepare-lanz-reader.sh" --check
printf 'course_capabilities=PREPARED\n'
