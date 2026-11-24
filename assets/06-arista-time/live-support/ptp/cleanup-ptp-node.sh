#!/usr/bin/env bash

set -Eeuo pipefail

if [[ "$#" -ne 8 ]]; then
  printf 'usage: %s IFACE DATA_IP_CIDR PEER_IP PTP_PIDFILE TCPDUMP_PIDFILE BASELINE_HUGEPAGES CLEANUP_LOG RUN_TAG\n' "$0" >&2
  exit 64
fi

readonly IFACE="$1"
readonly DATA_IP_CIDR="$2"
readonly PEER_IP="$3"
readonly PTP_PIDFILE="$4"
readonly TCPDUMP_PIDFILE="$5"
readonly BASELINE_HUGEPAGES="$6"
readonly CLEANUP_LOG="$7"
readonly RUN_TAG="$8"
readonly MGMT_IF="ens33"
readonly DATA_BDF="0000:03:00.0"
readonly EXPECTED_DRIVER="sfc"
readonly EXPECTED_DRIVER_VERSION="6.1.0.1009"

mkdir -p "$(dirname "$CLEANUP_LOG")"
exec > >(tee -a "$CLEANUP_LOG") 2>&1

log() {
  printf '%s %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"
}

stop_pidfile() {
  local pidfile="$1"
  local expected="$2"
  local pid=''
  local cmdline=''

  [[ -r "$pidfile" ]] || return 0
  pid="$(cat "$pidfile")"
  [[ "$pid" =~ ^[0-9]+$ ]] || return 0
  kill -0 "$pid" 2>/dev/null || return 0
  cmdline="$(tr '\0' ' ' < "/proc/${pid}/cmdline" 2>/dev/null || true)"
  [[ "$cmdline" == *"$expected"* ]] || {
    log "REFUSE_PID_MISMATCH pid=${pid} expected=${expected} cmdline=${cmdline}"
    return 1
  }
  kill -TERM "$pid" 2>/dev/null || true
  for _ in $(seq 1 20); do
    kill -0 "$pid" 2>/dev/null || return 0
    sleep 0.25
  done
  kill -KILL "$pid" 2>/dev/null || true
}

log "PTP_CLEANUP_BEGIN tag=${RUN_TAG} iface=${IFACE}"

stop_pidfile "$PTP_PIDFILE" ptp4l
stop_pidfile "$TCPDUMP_PIDFILE" tcpdump

pkill -TERM -x ptp4l 2>/dev/null || true
pkill -TERM -x tcpdump 2>/dev/null || true
for _ in $(seq 1 20); do
  if ! pgrep -x ptp4l >/dev/null && ! pgrep -x tcpdump >/dev/null; then
    break
  fi
  sleep 0.25
done

for proc in ptp4l phc2sys sfptpd ts2phc timemaster tcpdump; do
  if pgrep -x "$proc" >/dev/null; then
    log "PTP_CLEANUP_FAIL unexpected_process=${proc}"
    exit 1
  fi
done

if [[ -S /var/run/ptp4l ]]; then
  unlink /var/run/ptp4l
fi

/usr/sbin/hwstamp_ctl -i "$IFACE" -t 0 -r 0
sysctl -w "vm.nr_hugepages=${BASELINE_HUGEPAGES}"

[[ "$(basename "$(readlink -f "/sys/class/net/${MGMT_IF}/device")")" != "$DATA_BDF" ]]
[[ "$(basename "$(readlink -f "/sys/class/net/${IFACE}/device")")" == "$DATA_BDF" ]]
[[ "$(ethtool -i "$IFACE" | awk '/^driver:/ {print $2}')" == "$EXPECTED_DRIVER" ]]
[[ "$(ethtool -i "$IFACE" | awk '/^version:/ {print $2}')" == "$EXPECTED_DRIVER_VERSION" ]]
ip -4 addr show dev "$IFACE" | grep -Fq "$DATA_IP_CIDR"
[[ "$(cat "/sys/class/net/${IFACE}/carrier")" == 1 ]]
[[ -c /dev/ptp0 && -c /dev/onload && -c /dev/sfc_char ]]
[[ "$(sysctl -n vm.nr_hugepages)" == "$BASELINE_HUGEPAGES" ]]
ethtool "$IFACE" | grep -Fq 'Speed: 10000Mb/s'
ethtool "$IFACE" | grep -Fq 'Duplex: Full'
ethtool "$IFACE" | grep -Fq 'Link detected: yes'
ping -I "$IFACE" -c 3 -W 1 "$PEER_IP"

ip -br addr show dev "$MGMT_IF"
ip -br addr show dev "$IFACE"
ethtool -i "$IFACE"
ethtool "$IFACE" | grep -E 'Speed:|Duplex:|Link detected:'
ethtool -T "$IFACE" | grep -E 'hardware-(transmit|receive|raw-clock)|PTP Hardware Clock:'
printf 'onload_cp_server_pid=%s\n' "$(cat /proc/driver/onload/cp_server_pids)"
printf 'hugepages=%s\n' "$(sysctl -n vm.nr_hugepages)"
log "PTP_CLEANUP_PASS tag=${RUN_TAG} iface=${IFACE}"
