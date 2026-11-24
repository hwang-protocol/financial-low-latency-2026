#!/usr/bin/env bash
set -Eeuo pipefail

readonly run_id=20260917T023857Z-07-lanz-stream-ab
readonly run_dir="/run/flle-lanz-lower-${run_id}"
readonly cfg="${run_dir}/trex-dual.yaml"
readonly client_script="${run_dir}/trex_lanz_lower_client.py"
readonly prefix=fllelanzlower53935
readonly server_pgid_file="${run_dir}/server.pgid"
readonly server_pid_file="${run_dir}/server.pid"
readonly deadman_timer="flle-lanz-lower-recovery-${run_id}.timer"
readonly deadman_service="flle-lanz-lower-recovery-${run_id}.service"
readonly deadman_deadline_file="${run_dir}/deadman-deadline-monotonic.txt"

resolve_iface() {
  local bdf="$1"
  find "/sys/bus/pci/devices/${bdf}/net" -mindepth 1 -maxdepth 1 -printf '%f\n'
}

assert_management() {
  [[ "$(hostname)" == vm-broadcom-01 ]]
  [[ "$(basename "$(readlink -f /sys/class/net/ens33/device)")" == 0000:02:01.0 ]]
  ip -4 addr show dev ens33 | grep -Fq '10.1.1.11/24'
  ip route show default | grep -Fq 'default via 10.1.1.254 dev ens33 proto static'
}

show_hugepages() {
  local pool
  grep -E '^Huge|^Hugetlb' /proc/meminfo
  for pool in /sys/kernel/mm/hugepages/hugepages-*; do
    printf '%s nr=%s free=%s resv=%s surp=%s\n' \
      "$(basename "$pool")" \
      "$(<"${pool}/nr_hugepages")" \
      "$(<"${pool}/free_hugepages")" \
      "$(<"${pool}/resv_hugepages")" \
      "$(<"${pool}/surplus_hugepages")"
  done
  findmnt -rn -t hugetlbfs -o TARGET,SOURCE,FSTYPE,OPTIONS || true
}

assert_all_hugepages_zero() {
  local pool
  local mountpoint
  [[ "$(awk '/^Hugetlb:/ {print $2}' /proc/meminfo)" == 0 ]]
  for pool in /sys/kernel/mm/hugepages/hugepages-*; do
    [[ "$(<"${pool}/nr_hugepages")" == 0 ]]
    [[ "$(<"${pool}/free_hugepages")" == 0 ]]
    [[ "$(<"${pool}/resv_hugepages")" == 0 ]]
    [[ "$(<"${pool}/surplus_hugepages")" == 0 ]]
  done
  while IFS= read -r mountpoint; do
    [[ -d "$mountpoint" ]]
    [[ -z "$(find "$mountpoint" -mindepth 1 -maxdepth 1 -print -quit)" ]]
  done < <(findmnt -rn -t hugetlbfs -o TARGET)
}

assert_no_runtime() {
  ! pgrep -x t-rex-64 >/dev/null
  ! pgrep -x _t-rex-64 >/dev/null
  ! pgrep -x testpmd >/dev/null
  ! pgrep -f '^/usr/bin/python3 -m trex\.scapy_server\.scapy_zmq_server -p 4507$' >/dev/null
  ! ss -H -lntup | grep -E ':(4500|4501|4507)\b'
}

assert_empty_native_ports() {
  local spec bdf expected_mac iface driver
  for spec in '0000:03:00.0 00:0a:f7:f8:48:a0' '0000:03:00.1 00:0a:f7:f8:48:a1'; do
    read -r bdf expected_mac <<< "$spec"
    iface="$(resolve_iface "$bdf")"
    [[ -n "$iface" ]]
    [[ "$(cat "/sys/class/net/${iface}/address")" == "$expected_mac" ]]
    driver="$(basename "$(readlink -f "/sys/bus/pci/devices/${bdf}/driver")")"
    [[ "$driver" == bnxt_en ]]
    [[ "$(cat "/sys/class/net/${iface}/operstate")" == down ]]
    [[ -z "$(ip -o addr show dev "$iface")" ]]
    [[ ! -L "/sys/class/net/${iface}/master" ]]
    ! ip -details link show dev "$iface" | grep -Eq 'prog/xdp|xdp.*id'
    printf 'bdf=%s iface=%s mac=%s driver=%s state=down addr=none master=none xdp=none\n' \
      "$bdf" "$iface" "$expected_mac" "$driver"
  done
}

