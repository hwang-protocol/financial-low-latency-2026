#!/usr/bin/env bash
set -Eeuo pipefail
cd /qyt-fll
exec 9>/run/lock/flle-platform-runtime-prep.lock; flock -n 9
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-02-onload-runtime-prep"
OUT="reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"; printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
ARCHIVE="artifacts/blobs/x2522/onload/v9.0.2/onload-9f330e7-vm-2522-01.tgz"
sfutils_temp="$(mktemp -d /tmp/flle-sfutils-XXXXXX)"
trap 'rm -rf -- "$sfutils_temp"' EXIT
SFUTILS_ARCHIVE="$sfutils_temp/sfutils-8.3.3.1000.tar.gz"
# All classroom labels and actual readings are saved alongside the full stage logs.
{
printf '%s / prepare\n===== 查安装归档 =====\n核对固定归档的摘要，确认分发的是本课版本。\n' "$(hostname)"
printf '$ printf %q %q | sha256sum -c -\n' '%s\n' "998d218db3733d85e3732f56790eca963f24deb05c6da4306d4dd9ab0c29d9e2  $ARCHIVE"
printf '%s  %s\n' 998d218db3733d85e3732f56790eca963f24deb05c6da4306d4dd9ab0c29d9e2 "$ARCHIVE" | sha256sum -c -
printf '===== 准备授权查询工具源码 =====\n从本课缓存提取 sfutils 源码；目标机只构建 sfkey。\n$ python3 assets/02-trading-baseline/extract-sfutils-source.py %q\n' "$SFUTILS_ARCHIVE"
python3 assets/02-trading-baseline/extract-sfutils-source.py "$SFUTILS_ARCHIVE"
for item in '10.1.1.1 ens64np0 20.1.1.1' '10.1.1.2 ens64np1 20.1.1.2'; do
  read -r host iface addr <<<"$item"; remote="/var/tmp/$RUN_ID.tgz"; sfutils_remote="/var/tmp/$RUN_ID-sfutils.tgz"
  printf '\n%s / prepare\n===== 安装离线构建依赖 =====\n给目标主机补齐 Onload 构建工具；完整过程保存在日志。\n$ python3 assets/common/install-offline-packages.py %q onload-build\n' "$host" "$host"
  package_log="$OUT/raw/$host-packages.txt"
  if python3 assets/common/install-offline-packages.py "$host" onload-build >"$package_log" 2>&1; then rc=0; else rc=$?; fi
  printf '$ tail -n 8 %q\n' "$package_log"; tail -n 8 "$package_log"; test "$rc" -eq 0 || exit "$rc"
  printf '===== 分发安装归档 =====\n复制摘要已核对的源码归档；scp 成功时没有正文输出。\n$ scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes %q %q\n' "$ARCHIVE" "root@$host:$remote"
  scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes "$ARCHIVE" "root@$host:$remote"
  printf '$ scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes %q %q\n' "$SFUTILS_ARCHIVE" "root@$host:$sfutils_remote"
  scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes "$SFUTILS_ARCHIVE" "root@$host:$sfutils_remote"
  printf '===== 安装并核对运行库与授权 =====\n按需安装 Onload 和 sfkey，再检查版本、数据口及 Plus 功能。远端 bash 从本脚本的 REMOTE 段读取命令。\n$ ssh -o BatchMode=yes -o StrictHostKeyChecking=yes %q bash -s -- %q %q %q %q\n' "root@$host" "$remote" "$iface" "$addr" "$sfutils_remote"
  runtime_log="$OUT/raw/$host-runtime.txt"
  printf '完整输出：%s\n' "$runtime_log"
  if ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@"$host" bash -s -- "$remote" "$iface" "$addr" "$sfutils_remote" <<'REMOTE' >"$runtime_log" 2>&1
set -Eeuo pipefail
exec 8>/run/lock/flle-platform-runtime-prep.lock; flock -n 8
archive="$1"; iface="$2"; addr="$3"; sfutils_archive="$4"; src=/opt/flle/course-src/onload-9f330e7
cleanup(){ rm -f -- "$archive" "$sfutils_archive"; }; trap cleanup EXIT
printf '%s  %s\n' 998d218db3733d85e3732f56790eca963f24deb05c6da4306d4dd9ab0c29d9e2 "$archive" | sha256sum -c -
# ~~~~~装编译依赖；没有 /dev/onload 才编译安装~~~~~
if ! test -c /dev/onload; then
  if ! test -x "$src/scripts/onload_install"; then test ! -e "$src"; mkdir -p "${src%/*}"; tar -xzf "$archive" -C "${src%/*}"; fi
  "$src/scripts/onload_install" --no-initramfs
fi
# Persist both the matching driver and stable course interface name across reboot.
mkdir -p /etc/systemd/network /var/lib/flle
link=/etc/systemd/network/10-flle-data.link
wanted="$(printf '[Match]\nPath=pci-0000:03:00.0\n[Link]\nName=%s\n' "$iface")"
if ! cmp -s "$link" <(printf '%s\n' "$wanted"); then printf '%s\n' "$wanted" >"$link"; fi
kernel="$(uname -r)"; stamp="/var/lib/flle/runtime-initramfs-$kernel.sha256"
inputs="$(sha256sum "$link" "$(modinfo -n sfc)" "$(modinfo -n onload)")"
if ! cmp -s "$stamp" <(printf '%s\n' "$inputs"); then
  update-initramfs -u -k "$kernel"
  printf '%s\n' "$inputs" >"$stamp"
fi
expected_sfc="$(modinfo -F version sfc)"
loaded_sfc="$(cat /sys/module/sfc/version 2>/dev/null || true)"
if test "$loaded_sfc" != "$expected_sfc" || ! test -c /dev/onload; then onload_tool reload; fi
test "$(cat /sys/module/sfc/version)" = "$expected_sfc"
# ~~~~~reload 可能改网口名、丢掉地址；按 PCI 恢复后连续复核课程 IP~~~~~
udevadm settle
current="$(basename "$(find /sys/bus/pci/devices/0000:03:00.0/net -mindepth 1 -maxdepth 1 -print -quit)")"
test -n "$current"
if test "$current" != "$iface"; then
  test ! -e "/sys/class/net/$iface"; ip link set dev "$current" down
  ip link set dev "$current" name "$iface"
fi
# Reapplying an already-correct link interrupts live multicast/unicast reception.
# A repeated prep only reconfigures when the expected address is actually missing.
addr_snapshot="$(ip -4 -o addr show dev "$iface")"
if ! grep -Fq " $addr/" <<<"$addr_snapshot"; then networkctl reconfigure "$iface"; fi
ready=0; for n in $(seq 1 30); do addr_snapshot="$(ip -4 -o addr show dev "$iface")"; grep -Fq " $addr/" <<<"$addr_snapshot" && { ready=1; break; }; sleep 1; done
test "$ready" -eq 1; for _ in 1 2; do sleep 1; addr_snapshot="$(ip -4 -o addr show dev "$iface")"; grep -Fq " $addr/" <<<"$addr_snapshot"; done
version_snapshot="$(onload --version)"; grep -Eq '^Onload 9f330e7[[:space:]]*$' <<<"$version_snapshot"; grep -Eq '^Kernel module: 9f330e7[[:space:]]*$' <<<"$version_snapshot"; test -c /dev/onload; test -c /dev/sfc_char; test "$(basename "$(readlink /sys/bus/pci/devices/0000:03:00.0/driver)")" = sfc
# SFKEY_PREP_BEGIN: build only the query tool, after the matching sfc is loaded.
sfkey_bin=/usr/sbin/sfkey
sfkey_version="$($sfkey_bin --version 2>/dev/null || true)"
if ! grep -Eq '^sfkey firmware update utility: v8\.3\.3\.1000[[:space:]]*$' <<<"$sfkey_version"; then
  printf '%s  %s\n' 258ae93bd116c767188a4cf91917d5420dd1f3124a0279e51affcd63cebd6403 "$sfutils_archive" | sha256sum -c -
  mkdir -p /opt/flle/course-src
  sfkey_work="$(mktemp -d /opt/flle/course-src/sfkey-XXXXXX)"
  tar -xzf "$sfutils_archive" -C "$sfkey_work"
  printf '$ make -C %q -j2 build-sfkey NEW_GCC=1 AWK=awk\n' "$sfkey_work/sfutils-8.3.3.1000"
  make -C "$sfkey_work/sfutils-8.3.3.1000" -j2 build-sfkey NEW_GCC=1 AWK=awk
  install -m 0755 "$sfkey_work/sfutils-8.3.3.1000/build/linux/tmp/sfkey/sfkey" "$sfkey_bin"
  install -D -m 0644 "$sfkey_work/sfutils-8.3.3.1000/LICENSE" /usr/share/doc/flle-sfkey/LICENSE
fi
sfkey_version="$($sfkey_bin --version)"
grep -Eq '^sfkey firmware update utility: v8\.3\.3\.1000[[:space:]]*$' <<<"$sfkey_version"
# SFKEY_PREP_END
printf '\n%s / verify\n' "$(hostname)"
printf '\n===== 查主机名 =====\n[主机说明] 确认本段结果来自哪台机器。\n$ hostname\n%s\n' "$(hostname)"
printf '\n===== 查 Onload 版本 =====\n[版本说明] Onload 与 Kernel module 都应为 9f330e7，说明用户态库与已加载模块匹配。\n$ onload --version\n%s\n' "$version_snapshot"
printf '\n===== 查字符设备 =====\n[设备说明] 两个入口都应存在，且权限字段以 c 开头，表示配套内核模块已加载。\n$ ls -l /dev/onload /dev/sfc_char\n'; ls -l /dev/onload /dev/sfc_char
printf '\n===== 查网卡驱动 =====\n[驱动说明] 结果应指向 /sys/bus/pci/drivers/sfc，说明本步仍由 sfc 管理数据口。\n$ readlink -f /sys/bus/pci/devices/0000:03:00.0/driver\n%s\n' "$(readlink -f /sys/bus/pci/devices/0000:03:00.0/driver)"
printf '\n===== 查数据口地址 =====\n[地址说明] %s 应有 %s/24，确认加载驱动后课程地址正常。\n$ ip -4 -o addr show dev %s\n%s\n' "$iface" "$addr" "$iface" "$addr_snapshot"
# SFKEY_QUERY_BEGIN: never install, clear, back up or refresh activation keys.
printf '\n===== 查 sfkey 工具 =====\n[工具说明] sfkey 来自 sfutils；版本应为 v8.3.3.1000，后面用它读取本卡授权。\n$ sfkey --version\n%s\n' "$sfkey_version"
printf '\n===== 查 Plus 授权 =====\n[授权说明] Installed keys 后出现 Plus，表示卡上已有 Plus 授权。查询不更新试用授权。\n$ sfkey --adapter=%s --report --noevaluationupdate\n' "$iface"
"$sfkey_bin" --adapter="$iface" --report --noevaluationupdate
printf '\n===== 查已启用功能 =====\n[清单说明] 下面是网卡实际返回的功能；$ 前缀表示出厂随卡功能。\n$ sfkey --adapter=%s --inventory --keys --noevaluationupdate\n' "$iface"
"$sfkey_bin" --adapter="$iface" --inventory --keys --noevaluationupdate
printf '\n[功能名称怎么读]\n  Onload           普通 Socket 程序的用户态网络加速\n  TCP Direct       专用 API 的用户态 TCP/UDP 协议栈\n  Low Latency      网卡低延迟功能\n  Precision Time   精确时间与 PTP 功能\n  SolarCapture Tap 抓包相关功能\n  Plus             组合授权名称\n'
printf '\n[后续使用] 用 onload 启动交易客户端，再用 onload_stackdump 检查连接是否实际得到加速。\n'
# SFKEY_QUERY_END
REMOTE
  then rc=0; else rc=$?; fi
  if test "$rc" -ne 0; then printf '安装或核对失败，退出码 %s\n$ tail -n 20 %q\n' "$rc" "$runtime_log"; tail -n 20 "$runtime_log"; exit "$rc"; fi
  printf '关键结果（从 verify 阶段开始）：\n$ sed -n %q %q\n' '/^[^ ]* \/ verify/,$p' "$runtime_log"
  sed -n '/^[^ ]* \/ verify/,$p' "$runtime_log"
done
} 2>&1 | tee "$OUT/raw/result.txt"
(cd "$OUT" && sha256sum raw/*.txt run.env >SHA256SUMS); echo "evidence=$OUT"
