#!/usr/bin/env bash
set -Eeuo pipefail

readonly run_dir="$(cd "$(dirname "$0")" && pwd)"
readonly run_id="${run_dir##*/}"
readonly cfg="${run_dir}/trex-dual.yaml"
readonly client="${run_dir}/market_trex_client.py"
readonly archive="/opt/flle/prewarm/trex/v3.08.tar.gz"
readonly trex_root="/opt/trex/v3.08"
readonly prefix="fllemarketday"
readonly server_pid_file="${run_dir}/trex-server.pid"
readonly server_pgid_file="${run_dir}/trex-server.pgid"
readonly deadman_unit="flle-market-day-${run_id}"

resolve_iface() {
  find "/sys/bus/pci/devices/$1/net" -mindepth 1 -maxdepth 1 -printf '%f\n'
}

show_hugepages() {
  local pool mountpoint
  grep -E '^Huge|^Hugetlb' /proc/meminfo
  for pool in /sys/kernel/mm/hugepages/hugepages-*; do
    printf '%s nr=%s free=%s resv=%s surp=%s\n' \
      "${pool##*/}" "$(<"$pool/nr_hugepages")" \
      "$(<"$pool/free_hugepages")" "$(<"$pool/resv_hugepages")" \
      "$(<"$pool/surplus_hugepages")"
  done
  findmnt -rn -t hugetlbfs -o TARGET,SOURCE,FSTYPE,OPTIONS || true
  while IFS= read -r mountpoint; do
    printf 'hugetlbfs_mount=%s\n' "$mountpoint"
    find "$mountpoint" -xdev -mindepth 1 -maxdepth 2 \
      -printf '%y %s %p\n'
    find "$mountpoint" -xdev -type f -print0 \
      | xargs -0 -r fuser -v || true
  done < <(findmnt -rn -t hugetlbfs -o TARGET)
}

assert_zero_hugepages() {
  local pool mountpoint
  [[ "$(awk '/^Hugetlb:/ {print $2}' /proc/meminfo)" == 0 ]]
  for pool in /sys/kernel/mm/hugepages/hugepages-*; do
    [[ "$(<"$pool/nr_hugepages")" == 0 ]]
    [[ "$(<"$pool/free_hugepages")" == 0 ]]
    [[ "$(<"$pool/resv_hugepages")" == 0 ]]
    [[ "$(<"$pool/surplus_hugepages")" == 0 ]]
  done
  while IFS= read -r mountpoint; do
    [[ -z "$(find "$mountpoint" -mindepth 1 -print -quit)" ]]
  done < <(findmnt -rn -t hugetlbfs -o TARGET)
  [[ ! -e /mnt/huge ]]
}

assert_management() {
  [[ "$(hostname)" == vm-broadcom-01 ]]
  ip -4 addr show dev ens33 | grep -Fq '10.1.1.11/24'
  ip route show default | grep -Fq 'default via 10.1.1.254 dev ens33'
}

assert_kernel_ports() {
  local spec bdf expected iface driver
  for spec in \
    '0000:03:00.0 00:0a:f7:f8:48:a0' \
    '0000:03:00.1 00:0a:f7:f8:48:a1'; do
    read -r bdf expected <<<"$spec"
    iface="$(resolve_iface "$bdf")"
    driver="$(basename "$(readlink -f "/sys/bus/pci/devices/$bdf/driver")")"
    [[ -n "$iface" && "$driver" == bnxt_en ]]
    [[ "$(<"/sys/class/net/$iface/address")" == "$expected" ]]
    [[ "$(<"/sys/class/net/$iface/operstate")" == down ]]
    [[ -z "$(ip -o address show dev "$iface")" ]]
    [[ ! -L "/sys/class/net/$iface/master" ]]
    ! ip -details link show dev "$iface" | grep -Eq 'prog/xdp|xdp.*id'
    printf 'bdf=%s iface=%s mac=%s driver=%s state=down addr=none xdp=none\n' \
      "$bdf" "$iface" "$expected" "$driver"
  done
}

assert_no_runtime() {
  ! pgrep -x t-rex-64 >/dev/null
  ! pgrep -x _t-rex-64 >/dev/null
  ! pgrep -f 'market_trex_client.py' >/dev/null
  ! ss -H -lntup | grep -E ':(4500|4501|4507)\b'
}