stop_server() {
  local pgid server_pid
  if [[ -f "$server_pgid_file" ]]; then
    pgid="$(sed -n '1p' "$server_pgid_file")"
    if [[ "$pgid" =~ ^[0-9]+$ ]] && (( pgid > 1 )) && kill -0 -- "-${pgid}" 2>/dev/null; then
      kill -TERM -- "-${pgid}" 2>/dev/null || true
      for _ in $(seq 1 50); do
        kill -0 -- "-${pgid}" 2>/dev/null || break
        sleep 0.2
      done
      if kill -0 -- "-${pgid}" 2>/dev/null; then
        kill -KILL -- "-${pgid}" 2>/dev/null || true
      fi
    fi
  fi
  if [[ -f "$server_pid_file" ]]; then
    server_pid="$(sed -n '1p' "$server_pid_file")"
    if [[ "$server_pid" =~ ^[0-9]+$ ]] && (( server_pid > 1 )) && kill -0 "$server_pid" 2>/dev/null; then
      kill -TERM "$server_pid" 2>/dev/null || true
      for _ in $(seq 1 50); do
        kill -0 "$server_pid" 2>/dev/null || break
        sleep 0.2
      done
      kill -KILL "$server_pid" 2>/dev/null || true
    fi
  fi
  for scapy_pid in $(pgrep -f '^/usr/bin/python3 -m trex\.scapy_server\.scapy_zmq_server -p 4507$' 2>/dev/null || true); do
    kill -TERM "$scapy_pid" 2>/dev/null || true
  done
  rm -f -- "$server_pgid_file" "$server_pid_file"
}

arm_deadman() {
  local duration_seconds="$1"
  local armed_at deadline
  [[ "$duration_seconds" =~ ^[0-9]+$ ]]
  (( duration_seconds >= 900 ))
  ! systemctl is-active --quiet "$deadman_timer"
  armed_at="$(cut -d' ' -f1 /proc/uptime)"
  deadline="$(awk -v now="$armed_at" -v duration="$duration_seconds" 'BEGIN {printf "%.2f", now + duration}')"
  printf '%s\n' "$deadline" > "$deadman_deadline_file"
  if ! systemd-run --unit="${deadman_timer%.timer}" --on-active="${duration_seconds}s" \
    /usr/bin/bash "$0" recover; then
    rm -f -- "$deadman_deadline_file"
    return 1
  fi
  systemctl is-active --quiet "$deadman_timer"
  printf 'deadman_armed_at_monotonic=%s\n' "$armed_at"
  printf 'deadman_deadline_monotonic=%s\n' "$deadline"
  printf 'deadman_duration_seconds=%s\n' "$duration_seconds"
  systemctl show "$deadman_timer" -p ActiveState -p SubState -p NextElapseUSecMonotonic
  printf '%s\n' 'LANZ_LOWER_DEADMAN_ARM=PASS'
}

assert_deadman_budget() {
  local required_seconds="$1"
  local now deadline remaining
  [[ "$required_seconds" =~ ^[0-9]+$ ]]
  (( required_seconds > 120 ))
  systemctl is-active --quiet "$deadman_timer"
  [[ -s "$deadman_deadline_file" ]]
  now="$(cut -d' ' -f1 /proc/uptime)"
  deadline="$(sed -n '1p' "$deadman_deadline_file")"
  [[ "$deadline" =~ ^[0-9]+([.][0-9]+)?$ ]]
  remaining="$(awk -v deadline="$deadline" -v now="$now" 'BEGIN {printf "%.2f", deadline - now}')"
  awk -v remaining="$remaining" -v required="$required_seconds" \
    'BEGIN {exit !(remaining > required)}'
  printf 'deadman_checked_at_monotonic=%s\n' "$now"
  printf 'deadman_deadline_monotonic=%s\n' "$deadline"
  printf 'deadman_remaining_seconds=%s\n' "$remaining"
  printf 'deadman_required_seconds=%s\n' "$required_seconds"
  systemctl show "$deadman_timer" -p ActiveState -p SubState -p NextElapseUSecMonotonic
  printf '%s\n' 'LANZ_LOWER_DEADMAN_BUDGET=PASS'
}

