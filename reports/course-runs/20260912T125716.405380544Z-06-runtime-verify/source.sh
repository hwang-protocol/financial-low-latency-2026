#!/usr/bin/env bash
# Observe the runtime installed in Chapter 02. No installation or driver reload.
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%S.%NZ)-06-runtime-verify"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
cp "$0" "$OUT/source.sh"
finish(){ rc=$?; trap - EXIT; printf 'EXIT_CODE=%s\n' "$rc" >>"$OUT/run.env"; (cd "$OUT" && sha256sum raw/result.txt run.env source.sh >SHA256SUMS); echo "evidence=$OUT"; exit "$rc"; }
trap finish EXIT
{
for host in 10.1.1.1 10.1.1.2; do
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@"$host" bash -s <<'REMOTE'
set -Eeuo pipefail
field(){ printf '%-34s# %s\n' "$1" "$2"; }
fail(){ printf 'runtime=NOT_READY  # %s\n' "$1" >&2; exit 1; }

printf '\n# 1. 检查对象\n'
field "$(hostname)" '本次检查的主机'

onload_output="$(onload --version)"
onload_version="$(awk '$1 == "Onload" {print $2; exit}' <<<"$onload_output")"
kernel_version="$(awk '$1 == "Kernel" && $2 == "module:" {print $3; exit}' <<<"$onload_output")"
printf '\n# 2. Onload 版本：用户态运行库与内核模块的版本标识应相同\n'
field "Onload $onload_version" '用户态运行库'
field "Kernel module: $kernel_version" '配套的内核模块'

printf '\n# 3. 构建信息\n'
while IFS= read -r line; do
  case "$line" in
    'Onload '*|'Kernel module:'*) continue ;;
    'Copyright '*) printf '# 版权归属\n' ;;
    'Built:'*) printf '# 构建时间与构建类型：release 表示发布构建\n' ;;
    'Build profile header:'*) printf '# 编译时使用的配置头文件\n' ;;
    *) printf '# 其他原生输出\n' ;;
  esac
  printf '%s\n' "$line"
done <<<"$onload_output"
test -n "$onload_version" && test -n "$kernel_version" || fail '未能识别 Onload 或内核模块版本'
test "$onload_version" = "$kernel_version" || fail 'Onload 用户态运行库与内核模块版本不一致'

printf '\n# 4. sfc 驱动版本：当前已加载版本应与磁盘上的模块版本相同\n'
loaded_sfc="$(cat /sys/module/sfc/version)"
expected_sfc="$(modinfo -F version sfc)"
field "loaded_sfc=$loaded_sfc" '当前内核已加载的 sfc 版本'
field "expected_sfc=$expected_sfc" 'modinfo 查询到的磁盘模块版本'
test "$loaded_sfc" = "$expected_sfc" || fail '已加载的 sfc 与磁盘模块版本不一致'

printf '\n# 5. Onload 控制入口：/dev/onload 用于管理 Onload 栈\n'
printf '# ls -l 行首的 c 表示字符设备，供应用与驱动交互\n'
test -c /dev/onload || fail '/dev/onload 不存在或不是字符设备'
ls -l /dev/onload

printf '\n# 6. 网卡资源入口：/dev/sfc_char 用于申请 VI 等网卡资源\n'
printf '# VI（Virtual Interface，虚拟接口）包含用户态栈使用的收发队列和事件资源\n'
test -c /dev/sfc_char || fail '/dev/sfc_char 不存在或不是字符设备'
ls -l /dev/sfc_char

printf '\n# 7. 检查结果\n'
test "$(basename "$(readlink /sys/bus/pci/devices/0000:03:00.0/driver)")" = sfc || fail 'X2522 当前未绑定 sfc'
field 'runtime=READY' '本机运行时检查通过'
REMOTE
done
printf '# 两端均为 runtime=READY，再进入准备 B 检查网卡隔离\n'
printf '# 设备文件就绪说明控制入口可用；运行 ②、③再确认订单连接实际使用加速路径\n'
} 2>&1 | tee "$OUT/raw/result.txt"
