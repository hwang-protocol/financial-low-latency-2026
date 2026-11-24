#!/usr/bin/env bash
# Remote ownership guard for the real DPDK/F-Stack order client.
# Run only on vm-2522-02 over the 10.1.1.x management network.
set -Eeuo pipefail

BDF=0000:03:00.0
IFACE=ens64np1
ADDR=20.1.1.2/24
GROUP=7
EXPECTED_HOST=vm-2522-02
DEADMAN="${FLLE_DPDK_DEADMAN:-180}"
ROOT_PID=$BASHPID
USER_REF_SLOT_RAW="${FLLE_DPDK_USER_REF_SLOT-}"
USER_REF_BASE_RAW="${FLLE_DPDK_USER_REF_BASE-}"
USER_REF_SPAN_RAW="${FLLE_DPDK_USER_REF_SPAN-}"
UINT32_LIMIT=4294967296
HUGETLBFS=/dev/hugepages
REMOTE_LOCK=/run/lock/flle-x2522-0000_03_00_0.lock

recover_only() {
  local runtime_root="${1:?recover runtime root is required}"
  local session_dir="${2:?recover session directory is required}"
  local stop_file="${3:?recover stop file is required}"
  local gate_pid_file="${4:?recover gate pidfile is required}"
  local expected_token="${5:?recover lease token is required}"
  local binary="$runtime_root/bin/flle-trader-dpdk"
  local devbind="$runtime_root/bin/dpdk-devbind.py"
  local token_file="$session_dir/lease.token"
  local consumed_token_file="$session_dir/lease.token.consumed"
  local state_file="$session_dir/ownership.state"
  local ownership_baseline="$session_dir/ownership.baseline"
  local gate_identity="$session_dir/gate.identity"
  local trader_identity="$session_dir/trader.identity"
  local baseline_file="$session_dir/hugetlbfs.mount.baseline"
  local entries_baseline="$session_dir/hugetlbfs-files.baseline"
  local entries_final="$session_dir/hugetlbfs-files.recovery-final"
  local lease_receipt="$session_dir/lease-start.receipt"
  local prefix runtime_dir driver current address pages carrier ping_ok holders
  local pid expected_start expected_boot command start boot line extra
  local pid_field start_field boot_field token_field expected relative
  local lease_unit mount_baseline mount_final directory_baseline lease_state
  local timer_load_state timer_active_state
  local baseline_driver baseline_netdev baseline_address baseline_pages

  test "$(readlink -f "$0")" = \
    "$runtime_root/bin/x2522-dpdk-trader-remote.sh"
  for relative in bin/x2522-dpdk-trader-remote.sh bin/flle-trader-dpdk \
    bin/dpdk-devbind.py; do
    expected="$(awk -v path="$relative" '$2==path {print $1}' \
      "$runtime_root/MANIFEST.sha256")"
    test -n "$expected"
    test "$(sha256sum "$runtime_root/$relative" | awk '{print $1}')" = "$expected"
  done
  if ! test -s "$token_file" || [[ "$(<"$token_file")" != "$expected_token" ]]; then
    echo "DPDK_LEASE_RECOVERY stale_token=1 action=NONE"
    return 0
  fi
  test -s "$state_file"
  lease_state="$(sed -n 's/^state=//p' "$state_file")"
  case "$lease_state" in ARMED|MUTATING|OWNED) ;; *) return 1;; esac
  test -s "$ownership_baseline"
  baseline_driver="$(sed -n 's/^driver=//p' "$ownership_baseline")"
  baseline_netdev="$(sed -n 's/^netdev=//p' "$ownership_baseline")"
  baseline_address="$(sed -n 's/^address=//p' "$ownership_baseline")"
  baseline_pages="$(sed -n 's/^hugepages=//p' "$ownership_baseline")"
  test "$baseline_driver" = sfc
  test "$baseline_netdev" = "$IFACE"
  test "$baseline_address" = "$ADDR"
  test "$baseline_pages" = 0
  touch "$stop_file"

  validate_identity() {
    local identity="$1" expected_command_fragment="$2"
    test -s "$identity" || return 1
    IFS= read -r line <"$identity" || return 1
    read -r pid_field start_field boot_field token_field extra <<<"$line" \
      || return 1
    test -z "${extra:-}" || return 1
    case "$pid_field" in pid=*) pid="${pid_field#pid=}";; *) return 1;; esac
    case "$start_field" in start_ticks=*) expected_start="${start_field#start_ticks=}";; *) return 1;; esac
    case "$boot_field" in boot_id=*) expected_boot="${boot_field#boot_id=}";; *) return 1;; esac
    test "$token_field" = "lease_token=$expected_token" || return 1
    case "$pid" in ''|*[!0-9]*) return 1;; esac
    test -r "/proc/$pid/cmdline" || return 1
    start="$(awk '{print $22}' "/proc/$pid/stat")" || return 1
    boot="$(cat /proc/sys/kernel/random/boot_id)" || return 1
    command="$(tr '\0' ' ' <"/proc/$pid/cmdline")" || return 1
    test "$start" = "$expected_start" || return 1
    test "$boot" = "$expected_boot" || return 1
    case "$command" in
      *"$expected_command_fragment"*) return 0;;
      *) return 1;;
    esac
  }

  exec 9>"$REMOTE_LOCK"
  # The healthy gate owns this lock from preflight through exact restore.  A
  # recovery actor requests STOP and waits; it never races the gate as a second
  # device writer.  Signals are an escalation only after the healthy restore
  # budget has elapsed and after the full process identity is revalidated.
  if ! flock -w 180 9; then
    validate_identity "$gate_identity" \
      "$runtime_root/bin/x2522-dpdk-trader-remote.sh $runtime_root/etc/f-stack-x2522.ini $binary $session_dir $stop_file" || {
      echo "DPDK gate lock timed out but its exact identity is unavailable" >&2
      return 1
    }
    kill -TERM "$pid" 2>/dev/null || true
    for _ in $(seq 1 120); do
      kill -0 "$pid" 2>/dev/null || break
      sleep 0.5
    done
    if kill -0 "$pid" 2>/dev/null; then
      validate_identity "$gate_identity" \
        "$runtime_root/bin/x2522-dpdk-trader-remote.sh $runtime_root/etc/f-stack-x2522.ini $binary $session_dir $stop_file" || {
        echo "refusing to kill a changed DPDK gate identity" >&2
        return 1
      }
      kill -KILL "$pid"
    fi
    flock -w 120 9
  fi
  if ! test -s "$token_file" || [[ "$(<"$token_file")" != "$expected_token" ]]; then
    echo "DPDK_LEASE_RECOVERY stale_after_lock=1 action=NONE"
    return 0
  fi
  lease_state="$(sed -n 's/^state=//p' "$state_file")"
  case "$lease_state" in ARMED|MUTATING|OWNED) ;; *) return 1;; esac
  if ! test -e "$trader_identity"; then
    local -a orphan_candidates=()
    for process in /proc/[0-9]*; do
      [[ "$(readlink -f "$process/exe" 2>/dev/null || true)" = "$binary" ]] || continue
      command="$(tr '\0' ' ' <"$process/cmdline")"
      case "$command" in
        *"--conf $session_dir/f-stack.effective.ini"*)
          orphan_candidates+=("${process##*/}");;
      esac
    done
    test "${#orphan_candidates[@]}" -le 1
    if [[ "${#orphan_candidates[@]}" -eq 1 ]]; then
      pid="${orphan_candidates[0]}"
      start="$(awk '{print $22}' "/proc/$pid/stat")"
      boot="$(cat /proc/sys/kernel/random/boot_id)"
      printf 'pid=%s start_ticks=%s boot_id=%s lease_token=%s\n' \
        "$pid" "$start" "$boot" "$expected_token" \
        >"$trader_identity.tmp.$BASHPID"
      mv -- "$trader_identity.tmp.$BASHPID" "$trader_identity"
    fi
  fi
  if validate_identity "$trader_identity" \
      "$binary --conf $session_dir/f-stack.effective.ini"; then
    kill -INT "$pid" 2>/dev/null || true
    for _ in $(seq 1 80); do
      kill -0 "$pid" 2>/dev/null || break
      sleep 0.25
    done
    if kill -0 "$pid" 2>/dev/null; then
      validate_identity "$trader_identity" \
        "$binary --conf $session_dir/f-stack.effective.ini" || {
        echo "refusing to kill a changed DPDK trader identity" >&2
        return 1
      }
      kill -KILL "$pid"
      for _ in $(seq 1 40); do
        kill -0 "$pid" 2>/dev/null || break
        sleep 0.1
      done
    fi
    kill -0 "$pid" 2>/dev/null && return 1
  fi

  prefix="flle06_$(printf '%s' "$session_dir" | sha256sum | cut -c1-16)"
  runtime_dir="/var/run/dpdk/$prefix"
  test -s "$lease_receipt"
  lease_unit="$(sed -n 's/^lease_unit=//p' "$lease_receipt")"
  [[ "$lease_unit" =~ ^flle-x2522-lease-[0-9a-f]{20}$ ]]
  test "$(grep -Fxc "lease_token=$expected_token" "$lease_receipt")" -eq 1
  systemctl stop "$lease_unit.timer" >/dev/null 2>&1 || true
  timer_load_state="$(systemctl show -p LoadState --value \
    "$lease_unit.timer" 2>/dev/null || true)"
  timer_active_state="$(systemctl show -p ActiveState --value \
    "$lease_unit.timer" 2>/dev/null || true)"
  if [[ "$timer_load_state" != not-found ]]; then
    test "$timer_active_state" = inactive
  fi
  test -s "$baseline_file"
  mount_baseline="$(<"$baseline_file")"
  test -s "$entries_baseline"
  directory_baseline="$(sed -n '1p' "$entries_baseline")"
  if [[ "$lease_state" != ARMED ]]; then
    driver="$(basename "$(readlink "/sys/bus/pci/devices/$BDF/driver")" 2>/dev/null || true)"
    if [[ "$driver" != "$baseline_driver" ]]; then
      "$devbind" --bind="$baseline_driver" "$BDF"
      udevadm settle
    fi
    current="$(find "/sys/bus/pci/devices/$BDF/net" -mindepth 1 -maxdepth 1 \
      -printf '%f\n' 2>/dev/null | head -n1)"
    if [[ -n "$current" && "$current" != "$baseline_netdev" ]]; then
      ip link set "$current" down
      ip link set "$current" name "$baseline_netdev"
    fi
    ip link set "$baseline_netdev" up
    ip addr replace "$baseline_address" dev "$baseline_netdev"
    find "$HUGETLBFS" -maxdepth 1 -type f \
      \( -name "${prefix}map_*" -o -name "container-${prefix}map_*" \) \
      -delete 2>/dev/null || true
    test ! -d "$runtime_dir" || find "$runtime_dir" -depth -delete
    for _ in $(seq 1 30); do
      sysctl -w "vm.nr_hugepages=$baseline_pages" >/dev/null
      [[ "$(cat /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages)" \
        = "$baseline_pages" ]] && break
      sleep 1
    done
    if [[ "$mount_baseline" = ABSENT ]] && mountpoint -q "$HUGETLBFS"; then
      umount "$HUGETLBFS"
    fi
    if [[ "$directory_baseline" = directory=absent && -d "$HUGETLBFS" ]]; then
      rmdir "$HUGETLBFS"
    fi
  fi

  for _ in $(seq 1 30); do
    [[ "$(cat "/sys/class/net/$IFACE/carrier" 2>/dev/null || true)" = 1 ]] && break
    sleep 1
  done
  driver="$(basename "$(readlink "/sys/bus/pci/devices/$BDF/driver")")"
  mapfile -t recovered_ipv4 < <(ip -4 -o addr show dev "$IFACE" scope global)
  test "${#recovered_ipv4[@]}" -eq 1
  address="${recovered_ipv4[0]}"
  pages="$(cat /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages)"
  carrier="$(cat "/sys/class/net/$IFACE/carrier")"
  holders="$(fuser "/dev/vfio/$GROUP" 2>/dev/null | xargs || true)"
  ping_ok=0
  ping_output="$(LC_ALL=C ping -q -I "$IFACE" -c 3 -W 1 20.1.1.1 2>/dev/null || true)"
  grep -Fq '3 packets transmitted, 3 received' <<<"$ping_output" && ping_ok=1
  test "$driver" = "$baseline_driver"
  grep -Fq " $baseline_address " <<<"$address"
  test "$pages" = "$baseline_pages"
  test "$carrier" = 1
  test "$ping_ok" = 1
  test -z "$holders"
  test ! -e "$runtime_dir"
  test "$(find "$HUGETLBFS" -maxdepth 1 -type f \
    \( -name "${prefix}map_*" -o -name "container-${prefix}map_*" \) \
    -print -quit 2>/dev/null || true)" = ""
  mount_final="$(findmnt -rn --mountpoint "$HUGETLBFS" \
    -o FSTYPE,TARGET,SOURCE,OPTIONS 2>/dev/null || true)"
  test "${mount_final:-ABSENT}" = "$mount_baseline"
  if [[ -d "$HUGETLBFS" ]]; then
    {
      echo 'directory=present'
      find "$HUGETLBFS" -mindepth 1 -maxdepth 1 \
        -printf '%y %f\n' | LC_ALL=C sort
    } >"$entries_final"
  else
    echo 'directory=absent' >"$entries_final"
  fi
  cmp -s "$entries_baseline" "$entries_final"
  test "$(<"$token_file")" = "$expected_token"
  mv -- "$token_file" "$consumed_token_file"
  printf 'state=CONSUMED\nlease_token=%s\nactor=independent_recovery\n' \
    "$expected_token" >"$state_file.tmp.$BASHPID"
  mv -- "$state_file.tmp.$BASHPID" "$state_file"
  test ! -e "$token_file"
  test "$(<"$consumed_token_file")" = "$expected_token"
  {
    echo "lease_token=$expected_token"
    echo "recovery=PASS"
    echo "driver=$driver"
    echo "address=$address"
    echo "hugepages=$pages carrier=$carrier ping_ok=$ping_ok vfio_holders=0"
    echo 'ownership_state=CONSUMED'
    echo "timer_active=${timer_active_state:-not-found}"
  } >"$session_dir/lease-recovery.receipt.tmp.$BASHPID"
  mv -- "$session_dir/lease-recovery.receipt.tmp.$BASHPID" \
    "$session_dir/lease-recovery.receipt"
  echo "DPDK_LEASE_RECOVERY token=$expected_token restore=PASS"
}

