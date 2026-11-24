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
acquire_filter_lock(){
  # Use a chapter-independent name, but also contend with already-deployed
  # P4/RTL/reset scripts and old XDP processes that hold the legacy inode.
  # Never unlink/rename a live lock file: that would split mutual exclusion.
  exec 9>/var/tmp/flle-market-filter.lock || return 1
  if ! flock -n 9; then
    exec 9>&-
    echo '另一项过滤实验正在运行。' >&2; return 1
  fi
  if ! { exec 7>/var/tmp/flle-ch08-10.lock; }; then
    exec 9>&-
    return 1
  fi
  if ! flock -n 7; then
    exec 7>&- 9>&-
    echo '另一项过滤实验或交易重置正在运行。' >&2; return 1
  fi
}
platform_run(){
  test -s "$PLATFORM_STATE" || {
    echo '缺少第二章平台运行态；请先完成第二章上线。' >&2; return 1;
  }
  PARENT_RUN_ID="$(read_field "$PLATFORM_STATE" RUN_ID)"
  [[ "$PARENT_RUN_ID" =~ ^[A-Za-z0-9._-]+-02-trading-platform$ ]] || {
    echo '第二章平台 RUN_ID 无效；请核对平台运行态。' >&2; return 1;
  }
}
valid_market_mode(){
  case "$1" in UNICAST|MULTICAST|MULTICAST_A|MULTICAST_B|DUAL) return 0;; esac
  printf '无法识别行情模式：%s；保留原状态，未开始丢包。\n' "$1" >&2
  return 1
}
save_state(){
  PHASE="$1"
  printf 'RUN_ID=%s\nPARENT_RUN_ID=%s\nORIGINAL_MODE=%s\nPHASE=%s\n' \
    "$RUN_ID" "$PARENT_RUN_ID" "$ORIGINAL_MODE" "$PHASE" >"$OUT/state.env"
  cp "$OUT/state.env" "$STATE.tmp.$BASHPID"
  mv "$STATE.tmp.$BASHPID" "$STATE"
}
load_saved_state(){
  RUN_ID="$(read_field "$STATE" RUN_ID)"
  PARENT_RUN_ID="$(read_field "$STATE" PARENT_RUN_ID)"
  ORIGINAL_MODE="$(read_field "$STATE" ORIGINAL_MODE)"
  PHASE="$(read_field "$STATE" PHASE)"
  [[ "$RUN_ID" =~ ^[0-9]{8}T[0-9]{6}\.[0-9]{9}Z-07-xdp-drop$ &&
     "$PARENT_RUN_ID" =~ ^[A-Za-z0-9._-]+-02-trading-platform$ ]] || {
    printf '旧实验运行态身份无效：%s；请核对原文件。\n' "$STATE" >&2; return 1;
  }
  valid_market_mode "$ORIGINAL_MODE" || return 1
  case "$PHASE" in PREPARING|DROPPING|GAP_HELD|NEEDS_MANUAL_RESTART|RESTARTING|RESTART_FAILED|COMPLETE) ;;
    *) printf '旧实验阶段无效：%s；保留原记录。\n' "$PHASE" >&2; return 1;; esac
  OUT="$ROOT/Documents/reports/course-runs/$RUN_ID"; REMOTE="/var/tmp/$RUN_ID"
  test -d "$OUT/raw" || {
    printf '缺少原实验取证目录：%s；请检查或恢复原目录，保留当前运行态。\n' "$OUT/raw" >&2
    return 1
  }
  test -f "$OUT/run.env" || {
    printf '缺少原实验身份文件：%s；请检查或恢复原文件，保留当前运行态。\n' "$OUT/run.env" >&2
    return 1
  }
  local field
  for field in RUN_ID PARENT_RUN_ID ORIGINAL_MODE; do
    test "$(read_field "$OUT/run.env" "$field")" = "${!field}" || {
      printf '旧实验 %s 与原记录不一致：%s；保留原状态。\n' "$field" "$OUT/run.env" >&2; return 1;
    }
  done
}
load_state(){
  load_saved_state || return 1
  test "$(read_field "$PLATFORM_STATE" RUN_ID)" = "$PARENT_RUN_ID" || {
    echo '交易平台 RUN 已变化；停止自动操作，请核对原实验记录。' >&2; return 1;
  }
}
prepare_previous_run(){
  # A retained jump host can carry an unfinished record from a replaced platform.
  # Never restart/detach that old run or claim it was recovered on the new one.
  platform_run || return 1
  local current_parent="$PARENT_RUN_ID"
  if test "$(read_field "$STATE" PARENT_RUN_ID)" = "$current_parent"; then
    acknowledge_recovery
    return
  fi
  load_saved_state || return 1
  local controller_status current_state current_handoff archive_out
  controller_status="$(timeout 60 bash "$ROOT/apps/flle-trading-lab/scripts/transport_labctl.sh" controller-check "$current_parent" 2>&1)" || {
    printf '%s\n当前平台身份未确认，旧实验记录保持不变。\n' "$controller_status" >&2; return 1;
  }
  current_state="$(api_get)" || {
    echo '无法读取当前行情，旧实验记录保持不变。' >&2; return 1;
  }
  if ! printf '%s' "$current_state" | python3 -c '
import json, sys
try:
    state = json.load(sys.stdin)
    feed = state.get("feed") or {}
    session = state.get("session")
    ready = (bool(session) and feed.get("session") == session
             and feed.get("integrity") == "HEALTHY" and feed.get("trading_gate") == "OPEN"
             and feed.get("pending") == 0 and feed.get("next_expected", 0) > 1
             and not feed.get("resync_required", False)
             and (state.get("replay") or {}).get("status") == "PLAYING")
except (ValueError, TypeError, AttributeError):
    ready = False
if not ready:
    sys.exit("新平台行情尚未正常播放，旧实验记录保持不变；请核对网页行情状态。")
'; then return 1; fi
  current_handoff="$(bash "$COMMON/check-filter-handoff.sh" receiver 2>&1)" || {
    printf '%s\n接收口交接未通过，旧实验记录保持不变。\n' "$current_handoff" >&2; return 1;
  }
  test "$(read_field "$PLATFORM_STATE" RUN_ID)" = "$current_parent" || {
    echo '核验期间平台身份变化，旧实验记录保持不变。' >&2; return 1;
  }
  archive_out="$OUT/platform-replaced-$(date -u +%Y%m%dT%H%M%S.%NZ)"
  mkdir "$archive_out" || return 1
  cp "$STATE" "$archive_out/previous-state.env" || return 1
  printf 'REASON=PLATFORM_REPLACED\nOLD_PLATFORM=%s\nCURRENT_PLATFORM=%s\n' \
    "$PARENT_RUN_ID" "$current_parent" >"$archive_out/replacement.env" || return 1
  printf '%s\n' "$current_state" >"$archive_out/state.json" || return 1
  printf '%s\n' "$current_handoff" >"$archive_out/handoff.txt" || return 1
  printf '%s\n' "$controller_status" >"$archive_out/controller-check.txt" || return 1
  (cd "$archive_out" && sha256sum previous-state.env replacement.env state.json handoff.txt controller-check.txt >SHA256SUMS) || return 1
  cmp -s "$STATE" "$archive_out/previous-state.env" || return 1
  mv -- "$STATE" "$archive_out/previous-state.env" || return 1
  printf '旧实验属于已更换的平台，已归档；当前平台与接收口检查通过，继续本次实验。\n'
}
detach_owned(){
  remote2 "if test -f '$REMOTE/xdp-session.py'; then python3 '$REMOTE/xdp-session.py' detach; fi"
}
check_recovery_ready(){
  # Read-only: load_state must already have validated the saved run identity.
  test "$PHASE" = GAP_HELD || {
    echo '上次实验异常退出；先按教师维护说明核对挂载与运行态。' >&2; return 1;
  }
  test -s "$OUT/raw/state-held.json" && test -r "$OUT/raw/state-held.json" || {
    printf '旧缺口取证文件缺失、为空或不可读：%s；请检查或恢复原文件，网页重启不能补回它。\n' "$OUT/raw/state-held.json" >&2
    return 1
  }
  RECOVERY_STATE="$(api_get)" || {
    echo '无法读取当前行情状态，保留上次记录；请确认交易网页服务可连接。' >&2; return 1;
  }
  if ! printf '%s' "$RECOVERY_STATE" | python3 -c '
import json, sys
try:
    old = json.load(open(sys.argv[1]))
except (OSError, ValueError):
    sys.exit("旧缺口取证文件无法读取或解析：%s；请检查或恢复原文件。" % sys.argv[1])
if not isinstance(old, dict) or not old.get("session"):
    sys.exit("旧缺口取证文件缺少有效会话：%s；请核对原文件。" % sys.argv[1])
try:
    state = json.load(sys.stdin)
except ValueError:
    sys.exit("行情 API 返回无法解析的 JSON；请检查服务响应，保留上次记录。")
feed = state.get("feed") or {}
session = state.get("session")
ready = (bool(old.get("session")) and bool(session) and session != old["session"]
         and feed.get("session") == session and feed.get("integrity") == "HEALTHY"
         and feed.get("trading_gate") == "OPEN" and feed.get("pending") == 0
         and feed.get("next_expected", 0) > 1 and not feed.get("resync_required", False))
if not ready:
    sys.exit("行情尚未确认恢复：session=%s integrity=%s trading_gate=%s。"
             "看完报错后，在网页点击“重新开始并清空交易”，等待行情正常后再运行。" %
             (session, feed.get("integrity"), feed.get("trading_gate")))
' "$OUT/raw/state-held.json"; then
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
