#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-07-arista-inventory"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
TRANS="$OUT/raw/eos-transcript.txt"

printf '%s\n' \
  'show version' \
  'show interfaces Ethernet1 status' \
  'show interfaces Ethernet2 status' \
  'show interfaces Ethernet1 counters' \
  'show interfaces Ethernet2 counters' \
  'show vlan id 20' \
  'show mac address-table dynamic vlan 20' \
  'show switch forwarding-mode' >"$OUT/eos.plan"

python3 Documents/newDoc/assets/common/eos_cli.py --mode show \
  --plan "$OUT/eos.plan" --output "$TRANS" >/dev/null

{
  printf 'fll-arista / verify\n'
  while IFS='|' read -r title note cmd; do
    printf '===== 查%s =====\n%s\n$ %s\n' "$title" "$note" "$cmd"
    awk -v cmd="$cmd" '
      $0 == "$ " cmd {p=1; found=1; next}
      p && /^\$ / {exit}
      p && $0 == cmd " | no-more" {next}
      p {print}
      END {if (!found) exit 1}
    ' "$TRANS"
  done <<'ITEMS'
Et1状态|[Et1] 对: connected / VLAN 20 / full / 10G / 10GBASE-CR  证: Exchange 侧入口在课程链路上|show interfaces Ethernet1 status
Et2状态|[Et2] 对: connected / VLAN 20 / full / 10G / 10GBASE-CR  证: Trader 侧出口同速 10G|show interfaces Ethernet2 status
VLAN20成员|[VLAN20] 对: active，成员含 Cpu, Et1, Et2；工具口接入后列出  证: 实验走的是课程 VLAN20|show vlan id 20
VLAN20动态FDB|[FDB] 对: 000f.53d3.af20 在 Et1，000f.53d3.af21 在 Et2  证: 两端 MAC 学在正确的口|show mac address-table dynamic vlan 20
转发模式|[mode] 对: Current switching mode: cut through  证: 当前按 cut-through 工作，不是逐包时延|show switch forwarding-mode
ITEMS
} | tee "$OUT/raw/terminal.txt"
(cd "$OUT" && sha256sum raw/*.txt eos.plan run.env >SHA256SUMS)
echo "evidence=$OUT"
