#!/usr/bin/env bash
set -Eeuo pipefail
cd /qyt-fll
TOOLS=assets/02-trading-baseline
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-02-igmp-configure"
OUT="reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
{
  printf '10.1.1.253 / configure\n===== 配置 VLAN20 的组播侦听与查询器 =====\n让交换机学习接收端口，并持续查询成员。\n'
  printf '$ python3 assets/common/eos_cli.py --mode controlled-config --plan %s --output %s\n' "$TOOLS/igmp-configure.plan" "$OUT/raw/switch.txt"
  if python3 assets/common/eos_cli.py --mode controlled-config --plan "$TOOLS/igmp-configure.plan" --output "$OUT/raw/switch.txt" >"$OUT/raw/cli.txt" 2>&1; then rc=0; else rc=$?; fi
  if test "$rc" -ne 0; then cat "$OUT/raw/cli.txt"; exit "$rc"; fi
  printf '$ python3 %s/inspect-igmp.py %s --configuration --ab --display\n' "$TOOLS" "$OUT/raw/switch.txt"
  python3 "$TOOLS/inspect-igmp.py" "$OUT/raw/switch.txt" --configuration --ab --display
} 2>&1 | tee "$OUT/raw/classroom.txt"
sha256sum "$TOOLS/00c-igmp-configure.sh" "$TOOLS/igmp-configure.plan" "$TOOLS/inspect-igmp.py" "$OUT"/raw/* "$OUT/run.env" >"$OUT/SHA256SUMS"
