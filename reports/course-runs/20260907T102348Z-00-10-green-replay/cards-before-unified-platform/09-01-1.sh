#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
source Documents/newDoc/assets/common/flle-remote.sh
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-09-p4-toolchain-prep"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"

ssh "${FLLE_SSH_OPTS[@]}" root@10.1.1.101 bash -s <<'REMOTE' 2>&1 | tee "$OUT/raw/result.txt"
set -Eeuo pipefail
pre=/opt/flle/prewarm/p4; key=/var/tmp/flle-p4lang-release.key
cleanup(){ find /var/tmp -maxdepth 1 -type f -name "${key##*/}" -delete; }
trap cleanup EXIT
printf '===== root@10.1.1.101 =====\n'
printf '%s\n' '' '===== 查预热包指纹 =====' '[SHA-256] 对: 清单各项 OK  证: 安装输入与保存的归档一致' '$ sha256sum -c <预热包清单>'
(cd "$pre" && sha256sum -c <<'SUMS'
ee65e9a01021dde724545d35c94b584a7d5d1e65f36faab48358f2ac0d6980da  gfortran-11_11.4.0-1ubuntu1~22.04.3_amd64.deb
462546f6149fbef99b47f3e1e01e0743d256ae279337c7f89a80a976dfd02175  libclang-cpp14_1%3a14.0.0-1ubuntu1.1_amd64.deb
1923e57f02a96595e2111c203dbb660f4c5abae46d7bee83a0ccb8b002eb6fc3  libicu-dev_70.1-2_amd64.deb
9044b614a6c7fb6262e7cbeb13dc731fc0c92bed96281c1a3920dd706442ee8e  libllvm14_1%3a14.0.0-1ubuntu1.1_amd64.deb
174282e5c85c7b31fbfcc3aa7193488ccec53bc50003c42f70ad1e56ba75d59f  llvm-14_1%3a14.0.0-1ubuntu1.1_amd64.deb
01bbb2de771b165e5c881bf2e365facc78335a32ffb08a48288e7332834064fe  p4lang-p4c_1.2.4.2-3_amd64.deb
SUMS
)
install -m 644 "$pre"/*.deb /var/cache/apt/archives/
printf '%s\n' '' '===== 查获取软件仓库公钥 =====' '[curl] 对: 下载成功  证: 为软件源准备公钥' '$ curl -fsSL <P4 软件源>/Release.key -o /var/tmp/flle-p4lang-release.key'; curl -fsSL https://download.opensuse.org/repositories/home:/p4lang/xUbuntu_22.04/Release.key -o "$key"
test "$(sha256sum "$key" | cut -d' ' -f1)" = 097a01fe4df29fd629f1a3afbbd9177e47dd6f3b3d640f3da698a6bfe34cc7ad
printf '%s\n' '' '===== 查公钥文件指纹 =====' '[SHA-256] 对: 输出完整文件指纹  证: 记录本次使用的公钥文件' '$ sha256sum /var/tmp/flle-p4lang-release.key'; sha256sum "$key"
printf '%s\n' '' '===== 查公钥身份 =====' '[GPG] 对: 能显示主体与指纹  证: 公钥可解析且身份可审阅' '$ gpg --show-keys --with-fingerprint /var/tmp/flle-p4lang-release.key'; gpg --show-keys --with-fingerprint "$key"
gpg --batch --yes --dearmor -o /usr/share/keyrings/home_p4lang.gpg "$key"
printf '%s\n' 'deb [signed-by=/usr/share/keyrings/home_p4lang.gpg] https://download.opensuse.org/repositories/home:/p4lang/xUbuntu_22.04/ /' >/etc/apt/sources.list.d/home_p4lang.list
printf '%s\n' '' '===== 查包索引更新 =====' '[APT] 对: 更新无错误  证: P4 软件源可以提供包索引' '$ apt-get -o Acquire::Retries=3 update'
apt-get -o Acquire::Retries=3 update
printf '%s\n' '' '===== 查安装 P4 工具 =====' '[APT] 对: 三个包安装成功  证: 编译器、软件 target 与控制接口依赖齐备' '$ apt-get install p4lang-p4c p4lang-bmv2 p4lang-pi'; NEEDRESTART_MODE=l DEBIAN_FRONTEND=noninteractive apt-get -o Acquire::Retries=3 install -y --no-install-recommends p4lang-p4c p4lang-bmv2 p4lang-pi
printf '%s\n' '' '===== 查安装依赖完整性 =====' '[APT] 对: 无依赖错误  证: 安装结果可继续使用' '$ apt-get check'; apt-get check
printf '%s\n' '' 'Low-Latency-Ops / verify' '===== 查软件包版本 =====' '[P4 工具包] 对: p4c / bmv2 / pi 均有版本  证: 编译端依赖已安装' '$ dpkg-query -W p4lang-p4c p4lang-bmv2 p4lang-pi'; dpkg-query -W -f='${Package} ${Version}\n' p4lang-p4c p4lang-bmv2 p4lang-pi
printf '%s\n' '' 'Low-Latency-Ops / verify' '===== 查P4 编译器版本 =====' '[p4c] 对: 1.2.4.2  证: 实际调用的编译器版本明确' '$ p4c --version'; p4c --version
printf '%s\n' '' 'Low-Latency-Ops / verify' '===== 查软件 target 版本 =====' '[BMv2] 对: 1.15.0-68f4a978  证: 软件交换机可执行文件可用，尚未接流' '$ simple_switch --version'; simple_switch --version
printf '%s\n' '' 'Low-Latency-Ops / verify' '===== 查控制命令入口 =====' '[CLI] 对: /usr/bin/simple_switch_CLI  证: Thrift 控制客户端能从 PATH 找到' '$ command -v simple_switch_CLI'; command -v simple_switch_CLI
REMOTE
(cd "$OUT" && sha256sum raw/result.txt run.env >SHA256SUMS)
printf 'evidence=%s\n' "$OUT"
