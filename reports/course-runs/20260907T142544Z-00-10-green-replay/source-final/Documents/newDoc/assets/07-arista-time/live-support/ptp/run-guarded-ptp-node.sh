#!/usr/bin/env bash

set -Eeuo pipefail

: "${RUN_TAG:?set RUN_TAG}"
: "${ROLE:?set ROLE to master or client}"
: "${IFACE:?set IFACE}"
: "${MGMT_IP_CIDR:?set MGMT_IP_CIDR}"
: "${DATA_IP_CIDR:?set DATA_IP_CIDR}"
: "${PEER_IP:?set PEER_IP}"
: "${CONFIG_PATH:?set CONFIG_PATH}"
: "${PTP_LOG:?set PTP_LOG}"
: "${PCAP_PATH:?set PCAP_PATH}"
: "${TCPDUMP_LOG:?set TCPDUMP_LOG}"
: "${PTP_PIDFILE:?set PTP_PIDFILE}"
: "${TCPDUMP_PIDFILE:?set TCPDUMP_PIDFILE}"
: "${READY_MARKER:?set READY_MARKER}"
: "${CLEANUP_LOG:?set CLEANUP_LOG}"

readonly MGMT_IF="ens33"
readonly DATA_BDF="0000:03:00.0"
readonly EXPECTED_DRIVER="sfc"
readonly EXPECTED_DRIVER_VERSION="6.1.0.1009"
readonly BASELINE_HUGEPAGES="0"
readonly DURATION_SECONDS="70"
readonly CLEANUP_SCRIPT="/root/flle-preflight/cleanup-ptp-node.sh"
readonly DEADMAN_UNIT="flle-ptp-cleanup-${RUN_TAG//_/-}"

cleanup_armed=0
deadman_armed=0
ptp_wrapper_pid=''
tcpdump_wrapper_pid=''

log() {
  printf '%s %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"
}

fail() {
  log "FAIL $*"
  exit 1
}

cleanup() {
  local original_rc=$?
  trap - EXIT HUP INT TERM
  set +e

  if [[ "$cleanup_armed" -eq 1 ]]; then
    "$CLEANUP_SCRIPT" \
      "$IFACE" "$DATA_IP_CIDR" "$PEER_IP" \
      "$PTP_PIDFILE" "$TCPDUMP_PIDFILE" "$BASELINE_HUGEPAGES" \
      "$CLEANUP_LOG" "$RUN_TAG"
    local cleanup_rc=$?
    if [[ "$cleanup_rc" -eq 0 && "$deadman_armed" -eq 1 ]]; then
      systemctl stop "${DEADMAN_UNIT}.timer" "${DEADMAN_UNIT}.service" >/dev/null 2>&1 || true
      systemctl reset-failed "${DEADMAN_UNIT}.timer" "${DEADMAN_UNIT}.service" >/dev/null 2>&1 || true
      log "DEADMAN_DISARMED unit=${DEADMAN_UNIT}"
    elif [[ "$cleanup_rc" -ne 0 ]]; then
      log "CLEANUP_FAILED rc=${cleanup_rc}; deadman remains armed"
      [[ "$original_rc" -ne 0 ]] || original_rc="$cleanup_rc"
    fi
  fi
  exit "$original_rc"
}

trap cleanup EXIT HUP INT TERM
trap -p EXIT | grep -Fq cleanup || fail "EXIT cleanup trap is not registered"

[[ "$ROLE" == master || "$ROLE" == client ]] || fail "ROLE must be master or client"
[[ "$(id -u)" -eq 0 ]] || fail "must run as root"
[[ -x "$CLEANUP_SCRIPT" ]] || fail "cleanup script is missing"
[[ -r "$CONFIG_PATH" ]] || fail "PTP config is missing"
for tool in /usr/sbin/ptp4l /usr/sbin/pmc /usr/sbin/hwstamp_ctl /usr/bin/tcpdump; do
  [[ -x "$tool" ]] || fail "required tool missing: ${tool}"
done
[[ "$(basename "$(readlink -f "/sys/class/net/${MGMT_IF}/device")")" != "$DATA_BDF" ]] \
  || fail "management interface resolves to data BDF"
[[ "$(basename "$(readlink -f "/sys/class/net/${IFACE}/device")")" == "$DATA_BDF" ]] \
  || fail "data interface BDF mismatch"
ip -4 addr show dev "$MGMT_IF" | grep -Fq "$MGMT_IP_CIDR" || fail "management IP missing"
ip -4 addr show dev "$IFACE" | grep -Fq "$DATA_IP_CIDR" || fail "data IP missing"
ip route show default | grep -Eq "dev ${MGMT_IF}( |$)" || fail "default route left management interface"
[[ "$(ethtool -i "$IFACE" | awk '/^driver:/ {print $2}')" == "$EXPECTED_DRIVER" ]] \
  || fail "data driver mismatch"
