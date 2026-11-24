#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
source Documents/newDoc/assets/common/flle-remote.sh
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-09-p4-toolchain-prep"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"

python3 Documents/newDoc/assets/common/install-offline-packages.py 10.1.1.101 p4 2>&1 | tee "$OUT/raw/result.txt"
ssh "${FLLE_SSH_OPTS[@]}" root@10.1.1.101 bash -s <<'REMOTE' 2>&1 | tee -a "$OUT/raw/result.txt"
set -Eeuo pipefail
printf '%s\n' '' '10.1.1.101 / verify' '===== 查软件包版本 =====' '[P4 工具包] 对: p4c / bmv2 / pi 均有版本  证: 编译端依赖已安装' '$ dpkg-query -W p4lang-p4c p4lang-bmv2 p4lang-pi'; dpkg-query -W -f='${Package} ${Version}\n' p4lang-p4c p4lang-bmv2 p4lang-pi
printf '%s\n' '' '10.1.1.101 / verify' '===== 查P4 编译器版本 =====' '[p4c] 对: 1.2.4.2  证: 实际调用的编译器版本明确' '$ p4c --version'; p4c --version
printf '%s\n' '' '10.1.1.101 / verify' '===== 查软件 target 版本 =====' '[BMv2] 对: 1.15.0-68f4a978  证: 软件交换机可执行文件可用，尚未接流' '$ simple_switch --version'; simple_switch --version
printf '%s\n' '' '10.1.1.101 / verify' '===== 查控制命令入口 =====' '[CLI] 对: /usr/bin/simple_switch_CLI  证: Thrift 控制客户端能从 PATH 找到' '$ command -v simple_switch_CLI'; command -v simple_switch_CLI
REMOTE
(cd "$OUT" && sha256sum raw/result.txt run.env >SHA256SUMS)
printf 'evidence=%s\n' "$OUT"