disarm_deadman() {
  systemctl stop "$deadman_timer" "$deadman_service" 2>/dev/null || true
  systemctl reset-failed "$deadman_timer" "$deadman_service" 2>/dev/null || true
  ! systemctl is-active --quiet "$deadman_timer"
  rm -f -- "$deadman_deadline_file"
  printf '%s\n' 'LANZ_LOWER_DEADMAN_DISARM=PASS'
}

recover_host() {
  local bdf current_driver iface pool mountpoint
  stop_server
  for bdf in 0000:03:00.0 0000:03:00.1; do
    if [[ -L "/sys/bus/pci/devices/${bdf}/driver" ]]; then
      current_driver="$(basename "$(readlink -f "/sys/bus/pci/devices/${bdf}/driver")")"
      if [[ "$current_driver" != bnxt_en ]]; then
        printf '%s\n' "$bdf" > "/sys/bus/pci/devices/${bdf}/driver/unbind"
      fi
    fi
    [[ ! -e "/sys/bus/pci/devices/${bdf}/driver_override" ]] || printf '\n' > "/sys/bus/pci/devices/${bdf}/driver_override"
  done
  modprobe bnxt_en
  for bdf in 0000:03:00.0 0000:03:00.1; do
    if [[ ! -L "/sys/bus/pci/devices/${bdf}/driver" ]]; then
      printf '%s\n' "$bdf" > /sys/bus/pci/drivers/bnxt_en/bind
    fi
    [[ "$(basename "$(readlink -f "/sys/bus/pci/devices/${bdf}/driver")")" == bnxt_en ]]
    # Driver bind exposes eth0 before udev applies the stable PCI-based name.
    # Finish naming before selecting the interface for flush/down operations.
    udevadm settle --timeout=20
    iface=''
    for _ in $(seq 1 50); do
      iface="$(resolve_iface "$bdf" || true)"
      [[ -n "$iface" ]] && break
      sleep 0.2
    done
    [[ -n "$iface" ]]
    if ip -details link show dev "$iface" | grep -Eq 'prog/xdp|xdp.*id'; then
      ip link set dev "$iface" xdp off
    fi
    [[ ! -L "/sys/class/net/${iface}/master" ]] || ip link set dev "$iface" nomaster
    ip addr flush dev "$iface"
    ip link set dev "$iface" down
  done
  while IFS= read -r mountpoint; do
    find "$mountpoint" -mindepth 1 -maxdepth 1 -type f -name "*${prefix}*" -delete
  done < <(findmnt -rn -t hugetlbfs -o TARGET)
  for pool in /sys/kernel/mm/hugepages/hugepages-*; do
    printf '0\n' > "${pool}/nr_hugepages"
  done
  modprobe -r uio_pci_generic 2>/dev/null || true
  modprobe -r uio 2>/dev/null || true
  [[ ! -d "/var/run/dpdk/${prefix}" ]] || find "/var/run/dpdk/${prefix}" -depth -delete
}

