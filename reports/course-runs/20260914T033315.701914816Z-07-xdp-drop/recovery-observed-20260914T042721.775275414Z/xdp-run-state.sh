#!/usr/bin/env bash
# Shared by the foreground drop and the optional full-service restart.
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
check_recovery_ready(){
  # Read-only: load_state must already have validated the saved run identity.
  test "$PHASE" = GAP_HELD || {
    echo '上次实验异常退出；先按教师维护说明核对挂载与运行态。' >&2; return 1;
  }
  RECOVERY_STATE="$(api_get)" || {
    echo '无法读取当前行情状态，保留上次记录；请确认交易网页服务可连接。' >&2; return 1;
  }
  if ! printf '%s' "$RECOVERY_STATE" | python3 -c '
import json, sys
old = json.load(open(sys.argv[1]))
state = json.load(sys.stdin)
feed = state.get("feed") or {}
session = state.get("session")
ready = (bool(old.get("session")) and bool(session) and session != old["session"]
         and feed.get("session") == session and feed.get("integrity") == "HEALTHY"
         and feed.get("trading_gate") == "OPEN" and feed.get("pending") == 0
         and feed.get("next_expected", 0) > 1 and not feed.get("resync_required", False))
if not ready:
    sys.exit("行情尚未确认恢复：session=%s integrity=%s trading_gate=%s" %
             (session, feed.get("integrity"), feed.get("trading_gate")))
' "$OUT/raw/state-held.json"; then
    echo '看完报错后，在网页点击“重新开始并清空交易”，等待行情正常后再运行。' >&2
    return 1
  fi
  RECOVERY_HANDOFF="$(bash "$COMMON/check-filter-handoff.sh" receiver 2>&1)" || {
    printf '%s\n' "$RECOVERY_HANDOFF" >&2
    echo '接收口交接检查未通过，保留上次运行态；请核对驱动和过滤程序。' >&2
    return 1
  }
}
acknowledge_recovery(){
  # Only a fresh user invocation reaches here; no background reset or replay.
  load_state
  check_recovery_ready
  local recovery_out="$OUT/recovery-observed-$(date -u +%Y%m%dT%H%M%S.%NZ)"
  mkdir "$recovery_out"
  printf '%s\n' "$RECOVERY_STATE" >"$recovery_out/state.json"
  printf '%s\n' "$RECOVERY_HANDOFF" >"$recovery_out/handoff.txt"
  cp "$ASSET/live-support/xdp-run-state.sh" "$recovery_out/"
  (cd "$recovery_out" && sha256sum state.json handoff.txt xdp-run-state.sh >SHA256SUMS)
  save_state COMPLETE
  printf '已确认新行情会话 HEALTHY / OPEN，上次实验已完成。\n'
}
