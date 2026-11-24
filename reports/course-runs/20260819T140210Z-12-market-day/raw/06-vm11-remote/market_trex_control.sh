#!/usr/bin/env bash
set -Eeuo pipefail

readonly script_dir="$(cd "$(dirname "$0")" && pwd)"
readonly run_dir="${FLLE_MARKET_RUN_DIR:-$script_dir}"
if [[ -n "${FLLE_MARKET_RUN_DIR:-}" ]]; then
  [[ "$run_dir" =~ ^/run/flle-market-day/[0-9]{8}T[0-9]{6}Z-12-market-day$ ]]
  [[ -d "$run_dir" ]]
fi
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

wait_for_stable_iface() {
  local bdf="$1" candidate previous= stable=0
  local -a candidates=()
  for unused in $(seq 1 100); do
    mapfile -t candidates < <(resolve_iface "$bdf" 2>/dev/null || true)
    if (( ${#candidates[@]} == 1 )); then
      candidate="${candidates[0]}"
      if [[ -e "/sys/class/net/$candidate" ]] \
        && [[ "$(basename "$(readlink -f "/sys/class/net/$candidate/device")")" == "$bdf" ]] \
        && ip link show dev "$candidate" >/dev/null 2>&1; then
        if [[ "$candidate" == "$previous" ]]; then
          stable=$((stable + 1))
        else
          previous="$candidate"
          stable=1
        fi
        if (( stable >= 2 )); then
          printf '%s\n' "$candidate"
          return 0
        fi
      else
        previous=
        stable=0
      fi
    else
      previous=
      stable=0
    fi
    sleep 0.2
  done
  return 1
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
  [[ ! -e /mnt/huge && ! -L /mnt/huge ]]
}

assert_management() {
  [[ "$(hostname)" == vm-broadcom-01 ]]
  ip -4 addr show dev ens33 | grep -Fq '10.1.1.11/24'
  ip route show default | grep -Fq 'default via 10.1.1.254 dev ens33'
}

assert_kernel_ports() {
  local spec bdf expected iface driver flags override
  for spec in \
    '0000:03:00.0 00:0a:f7:f8:48:a0' \
    '0000:03:00.1 00:0a:f7:f8:48:a1'; do
    read -r bdf expected <<<"$spec"
    iface="$(resolve_iface "$bdf")"
    driver="$(basename "$(readlink -f "/sys/bus/pci/devices/$bdf/driver")")"
    override="$(<"/sys/bus/pci/devices/$bdf/driver_override")"
    [[ -n "$iface" && "$driver" == bnxt_en ]]
    [[ -z "$override" || "$override" == "(null)" ]]
    [[ "$(<"/sys/class/net/$iface/address")" == "$expected" ]]
    flags="$(<"/sys/class/net/$iface/flags")"
    (( (flags & 0x1) == 0 ))
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

show_final_baseline() {
  local bdf iface path
  printf '%s\n' '===== management: hostname / ens33 / default route ====='
  hostname
  ip -details -4 address show dev ens33
  ip route show default
  for bdf in 0000:03:00.0 0000:03:00.1; do
    printf '===== PCIe function %s: driver / netdev =====\n' "$bdf"
    readlink -f "/sys/bus/pci/devices/$bdf/driver" || true
    find "/sys/bus/pci/devices/$bdf/net" -mindepth 1 -maxdepth 1 \
      -printf '%f\n' 2>&1 || true
    while IFS= read -r iface; do
      [[ -n "$iface" ]] || continue
      ip -details link show dev "$iface" || true
      ip -o address show dev "$iface" || true
      ethtool -i "$iface" || true
    done < <(resolve_iface "$bdf" 2>/dev/null || true)
  done
  printf '%s\n' '===== hugepage pools / mounts / files / holders ====='
  show_hugepages
  for path in "/var/run/dpdk/$prefix" "$trex_root" /mnt/huge; do
    if [[ -e "$path" ]]; then
      find "$path" -maxdepth 2 -printf '%y %s %p\n' 2>&1 || true
    else
      printf 'path=%s state=absent\n' "$path"
    fi
  done
  printf '%s\n' '===== TRex processes / listeners / deadman units ====='
  ps -eo pid=,pgid=,comm=,args= \
    | grep -E '(t-rex-64|market_trex_client|testpmd|simple_switch)' \
    | grep -v grep || true
  ss -H -lntup | grep -E ':(4500|4501|4507)\b' || true
  systemctl show "${deadman_unit}.timer" "${deadman_unit}.service" \
    -p Id -p LoadState -p ActiveState -p SubState 2>&1 || true
}

assert_deadman_inactive() {
  local unit state
  for unit in "${deadman_unit}.timer" "${deadman_unit}.service"; do
    state="$(systemctl show "$unit" -p ActiveState --value 2>/dev/null || true)"
    [[ "$state" != active && "$state" != activating ]]
  done
}

assert_all_deadmen_inactive() {
  local unit state
  while read -r unit; do
    [[ "$unit" =~ ^flle-market-day-[0-9]{8}T[0-9]{6}Z-12-market-day\.(timer|service)$ ]]
    state="$(systemctl show "$unit" -p ActiveState --value 2>/dev/null || true)"
    [[ "$state" != active && "$state" != activating \
      && "$state" != deactivating && "$state" != reloading ]]
  done < <(
    systemctl list-units --all --no-legend --plain 'flle-market-day-*' \
      | awk '{print $1}'
  )
}

final_assert_common() {
  show_final_baseline
  printf '%s\n' '===== recovery safety gates ====='
  assert_management
  assert_zero_hugepages
  assert_kernel_ports
  assert_no_runtime
  [[ ! -e "/var/run/dpdk/$prefix" && ! -L "/var/run/dpdk/$prefix" ]]
  [[ ! -e "$trex_root" && ! -L "$trex_root" ]]
}

owned_client_pid() {
  local pid="$1" scope="$2" arg
  local -a argv=()
  [[ "$pid" =~ ^[0-9]+$ && "$pid" -gt 1 ]]
  [[ -r "/proc/$pid/cmdline" ]]
  mapfile -d '' -t argv 2>/dev/null <"/proc/$pid/cmdline" || return 1
  for arg in "${argv[@]}"; do
    if [[ "$scope" == run && "$arg" == "$client" ]]; then
      return 0
    fi
    if [[ "$scope" == orphan \
      && "$arg" =~ ^/run/flle-market-day/[0-9]{8}T[0-9]{6}Z-12-market-day/market_trex_client\.py$ ]]; then
      return 0
    fi
  done
  return 1
}

collect_owned_client_pids() {
  local scope="$1" proc pid
  for proc in /proc/[0-9]*; do
    pid="${proc##*/}"
    owned_client_pid "$pid" "$scope" || continue
    printf '%s\n' "$pid"
  done
}

stop_clients() {
  local scope="$1" pid
  local -a pids=()
  mapfile -t pids < <(collect_owned_client_pids "$scope")
  for pid in "${pids[@]}"; do
    owned_client_pid "$pid" "$scope" || continue
    printf 'client_signal=TERM pid=%s\n' "$pid"
    kill -TERM "$pid" 2>/dev/null || true
  done
  for unused in $(seq 1 50); do
    mapfile -t pids < <(collect_owned_client_pids "$scope")
    [[ "${#pids[@]}" -ne 0 ]] || break
    sleep 0.2
  done
  mapfile -t pids < <(collect_owned_client_pids "$scope")
  for pid in "${pids[@]}"; do
    owned_client_pid "$pid" "$scope" || continue
    printf 'client_signal=KILL pid=%s\n' "$pid"
    kill -KILL "$pid" 2>/dev/null || true
  done
  for unused in $(seq 1 50); do
    mapfile -t pids < <(collect_owned_client_pids "$scope")
    [[ "${#pids[@]}" -ne 0 ]] || break
    sleep 0.2
  done
  mapfile -t pids < <(collect_owned_client_pids "$scope")
  [[ "${#pids[@]}" -eq 0 ]]
}

owned_trex_pid() {
  local pid="$1" scope="$2" comm arg cfg_value=
  local prefix_ok=0 cfg_ok=0 index
  local -a argv=()
  [[ "$pid" =~ ^[0-9]+$ && "$pid" -gt 1 ]]
  [[ -r "/proc/$pid/comm" && -r "/proc/$pid/cmdline" ]]
  comm="$(cat "/proc/$pid/comm" 2>/dev/null)" || return 1
  [[ "$comm" == t-rex-64 || "$comm" == _t-rex-64 ]]
  mapfile -d '' -t argv 2>/dev/null <"/proc/$pid/cmdline" || return 1
  for ((index=0; index<${#argv[@]}; index++)); do
    arg="${argv[$index]}"
    if [[ "$arg" == --prefix && $((index + 1)) -lt ${#argv[@]} \
      && "${argv[$((index + 1))]}" == "$prefix" ]]; then
      prefix_ok=1
    fi
    if [[ "$arg" == --cfg && $((index + 1)) -lt ${#argv[@]} ]]; then
      cfg_value="${argv[$((index + 1))]}"
      if [[ "$scope" == run && "$cfg_value" == "$cfg" ]]; then
        cfg_ok=1
      elif [[ "$scope" == orphan \
        && "$cfg_value" =~ ^/run/flle-market-day/[0-9]{8}T[0-9]{6}Z-12-market-day/trex-dual\.yaml$ ]]; then
        cfg_ok=1
      fi
    fi
  done
  [[ "$prefix_ok" -eq 1 && "$cfg_ok" -eq 1 ]]
}

collect_owned_trex_pids() {
  local scope="$1" proc pid
  for proc in /proc/[0-9]*; do
    pid="${proc##*/}"
    owned_trex_pid "$pid" "$scope" || continue
    printf '%s\n' "$pid"
  done
}

stop_server() {
  local scope="$1" file value pid
  local -a pids=()
  if [[ "$scope" == run ]]; then
    for file in "$server_pgid_file" "$server_pid_file"; do
      [[ -s "$file" ]] || continue
      value="$(sed -n '1p' "$file")"
      if [[ "$value" =~ ^[0-9]+$ && "$value" -gt 1 ]] \
        && owned_trex_pid "$value" "$scope"; then
        printf 'owned_server_hint=%s pid=%s\n' "$file" "$value"
      else
        printf 'stale_server_hint=%s value=%s action=ignored\n' "$file" "$value"
      fi
    done
  fi
  mapfile -t pids < <(collect_owned_trex_pids "$scope")
  for pid in "${pids[@]}"; do
    owned_trex_pid "$pid" "$scope" || continue
    printf 'server_signal=TERM pid=%s\n' "$pid"
    kill -TERM "$pid" 2>/dev/null || true
  done
  for unused in $(seq 1 50); do
    mapfile -t pids < <(collect_owned_trex_pids "$scope")
    [[ "${#pids[@]}" -ne 0 ]] || break
    sleep 0.2
  done
  mapfile -t pids < <(collect_owned_trex_pids "$scope")
  for pid in "${pids[@]}"; do
    owned_trex_pid "$pid" "$scope" || continue
    printf 'server_signal=KILL pid=%s\n' "$pid"
    kill -KILL "$pid" 2>/dev/null || true
  done
  for unused in $(seq 1 50); do
    mapfile -t pids < <(collect_owned_trex_pids "$scope")
    [[ "${#pids[@]}" -ne 0 ]] || break
    sleep 0.2
  done
  mapfile -t pids < <(collect_owned_trex_pids "$scope")
  [[ "${#pids[@]}" -eq 0 ]]
  if [[ "$scope" == run ]]; then
    rm -f -- "$server_pid_file" "$server_pgid_file"
  fi
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
  local scope="$1" spec bdf expected current iface flags override pool mountpoint
  stop_clients "$scope"
  stop_server "$scope"
  for bdf in 0000:03:00.0 0000:03:00.1; do
    override="$(<"/sys/bus/pci/devices/$bdf/driver_override")"
    [[ -z "$override" || "$override" == "(null)" \
      || "$override" == uio_pci_generic || "$override" == bnxt_en ]]
    if [[ -L "/sys/bus/pci/devices/$bdf/driver" ]]; then
      current="$(basename "$(readlink -f "/sys/bus/pci/devices/$bdf/driver")")"
      [[ "$current" == bnxt_en || "$current" == uio_pci_generic ]]
      if [[ "$current" == bnxt_en ]]; then
        iface="$(resolve_iface "$bdf")"
        [[ -n "$iface" ]]
        flags="$(<"/sys/class/net/$iface/flags")"
        (( (flags & 0x1) == 0 ))
        [[ "$(<"/sys/class/net/$iface/operstate")" == down ]]
        [[ -z "$(ip -o address show dev "$iface")" ]]
        [[ ! -L "/sys/class/net/$iface/master" ]]
        ! ip -details link show dev "$iface" | grep -Eq 'prog/xdp|xdp.*id'
      fi
      [[ "$current" == bnxt_en ]] || \
        printf '%s\n' "$bdf" >"/sys/bus/pci/devices/$bdf/driver/unbind"
    fi
    printf '\n' >"/sys/bus/pci/devices/$bdf/driver_override"
  done
  modprobe bnxt_en
  for bdf in 0000:03:00.0 0000:03:00.1; do
    [[ -L "/sys/bus/pci/devices/$bdf/driver" ]] \
      || printf '%s\n' "$bdf" >/sys/bus/pci/drivers/bnxt_en/bind
  done
  udevadm settle --timeout=30
  for spec in \
    '0000:03:00.0 00:0a:f7:f8:48:a0' \
    '0000:03:00.1 00:0a:f7:f8:48:a1'; do
    read -r bdf expected <<<"$spec"
    iface="$(wait_for_stable_iface "$bdf")"
    [[ "$(<"/sys/class/net/$iface/address")" == "$expected" ]]
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
  [[ ! -L /mnt/huge ]]
  [[ ! -e /mnt/huge ]] || rmdir /mnt/huge
  for pool in /sys/kernel/mm/hugepages/hugepages-*; do
    printf '0\n' >"$pool/nr_hugepages"
  done
  modprobe -r uio_pci_generic 2>/dev/null || true
  modprobe -r uio 2>/dev/null || true
  if [[ -e "/var/run/dpdk/$prefix" || -L "/var/run/dpdk/$prefix" ]]; then
    [[ -d "/var/run/dpdk/$prefix" && ! -L "/var/run/dpdk/$prefix" ]]
    find "/var/run/dpdk/$prefix" -depth -delete
  fi
  if [[ -e "$trex_root" || -L "$trex_root" ]]; then
    [[ -d "$trex_root" && ! -L "$trex_root" ]]
    find "$trex_root" -depth -delete
  fi
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
    [[ ! -e "$trex_root" && ! -L "$trex_root" \
      && ! -e "/var/run/dpdk/$prefix" && ! -L "/var/run/dpdk/$prefix" ]]
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
    recover_host run
    disarm_deadman
    assert_management
    assert_zero_hugepages
    assert_kernel_ports
    assert_no_runtime
    ;;
  orphan-recover)
    [[ "${FLLE_MARKET_ORPHAN_RECOVERY:-}" == CONFIRMED ]]
    recover_host orphan
    assert_management
    assert_zero_hugepages
    assert_kernel_ports
    assert_no_runtime
    assert_all_deadmen_inactive
    ;;
  deadman-recover)
    recover_host run
    ;;
  final-assert)
    final_assert_common
    assert_deadman_inactive
    ;;
  orphan-final-assert)
    [[ "${FLLE_MARKET_ORPHAN_RECOVERY:-}" == CONFIRMED ]]
    final_assert_common
    assert_all_deadmen_inactive
    ;;
  *)
    printf 'usage: %s {preflight|start|renew|pressure CALM|pressure BURST|status|recover|orphan-recover|final-assert|orphan-final-assert}\n' "$0" >&2
    exit 2
    ;;
esac
