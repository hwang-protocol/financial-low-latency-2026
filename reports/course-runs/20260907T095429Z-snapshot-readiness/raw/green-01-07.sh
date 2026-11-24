#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency

RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-01-link-pair"
OUT="Documents/reports/course-runs/${RUN_ID}"
mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"

# 主机侧：到 .1/.2 各读一次数据口 ethtool
for item in '10.1.1.1 ens64np0' '10.1.1.2 ens64np1'; do
  read -r host data_if <<<"$item"
  printf '\n===== root@%s =====\n$ ethtool %s\n' "$host" "$data_if" | tee -a "$OUT/raw/host-links.txt"
  ssh -n -o BatchMode=yes -o StrictHostKeyChecking=yes "root@$host" \
    "ethtool '$data_if'" 2>&1 | tee -a "$OUT/raw/host-links.txt"
done

# 交换机侧：读 Et1、Et2 端口状态和 VLAN20
printf '%s\n' 'show interfaces Ethernet1 status' \
  'show interfaces Ethernet2 status' 'show vlan id 20' >"$OUT/eos.plan"
printf '===== admin@10.1.1.253 · EOS link state =====\n'; python3 Documents/newDoc/assets/common/eos_cli.py --mode show \
  --plan "$OUT/eos.plan" --output "$OUT/raw/arista-links.txt" \
  2>&1 | tee "$OUT/raw/arista-terminal.txt"

(cd "$OUT" && sha256sum raw/* run.env eos.plan >SHA256SUMS); printf 'evidence=%s\n' "$OUT"
