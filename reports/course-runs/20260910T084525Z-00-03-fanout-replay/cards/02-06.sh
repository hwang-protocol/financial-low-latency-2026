#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
TOOLS=Documents/newDoc/assets/02-trading-baseline
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-02-igmp-members"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
{
  printf '10.1.1.253 / verify\n===== 查看交换机组播状态与成员表 =====\n查询 VLAN20 的转发方式、查询器和行情组成员，不修改配置。\n'
  printf '$ python3 Documents/newDoc/assets/common/eos_cli.py --mode show --plan %s --output %s\n' "$TOOLS/igmp-show.plan" "$OUT/raw/switch.txt"
  if python3 Documents/newDoc/assets/common/eos_cli.py --mode show --plan "$TOOLS/igmp-show.plan" --output "$OUT/raw/switch.txt" >"$OUT/raw/cli.txt" 2>&1; then rc=0; else rc=$?; fi
  if test "$rc" -ne 0; then cat "$OUT/raw/cli.txt"; exit "$rc"; fi
  printf '$ python3 %s/inspect-igmp.py %s --members --display\n' "$TOOLS" "$OUT/raw/switch.txt"
  python3 "$TOOLS/inspect-igmp.py" "$OUT/raw/switch.txt" --members --display
} 2>&1 | tee "$OUT/raw/classroom.txt"
sha256sum "$TOOLS/01b-inspect-multicast.sh" "$TOOLS/igmp-show.plan" "$TOOLS/inspect-igmp.py" "$OUT"/raw/* "$OUT/run.env" >"$OUT/SHA256SUMS"