if [[ "${1:-}" == --recover-only ]]; then
  shift
  recover_only "$@"
  exit
fi

CONFIG="${1:?usage: $0 CONFIG BINARY SESSION_DIR STOP_FILE}"
BINARY="${2:?usage: $0 CONFIG BINARY SESSION_DIR STOP_FILE}"
SESSION_DIR="${3:?usage: $0 CONFIG BINARY SESSION_DIR STOP_FILE}"
STOP_FILE="${4:?usage: $0 CONFIG BINARY SESSION_DIR STOP_FILE}"
RUNTIME_ROOT="$(cd -- "$(dirname -- "$BINARY")/.." && pwd)"
DPDK_DEVBIND="$RUNTIME_ROOT/bin/dpdk-devbind.py"
GATE_PID_FILE="${FLLE_DPDK_GATE_PID_FILE:?FLLE_DPDK_GATE_PID_FILE is required}"
LEASE_TOKEN="${FLLE_DPDK_LEASE_TOKEN:?FLLE_DPDK_LEASE_TOKEN is required}"
[[ "$DEADMAN" =~ ^[0-9]+$ ]]
(( DEADMAN >= 30 && DEADMAN <= 3600 ))
export LD_LIBRARY_PATH="$RUNTIME_ROOT/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
mkdir -p "$SESSION_DIR"
test "$(readlink -f "$0")" = "$RUNTIME_ROOT/bin/x2522-dpdk-trader-remote.sh"
test "$(readlink -f "$CONFIG")" = "$RUNTIME_ROOT/etc/f-stack-x2522.ini"
test "$(readlink -f "$BINARY")" = "$RUNTIME_ROOT/bin/flle-trader-dpdk"
for relative in bin/x2522-dpdk-trader-remote.sh bin/flle-trader-dpdk \
  bin/dpdk-devbind.py etc/f-stack-x2522.ini; do
  expected="$(awk -v path="$relative" '$2==path {print $1}' \
    "$RUNTIME_ROOT/MANIFEST.sha256")"
  test -n "$expected"
  test "$(sha256sum "$RUNTIME_ROOT/$relative" | awk '{print $1}')" = "$expected"
