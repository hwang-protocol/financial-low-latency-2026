#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
source Documents/reports/run-state/02-trading-baseline.env
PLATFORM_RUN_ID="$RUN_ID"
CHECK_RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-04-fixed-cv-rerun"
OUT="$PWD/Documents/reports/course-runs/$CHECK_RUN_ID"
mkdir -p "$OUT/raw"
printf 'CHECK_RUN_ID=%s\nPLATFORM_RUN_ID=%s\nOUT=%s\nSTATUS=STARTED\n' "$CHECK_RUN_ID" "$PLATFORM_RUN_ID" "$OUT" > Documents/reports/run-state/04-fixed-cv-rerun.env
cp /tmp/flle-ch04-fixed-rerun.sh "$OUT/entry.sh"
cp Documents/reports/run-state/05-fixed-cv.env "$OUT/raw/previous-fixed.env"
cp Documents/reports/run-state/05-deque-cv.env "$OUT/raw/baseline-deque.env"
CTL=apps/flle-trading-lab/scripts/transport_labctl.sh
printf 'RERUN_EVIDENCE=%s\n' "$OUT"
curl -fsS --max-time 10 http://10.1.1.101:8088/api/state > "$OUT/raw/state-before.json"
curl -fsS --max-time 10 http://10.1.1.101:8088/api/transport-lab > "$OUT/raw/transport-before.json"
python3 - "$OUT/raw/transport-before.json" <<'PY'
import json,sys
s=json.load(open(sys.argv[1]))
assert (s['mode'],s['transition'],s['owner'])==('SFC','READY','sfc'),s
assert all(s['clients'][k]['health']['status']=='ONLINE' for k in ('trader_manual','trader_onload','trader_tcpdirect'))
print('PRECHECK SFC/READY/sfc PASS')
PY
restore(){
  local rc=$?
  trap - EXIT
  set +e
  printf '\nRESTORING CH06 HANDOFF (measurement exit=%s)\n' "$rc"
  bash Documents/newDoc/assets/06-arista-time/13-trading-online-final.sh > "$OUT/raw/restore-final.txt" 2>&1
  restore_rc=$?
  tail -n 16 "$OUT/raw/restore-final.txt"
  curl -fsS --max-time 10 http://10.1.1.101:8088/api/state > "$OUT/raw/state-after.json"
  curl -fsS --max-time 10 http://10.1.1.101:8088/api/transport-lab > "$OUT/raw/transport-after.json"
  printf 'measurement_exit=%s\nrestore_exit=%s\n' "$rc" "$restore_rc" | tee "$OUT/raw/outcome.txt"
  (cd "$OUT" && find raw -type f -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS)
  printf 'CHECK_RUN_ID=%s\nPLATFORM_RUN_ID=%s\nOUT=%s\nMEASUREMENT_EXIT=%s\nRESTORE_EXIT=%s\nSTATUS=FINISHED\n' "$CHECK_RUN_ID" "$PLATFORM_RUN_ID" "$OUT" "$rc" "$restore_rc" > Documents/reports/run-state/04-fixed-cv-rerun.env
  if test "$restore_rc" -ne 0; then exit "$restore_rc"; fi
  exit "$rc"
}
trap restore EXIT
printf 'Switching existing platform to SOFTWARE\n'
bash "$CTL" baseline "$PLATFORM_RUN_ID" > "$OUT/raw/baseline-switch.txt" 2>&1
curl -fsS --max-time 10 http://10.1.1.101:8088/api/state > "$OUT/raw/state-before-replay-restart.json"
curl -fsS --max-time 20 -X POST -H 'Content-Type: application/json' -d '{"action":"RESTART"}' http://10.1.1.101:8088/api/replay > "$OUT/raw/replay-restart.json"
for attempt in $(seq 1 80); do
  curl -fsS --max-time 10 http://10.1.1.101:8088/api/state > "$OUT/raw/state-software.json"
  if python3 - "$OUT/raw/state-software.json" <<'PY'
import json,sys
s=json.load(open(sys.argv[1]))
assert all(s['health'][k]['status']=='ONLINE' for k in ('exchange','gateway','trader_auto','trader_manual'))
assert s['replay']['status']=='PLAYING'
book=s.get('trader_books',{}).get('AAPL',{})
assert book.get('bids') and book.get('asks'), 'waiting for AAPL book'
assert s['feed']['trading_gate']=='OPEN',s['feed']
PY
  then break; fi
  if test "$attempt" -eq 80; then exit 1; fi
  sleep 0.5
done
printf 'Running unchanged Chapter 04 card 2 exactly once\n'
PYTHONUNBUFFERED=1 bash Documents/newDoc/assets/04-live-software/02-measure-fixed-cv.sh > "$OUT/raw/measurement-entry.txt" 2>&1
cp Documents/reports/run-state/05-fixed-cv.env "$OUT/raw/new-fixed.env"
cat "$OUT/raw/measurement-entry.txt"
