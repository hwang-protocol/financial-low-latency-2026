#!/usr/bin/env bash
# 教师安全工具：只在 .1 上运行。取得 X2522，启动 testpmd，收到 stop 或到时后交还。
set -Eeuo pipefail

BDF=0000:03:00.0
IFACE=ens64np0
ADDR=20.1.1.1/24
GROUP=7
DEADMAN=120
STOP_FILE="${STOP_FILE:?set STOP_FILE}"
SESSION_DIR="${SESSION_DIR:?set SESSION_DIR}"
mkdir -p "$SESSION_DIR"
exec > >(tee "$SESSION_DIR/session.log") 2>&1

current_netdev() {
  find "/sys/bus/pci/devices/$BDF/net" -mindepth 1 -maxdepth 1 -printf '%f\n' 2>/dev/null | head -n 1
}

restore() {
  set +e
  if [[ -n "${tpmd:-}" ]]; then
    kill -INT "$tpmd" 2>/dev/null || true
    wait "$tpmd" 2>/dev/null || true
  fi
  pkill -x dpdk-testpmd 2>/dev/null || true
  /usr/bin/dpdk-devbind.py --bind=sfc "$BDF" >/dev/null 2>&1 || true
  udevadm settle || true
  current="$(current_netdev)"
  if [[ -n "$current" && "$current" != "$IFACE" ]]; then
    ip link set "$current" down || true
    ip link set "$current" name "$IFACE" || true
  fi
  ip link set "$IFACE" up || true
  ip addr replace "$ADDR" dev "$IFACE" || true
  find /dev/hugepages -maxdepth 1 -type f -name 'rtemap_*' -delete 2>/dev/null || true
  sysctl -w vm.nr_hugepages=0 || true
  {
    echo '=== restore ==='
    echo "driver=$(basename "$(readlink "/sys/bus/pci/devices/$BDF/driver")" 2>/dev/null)"
    echo "netdev=$(current_netdev)"
    ip -4 -o addr show dev "$IFACE" || true
    echo "carrier=$(cat "/sys/class/net/$IFACE/carrier" 2>/dev/null || echo missing)"
    echo "hugepages=$(cat /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages)"
    echo RESTORE_DONE
  } | tee "$SESSION_DIR/restore.receipt"
}
trap restore EXIT

# ~~~~~二次核对 sfc / 网口 / group / unsafe=N~~~~~
echo '=== preflight ==='
test "$(basename "$(readlink "/sys/bus/pci/devices/$BDF/driver")")" = sfc
test "$(current_netdev)" = "$IFACE"
ip -4 -o addr show dev "$IFACE" | grep -Fq " $ADDR "
test "$(basename "$(readlink -f "/sys/bus/pci/devices/$BDF/iommu_group")")" = "$GROUP"
mapfile -t group_devices < <(find "/sys/kernel/iommu_groups/$GROUP/devices" -mindepth 1 -maxdepth 1 -printf '%f\n')
test "${#group_devices[@]}" -eq 1
test "${group_devices[0]}" = "$BDF"
test "$(cat /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages)" = 0
modprobe vfio-pci
test "$(cat /sys/module/vfio/parameters/enable_unsafe_noiommu_mode)" = N
printf 'driver=sfc group=%s group_device=%s unsafe_noiommu=N\n' "$GROUP" "${group_devices[0]}"

# ~~~~~绑 vfio-pci，起 testpmd macswap~~~~~
sysctl -w vm.nr_hugepages=256
test "$(cat /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages)" = 256
if ! findmnt -t hugetlbfs >/dev/null; then
  mkdir -p /dev/hugepages
  mount -t hugetlbfs nodev /dev/hugepages
fi
ip link set "$IFACE" down
/usr/bin/dpdk-devbind.py --bind=vfio-pci "$BDF"
test "$(basename "$(readlink "/sys/bus/pci/devices/$BDF/driver")")" = vfio-pci
rm -f "$STOP_FILE"

/usr/bin/dpdk-testpmd -l 1-2 -n 2 -m 128 -a "$BDF" -- \
  --nb-cores=1 --rxq=1 --txq=1 --rxd=256 --txd=256 \
  --total-num-mbufs=2048 --forward-mode=macswap --auto-start --stats-period 2 \
  >"$SESSION_DIR/testpmd.log" 2>&1 &
tpmd=$!
sleep 6
kill -0 "$tpmd"
grep -Fq 'Using IOMMU type 1' "$SESSION_DIR/testpmd.log"
echo TESTPMD_READY

# ~~~~~stop 或 120 秒到时后交还 sfc~~~~~
for ((second=0; second<DEADMAN; second++)); do
  [[ -f "$STOP_FILE" ]] && break
  kill -0 "$tpmd"
  sleep 1
done
[[ -f "$STOP_FILE" ]] || { echo 'deadman_expired=1'; exit 124; }