stop_server() {
  local value
  for file in "$server_pgid_file" "$server_pid_file"; do
    [[ -s "$file" ]] || continue
    value="$(sed -n '1p' "$file")"
    [[ "$value" =~ ^[0-9]+$ && "$value" -gt 1 ]] || continue
    if [[ "$file" == "$server_pgid_file" ]]; then
      kill -TERM -- "-$value" 2>/dev/null || true
    else
      kill -TERM "$value" 2>/dev/null || true
    fi
  done
  for unused in $(seq 1 50); do
    pgrep -x t-rex-64 >/dev/null || pgrep -x _t-rex-64 >/dev/null || break
    sleep 0.2
  done
  pkill -KILL -x t-rex-64 2>/dev/null || true
  pkill -KILL -x _t-rex-64 2>/dev/null || true
  pkill -TERM -f '^/usr/bin/python3 -m trex\.scapy_server' 2>/dev/null || true
  rm -f -- "$server_pid_file" "$server_pgid_file"
}

disarm_deadman() {
  systemctl stop "${deadman_unit}.timer" "${deadman_unit}.service" \
    2>/dev/null || true
  systemctl reset-failed "${deadman_unit}.timer" "${deadman_unit}.service" \
    2>/dev/null || true
}

arm_deadman() {
  disarm_deadman
  systemd-run --unit="$deadman_unit" --on-active=1800s \
    /usr/bin/bash "$0" deadman-recover
  systemctl show "${deadman_unit}.timer" \
    -p ActiveState -p SubState -p NextElapseUSecMonotonic
}

recover_host() {
  local bdf current iface pool mountpoint
  stop_server
  for bdf in 0000:03:00.0 0000:03:00.1; do
    if [[ -L "/sys/bus/pci/devices/$bdf/driver" ]]; then
      current="$(basename "$(readlink -f "/sys/bus/pci/devices/$bdf/driver")")"
      [[ "$current" == bnxt_en ]] \
        || printf '%s\n' "$bdf" >"/sys/bus/pci/devices/$bdf/driver/unbind"
    fi
    [[ ! -e "/sys/bus/pci/devices/$bdf/driver_override" ]] \
      || printf '\n' >"/sys/bus/pci/devices/$bdf/driver_override"
  done
  modprobe bnxt_en
  for bdf in 0000:03:00.0 0000:03:00.1; do
    [[ -L "/sys/bus/pci/devices/$bdf/driver" ]] \
      || printf '%s\n' "$bdf" >/sys/bus/pci/drivers/bnxt_en/bind
    for unused in $(seq 1 50); do
      iface="$(resolve_iface "$bdf" || true)"
      [[ -n "$iface" ]] && break
      sleep 0.2
    done
    [[ -n "$iface" ]]
    ip link set dev "$iface" xdp off 2>/dev/null || true
    [[ ! -L "/sys/class/net/$iface/master" ]] || ip link set "$iface" nomaster
    ip address flush dev "$iface"
    ip link set dev "$iface" down
  done
  while IFS= read -r mountpoint; do
    find "$mountpoint" -mindepth 1 -type f -name "*${prefix}*" -delete
  done < <(findmnt -rn -t hugetlbfs -o TARGET)
  if mountpoint -q /mnt/huge; then
    [[ "$(findmnt -rn -T /mnt/huge -o SOURCE,FSTYPE)" == "nodev hugetlbfs" ]]
    [[ -z "$(find /mnt/huge -mindepth 1 -print -quit)" ]]
    umount /mnt/huge
  fi
  [[ ! -e /mnt/huge ]] || rmdir /mnt/huge
  for pool in /sys/kernel/mm/hugepages/hugepages-*; do
    printf '0\n' >"$pool/nr_hugepages"
  done
  modprobe -r uio_pci_generic 2>/dev/null || true
  modprobe -r uio 2>/dev/null || true
  [[ ! -d "/var/run/dpdk/$prefix" ]] \
    || find "/var/run/dpdk/$prefix" -depth -delete
  [[ ! -d "$trex_root" ]] || find "$trex_root" -depth -delete
  rmdir /opt/trex 2>/dev/null || true
}