done
gate_cpu="$(awk '/^Cpus_allowed_list:/ {print $2}' "/proc/$ROOT_PID/status")"
test "$gate_cpu" = 0
[[ "$LEASE_TOKEN" =~ ^[A-Za-z0-9._-]+$ ]]
exec 9>"$REMOTE_LOCK"
flock -n 9 || {
  echo "another X2522 ownership wrapper or recovery holds $REMOTE_LOCK" >&2
  exit 75
}
gate_start_ticks="$(awk '{print $22}' "/proc/$ROOT_PID/stat")"
gate_boot_id="$(cat /proc/sys/kernel/random/boot_id)"
test ! -e "$STOP_FILE"
DPDK_FILE_PREFIX="flle06_$(printf '%s' "$SESSION_DIR" | sha256sum | cut -c1-16)"
[[ "$DPDK_FILE_PREFIX" =~ ^[a-zA-Z0-9_]+$ ]]
DPDK_RUNTIME_DIR="/var/run/dpdk/$DPDK_FILE_PREFIX"
LEASE_UNIT="flle-x2522-lease-$(printf '%s' "$SESSION_DIR:$LEASE_TOKEN" | sha256sum | cut -c1-20)"
EFFECTIVE_CONFIG="$SESSION_DIR/f-stack.effective.ini"
HUGETLBFS_FILES_BASELINE="$SESSION_DIR/hugetlbfs-files.baseline"
HUGETLBFS_FILES_FINAL="$SESSION_DIR/hugetlbfs-files.final"
OWNERSHIP_BASELINE="$SESSION_DIR/ownership.baseline"
OWNERSHIP_STATE="$SESSION_DIR/ownership.state"

