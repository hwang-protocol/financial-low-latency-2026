#!/usr/bin/env bash
# One foreground stage only. stage-session.py owns locking, persistence and recovery.
set -Eeuo pipefail
trap 'rc=$?; printf "stage=%s failed at line=%s status=%s; inspect this RUN raw receipts\n" "${1:-unknown}" "$LINENO" "$rc" >&2' ERR
cd /financial-low-latency
source Documents/newDoc/assets/common/flle-remote.sh
ROOT=/financial-low-latency
ASSET="$ROOT/Documents/newDoc/assets/09-verilator"
COMMON="$ROOT/Documents/newDoc/assets/common"
: "${RUN_ID:?}" "${OUT:?}" "${ORIGINAL_MODE:?}" "${ORIGINAL_PLAYBACK:?}"
[[ "$RUN_ID" =~ ^[0-9]{8}T[0-9]{6}Z-10-rtl-stages$ ]]
test "$OUT" = "$ROOT/Documents/reports/course-runs/$RUN_ID"
[[ "$ORIGINAL_MODE" =~ ^(UNICAST|MULTICAST|MULTICAST_A|MULTICAST_B|DUAL)$ ]]
[[ "$ORIGINAL_PLAYBACK" =~ ^(PLAYING|PAUSED)$ ]]
REMOTE="/var/tmp/$RUN_ID"
API=http://10.1.1.101:8088
remote2(){ ssh -n "${FLLE_SSH_OPTS[@]}" root@10.1.1.2 "$@"; }
control(){ remote2 "python3 '$REMOTE/remote-control.py' '$1'"; }
state(){ curl --max-time 5 -fsS "$API/api/state" >"$OUT/raw/$1.json"; }
post(){ curl --max-time 5 -fsS -X POST -H 'Content-Type: application/json' -d "$2" "$API/api/$1"; }
replay(){
  post replay "{\"action\":\"$1\"}" >"$OUT/raw/replay-$1-reply.json"
  python3 - "$API" "$1" "$OUT/raw/replay-$1.json" <<'PY'
import json, sys, time, urllib.request
api, action, output = sys.argv[1:]
expected = 'PAUSED' if action == 'PAUSE' else 'PLAYING'
for _ in range(50):
    with urllib.request.urlopen(api+'/api/state', timeout=2) as response: data=json.load(response)
    if data['replay']['status'] == expected:
        with open(output, 'w') as f: json.dump(data, f)
        break
    time.sleep(0.1)
else: raise SystemExit('replay did not become '+expected)
PY
}
feed(){ python3 "$COMMON/wait-feed-state.py" "$API/api/state" "$1" "${@:3}" >"$OUT/raw/$2.json"; }
log(){ remote2 "cat '$REMOTE/adapter.log'" >"$OUT/raw/$1.log"; }
check(){ python3 "$ASSET/live-support/stage-output.py" "$1" "$OUT"; }

prepare(){
  printf 'RUN_ID=%s\nBUILD_HOST=10.1.1.2\nRTL_HOST=10.1.1.2\nORIGINAL_MODE=%s\nORIGINAL_PLAYBACK=%s\n' \
    "$RUN_ID" "$ORIGINAL_MODE" "$ORIGINAL_PLAYBACK" >"$OUT/run.env"
  cp "$ASSET/market_filter.sv" "$ASSET/mold_filter_adapter.cpp" "$ASSET"/08[a-d]-*.sh \
    "$ASSET/live-support/remote-control.py" "$ASSET/live-support/classroom-output.py" \
    "$COMMON/feed-guardianctl.sh" "$COMMON/wait-feed-state.py" \
    "$COMMON/assert-feed-order-gate.py" "$COMMON/assert-feed-gap-ui.py" \
    "$COMMON/prove-trading-recovered.py" "$OUT/source/"
  bash "$COMMON/check-filter-handoff.sh" bridge >"$OUT/raw/handoff-before.txt"
  state state-before
  remote2 "test ! -e /var/tmp/flle-market-filter.cmd && ! pgrep -af '[m]old_filter_adapter'"
  # Recovery may act only after all ownership/preflight gates have passed.
  touch "$OUT/armed"
  remote2 "mkdir '$REMOTE'"
  scp -q "${FLLE_SSH_OPTS[@]}" "$ASSET/market_filter.sv" "$ASSET/mold_filter_adapter.cpp" \
    "$ASSET/live-support/remote-control.py" root@10.1.1.2:"$REMOTE/"
  remote2 "set -Eeuo pipefail; cd '$REMOTE'; timeout 300 verilator --cc --exe --build --Wall -Wno-fatal --top-module market_filter -o mold_filter_adapter market_filter.sv mold_filter_adapter.cpp; obj_dir/mold_filter_adapter --selftest; cp obj_dir/mold_filter_adapter mold_filter_adapter" >"$OUT/raw/build-and-selftest.txt" 2>&1
  python3 "$ASSET/live-support/classroom-output.py" selftest <"$OUT/raw/build-and-selftest.txt"
  scp -q "${FLLE_SSH_OPTS[@]}" root@10.1.1.2:"$REMOTE/mold_filter_adapter" "$OUT/artifacts/"
  bash "$COMMON/feed-guardianctl.sh" unicast-only --defer-feed-check >"$OUT/raw/feed-guardian-unicast-only.txt"
  control start >"$OUT/raw/adapter-start.txt"
  post market '{"market_mode":"MULTICAST_A"}' >"$OUT/raw/market-start.json"
  before="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["session"])' "$OUT/raw/state-before.json")"
  replay RESTART
  feed HEALTHY feed-baseline --timeout 25 --session-not "$before"
  replay PAUSE
  feed HEALTHY feed-baseline --timeout 10
  state state-prepared
  control check >"$OUT/raw/adapter-check-prepare.txt"
  log adapter-prepared
  check prepare
}

