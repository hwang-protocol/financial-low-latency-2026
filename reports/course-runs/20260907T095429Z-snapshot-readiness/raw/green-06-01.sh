#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-06-onload-runtime-prep"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"; printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
ARCHIVE="artifacts/blobs/x2522/onload/v9.0.2/onload-9f330e7-vm-2522-01.tgz"
# ~~~~~通过管理网向两端分发 Onload 安装归档~~~~~
printf '%s  %s\n' 998d218db3733d85e3732f56790eca963f24deb05c6da4306d4dd9ab0c29d9e2 "$ARCHIVE" | sha256sum -c -
for item in '10.1.1.1 ens64np0 20.1.1.1' '10.1.1.2 ens64np1 20.1.1.2'; do
  read -r host iface addr <<<"$item"; remote="/var/tmp/$RUN_ID.tgz"
  scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes "$ARCHIVE" "root@$host:$remote"
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@"$host" bash -s -- "$remote" "$iface" "$addr" <<'REMOTE' 2>&1 | tee -a "$OUT/raw/result.txt"
set -Eeuo pipefail
archive="$1"; iface="$2"; addr="$3"; src=/opt/flle/course-src/onload-9f330e7
cleanup(){ find /var/tmp -maxdepth 1 -type f -name "${archive##*/}" -delete; }; trap cleanup EXIT
printf '%s  %s\n' 998d218db3733d85e3732f56790eca963f24deb05c6da4306d4dd9ab0c29d9e2 "$archive" | sha256sum -c -
# ~~~~~装编译依赖；没有 /dev/onload 才编译安装~~~~~
pre=/opt/flle/prewarm/apt; cache=/var/cache/apt/archives
(cd "$pre" && printf '%s  %s\n' \
  5243177370b810cc40341801a3b8def6cdd7477ac765862f7727a868629947a3 cpp-11_11.4.0-1ubuntu1~22.04.3_amd64.deb \
  ddbaa04f056637caa11798750638bf4586c8b273719fd1bee70d0ecb3d872b94 g++-11_11.4.0-1ubuntu1~22.04.3_amd64.deb \
  5422307110e695d62a2574c8b765bf38d48b2ed520206e5b7d2b9081a68008f3 gcc-11_11.4.0-1ubuntu1~22.04.3_amd64.deb | sha256sum -c -)
install -m 644 "$pre"/*.deb "$cache/"
apt-get -o Acquire::Retries=3 update
DEBIAN_FRONTEND=noninteractive apt-get -o Acquire::Retries=3 install -y --no-install-recommends build-essential libcap-dev python3-dev "linux-headers-$(uname -r)"
if ! test -c /dev/onload; then
  if ! test -x "$src/scripts/onload_install"; then test ! -e "$src"; mkdir -p "${src%/*}"; tar -xzf "$archive" -C "${src%/*}"; fi
  "$src/scripts/onload_install" --no-initramfs
  onload_tool reload
fi
# ~~~~~reload 可能改网口名、丢掉地址；按 PCI 恢复后连续复核课程 IP~~~~~
udevadm settle
current="$(basename "$(find /sys/bus/pci/devices/0000:03:00.0/net -mindepth 1 -maxdepth 1 -print -quit)")"
test -n "$current"
if test "$current" != "$iface"; then
  test ! -e "/sys/class/net/$iface"; ip link set dev "$current" down
  ip link set dev "$current" name "$iface"
fi
networkctl reconfigure "$iface" || true
ready=0; for n in $(seq 1 30); do addr_snapshot="$(ip -4 -o addr show dev "$iface")"; grep -Fq " $addr/" <<<"$addr_snapshot" && { ready=1; break; }; sleep 1; done
test "$ready" -eq 1; for _ in 1 2; do sleep 1; addr_snapshot="$(ip -4 -o addr show dev "$iface")"; grep -Fq " $addr/" <<<"$addr_snapshot"; done
version_snapshot="$(onload --version)"; grep -Eq '^Onload 9f330e7[[:space:]]*$' <<<"$version_snapshot"; grep -Eq '^Kernel module: 9f330e7[[:space:]]*$' <<<"$version_snapshot"; test -c /dev/onload; test -c /dev/sfc_char; test "$(basename "$(readlink /sys/bus/pci/devices/0000:03:00.0/driver)")" = sfc
printf '\n%s / verify\n' "$(hostname)"
printf '===== 查主机名 =====\n[哪台] 对: vm-2522-01 或 vm-2522-02  证: 没看错机\n$ hostname\n%s\n' "$(hostname)"
printf '===== 查 Onload 版本 =====\n[Onload版本] 对: Onload 9f330e7 与 Kernel module: 9f330e7 两行一致  证: 用户态与模块同一棵树\n$ onload --version\n%s\n' "$version_snapshot"
printf '===== 查字符设备 =====\n[字符设备] 对: /dev/onload 与 /dev/sfc_char 都以 c 开头  证: 栈控制和 VI 入口都在\n$ ls -l /dev/onload /dev/sfc_char\n'; ls -l /dev/onload /dev/sfc_char
printf '===== 查出站闸主人 =====\n[出站闸主人] 对: /sys/bus/pci/drivers/sfc  证: 本步仍由 sfc 管卡\n$ readlink -f .../0000:03:00.0/driver\n%s\n' "$(readlink -f /sys/bus/pci/devices/0000:03:00.0/driver)"
printf '===== 查数据口地址 =====\n[数据口] 对: %s 上有 %s/24  证: reload 后课程地址还在\n$ ip -4 -o addr show dev %s\n%s\n' "$iface" "$addr" "$iface" "$addr_snapshot"
REMOTE
done
(cd "$OUT" && sha256sum raw/result.txt run.env >SHA256SUMS); echo "evidence=$OUT"
