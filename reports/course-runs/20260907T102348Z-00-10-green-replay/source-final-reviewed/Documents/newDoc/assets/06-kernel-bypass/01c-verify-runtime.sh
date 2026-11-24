#!/usr/bin/env bash
# Observe the runtime installed in Chapter 02. No installation or driver reload.
set -Eeuo pipefail
cd /financial-low-latency
for host in 10.1.1.1 10.1.1.2; do
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@"$host" bash -s <<'REMOTE'
set -Eeuo pipefail
printf '\n===== 已部署的 Onload 运行时 =====\n'
hostname
onload --version
loaded_sfc="$(cat /sys/module/sfc/version)"
expected_sfc="$(modinfo -F version sfc)"
printf 'loaded_sfc=%s expected_sfc=%s\n' "$loaded_sfc" "$expected_sfc"
test "$loaded_sfc" = "$expected_sfc"
test -c /dev/onload && test -c /dev/sfc_char
ls -l /dev/onload /dev/sfc_char
test "$(basename "$(readlink /sys/bus/pci/devices/0000:03:00.0/driver)")" = sfc
echo runtime=READY
REMOTE
done