arm(){
  control check >"$OUT/raw/adapter-check-arm.txt"
  state state-before-arm
  log adapter-before-arm
  check before-arm
  # Equivalent to printf 'block\n' > /var/tmp/flle-market-filter.cmd on .2.
  # The helper refuses an occupied file and verifies this RUN's adapter identity.
  control block >"$OUT/raw/block-command.txt"
  replay RESUME
  feed GAP feed-gap --timeout 12
  replay PAUSE
  feed GAP feed-gap --timeout 5
  state state-armed
  log adapter-armed
  check arm
}

verify(){
  control check >"$OUT/raw/adapter-check-verify.txt"
  state state-verify
  feed GAP feed-verify --timeout 5
  log adapter-verify
  # Check the live paused session against the captured DROP before trying an order.
  check gap
  python3 "$COMMON/assert-feed-order-gate.py" "$API" >"$OUT/raw/order-gate.json"
  python3 "$COMMON/assert-feed-gap-ui.py" "$API" "$OUT/raw" >"$OUT/raw/gui-gap-contract.json"
  check verify
}

cleanup(){
  # Stop only the identity-checked RUN adapter. Keep its files for audit/retry.
  if remote2 "test -f '$REMOTE/remote-control.py'"; then
    control stop >"$OUT/raw/adapter-stop.txt"
    if remote2 "test -f '$REMOTE/adapter.log'"; then log adapter-final; fi
  else
    remote2 "test ! -e /var/tmp/flle-market-filter.cmd && ! pgrep -af '[m]old_filter_adapter'"
    printf 'adapter_stopped=1 control_absent=1\n' >"$OUT/raw/adapter-stop.txt"
  fi
  post market "{\"market_mode\":\"$ORIGINAL_MODE\"}" >"$OUT/raw/market-restored.json"
  bash "$COMMON/feed-guardianctl.sh" direct --defer-feed-check >"$OUT/raw/feed-guardian-restored.txt"
  state state-before-recovery
  before="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["session"])' "$OUT/raw/state-before-recovery.json")"
  replay RESTART
  feed HEALTHY feed-final --timeout 25 --session-not "$before"
  if test "$ORIGINAL_PLAYBACK" = PAUSED; then replay PAUSE; fi
  state state-restored
  bash "$COMMON/check-filter-handoff.sh" bridge >"$OUT/raw/handoff-after.txt"
  printf 'cleanup=PASS\n'
}

restore(){
  cleanup
  # Only the explicit classroom recovery stage sends the two verification orders.
  replay RESUME
  touch "$OUT/order-check-started"
  python3 "$COMMON/prove-trading-recovered.py" "$API" "$OUT/raw/post-restore-orders" >"$OUT/raw/post-restore-orders.json"
  if test "$ORIGINAL_PLAYBACK" = PAUSED; then replay PAUSE; fi
  state state-restored
  check restore
}

case "${1:?stage required}" in
  prepare) prepare ;;
  arm) arm ;;
  verify) verify ;;
  restore) restore ;;
  cleanup) cleanup ;;
  *) exit 2 ;;
esac
