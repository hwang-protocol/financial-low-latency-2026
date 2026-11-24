#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-06-onload-inventory"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"

# ~~~~~两端只读：版本、两个入口、sfc 驱动~~~~~
for host in 10.1.1.1 10.1.1.2; do
  printf '\n===== root@%s =====\n' "$host"
  ssh -n -o BatchMode=yes -o StrictHostKeyChecking=yes root@"$host" '
    printf "$ hostname\n"; hostname
    printf "$ onload --version\n"; onload --version
    printf "$ ls -l /dev/onload /dev/sfc_char\n"; ls -l /dev/onload /dev/sfc_char
    printf "$ readlink -f /sys/bus/pci/devices/0000:03:00.0/driver\n"
    readlink -f /sys/bus/pci/devices/0000:03:00.0/driver
  '
done 2>&1 | tee "$OUT/raw/result.txt"
(cd "$OUT" && sha256sum raw/result.txt run.env >SHA256SUMS)
echo "evidence=$OUT"