list_owned_hugefiles() {
  find "$HUGETLBFS" -maxdepth 1 -type f \
    \( -name "${DPDK_FILE_PREFIX}map_*" \
       -o -name "container-${DPDK_FILE_PREFIX}map_*" \) -print \
    2>/dev/null
}

remove_owned_hugefiles() {
  find "$HUGETLBFS" -maxdepth 1 -type f \
    \( -name "${DPDK_FILE_PREFIX}map_*" \
       -o -name "container-${DPDK_FILE_PREFIX}map_*" \) -delete \
    2>/dev/null
}
exec > >(tee "$SESSION_DIR/session.log") 2>&1
rm -f -- "$SESSION_DIR/trader-exit.receipt" \
  "$SESSION_DIR/gate-exit.receipt" "$SESSION_DIR/lease.token.consumed" \
  "$SESSION_DIR/ownership.state"

trader_pid=""
trader_exit_status="not_started"
trader_termination="not_started"
trader_cleanup_mode="not_observed"
trader_shutdown_rc="not_observed"
trader_peer_eof="not_observed"
hugetlbfs_mounted_by_wrapper=0
hugetlbfs_dir_created_by_wrapper=0
lease_armed=0
lease_published=0
hardware_mutated=0
HUGETLBFS_BASELINE="$(findmnt -rn --mountpoint "$HUGETLBFS" \
  -o FSTYPE,TARGET,SOURCE,OPTIONS 2>/dev/null || true)"
printf '%s\n' "${HUGETLBFS_BASELINE:-ABSENT}" \
  >"$SESSION_DIR/hugetlbfs.mount.baseline"
if mountpoint -q "$HUGETLBFS" && [[ "$HUGETLBFS_BASELINE" != hugetlbfs\ * ]]; then
  echo "$HUGETLBFS is an unexpected non-hugetlbfs mount" >&2
  exit 1
fi

snapshot_hugetlbfs_entries() {
  local output="${1:?snapshot output is required}"
  if [[ -d "$HUGETLBFS" ]]; then
    {
      echo 'directory=present'
      find "$HUGETLBFS" -mindepth 1 -maxdepth 1 \
        -printf '%y %f\n' | LC_ALL=C sort
    } >"$output"
  else
    echo 'directory=absent' >"$output"
  fi
}

snapshot_hugetlbfs_entries "$HUGETLBFS_FILES_BASELINE"
test ! -e "$DPDK_RUNTIME_DIR"
test "$(list_owned_hugefiles | head -n 1)" = ""
test "$(grep -Ec '^#?file_prefix=' "$CONFIG")" -eq 1
sed -E "s/^#?file_prefix=.*/file_prefix=$DPDK_FILE_PREFIX/" \
  "$CONFIG" >"$EFFECTIVE_CONFIG"
grep -Fxq "file_prefix=$DPDK_FILE_PREFIX" "$EFFECTIVE_CONFIG"

record_trader_exit() {
  local tmp="$SESSION_DIR/trader-exit.receipt.tmp.$BASHPID"
  {
    echo "trader_exit_status=$trader_exit_status"
    echo "trader_termination=$trader_termination"
    echo "cleanup_mode=$trader_cleanup_mode"
    echo "shutdown_rc=$trader_shutdown_rc"
    echo "peer_eof=$trader_peer_eof"
  } >"$tmp"
  mv -- "$tmp" "$SESSION_DIR/trader-exit.receipt"
}

