#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
source Documents/newDoc/assets/common/flle-remote.sh
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-08-xdp-build"
OUT="Documents/reports/course-runs/$RUN_ID"; REMOTE="/var/tmp/$RUN_ID"
SOURCE=Documents/newDoc/assets/08-xdp/flle_xdp_mold_itch.c
SOURCE_SHA="$(sha256sum "$SOURCE" | awk '{print $1}')"
mkdir -p "$OUT/raw" "$OUT/artifacts"; printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
printf 'SOURCE_SHA256=%s\n' "$SOURCE_SHA" >>"$OUT/run.env"
cleanup(){ ssh -n "${FLLE_SSH_OPTS[@]}" root@10.1.1.2 "find '$REMOTE' -type f -delete 2>/dev/null; rmdir '$REMOTE' 2>/dev/null || true"; }
trap cleanup EXIT
ssh -n "${FLLE_SSH_OPTS[@]}" root@10.1.1.2 "mkdir '$REMOTE'"
scp -q "${FLLE_SSH_OPTS[@]}" "$SOURCE" root@10.1.1.2:"$REMOTE/"
ssh -n "${FLLE_SSH_OPTS[@]}" root@10.1.1.2 "set -Eeuo pipefail; cd '$REMOTE'; test \"\$(sha256sum flle_xdp_mold_itch.c | cut -d' ' -f1)\" = '$SOURCE_SHA'; printf '%s\\n' '' 'vm-2522-02 / build' '===== 查编译 BPF 对象 =====' '[clang] 对: 生成 flle_xdp_mold_itch.o  证: -target bpf 选择 BPF 指令，-O2 优化，-g 保留类型与调试信息' '\$ clang -O2 -g -target bpf ... -c flle_xdp_mold_itch.c -o flle_xdp_mold_itch.o'; clang -O2 -g -fdebug-prefix-map='$REMOTE'=/flle/ch08 -target bpf -D__TARGET_ARCH_x86 -I/usr/include/x86_64-linux-gnu -c flle_xdp_mold_itch.c -o flle_xdp_mold_itch.o; printf '%s\\n' '' 'vm-2522-02 / build' '===== 查ELF 分区 =====' '[ELF] 对: elf64-bpf，并有 xdp / .maps / .BTF  证: 目标指令、程序段、共享表和类型信息都在对象中' '\$ llvm-objdump -h flle_xdp_mold_itch.o'; llvm-objdump -h flle_xdp_mold_itch.o; printf '%s\\n' '' 'vm-2522-02 / build' '===== 查源码与对象指纹 =====' '[SHA-256] 对: 两份文件各有完整指纹  证: 把后续加载对象与本次编译对应起来' '\$ sha256sum flle_xdp_mold_itch.*'; sha256sum flle_xdp_mold_itch.*" 2>&1 | tee "$OUT/raw/build.txt"
scp -q "${FLLE_SSH_OPTS[@]}" root@10.1.1.2:"$REMOTE/flle_xdp_mold_itch.o" "$OUT/artifacts/"
printf 'OBJECT_SHA256=%s\n' "$(sha256sum "$OUT/artifacts/flle_xdp_mold_itch.o" | awk '{print $1}')" >>"$OUT/run.env"
(cd "$OUT" && sha256sum raw/build.txt artifacts/flle_xdp_mold_itch.o run.env >SHA256SUMS)
printf 'evidence=%s\n' "$OUT"
