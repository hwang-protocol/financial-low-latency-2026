#!/usr/bin/env bash
# 单向延时卡的远端收尾：只回收本卡自己启动的东西。
#
# 本卡在交易系统在线时运行，因此这里刻意不碰大页、驱动绑定、IP 配置和 Onload
# 状态——那些由第 05 章 RUN 持有。只停本卡启动的 ptp4l，并把网卡硬件打戳开关
# 还原成进场前记录的值。

set -Eeuo pipefail

if [[ "$#" -ne 6 ]]; then
  printf 'usage: %s IFACE PTP_PIDFILE BASELINE_TX_TYPE BASELINE_RX_FILTER CLEANUP_LOG RUN_TAG\n' "$0" >&2
  exit 64
fi

readonly IFACE="$1"
readonly PTP_PIDFILE="$2"
readonly BASELINE_TX_TYPE="$3"
readonly BASELINE_RX_FILTER="$4"
readonly CLEANUP_LOG="$5"
readonly RUN_TAG="$6"

mkdir -p "$(dirname "$CLEANUP_LOG")"
exec > >(tee -a "$CLEANUP_LOG") 2>&1

log() {
  printf '%s %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"
}

stop_pidfile() {
  local pidfile="$1" expected="$2" pid='' cmdline=''
  [[ -r "$pidfile" ]] || return 0
  pid="$(cat "$pidfile")"
  [[ "$pid" =~ ^[0-9]+$ ]] || return 0
  kill -0 "$pid" 2>/dev/null || return 0
  cmdline="$(tr '\0' ' ' < "/proc/${pid}/cmdline" 2>/dev/null || true)"
  # 只杀确认是自己启动的 ptp4l，PID 复用时拒绝动手。
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

log "ONEWAY_CLEANUP_BEGIN tag=${RUN_TAG} iface=${IFACE}"

stop_pidfile "$PTP_PIDFILE" ptp4l
pkill -TERM -x ptp4l 2>/dev/null || true
for _ in $(seq 1 20); do
  pgrep -x ptp4l >/dev/null || break
  sleep 0.25
done

for proc in ptp4l phc2sys sfptpd ts2phc timemaster; do
  if pgrep -x "$proc" >/dev/null; then
    log "ONEWAY_CLEANUP_FAIL unexpected_process=${proc}"
    exit 1
  fi
done

if [[ -S /var/run/ptp4l ]]; then
  unlink /var/run/ptp4l
fi

# 还原进场前记录的打戳开关，不使用写死的 0/0。
/usr/sbin/hwstamp_ctl -i "$IFACE" -t "$BASELINE_TX_TYPE" -r "$BASELINE_RX_FILTER"

pkill -f 'oneway_rx.py' 2>/dev/null || true
pkill -f 'oneway_tx.py' 2>/dev/null || true

ip -br addr show dev "$IFACE"
ethtool "$IFACE" | grep -E 'Speed:|Duplex:|Link detected:'
printf 'hugepages_untouched=%s\n' "$(sysctl -n vm.nr_hugepages)"
log "ONEWAY_CLEANUP_PASS tag=${RUN_TAG} iface=${IFACE}"
