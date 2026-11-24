#!/usr/bin/env bash
# Observe the isolation already prepared in Chapter 02. No reboot or GRUB edit.
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%S.%NZ)-05-iommu-verify"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
cp "$0" "$OUT/source.sh"
finish(){ rc=$?; trap - EXIT; printf 'EXIT_CODE=%s\n' "$rc" >>"$OUT/run.env"; (cd "$OUT" && sha256sum raw/result.txt run.env source.sh >SHA256SUMS); echo "evidence=$OUT"; exit "$rc"; }
trap finish EXIT
{
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
} 2>&1 | tee "$OUT/raw/result.txt"