[[ "$(ethtool -i "$IFACE" | awk '/^version:/ {print $2}')" == "$EXPECTED_DRIVER_VERSION" ]] \
  || fail "data driver version mismatch"
[[ "$(cat "/sys/class/net/${IFACE}/carrier")" == 1 ]] || fail "data carrier missing"
[[ -c /dev/ptp0 ]] || fail "PHC device missing"
ethtool -T "$IFACE" | grep -Fq 'hardware-transmit' || fail "hardware TX timestamp unsupported"
ethtool -T "$IFACE" | grep -Fq 'hardware-receive' || fail "hardware RX timestamp unsupported"
ethtool -T "$IFACE" | grep -Fq 'hardware-raw-clock' || fail "raw PHC unsupported"
[[ "$(sysctl -n vm.nr_hugepages)" == "$BASELINE_HUGEPAGES" ]] || fail "hugepages baseline drift"
for proc in ptp4l phc2sys sfptpd ts2phc timemaster tcpdump dpdk-testpmd iperf3; do
  pgrep -x "$proc" >/dev/null && fail "conflicting process active: ${proc}"
done
for stack_file in /proc/driver/onload/stacks /proc/driver/onload/stacks_k /proc/driver/onload/stacks_ul; do
  ! grep -q '[^[:space:]]' "$stack_file" 2>/dev/null || \
    fail "active Onload application stack: ${stack_file}"
done
pgrep -f '[f]lle-(trader|exchange)' >/dev/null && fail "active FLLE trading process"
ping -I "$IFACE" -c 3 -W 1 "$PEER_IP" >/dev/null || fail "baseline peer ping failed"

log "PTP_PRECHECK_PASS tag=${RUN_TAG} role=${ROLE} iface=${IFACE}"
rm -f "$READY_MARKER" "$PTP_PIDFILE" "$TCPDUMP_PIDFILE"
: > "$PTP_LOG"
: > "$TCPDUMP_LOG"
: > "$CLEANUP_LOG"
cleanup_armed=1

systemd-run \
  --unit="$DEADMAN_UNIT" \
  --on-active=100s \
  --collect \
  "$CLEANUP_SCRIPT" \
    "$IFACE" "$DATA_IP_CIDR" "$PEER_IP" \
    "$PTP_PIDFILE" "$TCPDUMP_PIDFILE" "$BASELINE_HUGEPAGES" \
    "$CLEANUP_LOG" "$RUN_TAG"
deadman_armed=1
systemctl is-active "${DEADMAN_UNIT}.timer" >/dev/null
log "DEADMAN_ARMED unit=${DEADMAN_UNIT} delay_seconds=100"

timeout --signal=INT --kill-after=3s "${DURATION_SECONDS}s" \
  /usr/bin/tcpdump -ni "$IFACE" -U -s 0 -w "$PCAP_PATH" \
  '(udp port 319 or udp port 320)' \
  >"$TCPDUMP_LOG" 2>&1 &
tcpdump_wrapper_pid=$!
printf '%s\n' "$tcpdump_wrapper_pid" > "$TCPDUMP_PIDFILE"

ptp_args=(/usr/sbin/ptp4l -f "$CONFIG_PATH" -i "$IFACE" -m -q)
if [[ "$ROLE" == client ]]; then
  ptp_args+=(-s)
fi
timeout --signal=TERM --kill-after=5s "${DURATION_SECONDS}s" \
  "${ptp_args[@]}" >"$PTP_LOG" 2>&1 &
ptp_wrapper_pid=$!
printf '%s\n' "$ptp_wrapper_pid" > "$PTP_PIDFILE"

ready=0
for _ in $(seq 1 80); do
  if [[ -S /var/run/ptp4l ]] && kill -0 "$ptp_wrapper_pid" 2>/dev/null; then
    ready=1
    break
  fi
  kill -0 "$ptp_wrapper_pid" 2>/dev/null || break
  sleep 0.25
done
[[ "$ready" -eq 1 ]] || fail "ptp4l did not create its management socket"
printf 'ready_at_utc=%s\ntag=%s\nrole=%s\niface=%s\n' \
  "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$RUN_TAG" "$ROLE" "$IFACE" > "$READY_MARKER"
log "PTP_READY marker=${READY_MARKER}"

set +e
wait "$ptp_wrapper_pid"
ptp_rc=$?
set -e
log "PTP_FINISHED rc=${ptp_rc} expected_timeout_rc=124"
if [[ "$ptp_rc" -ne 124 && "$ptp_rc" -ne 0 ]]; then
  fail "ptp4l exited unexpectedly"
fi

set +e
wait "$tcpdump_wrapper_pid"
tcpdump_rc=$?
set -e
log "TCPDUMP_FINISHED rc=${tcpdump_rc} expected_timeout_rc=124"
if [[ "$tcpdump_rc" -ne 124 && "$tcpdump_rc" -ne 0 ]]; then
  fail "tcpdump exited unexpectedly"
fi

log "PTP_RUNNER_PASS tag=${RUN_TAG} role=${ROLE}"
