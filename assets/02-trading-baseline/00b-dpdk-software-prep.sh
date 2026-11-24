#!/usr/bin/env bash
# Install the fixed software before creating a trading session; do not start it.
set -Eeuo pipefail
cd /qyt-fll
exec 9>/run/lock/flle-ch02-dpdk-software.lock; flock -n 9
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-02-dpdk-software-prep"
OUT="reports/course-runs/$RUN_ID"
mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
finish(){
  rc=$?; trap - EXIT
  printf 'EXIT_CODE=%s\n' "$rc" >>"$OUT/run.env"
  (cd "$OUT" && sha256sum raw/*.txt run.env >SHA256SUMS)
  printf 'evidence=%s\n' "$OUT"
  exit "$rc"
}
trap finish EXIT
ARCHIVE=artifacts/blobs/x2522/ch05-four-path/v13/flle-ch05-four-path-v13-x86_64-jammy-runtime.tgz
SHA=0e5d77fef1e4891b9f2220681c18162da6c605ea5619ea00e28022f23281dc00
CACHE="/opt/flle/prepared-runtime/$SHA"
SSH=(ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=8)
{
printf '===== 核对安装包 =====\n[来源说明] 使用课程缓存的固定运行包；F-Stack 和 DPDK 已编入交易客户端。\n'
printf '$ sha256sum %q\n' "$ARCHIVE"
sha256sum "$ARCHIVE"
test "$(sha256sum "$ARCHIVE" | awk '{print $1}')" = "$SHA"
for host in 10.1.1.1 10.1.1.2; do
  remote="/var/tmp/$RUN_ID-runtime.tgz"
  printf '\n===== 准备 %s 的软件 =====\n' "$host"
  if "${SSH[@]}" root@"$host" test -d "$CACHE"; then
    printf '[安装说明] 已有本版本，核对后复用。\n'
  else
    rc=$?; test "$rc" -eq 1 || exit "$rc"
    printf '[安装说明] 安装到独立目录；此时不启动客户端、不改绑数据口。\n'
    printf '$ scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes %q %q\n' "$ARCHIVE" "root@$host:$remote"
    scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes "$ARCHIVE" "root@$host:$remote"
  fi
  log="$OUT/raw/$host-software.txt"
  printf '完整日志：%s\n' "$log"
  if "${SSH[@]}" root@"$host" bash -s -- "$remote" "$CACHE" "$SHA" <<'REMOTE' >"$log" 2>&1
set -Eeuo pipefail
incoming="$1"; cache="$2"; expected_sha="$3"; stage=""
exec 8>/run/lock/flle-prepared-runtime.lock; flock -n 8
cleanup(){ test -z "$stage" || rm -rf -- "$stage"; rm -f -- "$incoming"; }
trap cleanup EXIT
# B1 must have completed before any software is published as ready.
group="$(readlink -f /sys/bus/pci/devices/0000:03:00.0/iommu_group)"
if ! test -d "$group/devices"; then
  echo '缺少 IOMMU 隔离组；先执行准备 B1（00b-iommu-prep.sh）。' >&2
  exit 1
fi
if test "${group##*/}" != 7 || test "$(find "$group/devices" -mindepth 1 -maxdepth 1 -printf '%f\n')" != 0000:03:00.0; then
  echo '隔离组不符合本课配置：应为组 7，且只包含数据口 0000:03:00.0。请先核对准备 B1。' >&2
  exit 1
fi
if test "$(cat /sys/module/vfio/parameters/enable_unsafe_noiommu_mode)" != N; then
  echo 'VFIO 安全模式未就绪：enable_unsafe_noiommu_mode 应为 N。请先完成准备 B1。' >&2
  exit 1
fi
if test "$(basename "$(readlink /sys/bus/pci/devices/0000:03:00.0/driver)")" != sfc; then
  echo '数据口当前不归 sfc；请先用课程控制器恢复普通网口，再执行软件准备。' >&2
  exit 1
fi
verify_software(){
  local base="$1" runtime="$1/flle-ch05-four-path" deps symbols names
  printf '%s  %s\n' "$expected_sha" "$base/runtime.tgz" | sha256sum -c -
  (cd "$runtime" && sha256sum -c MANIFEST.sha256)
  test -x "$runtime/bin/flle-trader-dpdk"
  test -x "$runtime/bin/dpdk-devbind.py"
  symbols="$(readelf -Ws "$runtime/bin/flle-trader-dpdk")"
  grep -Eq '[[:space:]]ff_init$' <<<"$symbols"
  grep -Eq '[[:space:]]rte_eal_init$' <<<"$symbols"
  names="$(strings "$runtime/bin/flle-trader-dpdk")"
  grep -Fxq net_sfc_efx <<<"$names"
  deps="$(LD_LIBRARY_PATH="$runtime/lib" ldd "$runtime/bin/flle-trader-dpdk")"
  printf '%s\n' "$deps"
  if grep -Fq 'not found' <<<"$deps"; then return 1; fi
}
if ! test -d "$cache"; then
  printf '%s  %s\n' "$expected_sha" "$incoming" | sha256sum -c -
  mkdir -p "${cache%/*}"
  stage="$(mktemp -d "${cache%/*}/.install-XXXXXX")"
  cp "$incoming" "$stage/runtime.tgz"
  tar -xzf "$stage/runtime.tgz" -C "$stage"
  verify_software "$stage"
  mv -T "$stage" "$cache"; stage=""
else
  verify_software "$cache"
fi
runtime="$cache/flle-ch05-four-path"
printf '\n%s / verify\n' "$(hostname)"
printf '\n===== 查网卡型号 =====\n[型号说明] Subsystem 是板卡型号；方括号中是 PCI 厂商与设备编号。\n$ lspci -nnk -s 0000:03:00.0\n'
LC_ALL=C lspci -nnk -s 0000:03:00.0
printf '\n[支持文档] DPDK 21.11.9 → Solarflare libefx-based PMD → Supported NICs\nhttps://doc.dpdk.org/guides-21.11/nics/sfc_efx.html#supported-nics\n该节列出 Solarflare X2522 Dual Port SFP28 10/25GbE Adapter。\n'
printf '\n===== 查已安装软件的版本 =====\n[版本说明] 以下读取安装包的构建记录。\n'
version_query='import json,sys; d=json.load(open(sys.argv[1]))["dependencies"]["f_stack_dpdk"]; print("DPDK:",d["dpdk_version"]); print("F-Stack:",d["f_stack_commit"])'
printf '$ python3 -c %q %q\n' "$version_query" "$runtime/provenance/BUILD-PROVENANCE.json"
python3 -c "$version_query" "$runtime/provenance/BUILD-PROVENANCE.json"
printf '\n===== 查运行程序文件 =====\n[文件说明] flle-trader-dpdk 是已编入 DPDK/F-Stack 的交易客户端；dpdk-devbind.py 用于后续切换网卡驱动。\n'
printf '$ cd %q\n' "$runtime"
(
  cd "$runtime"
  printf '$ ls -lh bin/flle-trader-dpdk bin/dpdk-devbind.py\n'
  ls -lh bin/flle-trader-dpdk bin/dpdk-devbind.py
  printf '$ test -x bin/flle-trader-dpdk && test -x bin/dpdk-devbind.py\n'
  test -x bin/flle-trader-dpdk && test -x bin/dpdk-devbind.py || exit 1
  printf '[文件检查] 两个程序均存在且可执行。\n'
)
printf '\n===== 查客户端已包含两套库 =====\n[链接说明] ff_init 来自 F-Stack；rte_eal_init 来自 DPDK。以下读取程序符号，不启动程序。\n'
printf '$ readelf -Ws %q | awk %q | sort -u\n' "$runtime/bin/flle-trader-dpdk" '$NF=="ff_init" || $NF=="rte_eal_init" {print $NF}'
readelf -Ws "$runtime/bin/flle-trader-dpdk" | awk '$NF=="ff_init" || $NF=="rte_eal_init" {print $NF}' | sort -u
printf '\n[PMD说明] 客户端中也包含 X2522 对应的 net_sfc_efx 驱动。\n'
printf '$ strings %q | grep -Fx net_sfc_efx | sort -u\n' "$runtime/bin/flle-trader-dpdk"
strings "$runtime/bin/flle-trader-dpdk" | grep -Fx net_sfc_efx | sort -u
printf '\n===== 查隔离与驱动状态 =====\n[状态说明] 已有 IOMMU 隔离组，unsafe 模式为 N；网卡仍归 sfc。\n$ readlink -f /sys/bus/pci/devices/0000:03:00.0/iommu_group\n%s\n' "$group"
printf '$ cat /sys/module/vfio/parameters/enable_unsafe_noiommu_mode\n'; cat /sys/module/vfio/parameters/enable_unsafe_noiommu_mode
printf '$ readlink -f /sys/bus/pci/devices/0000:03:00.0/driver\n'; readlink -f /sys/bus/pci/devices/0000:03:00.0/driver
printf '\n[准备完成] 软件文件、链接依赖与隔离状态已核对。运行①使用这份软件恢复交易系统；第 05 章切到 DPDK 时才启动客户端并接管数据口。\n'
REMOTE
  then rc=0; else rc=$?; fi
  if test "$rc" -ne 0; then tail -n 25 "$log"; exit "$rc"; fi
  sed -n '/^[^ ]* \/ verify/,$p' "$log"
done
} 2>&1 | tee "$OUT/raw/result.txt"
