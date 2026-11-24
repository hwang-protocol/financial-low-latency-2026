#!/usr/bin/env bash
# Remote safety wrapper for the one-host F-Stack/X2522 TCP smoke.
# Run only on vm-2522-02 over the 10.1.1.x management network.
set -Eeuo pipefail

BDF=0000:03:00.0
IFACE=ens64np1
ADDR=20.1.1.2/24
GROUP=7
EXPECTED_HOST=vm-2522-02
DEADMAN=90
ROOT_PID=$BASHPID

CONFIG="${1:?usage: $0 CONFIG BINARY SESSION_DIR}"
BINARY="${2:?usage: $0 CONFIG BINARY SESSION_DIR}"
SESSION_DIR="${3:?usage: $0 CONFIG BINARY SESSION_DIR}"
mkdir -p "$SESSION_DIR"
exec > >(tee "$SESSION_DIR/session.log") 2>&1

current_netdev() {
  find "/sys/bus/pci/devices/$BDF/net" -mindepth 1 -maxdepth 1 \
    -printf '%f\n' 2>/dev/null | head -n 1
}

restore() {
  [[ "$BASHPID" -eq "$ROOT_PID" ]] || return 0
  set +e
  pkill -f "^${BINARY} " 2>/dev/null || true
  /usr/bin/dpdk-devbind.py --bind=sfc "$BDF" >/dev/null 2>&1 || true
  udevadm settle || true

  current="$(current_netdev)"
  if [[ -n "$current" && "$current" != "$IFACE" ]]; then
    ip link set "$current" down || true
    ip link set "$current" name "$IFACE" || true
  fi
  ip link set "$IFACE" up || true
  ip addr replace "$ADDR" dev "$IFACE" || true
  for _ in $(seq 1 30); do
    [[ "$(cat "/sys/class/net/$IFACE/carrier" 2>/dev/null)" = 1 ]] && break
    sleep 1
  done

  find /dev/hugepages -maxdepth 1 -type f -name 'rtemap_*' -delete \
    2>/dev/null || true
  for _ in $(seq 1 30); do
    sysctl -w vm.nr_hugepages=0 >/dev/null 2>&1 || true
    [[ "$(cat /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages)" = 0 ]] \
      && break
    sleep 1
  done

  {
    echo '=== restore ==='
    echo "driver=$(basename "$(readlink "/sys/bus/pci/devices/$BDF/driver")" 2>/dev/null)"
    echo "netdev=$(current_netdev)"
    ip -4 -o addr show dev "$IFACE" || true
    echo "hugepages=$(cat /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages)"
    echo RESTORE_DONE
  } | tee "$SESSION_DIR/restore.receipt"
}
trap restore EXIT

echo '=== preflight ==='
test "$(hostname)" = "$EXPECTED_HOST"
test -x "$BINARY"
test -r "$CONFIG"
test "$(basename "$(readlink "/sys/bus/pci/devices/$BDF/driver")")" = sfc
test "$(current_netdev)" = "$IFACE"
ip -4 -o addr show dev "$IFACE" | grep -Fq " $ADDR "
test "$(basename "$(readlink -f "/sys/bus/pci/devices/$BDF/iommu_group")")" = "$GROUP"
mapfile -t group_devices < <(find "/sys/kernel/iommu_groups/$GROUP/devices" \
  -mindepth 1 -maxdepth 1 -printf '%f\n')
test "${#group_devices[@]}" -eq 1
test "${group_devices[0]}" = "$BDF"
test "$(cat /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages)" = 0
modprobe vfio-pci
test "$(cat /sys/module/vfio/parameters/enable_unsafe_noiommu_mode)" = N
printf 'driver=sfc group=%s group_device=%s unsafe_noiommu=N\n' \
  "$GROUP" "${group_devices[0]}"

echo '=== acquire X2522 with safe VFIO ==='
sysctl -w vm.nr_hugepages=256
test "$(cat /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages)" = 256
if ! findmnt -t hugetlbfs >/dev/null; then
  mkdir -p /dev/hugepages
  mount -t hugetlbfs nodev /dev/hugepages
fi
ip link set "$IFACE" down
/usr/bin/dpdk-devbind.py --bind=vfio-pci "$BDF"
test "$(basename "$(readlink "/sys/bus/pci/devices/$BDF/driver")")" = vfio-pci

echo '=== F-Stack TCP over DPDK net_sfc_efx ==='
timeout --signal=INT --kill-after=5 "$DEADMAN" \
  taskset -c 2 "$BINARY" --conf "$CONFIG" --proc-type=primary --proc-id=0 \
  | tee "$SESSION_DIR/fstack.log"
grep -Fq 'FSTACK_TCP_SMOKE_PASS bytes=52' "$SESSION_DIR/fstack.log"
echo FSTACK_X2522_SMOKE_DONE