wait_for_trader_exit() {
  local request_stop="${1:?request-stop flag is required}" rc escalated=0
  [[ -n "$trader_pid" ]] || return 0
  if [[ "$request_stop" = 1 ]]; then
    trader_termination=SIGINT
    kill -INT "$trader_pid" 2>/dev/null || true
  else
    trader_termination=unexpected
  fi
  for _ in $(seq 1 80); do
    kill -0 "$trader_pid" 2>/dev/null || break
    sleep 0.25
  done
  if kill -0 "$trader_pid" 2>/dev/null; then
    escalated=1
    trader_termination=SIGTERM_TIMEOUT
    kill -TERM "$trader_pid" 2>/dev/null || true
    for _ in $(seq 1 20); do
      kill -0 "$trader_pid" 2>/dev/null || break
      sleep 0.25
    done
  fi
  if kill -0 "$trader_pid" 2>/dev/null; then
    escalated=1
    trader_termination=SIGKILL_TIMEOUT
    kill -KILL "$trader_pid" 2>/dev/null || true
  fi
  if wait "$trader_pid"; then rc=0; else rc=$?; fi
  trader_exit_status=$rc
  trader_pid=""
  record_trader_exit
  if [[ "$escalated" -eq 1 && "$rc" -eq 0 ]]; then return 124; fi
  return "$rc"
}

require_trader_alive() {
  kill -0 "$trader_pid" 2>/dev/null && return 0
  local rc
  if wait_for_trader_exit 0; then rc=0; else rc=$?; fi
  echo "DPDK trader exited before STOP: status=$rc" >&2
  [[ "$rc" -ne 0 ]] || rc=1
  return "$rc"
}

for value_name in USER_REF_SLOT_RAW USER_REF_BASE_RAW USER_REF_SPAN_RAW; do
  value="${!value_name}"
  [[ "$value" =~ ^[0-9]+$ ]] || {
    printf 'invalid unsigned integer: %s=%q\n' "$value_name" "$value" >&2
    exit 2
  }
  [[ "${#value}" -le 10 ]] || {
    printf 'unsigned integer is too large: %s=%q\n' "$value_name" "$value" >&2
    exit 2
  }
