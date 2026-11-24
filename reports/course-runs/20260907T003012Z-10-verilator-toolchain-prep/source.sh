#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
source Documents/newDoc/assets/common/flle-remote.sh
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-10-verilator-toolchain-prep"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
printf 'BUILD_HOST=10.1.1.2\n' >>"$OUT/run.env"
cp "$OUT/run.env" Documents/reports/run-state/10-verilator-toolchain-prep.env
cp Documents/newDoc/assets/10-verilator/00-verilator-toolchain-prep.sh "$OUT/source.sh"
trap 'rc=$?; printf "EXIT_CODE=%s\n" "$rc" >>"$OUT/run.env"; cp "$OUT/run.env" Documents/reports/run-state/10-verilator-toolchain-prep.env; (cd "$OUT" && sha256sum raw/result.txt run.env source.sh >SHA256SUMS); printf "evidence=%s\n" "$OUT"; exit "$rc"' EXIT

ssh "${FLLE_SSH_OPTS[@]}" root@10.1.1.2 bash -s <<'REMOTE' 2>&1 | tee "$OUT/raw/result.txt"
set -Eeuo pipefail
printf '===== root@10.1.1.2 =====\n'
printf '%s\n' '' '===== 查软件源配置 =====' '[APT] 对: 源配置可读  证: 明确构建工具从哪里安装' '$ sed -n 1,12p /etc/apt/sources.list'
sed -n '1,12p' /etc/apt/sources.list
printf '%s\n' '' '===== 查包索引更新 =====' '[APT] 对: 更新无错误  证: 安装前取得软件包索引' '$ apt-get -o Acquire::Retries=3 update'
apt-get -o Acquire::Retries=3 update
printf '%s\n' '' '===== 查安装周期模型工具 =====' '[APT] 对: Verilator 4.038-1 / g++ / make 安装成功  证: 编译与链接环境齐备' '$ apt-get install g++ make verilator=4.038-1'; NEEDRESTART_MODE=l DEBIAN_FRONTEND=noninteractive apt-get -o Acquire::Retries=3 install -y --no-install-recommends g++ make verilator=4.038-1
printf '%s\n' '' '===== 查安装依赖完整性 =====' '[APT] 对: 无依赖错误  证: 安装结果可继续使用' '$ apt-get check'; apt-get check
printf '%s\n' '' 'vm-2522-02 / verify' '===== 查构建工具包 =====' '[工具包] 对: verilator 4.038-1，g++ 和 make 已安装  证: 仿真构建所需三类工具齐备' '$ dpkg-query -W verilator g++ make'; dpkg-query -W -f='${Package} ${Version}\n' verilator g++ make
printf '%s\n' '' 'vm-2522-02 / verify' '===== 查RTL 翻译器版本 =====' '[Verilator] 对: 4.038  证: 把 SystemVerilog 翻译成 C++ 周期模型的工具可用' '$ verilator --version'; verilator --version
printf '%s\n' '' 'vm-2522-02 / verify' '===== 查C++ 编译器版本 =====' '[g++] 对: 能打印版本  证: 把 Verilator 生成的 C++ 与 adapter 编成程序' '$ g++ --version'; g++ --version
printf '%s\n' '' 'vm-2522-02 / verify' '===== 查构建工具版本 =====' '[make] 对: 能打印版本  证: 按生成的 Makefile 编译并链接模型' '$ make --version'; make --version
REMOTE
