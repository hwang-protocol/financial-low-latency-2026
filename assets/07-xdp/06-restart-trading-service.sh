#!/usr/bin/env bash
# Optional full-service restart for troubleshooting; normal recovery uses the web UI.
set -Eeuo pipefail
cd /qyt-fll
source assets/07-xdp/live-support/xdp-run-state.sh
acquire_filter_lock
exec 8>/run/lock/flle-platform-deploy.lock
flock -n 8 || { echo '交易平台正在部署或重启。' >&2; exit 1; }
test -s "$STATE" || { echo '没有已保存的第07章丢包运行态。' >&2; exit 1; }
load_state
if test "$PHASE" = COMPLETE; then echo '本次实验已确认恢复。'; exit; fi
RESTART_OUT="$OUT/restart-$(date -u +%Y%m%dT%H%M%S.%NZ)"
mkdir "$RESTART_OUT"
cp "$0" "$ASSET/live-support/xdp-run-state.sh" "$RESTART_OUT/"
on_exit(){
  local rc=$?; trap - EXIT
  save_state RESTART_FAILED || true
  printf '重启未完成（退出码 %s），请查 %s；修复后可重试本入口。\n' "$rc" "$RESTART_OUT" >&2
  exit "$rc"
}
trap on_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
# Foreign attachments or other filter experiments must be resolved before stop.
detach_owned >"$RESTART_OUT/detach.txt" 2>&1
remote2 "set -eu; link=\$(ip -details link show dev ens64np1); test -n \"\$link\"; ! printf '%s' \"\$link\" | grep -q prog/xdp" >"$RESTART_OUT/filter-check.txt" 2>&1
save_state RESTARTING
CTL="$ROOT/apps/flle-trading-lab/scripts/transport_labctl.sh"
printf '\n===== 停止整套交易服务 =====\n'
timeout 180 bash "$CTL" stop "$PARENT_RUN_ID" >"$RESTART_OUT/stop.txt" 2>&1
printf '\n===== 启动整套交易服务 =====\n'
timeout 240 bash "$CTL" baseline "$PARENT_RUN_ID" >"$RESTART_OUT/start.txt" 2>&1
api_post market "{\"market_mode\":\"$ORIGINAL_MODE\"}" >"$RESTART_OUT/market.json"
api_get >"$RESTART_OUT/state-started.json"
session_before="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["session"])' "$RESTART_OUT/state-started.json")"
api_post replay '{"action":"RESTART"}' >"$RESTART_OUT/replay.json"
printf '\n===== 查重启后的行情 =====\n'
python3 "$COMMON/wait-feed-state.py" "$API/api/state" HEALTHY --timeout 25 --session-not "$session_before" | tee "$RESTART_OUT/feed-healthy.json"
python3 - "$RESTART_OUT/feed-healthy.json" <<'PY'
import json, sys
feed = json.load(open(sys.argv[1]))["feed"]
assert feed["trading_gate"] == "OPEN", feed
PY
timeout 90 bash "$CTL" verify "$PARENT_RUN_ID" >"$RESTART_OUT/verify.txt" 2>&1
bash "$COMMON/check-filter-handoff.sh" receiver >"$RESTART_OUT/handoff-after.txt"
api_get >"$RESTART_OUT/state-after.json"
(cd "$RESTART_OUT" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum >SHA256SUMS)
save_state COMPLETE
trap - EXIT INT TERM
printf 'result=RESTARTED\nfeed=HEALTHY trading_gate=OPEN\n已重启交易所、行情接收器、客户端、控制器和网页后台。刷新网页查看恢复结果。\nevidence=%s\n' "$RESTART_OUT"
