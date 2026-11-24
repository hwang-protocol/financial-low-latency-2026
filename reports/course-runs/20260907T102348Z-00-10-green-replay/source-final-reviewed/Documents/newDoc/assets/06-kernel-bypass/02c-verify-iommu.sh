#!/usr/bin/env bash
# Observe the isolation already prepared in Chapter 02. No reboot or GRUB edit.
set -Eeuo pipefail
cd /financial-low-latency
for host in 10.1.1.1 10.1.1.2; do
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@"$host" bash -s <<'REMOTE'
set -Eeuo pipefail
printf '\n===== 已生效的网卡隔离 =====\n'
hostname
cat /proc/cmdline
group="$(readlink -f /sys/bus/pci/devices/0000:03:00.0/iommu_group)"
test -d "$group/devices"
printf 'iommu_group=%s\n' "$group"
devices="$(find "$group/devices" -mindepth 1 -maxdepth 1 -printf '%f\n')"
test "$devices" = 0000:03:00.0
printf 'devices=%s\n' "$devices"
test "$(cat /sys/module/vfio/parameters/enable_unsafe_noiommu_mode)" = N
echo isolation=READY
REMOTE
done
