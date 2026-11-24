#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
source Documents/reports/run-state/02-feed-buffer-fix.env
FIX_ID="$RUN_ID"
FIX_OUT="$OUT"
TOOLS=Documents/newDoc/assets/02-trading-baseline
cp "$0" "$FIX_OUT/full-chapter-check.sh"
cp /tmp/flle-feed-sustain.py "$FIX_OUT/feed-sustain.py"
finish() {
  rc=$?
  trap - EXIT
  printf 'FULL_CHECK_RC=%s\n' "$rc" >>"$FIX_OUT/run.env"
  printf 'STATUS=FINISHED\nFULL_CHECK_RC=%s\n' "$rc" >>Documents/reports/run-state/02-feed-buffer-fix.env
  sha256sum "$FIX_OUT/run.env" "$FIX_OUT/full-chapter-check.sh" "$FIX_OUT/feed-sustain.py" "$FIX_OUT/receiver-source.tgz" "$FIX_OUT"/raw/* >"$FIX_OUT/SHA256SUMS"
  exit "$rc"
}
trap finish EXIT
stage() {
  local name="$1" rc
  shift
  printf '\nSTART %s\n' "$name"
  if "$@" </dev/null >"$FIX_OUT/raw/$name.txt" 2>&1; then rc=0; else rc=$?; fi
  printf '%s_RC=%s\n' "$name" "$rc" >>"$FIX_OUT/run.env"
  tail -n 8 "$FIX_OUT/raw/$name.txt"
  printf 'END %s rc=%s\n' "$name" "$rc"
  return "$rc"
}
source Documents/reports/run-state/02-trading-baseline.env
printf 'OLD_PLATFORM_RUN=%s\n' "$RUN_ID" >>"$FIX_OUT/run.env"
stage stop_old bash apps/flle-trading-lab/scripts/transport_labctl.sh stop "$RUN_ID"
stage prep_a bash "$TOOLS/00a-runtime-prep.sh"
stage prep_b bash "$TOOLS/00b-iommu-prep.sh"
stage prep_c bash "$TOOLS/00c-igmp-configure.sh"
stage restore bash "$TOOLS/01-restore-trading-lab.sh"
source Documents/reports/run-state/02-trading-baseline.env
printf 'PLATFORM_RUN=%s\n' "$RUN_ID" >>"$FIX_OUT/run.env"
API="${WEB_URL%/}"
stage healthy_start python3 Documents/newDoc/assets/common/wait-feed-state.py "$API/api/state" HEALTHY --timeout 30
stage receiver_buffer ssh -n -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 "cat '$RUN_DIR/feed-receiver.log'; ss -u -a -n -m '( sport = :42121 or sport = :31032 )'; cat /proc/net/snmp; sysctl net.core.rmem_default net.core.rmem_max"
stage join bash "$TOOLS/01a-join-multicast.sh"
stage members bash "$TOOLS/01b-inspect-multicast.sh"
stage multicast bash "$TOOLS/01c-check-multicast-feed.sh"
stage sustained python3 "$FIX_OUT/feed-sustain.py" "$API/api/state"
stage multicast_after_burst bash "$TOOLS/01c-check-multicast-feed.sh"
stage first_trade bash "$TOOLS/02-first-trade.sh"
stage readonly_review bash "$TOOLS/03-readonly-review.sh"
stage healthy_end python3 Documents/newDoc/assets/common/wait-feed-state.py "$API/api/state" HEALTHY --timeout 30
stage udp_end ssh -n -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 "cat /proc/net/udp /proc/net/snmp; ss -u -a -n -m '( sport = :42121 or sport = :31032 )'"
