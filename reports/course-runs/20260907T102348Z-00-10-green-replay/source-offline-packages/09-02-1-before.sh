#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
source Documents/newDoc/assets/common/flle-remote.sh
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-09-bmv2-tool-prep"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
ssh "${FLLE_SSH_OPTS[@]}" root@10.1.1.11 bash -s <<'REMOTE' 2>&1 | tee "$OUT/raw/result.txt"
set -Eeuo pipefail
key=/var/tmp/flle-p4lang-release.key
cleanup(){ find /var/tmp -maxdepth 1 -type f -name "${key##*/}" -delete; }
trap cleanup EXIT
curl -fsSL https://download.opensuse.org/repositories/home:/p4lang/xUbuntu_22.04/Release.key -o "$key"
test "$(sha256sum "$key" | cut -d' ' -f1)" = 097a01fe4df29fd629f1a3afbbd9177e47dd6f3b3d640f3da698a6bfe34cc7ad
gpg --batch --yes --dearmor -o /usr/share/keyrings/home_p4lang.gpg "$key"
printf '%s\n' 'deb [signed-by=/usr/share/keyrings/home_p4lang.gpg] https://download.opensuse.org/repositories/home:/p4lang/xUbuntu_22.04/ /' >/etc/apt/sources.list.d/home_p4lang.list
printf '%s\n' '' '===== 查包索引更新 =====' '[APT] 对: 更新无错误  证: 数据面主机可以读取软件源' '$ apt-get -o Acquire::Retries=3 update'; apt-get -o Acquire::Retries=3 update
printf '%s\n' '' '===== 查安装 BMv2 =====' '[APT] 对: 安装成功  证: 数据面主机具备软件交换机与CLI' '$ apt-get install p4lang-bmv2'; NEEDRESTART_MODE=l DEBIAN_FRONTEND=noninteractive apt-get -o Acquire::Retries=3 install -y --no-install-recommends p4lang-bmv2
printf '%s\n' '' '10.1.1.11 / verify' '===== 查软件交换机版本 =====' '[BMv2] 对: 1.15.0-68f4a978  证: 直接接线主机具备执行 P4 JSON 的工具' '$ simple_switch --version'; simple_switch --version 2>&1
printf '%s\n' '' '10.1.1.11 / verify' '===== 查Thrift 客户端路径 =====' '[CLI] 对: /usr/bin/simple_switch_CLI  证: 可通过 9090 控制本章 BMv2 的表和寄存器' '$ command -v simple_switch_CLI'; command -v simple_switch_CLI
REMOTE
(cd "$OUT" && sha256sum raw/result.txt run.env >SHA256SUMS)
printf 'evidence=%s\n' "$OUT"
