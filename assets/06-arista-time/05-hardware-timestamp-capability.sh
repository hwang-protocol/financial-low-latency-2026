#!/usr/bin/env bash
set -Eeuo pipefail
cd /qyt-fll
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-07-hw-timestamp"
OUT="reports/course-runs/$RUN_ID"
COMMON="assets/common"
mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"

printf '%s\n' \
  'show hostname' \
  'show ptp' \
  'show running-config all interfaces Ethernet2 | include timestamp|ptp' \
  >"$OUT/raw/switch.plan"

{
  printf 'fll-arista / verify\n===== 查交换机 PTP =====\n[show ptp] 对: PTP Mode: Disabled  证: 7150 认得 PTP，当前没开\n'
  python3 "$COMMON/eos_cli.py" --mode show --plan "$OUT/raw/switch.plan" --output "$OUT/raw/switch.txt" >/dev/null
  cat "$OUT/raw/switch.txt"
  printf 'vm-2522-02 / verify\n===== 查 Linux 网卡 =====\n[ethtool -T] 对: hardware-transmit / hardware-receive / PTP Hardware Clock: 0  证: 这张 X2522 能盖硬件 TX/RX 戳\n'
  ssh -n -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
    "name=\$(hostname); printf '\$ hostname\n%s\n\$ ethtool -T ens64np1\n' \"\$name\"; ethtool -T ens64np1"
} 2>&1 | tee "$OUT/raw/result.txt"

(cd "$OUT" && sha256sum raw/result.txt raw/switch.txt run.env >SHA256SUMS)
echo "evidence=$OUT"
