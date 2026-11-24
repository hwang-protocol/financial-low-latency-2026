#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency

RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-01-driver-owner"
OUT="Documents/reports/course-runs/${RUN_ID}"
mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"

{
for item in '10.1.1.1 ens64np0' '10.1.1.2 ens64np1'; do
  read -r host data_if <<<"$item"
  printf '\n===== root@%s · %s =====\n' "$host" "$data_if"
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes "root@$host" \
    bash -s -- "$data_if" <<'REMOTE'
set -Eeuo pipefail
data_if="$1"
bdf="$(basename "$(readlink -f "/sys/class/net/$data_if/device")")"
printf '$ readlink -f /sys/bus/pci/devices/%s/driver\n' "$bdf"
readlink -f "/sys/bus/pci/devices/$bdf/driver"
printf '$ ethtool -i %s\n' "$data_if"
ethtool -i "$data_if"
REMOTE
done
} 2>&1 | tee "$OUT/raw/driver-owner.txt"
(cd "$OUT" && sha256sum raw/driver-owner.txt run.env >SHA256SUMS); printf 'evidence=%s\n' "$OUT"
