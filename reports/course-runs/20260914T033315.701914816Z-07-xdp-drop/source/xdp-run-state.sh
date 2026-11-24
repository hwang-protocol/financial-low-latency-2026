#!/usr/bin/env bash
# Shared by the foreground drop and explicitly requested restart commands.
ROOT=/financial-low-latency
ASSET="$ROOT/Documents/newDoc/assets/07-xdp"
COMMON="$ROOT/Documents/newDoc/assets/common"
STATE="$ROOT/Documents/reports/run-state/07-xdp-drop.env"
PLATFORM_STATE="$ROOT/Documents/reports/run-state/02-trading-baseline.env"
API=http://10.1.1.101:8088
source "$COMMON/flle-remote.sh"
remote2(){ timeout 45 ssh -n "${FLLE_SSH_OPTS[@]}" root@10.1.1.2 "$@"; }
api_get(){ curl --connect-timeout 8 --max-time 15 -fsS "$API/api/state"; }
api_post(){ curl --connect-timeout 8 --max-time 15 -fsS -X POST -H 'Content-Type: application/json' -d "$2" "$API/api/$1"; }
read_field(){ sed -n "s/^$2=//p" "$1"; }
platform_run(){
  PARENT_RUN_ID="$(read_field "$PLATFORM_STATE" RUN_ID)"
  [[ "$PARENT_RUN_ID" =~ ^[A-Za-z0-9._-]+-02-trading-platform$ ]]
}
save_state(){
  PHASE="$1"
  printf 'RUN_ID=%s\nPARENT_RUN_ID=%s\nORIGINAL_MODE=%s\nPHASE=%s\n' \
    "$RUN_ID" "$PARENT_RUN_ID" "$ORIGINAL_MODE" "$PHASE" >"$OUT/state.env"
  cp "$OUT/state.env" "$STATE.tmp.$BASHPID"
  mv "$STATE.tmp.$BASHPID" "$STATE"
}
load_state(){
  RUN_ID="$(read_field "$STATE" RUN_ID)"
  PARENT_RUN_ID="$(read_field "$STATE" PARENT_RUN_ID)"
  ORIGINAL_MODE="$(read_field "$STATE" ORIGINAL_MODE)"
  PHASE="$(read_field "$STATE" PHASE)"
  [[ "$RUN_ID" =~ ^[0-9]{8}T[0-9]{6}\.[0-9]{9}Z-07-xdp-drop$ ]]
  [[ "$PARENT_RUN_ID" =~ ^[A-Za-z0-9._-]+-02-trading-platform$ ]]
  case "$ORIGINAL_MODE" in UNICAST|MULTICAST|DUAL) ;; *) return 1;; esac
  case "$PHASE" in PREPARING|DROPPING|GAP_HELD|NEEDS_MANUAL_RESTART|RESTARTING|RESTART_FAILED|COMPLETE) ;; *) return 1;; esac
  OUT="$ROOT/Documents/reports/course-runs/$RUN_ID"; REMOTE="/var/tmp/$RUN_ID"
  test -d "$OUT/raw" && test -f "$OUT/run.env"
  test "$(read_field "$OUT/run.env" RUN_ID)" = "$RUN_ID"
  test "$(read_field "$OUT/run.env" PARENT_RUN_ID)" = "$PARENT_RUN_ID"
  test "$(read_field "$OUT/run.env" ORIGINAL_MODE)" = "$ORIGINAL_MODE"
  test "$(read_field "$PLATFORM_STATE" RUN_ID)" = "$PARENT_RUN_ID" || {
    echo '交易平台 RUN 已变化；停止自动操作，请核对原实验记录。' >&2; return 1;
  }
}
detach_owned(){
  remote2 "if test -f '$REMOTE/xdp-session.py'; then python3 '$REMOTE/xdp-session.py' detach; fi"
}
