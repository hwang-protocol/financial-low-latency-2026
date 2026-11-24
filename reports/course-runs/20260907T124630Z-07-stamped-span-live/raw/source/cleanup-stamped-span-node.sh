#!/usr/bin/env bash
# 停本机 ptp4l / tcpdump，并按进场值还原网卡打戳开关。
set -eu
IFACE="$1"
PTP_PIDFILE="$2"
TCPDUMP_PIDFILE="$3"
TX_TYPE="$4"
RX_FILTER="$5"
LOG="$6"

stop_pidfile() {
  local pidfile="$1"
  test -f "$pidfile" || return 0
  local pid
  pid="$(cat "$pidfile")"
  if test -n "$pid" && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
    sleep 0.2
    kill -9 "$pid" 2>/dev/null || true
  fi
  rm -f "$pidfile"
}

{
  stop_pidfile "$PTP_PIDFILE"
  stop_pidfile "$TCPDUMP_PIDFILE"
  pkill -x ptp4l 2>/dev/null || true
  /usr/sbin/hwstamp_ctl -i "$IFACE" -t "$TX_TYPE" -r "$RX_FILTER" || true
} >"$LOG" 2>&1