case "${1:-}" in
  preflight)
    assert_management
    assert_zero_hugepages
    assert_kernel_ports
    assert_no_runtime
    [[ -f "$archive" && -f "$cfg" && -f "$client" ]]
    [[ "$(stat -c %s "$archive")" == 284092535 ]]
    [[ "$(sha256sum "$archive" | cut -d' ' -f1)" == \
      d2ac73627906c4ce01127c1c6954464fab373463966ea9592509446e74972b5f ]]
    [[ ! -e "$trex_root" && ! -e "/var/run/dpdk/$prefix" ]]
    show_hugepages
    ;;
  start)
    startup_failure() {
      status=$?; trap - ERR
      printf 'TRex start failed status=%s\n' "$status" >&2
      [[ ! -f "$run_dir/bind.log" ]] || { printf '%s\n' '$ bind.log'; tail -n 80 "$run_dir/bind.log"; }
      [[ ! -f "$run_dir/server.log" ]] || { printf '%s\n' '$ server.log'; tail -n 120 "$run_dir/server.log"; }
      exit "$status"
    }
    trap startup_failure ERR
    /usr/bin/bash "$0" preflight
    arm_deadman
    install -d -m 0755 /opt/trex
    tar -xzf "$archive" -C /opt/trex
    [[ -x "$trex_root/t-rex-64" ]]
    modprobe uio_pci_generic
    sysctl -w vm.nr_hugepages=1024
    cd "$trex_root"
    ./dpdk_nic_bind.py --bind=uio_pci_generic \
      0000:03:00.0 0000:03:00.1 >"$run_dir/bind.log" 2>&1
    setsid ./t-rex-64 -i --stl --no-key --cfg "$cfg" --software \
      --no-hw-flow-stat --no-flow-control-change --checksum-offload-disable \
      --no-scapy-server --no-watchdog --prefix "$prefix" \
      --mbuf-factor 0.1 -c 1 >"$run_dir/server.log" 2>&1 </dev/null &
    pid=$!
    printf '%s\n' "$pid" >"$server_pid_file"
    for attempt in $(seq 1 300); do
      if kill -0 "$pid" 2>/dev/null \
        && ss -H -lnt | grep -Eq ':(4500|4501)\b'; then
        pgid="$(ps -o pgid= -p "$pid" | tr -d '[:space:]')"
        [[ "$pgid" == "$pid" ]] || exit 70
        printf '%s\n' "$pgid" >"$server_pgid_file"
        printf 'server_ready attempt=%s pid=%s pgid=%s\n' "$attempt" "$pid" "$pgid"
        break
      fi
      sleep 0.2
    done
    [[ -s "$server_pgid_file" ]]
    python3 "$client" --run-id "$run_id" --mode prepare \
      --summary "$run_dir/trex-prepare.json"
    trap - ERR
    ;;
  renew)
    pgrep -x t-rex-64 >/dev/null || pgrep -x _t-rex-64 >/dev/null
    arm_deadman
    ;;
  pressure)
    phase="${2:?CALM or BURST required}"
    [[ "$phase" == CALM || "$phase" == BURST ]]
    arm_deadman
    python3 "$client" --run-id "$run_id" --mode pressure --phase "$phase" \
      --summary "$run_dir/trex-${phase,,}.json"
    ;;
  status)
    assert_management
    ps -eo pid=,pgid=,comm=,args= \
      | grep -E '(t-rex-64|market_trex_client)' | grep -v grep || true
    ss -H -lntup | grep -E ':(4500|4501|4507)\b' || true
    show_hugepages
    ;;
  recover)
    recover_host
    disarm_deadman
    assert_management
    assert_zero_hugepages
    assert_kernel_ports
    assert_no_runtime
    ;;
  deadman-recover)
    recover_host
    ;;
  final-assert)
    assert_management
    assert_zero_hugepages
    assert_kernel_ports
    assert_no_runtime
    [[ ! -d "/var/run/dpdk/$prefix" ]]
    show_hugepages
    ps -eo pid=,pgid=,comm=,args= \
      | grep -E '(t-rex-64|market_trex_client|testpmd|simple_switch)' \
      | grep -v grep || true
    ss -H -lntup | grep -E ':(4500|4501|4507)\b' || true
    ;;
  *)
    printf 'usage: %s {preflight|start|renew|pressure CALM|pressure BURST|status|recover|final-assert}\n' "$0" >&2
    exit 2
    ;;
esac