done
USER_REF_SLOT=$((10#$USER_REF_SLOT_RAW))
USER_REF_BASE=$((10#$USER_REF_BASE_RAW))
USER_REF_SPAN=$((10#$USER_REF_SPAN_RAW))
(( USER_REF_BASE > 0 && USER_REF_BASE < UINT32_LIMIT )) || {
  echo "user_ref base is outside uint32: $USER_REF_BASE" >&2
  exit 2
}
(( USER_REF_SPAN > 0 && USER_REF_SPAN <= UINT32_LIMIT - USER_REF_BASE )) || {
  printf 'user_ref span crosses uint32 boundary: base=%s span=%s\n' \
    "$USER_REF_BASE" "$USER_REF_SPAN" >&2
  exit 2
}
USER_REF_END_EXCLUSIVE=$((USER_REF_BASE + USER_REF_SPAN))
{
  echo "user_ref_slot=$USER_REF_SLOT"
  echo "user_ref_base=$USER_REF_BASE"
  echo "user_ref_span=$USER_REF_SPAN"
  echo "user_ref_end_exclusive=$USER_REF_END_EXCLUSIVE"
} | tee "$SESSION_DIR/user-ref.receipt"

current_netdev() {
  find "/sys/bus/pci/devices/$BDF/net" -mindepth 1 -maxdepth 1 \
    -printf '%f\n' 2>/dev/null | head -n 1
}

restore() {
  local wrapper_rc="${1:-$?}" cleanup_trader_rc=0 final_rc restore_ok=1
  local driver netdev address hugepages carrier ping_ok vfio_holders
  local hugetlbfs_current hugefile_leaks dpdk_runtime_leak
  local timer_load service_load timer_state service_state current_cidr token_value
  final_rc="$wrapper_rc"
  [[ "$BASHPID" -eq "$ROOT_PID" ]] || return 0
  set +e
  if [[ -n "$trader_pid" ]]; then
    if wait_for_trader_exit 1; then
      cleanup_trader_rc=0
    else
      cleanup_trader_rc=$?
    fi
    set +e
  fi
  if [[ "$cleanup_trader_rc" -ne 0 && "$final_rc" -eq 0 ]]; then
    final_rc="$cleanup_trader_rc"
  fi
  if [[ "$hardware_mutated" -eq 1 ]]; then
    "$DPDK_DEVBIND" --bind=sfc "$BDF" >/dev/null 2>&1 || true
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
    remove_owned_hugefiles || true
    if [[ -d "$DPDK_RUNTIME_DIR" ]]; then
      find "$DPDK_RUNTIME_DIR" -depth -delete 2>/dev/null || true
    fi
    for _ in $(seq 1 30); do
      sysctl -w vm.nr_hugepages=0 >/dev/null 2>&1 || true
      [[ "$(cat /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages)" = 0 ]] \
        && break
      sleep 1
    done
    if [[ "$hugetlbfs_mounted_by_wrapper" -eq 1 ]]; then
      umount "$HUGETLBFS" || true
    fi
    if [[ "$hugetlbfs_dir_created_by_wrapper" -eq 1 ]]; then
      rmdir "$HUGETLBFS" 2>/dev/null || true
    fi
  fi
  driver="$(basename "$(readlink "/sys/bus/pci/devices/$BDF/driver")" 2>/dev/null)"
  netdev="$(current_netdev)"
  address="$(ip -4 -o addr show dev "$IFACE" 2>/dev/null || true)"
  hugepages="$(cat /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages 2>/dev/null)"
  carrier="$(cat "/sys/class/net/$IFACE/carrier" 2>/dev/null || true)"
  ping_ok=0
  ping_output="$(LC_ALL=C ping -q -I "$IFACE" -c 3 -W 1 20.1.1.1 2>/dev/null || true)"
  grep -Fq '3 packets transmitted, 3 received' <<<"$ping_output" && ping_ok=1
  vfio_holders="$(fuser "/dev/vfio/$GROUP" 2>/dev/null | xargs || true)"
  hugetlbfs_current="$(findmnt -rn --mountpoint "$HUGETLBFS" \
    -o FSTYPE,TARGET,SOURCE,OPTIONS 2>/dev/null || true)"
  snapshot_hugetlbfs_entries "$HUGETLBFS_FILES_FINAL"
  hugefile_leaks="$(list_owned_hugefiles | xargs || true)"
  dpdk_runtime_leak=0
  [[ ! -e "$DPDK_RUNTIME_DIR" ]] || dpdk_runtime_leak=1
  [[ "$driver" = sfc ]] || restore_ok=0
  [[ "$netdev" = "$IFACE" ]] || restore_ok=0
  mapfile -t restored_ipv4 < <(ip -4 -o addr show dev "$IFACE" scope global 2>/dev/null)
  [[ "${#restored_ipv4[@]}" -eq 1 ]] || restore_ok=0
  current_cidr="$(awk '{print $4}' <<<"${restored_ipv4[0]-}")"
  [[ "$current_cidr" = "$ADDR" ]] || restore_ok=0
  [[ "$hugepages" = 0 && "$carrier" = 1 && "$ping_ok" = 1 ]] || restore_ok=0
  [[ -z "$vfio_holders" ]] || restore_ok=0
  [[ "$hugetlbfs_current" = "$HUGETLBFS_BASELINE" ]] || restore_ok=0
  cmp -s "$HUGETLBFS_FILES_BASELINE" "$HUGETLBFS_FILES_FINAL" || restore_ok=0
  [[ -z "$hugefile_leaks" && "$dpdk_runtime_leak" -eq 0 ]] || restore_ok=0
  if [[ "$restore_ok" -eq 1 && "$lease_published" -eq 1 ]]; then
    if [[ "$lease_armed" -eq 1 ]]; then
      systemctl stop "$LEASE_UNIT.timer" "$LEASE_UNIT.service" \
        >/dev/null 2>&1 || true
      timer_load="$(systemctl show -p LoadState --value \
        "$LEASE_UNIT.timer" 2>/dev/null || true)"
      service_load="$(systemctl show -p LoadState --value \
        "$LEASE_UNIT.service" 2>/dev/null || true)"
      timer_state="$(systemctl show -p ActiveState --value \
        "$LEASE_UNIT.timer" 2>/dev/null || true)"
      service_state="$(systemctl show -p ActiveState --value \
        "$LEASE_UNIT.service" 2>/dev/null || true)"
      { [[ "$timer_load" = not-found ]] || [[ "$timer_state" = inactive ]]; } \
        || restore_ok=0
      { [[ "$service_load" = not-found ]] || [[ "$service_state" = inactive ]]; } \
        || restore_ok=0
    fi
    if [[ "$restore_ok" -eq 1 ]]; then
      token_value="$(<"$SESSION_DIR/lease.token")" || restore_ok=0
      [[ "$token_value" = "$LEASE_TOKEN" ]] || restore_ok=0
    fi
    if [[ "$restore_ok" -eq 1 ]]; then
      mv -- "$SESSION_DIR/lease.token" \
        "$SESSION_DIR/lease.token.consumed" || restore_ok=0
    fi
    if [[ "$restore_ok" -eq 1 ]]; then
      if write_ownership_state CONSUMED gate; then
        lease_armed=0
        lease_published=0
      else
        restore_ok=0
      fi
    fi
  fi
  if [[ "$restore_ok" -ne 1 && "$final_rc" -eq 0 ]]; then final_rc=1; fi
  {
    echo '=== restore ==='
    echo "driver=$driver"
    echo "netdev=$netdev"
    printf '%s\n' "$address"
    echo "hugepages=$hugepages carrier=$carrier ping_ok=$ping_ok vfio_holders=${vfio_holders:-0}"
    echo "hugetlbfs_baseline=${HUGETLBFS_BASELINE:-ABSENT}"
    echo "hugetlbfs_final=${hugetlbfs_current:-ABSENT}"
    echo "file_prefix=$DPDK_FILE_PREFIX hugefile_leaks=${hugefile_leaks:-0} dpdk_runtime_leak=$dpdk_runtime_leak"
    echo "independent_lease_unit=$LEASE_UNIT lease_armed=$lease_armed"
    echo "lease_published=$lease_published"
    echo "lease_token=$LEASE_TOKEN"
    echo "ownership_state=$([[ "$lease_published" -eq 0 ]] && echo CONSUMED || echo ACTIVE)"
    echo "hugetlbfs_entries_match=$([[ -s "$HUGETLBFS_FILES_BASELINE" ]] && cmp -s "$HUGETLBFS_FILES_BASELINE" "$HUGETLBFS_FILES_FINAL" && echo 1 || echo 0)"
    echo "restore_state=$([[ "$restore_ok" -eq 1 ]] && echo PASS || echo FAIL)"
    echo "independent_lease_armed=$lease_armed"
  } | tee "$SESSION_DIR/restore.receipt"
  {
    echo "wrapper_exit_status=$final_rc"
    echo "trader_exit_status=$trader_exit_status"
    echo "cleanup_trader_exit_status=$cleanup_trader_rc"
    echo "restore_state=$([[ "$restore_ok" -eq 1 ]] && echo PASS || echo FAIL)"
    echo "lease_token=$LEASE_TOKEN"
    echo "ownership_state=$([[ "$lease_published" -eq 0 ]] && echo CONSUMED || echo ACTIVE)"
  } >"$SESSION_DIR/gate-exit.receipt"
  return "$final_rc"
}
finish() {
  local wrapper_rc=$? final_rc
  trap - EXIT
  if restore "$wrapper_rc"; then final_rc=0; else final_rc=$?; fi
  exit "$final_rc"
}

echo '=== preflight ==='
command -v findmnt mountpoint fuser flock systemctl systemd-run >/dev/null
test "$(hostname)" = "$EXPECTED_HOST"
test -x "$BINARY"
test -x "$DPDK_DEVBIND"
test -r "$CONFIG"
for process in /proc/[0-9]*; do
  [[ "$(readlink -f "$process/exe" 2>/dev/null || true)" != "$BINARY" ]] || {
    echo "an existing DPDK trader must be recovered before a new lease starts" >&2
    exit 1
  }
done
test "$(basename "$(readlink "/sys/bus/pci/devices/$BDF/driver")")" = sfc
test "$(current_netdev)" = "$IFACE"
ip -4 -o addr show dev "$IFACE" | grep -Fq " $ADDR "
test "$(basename "$(readlink -f "/sys/bus/pci/devices/$BDF/iommu_group")")" = "$GROUP"
mapfile -t group_devices < <(find "/sys/kernel/iommu_groups/$GROUP/devices" \
  -mindepth 1 -maxdepth 1 -printf '%f\n')
test "${#group_devices[@]}" -eq 1
test "${group_devices[0]}" = "$BDF"
test "$(cat /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages)" = 0
mapfile -t baseline_ipv4 < <(ip -4 -o addr show dev "$IFACE" scope global)
test "${#baseline_ipv4[@]}" -eq 1
grep -Fq " $ADDR " <<<"${baseline_ipv4[0]}"
baseline_cidr="$(awk '{print $4}' <<<"${baseline_ipv4[0]}")"
test "$baseline_cidr" = "$ADDR"
{
  echo 'driver=sfc'
  echo "netdev=$IFACE"
  echo "address=$baseline_cidr"
  echo 'hugepages=0'
} >"$OWNERSHIP_BASELINE.tmp.$BASHPID"
mv -- "$OWNERSHIP_BASELINE.tmp.$BASHPID" "$OWNERSHIP_BASELINE"
printf 'driver=sfc group=%s group_device=%s\n' \
  "$GROUP" "${group_devices[0]}"
printf 'hugetlbfs_baseline=%s\n' "${HUGETLBFS_BASELINE:-ABSENT}"
printf 'file_prefix=%s hugetlbfs_entries_baseline=%s\n' \
  "$DPDK_FILE_PREFIX" "$HUGETLBFS_FILES_BASELINE"

write_ownership_state() {
  local state="${1:?ownership state is required}" actor="${2:?actor is required}"
  printf 'state=%s\nlease_token=%s\nactor=%s\n' \
    "$state" "$LEASE_TOKEN" "$actor" >"$OWNERSHIP_STATE.tmp.$BASHPID"
  mv -- "$OWNERSHIP_STATE.tmp.$BASHPID" "$OWNERSHIP_STATE"
}

# Everything above is read-only with respect to X2522 ownership.  From this
# point onward any failure must cancel the lease and, once MUTATING is durable,
# restore the exact baseline.
trap finish EXIT
gate_tmp="$GATE_PID_FILE.tmp.$BASHPID"
printf '%s\n' "$ROOT_PID" >"$gate_tmp"
mv -- "$gate_tmp" "$GATE_PID_FILE"
printf '%s\n' "$LEASE_TOKEN" >"$SESSION_DIR/lease.token.tmp.$BASHPID"
mv -- "$SESSION_DIR/lease.token.tmp.$BASHPID" "$SESSION_DIR/lease.token"
lease_published=1
write_ownership_state ARMED gate
printf 'pid=%s start_ticks=%s boot_id=%s lease_token=%s\n' \
  "$ROOT_PID" "$gate_start_ticks" "$gate_boot_id" "$LEASE_TOKEN" \
  >"$SESSION_DIR/gate.identity.tmp.$BASHPID"
mv -- "$SESSION_DIR/gate.identity.tmp.$BASHPID" "$SESSION_DIR/gate.identity"
{
  echo "gate_pid=$ROOT_PID"
  echo "gate_cpus_allowed_list=$gate_cpu"
  echo "runtime_manifest_sha256=$(sha256sum "$RUNTIME_ROOT/MANIFEST.sha256" | awk '{print $1}')"
  echo "wrapper_sha256=$(sha256sum "$RUNTIME_ROOT/bin/x2522-dpdk-trader-remote.sh" | awk '{print $1}')"
  echo "binary_sha256=$(sha256sum "$BINARY" | awk '{print $1}')"
  echo "config_sha256=$(sha256sum "$CONFIG" | awk '{print $1}')"
  echo "lease_token=$LEASE_TOKEN"
} >"$SESSION_DIR/gate-start.receipt.tmp.$BASHPID"
mv -- "$SESSION_DIR/gate-start.receipt.tmp.$BASHPID" \
  "$SESSION_DIR/gate-start.receipt"

echo '=== arm independent ownership lease ==='
systemctl stop "$LEASE_UNIT.timer" "$LEASE_UNIT.service" >/dev/null 2>&1 || true
systemctl reset-failed "$LEASE_UNIT.timer" "$LEASE_UNIT.service" \
  >/dev/null 2>&1 || true
lease_armed=1
{
  echo "lease_unit=$LEASE_UNIT"
  echo "lease_seconds=$DEADMAN"
  echo "lease_token=$LEASE_TOKEN"
  echo "recovery_executor=systemd_timer_independent_of_wrapper"
} >"$SESSION_DIR/lease-start.receipt.tmp.$BASHPID"
mv -- "$SESSION_DIR/lease-start.receipt.tmp.$BASHPID" \
  "$SESSION_DIR/lease-start.receipt"
systemd-run --quiet --unit="$LEASE_UNIT" --on-active="${DEADMAN}s" \
  --timer-property=AccuracySec=1s \
  "$RUNTIME_ROOT/bin/x2522-dpdk-trader-remote.sh" --recover-only \
  "$RUNTIME_ROOT" "$SESSION_DIR" "$STOP_FILE" "$GATE_PID_FILE" \
  "$LEASE_TOKEN"
test "$(systemctl show -p ActiveState --value "$LEASE_UNIT.timer")" = active
test "$(systemctl show -p SubState --value "$LEASE_UNIT.timer")" = waiting
test "$(systemctl show -p ActiveState --value "$LEASE_UNIT.service")" = inactive
echo "DPDK_INDEPENDENT_LEASE unit=$LEASE_UNIT seconds=$DEADMAN armed=1"

echo '=== acquire X2522 with safe VFIO ==='
modprobe vfio-pci
test "$(cat /sys/module/vfio/parameters/enable_unsafe_noiommu_mode)" = N
echo 'unsafe_noiommu=N'
write_ownership_state MUTATING gate
hardware_mutated=1
sysctl -w vm.nr_hugepages=256
test "$(cat /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages)" = 256
if [[ -z "$HUGETLBFS_BASELINE" ]]; then
  if [[ ! -d "$HUGETLBFS" ]]; then
    mkdir "$HUGETLBFS"
    hugetlbfs_dir_created_by_wrapper=1
  fi
  mount -t hugetlbfs nodev "$HUGETLBFS"
  hugetlbfs_mounted_by_wrapper=1
fi
ip link set "$IFACE" down
"$DPDK_DEVBIND" --bind=vfio-pci "$BDF"
test "$(basename "$(readlink "/sys/bus/pci/devices/$BDF/driver")")" = vfio-pci
write_ownership_state OWNED gate

echo '=== start DPDK/F-Stack OUCH client ==='
env FLLE_MANAGEMENT_PORT=48125 FLLE_TELEMETRY_HOST=10.1.1.101 \
  FLLE_DPDK_HELPER_CPU=3 FLLE_DPDK_HEARTBEAT=0 \
  FLLE_DPDK_USER_REF_BASE="$USER_REF_BASE" \
  FLLE_DPDK_USER_REF_SPAN="$USER_REF_SPAN" \
  taskset -c 2,3 "$BINARY" --conf "$EFFECTIVE_CONFIG" --proc-type=primary --proc-id=0 \
  >"$SESSION_DIR/fstack.log" 2>&1 9>&- &
trader_pid=$!
echo "trader_pid=$trader_pid"
printf '%s\n' "$trader_pid" >"$SESSION_DIR/trader.pid"
trader_start_ticks="$(awk '{print $22}' "/proc/$trader_pid/stat")"
trader_boot_id="$(cat /proc/sys/kernel/random/boot_id)"
printf 'pid=%s start_ticks=%s boot_id=%s lease_token=%s\n' \
  "$trader_pid" "$trader_start_ticks" "$trader_boot_id" "$LEASE_TOKEN" \
  >"$SESSION_DIR/trader.identity.tmp.$BASHPID"
mv -- "$SESSION_DIR/trader.identity.tmp.$BASHPID" \
  "$SESSION_DIR/trader.identity"

ready=0
for _ in $(seq 1 80); do
  require_trader_alive
  state="$(timeout 1 bash -c 'exec 3<>/dev/tcp/10.1.1.2/48125; printf "STATE\n" >&3; IFS= read -r line <&3; printf "%s" "$line"' 2>/dev/null || true)"
  if [[ "$state" == *'"status":"ONLINE"'* &&
        "$state" == *'"order_transport":"DPDK_FSTACK"'* &&
        "$state" == *'"queue_mode":"DEQUE_CV"'* &&
        "$state" == *'"user_ref_base":'"$USER_REF_BASE"','* &&
        "$state" == *'"user_ref_span":'"$USER_REF_SPAN"','* ]]; then
    printf '%s\n' "$state" >"$SESSION_DIR/ready-state.json"
    ready=1
    break
  fi
  sleep 0.25
done
test "$ready" -eq 1
grep -Fq 'Using IOMMU type 1' "$SESSION_DIR/fstack.log"
grep -Fq 'Probe PCI driver: net_sfc_efx' "$SESSION_DIR/fstack.log"
grep -Fq 'running FW variant is ultra-low-latency' "$SESSION_DIR/fstack.log"
printf 'DPDK_TRADER_READY slot=%s user_ref_base=%s user_ref_span=%s\n' \
  "$USER_REF_SLOT" "$USER_REF_BASE" "$USER_REF_SPAN"

for ((second=0; second<DEADMAN; second++)); do
  [[ -f "$STOP_FILE" ]] && break
  require_trader_alive
  sleep 1
done
[[ -f "$STOP_FILE" ]] || { echo deadman_expired=1; exit 124; }
echo DPDK_TRADER_STOP_REQUESTED
if wait_for_trader_exit 1; then
  cleanup_line='cleanup_mode=PROCESS_EXIT_BYPASS_INCOMPLETE_FSTACK_CLEANUP shutdown_rc=0 peer_eof=1'
  test "$(grep -Fxc "$cleanup_line" "$SESSION_DIR/fstack.log")" -eq 1
  trader_cleanup_mode=PROCESS_EXIT_BYPASS_INCOMPLETE_FSTACK_CLEANUP
  trader_shutdown_rc=0
  trader_peer_eof=1
  record_trader_exit
  echo 'DPDK_TRADER_STOPPED status=0'
else
  trader_rc=$?
  echo "DPDK_TRADER_STOP_FAILED status=$trader_rc" >&2
  exit "$trader_rc"
fi
