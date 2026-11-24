#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency

RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-01-pci-identity"
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
printf '$ readlink -f /sys/class/net/%s/device\n' "$data_if"
readlink -f "/sys/class/net/$data_if/device"
printf '$ cat /sys/class/net/%s/address\n' "$data_if"
cat "/sys/class/net/$data_if/address"
bdf="$(basename "$(readlink -f "/sys/class/net/$data_if/device")")"
printf '$ lspci -nn -s %s\n' "$bdf"
lspci -nn -s "$bdf"
REMOTE
done
} 2>&1 | tee "$OUT/raw/pci-identity.txt"
(cd "$OUT" && sha256sum raw/pci-identity.txt run.env >SHA256SUMS); printf 'evidence=%s\n' "$OUT"
