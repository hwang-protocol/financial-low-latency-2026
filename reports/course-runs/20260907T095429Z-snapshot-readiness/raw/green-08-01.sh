#!/usr/bin/env bash
(
set -Eeuo pipefail
cd /financial-low-latency
mkdir -p Documents/reports/course-runs
OUT="$(mktemp -d "Documents/reports/course-runs/$(date -u +%Y%m%dT%H%M%SZ)-08-xdp-toolchain-prep-XXXXXX")"
RUN_ID="${OUT##*/}"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
finish(){ rc=$?; trap - EXIT; printf 'EXIT_CODE=%s\n' "$rc" >>"$OUT/run.env"; (cd "$OUT" && sha256sum raw/result.txt run.env >SHA256SUMS) || rc=1; printf 'exit_code=%s evidence=%s\n' "$rc" "$OUT"; exit "$rc"; }
trap finish EXIT
trap 'printf "本地失败 rc=%s line=%s；日志：%s/raw/result.txt\n" "$?" "$LINENO" "$OUT" >&2' ERR
: >"$OUT/raw/result.txt"
source Documents/newDoc/assets/common/flle-remote.sh
ssh "${FLLE_SSH_OPTS[@]}" root@10.1.1.2 bash -s <<'REMOTE' 2>&1 | tee "$OUT/raw/result.txt"
set -Eeuo pipefail
trap 'rc=$?; printf "远端失败 rc=%s line=%s command=%s\n" "$rc" "$LINENO" "$BASH_COMMAND" >&2' ERR
printf '%s\n' '' 'vm-2522-02 / prepare' '===== 查安装编译与查看工具 =====' '[工具链] 对: 安装过程无错误  证: 准备 clang、LLVM、libbpf 与当前内核配套 bpftool'
packages=(clang llvm libbpf-dev "linux-tools-$(uname -r)")
ready=1
for pkg in "${packages[@]}"; do [[ "$(dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null)" == 'install ok installed' ]] || ready=0; done
for tool in clang llvm-objdump bpftool ip; do command -v "$tool" >/dev/null || ready=0; done
if (( ready )); then
  printf '%s\n' '工具包与命令入口已齐全，跳过 apt 更新和安装；继续读取实际版本。'
else
printf '%s\n' '' '===== 查包索引更新 ====='  '[APT] 对: 更新无错误  证: 安装前取得仓库包索引' '$ apt-get -o Acquire::Retries=3 update'
apt-get -o Acquire::Retries=3 -o DPkg::Lock::Timeout=120 update
printf '%s\n' '' '===== 查安装 XDP 工具 =====' '[APT] 对: 安装成功  证: 准备编译器与当前内核对应的查看工具' '$ apt-get install clang llvm libbpf-dev linux-tools-<当前内核版本>'
NEEDRESTART_MODE=l DEBIAN_FRONTEND=noninteractive apt-get -o Acquire::Retries=3 -o DPkg::Lock::Timeout=120 install -y --no-install-recommends "${packages[@]}"
fi
printf '%s\n' '' 'vm-2522-02 / verify' '===== 查C 编译器版本 =====' '[clang] 对: Ubuntu clang 14.0.0  证: 把 XDP C 源码编成 BPF 指令的编译器可用' '$ clang --version'; clang --version | sed -n '1,2p'
printf '%s\n' '' 'vm-2522-02 / verify' '===== 查BPF 查看工具版本 =====' '[bpftool] 对: v5.15.193  证: 可查询内核中的 BPF 程序和 map' '$ bpftool version'; bpftool version
printf '%s\n' '' 'vm-2522-02 / verify' '===== 查网络配置工具版本 =====' '[iproute2] 对: iproute2-5.15.0 / libbpf 0.5.0  证: 挂载 XDP 所用的 ip 工具及其 BPF 库版本明确' '$ ip -V'; ip -V
REMOTE
)
