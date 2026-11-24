#!/usr/bin/env bash
set -Eeuo pipefail

readonly iface=ens64np1
readonly expected_mac=00:0f:53:d3:af:21

[[ "$(hostname)" == vm-2522-02 ]]
[[ "$(cat "/sys/class/net/${iface}/address")" == "$expected_mac" ]]
[[ "$(basename "$(readlink -f "/sys/class/net/${iface}/device/driver")")" == sfc ]]

printf 'snapshot_label=%s\n' "${1:?snapshot label required}"
printf 'captured_at_utc=%s\n' "$(date -u +%FT%T.%NZ)"
printf 'monotonic_seconds=%s\n' "$(cut -d' ' -f1 /proc/uptime)"
ip -br link show dev "$iface"
ip -br -4 addr show dev "$iface"
ethtool "$iface" | sed -n '/Speed:/p;/Duplex:/p;/Link detected:/p'
printf '%s\n' '=== sysfs ==='
for counter in rx_packets rx_bytes rx_dropped rx_errors rx_missed_errors tx_packets tx_bytes tx_dropped tx_errors; do
  [[ -r "/sys/class/net/${iface}/statistics/${counter}" ]] || continue
  printf '%s=%s\n' "$counter" "$(<"/sys/class/net/${iface}/statistics/${counter}")"
done
printf '%s\n' '=== ethtool ==='
ethtool -S "$iface"