case "${1:-}" in
  preflight)
    assert_management
    assert_all_hugepages_zero
    assert_empty_native_ports
    assert_no_runtime
    [[ -f "$cfg" ]]
    [[ -f "$client_script" ]]
    [[ -f /opt/flle/prewarm/trex/v3.08.tar.gz ]]
    [[ "$(stat -c '%s' /opt/flle/prewarm/trex/v3.08.tar.gz)" == 284092535 ]]
    [[ "$(sha256sum /opt/flle/prewarm/trex/v3.08.tar.gz | cut -d' ' -f1)" == d2ac73627906c4ce01127c1c6954464fab373463966ea9592509446e74972b5f ]]
    [[ "$(sha256sum /opt/trex/v3.08/so/x86_64/libbnxt-64.so | cut -d' ' -f1)" == 44d8eaed23440f9db4ae5765b308cf0a09d4a948cfd44c3fd6a206a023ec00ba ]]
    show_hugepages
    printf '%s\n' 'LANZ_TREX_PREFLIGHT=PASS'
    ;;
  start)
    assert_management
    assert_all_hugepages_zero
    assert_empty_native_ports
    assert_no_runtime
    modprobe uio_pci_generic
    sysctl -w vm.nr_hugepages=1024
    [[ "$(sysctl -n vm.nr_hugepages)" == 1024 ]]
    cd /opt/trex/v3.08
    ./dpdk_nic_bind.py --bind=uio_pci_generic 0000:03:00.0 0000:03:00.1 > "${run_dir}/bind.log" 2>&1
    for bdf in 0000:03:00.0 0000:03:00.1; do
      [[ "$(basename "$(readlink -f "/sys/bus/pci/devices/${bdf}/driver")")" == uio_pci_generic ]]
    done
    setsid ./t-rex-64 -i --stl --no-key \
      --cfg "$cfg" --software --no-hw-flow-stat \
      --no-flow-control-change --checksum-offload-disable \
      --no-scapy-server --no-watchdog --prefix "$prefix" \
      --mbuf-factor 0.1 -c 1 > "${run_dir}/server.log" 2>&1 < /dev/null &
    server_pid=$!
    printf '%s\n' "$server_pid" > "$server_pid_file"
    ready=0
    for attempt in $(seq 1 300); do
      if kill -0 "$server_pid" 2>/dev/null \
        && ss -H -lnt | grep -Eq '(^|[[:space:]])[^[:space:]]*:4500[[:space:]]' \
        && ss -H -lnt | grep -Eq '(^|[[:space:]])[^[:space:]]*:4501[[:space:]]'; then
        actual_pgid="$(ps -o pgid= -p "$server_pid" | tr -d '[:space:]')"
        if [[ "$actual_pgid" =~ ^[0-9]+$ ]] && [[ "$actual_pgid" == "$server_pid" ]] \
          && kill -0 -- "-${actual_pgid}" 2>/dev/null; then
          printf '%s\n' "$actual_pgid" > "$server_pgid_file"
          printf 'server_ready_attempt=%s pid=%s pgid=%s\n' \
            "$attempt" "$server_pid" "$actual_pgid" | tee "${run_dir}/server-ready.txt"
          ready=1
          break
        fi
      fi
      sleep 0.2
    done
    [[ "$ready" == 1 ]]
    printf '%s\n' 'LANZ_TREX_SERVER_START=PASS'
    ;;
  status)
    assert_management
    ps -eo pid=,pgid=,comm=,args= | grep -E '(t-rex-64|trex_lanz_client)' | grep -v grep || true
    ss -H -lntup | grep -E ':(4500|4501|4507)\b' || true
    show_hugepages
    ;;
  stop)
    stop_server
    printf '%s\n' 'LANZ_TREX_SERVER_STOP=PASS'
    ;;
  arm-deadman)
    arm_deadman "${2:?deadman duration seconds required}"
    ;;
  deadman-budget)
    assert_deadman_budget "${2:?required remaining seconds required}"
    ;;
  disarm-deadman)
    disarm_deadman
    ;;
  recover)
    recover_host
    assert_management
    assert_all_hugepages_zero
    assert_empty_native_ports
    assert_no_runtime
    printf '%s\n' 'LANZ_TREX_RECOVERY=PASS'
    ;;
  final-assert)
    assert_management
    assert_all_hugepages_zero
    assert_empty_native_ports
    assert_no_runtime
    [[ ! -d "/var/run/dpdk/${prefix}" ]]
    ! systemctl is-active --quiet "$deadman_timer"
    show_hugepages
    printf '%s\n' 'LANZ_TREX_FINAL_ASSERT=PASS'
    ;;
  *)
    printf 'usage: %s {preflight|start|status|stop|recover|final-assert|arm-deadman SECONDS|deadman-budget SECONDS|disarm-deadman}\n' "$0" >&2
    exit 2
    ;;
esac
