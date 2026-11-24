#!/usr/bin/env bash
set -Eeuo pipefail
cd /qyt-fll
TOOLS=assets/02-trading-baseline
source reports/run-state/02-trading-baseline.env
BASE_RUN_ID="$RUN_ID"; API="${WEB_URL%/}"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-02-readonly-review"
OUT="reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\nBASE_RUN_ID=%s\n' "$RUN_ID" "$BASE_RUN_ID" >"$OUT/run.env"
{
  printf '===== 复查平台进程与部署文件 =====\n$ bash apps/flle-trading-lab/scripts/transport_labctl.sh verify %s\n' "$BASE_RUN_ID"
  if bash apps/flle-trading-lab/scripts/transport_labctl.sh verify "$BASE_RUN_ID" >"$OUT/raw/platform.txt" 2>&1; then rc=0; else rc=$?; fi
  if test "$rc" -ne 0; then tail -n 20 "$OUT/raw/platform.txt"; exit "$rc"; fi
  filter='/^[A-Za-z][A-Za-z0-9_-]*=/ && length($0)<=240 {print}'
  printf '$ awk %q %q\n' "$filter" "$OUT/raw/platform.txt"; awk "$filter" "$OUT/raw/platform.txt"
  printf '===== 复查主机成员 =====\n$ ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 ip maddr show dev ens64np1\n'
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 'ip maddr show dev ens64np1' | tee "$OUT/raw/membership.txt"
  printf '===== 复查交换机成员 =====\n$ python3 assets/common/eos_cli.py --mode show --plan %s --output %s\n' "$TOOLS/igmp-show.plan" "$OUT/raw/switch.txt"
  if python3 assets/common/eos_cli.py --mode show --plan "$TOOLS/igmp-show.plan" --output "$OUT/raw/switch.txt" >"$OUT/raw/cli.txt" 2>&1; then rc=0; else rc=$?; fi
  if test "$rc" -ne 0; then cat "$OUT/raw/cli.txt"; exit "$rc"; fi
  printf '$ python3 %s/inspect-igmp.py %s --members --display\n' "$TOOLS" "$OUT/raw/switch.txt"
  python3 "$TOOLS/inspect-igmp.py" "$OUT/raw/switch.txt" --members --display
  printf '===== 查看此刻的行情完整性 =====\nONLINE 只表示进程在线；继续下单前还要确认行情为 HEALTHY、保护闸为 OPEN。\n$ curl -fsS --max-time 10 %q\n' "$API/api/state"
  curl -fsS --max-time 10 "$API/api/state" >"$OUT/raw/state.json"
  summary='import json,sys; s=json.load(open(sys.argv[1])); f=s.get("feed") or {}; print("market_mode=%s integrity=%s next_expected=%s trading_gate=%s" % (s.get("market_mode"),f.get("integrity"),f.get("next_expected"),f.get("trading_gate")))'
  printf '$ python3 -c %q %q\n' "$summary" "$OUT/raw/state.json"; python3 -c "$summary" "$OUT/raw/state.json"
} 2>&1 | tee "$OUT/raw/classroom.txt"
sha256sum "$TOOLS/03-readonly-review.sh" "$TOOLS/igmp-show.plan" "$TOOLS/inspect-igmp.py" "$OUT"/raw/* "$OUT/run.env" >"$OUT/SHA256SUMS"
