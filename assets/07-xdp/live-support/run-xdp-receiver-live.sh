#!/usr/bin/env bash
# Drop once, pause replay, and leave the GAP for the reader. Never auto-recover.
set -Eeuo pipefail
cd /qyt-fll
source assets/07-xdp/live-support/xdp-run-state.sh
STAGE=检查前次运行态
STEP_LOG=
on_error(){
  local rc=$?
  printf '运行④失败：%s（退出码 %s）。\n' "$STAGE" "$rc" >&2
  if test -n "$STEP_LOG" && test -f "$STEP_LOG"; then
    tail -n 20 "$STEP_LOG" >&2
  fi
}
trap on_error ERR
acquire_filter_lock
exec 8>/run/lock/flle-platform-deploy.lock
flock -n 8 || { echo '交易平台正在部署或重启。' >&2; exit 1; }
if test -s "$STATE" && test "$(read_field "$STATE" PHASE)" != COMPLETE; then
  prepare_previous_run
fi
platform_run
RUN_ID="$(date -u +%Y%m%dT%H%M%S.%NZ)-07-xdp-drop"
OUT="$ROOT/reports/course-runs/$RUN_ID"; REMOTE="/var/tmp/$RUN_ID"
test ! -e "$OUT"; mkdir -p "$OUT/raw" "$OUT/artifacts" "$OUT/source" "${STATE%/*}"
SOURCE_SHA="$(sha256sum "$ASSET/flle_xdp_mold_itch.c" | cut -d' ' -f1)"
printf 'RUN_ID=%s\nPARENT_RUN_ID=%s\nSOURCE_SHA256=%s\n' "$RUN_ID" "$PARENT_RUN_ID" "$SOURCE_SHA" >"$OUT/run.env"
STAGE=检查平台与接收口; STEP_LOG="$OUT/raw/handoff-before.txt"
bash "$COMMON/check-filter-handoff.sh" receiver >"$STEP_LOG" 2>&1
STAGE=读取行情基线; STEP_LOG=
api_get >"$OUT/raw/state-before.json"
python3 - "$OUT/raw/state-before.json" <<'PREFLIGHT'
import json, sys
state = json.load(open(sys.argv[1]))
assert (state.get("feed") or {}).get("integrity") != "GAP", "已有行情缺口，请先处理原故障；本步不会清掉它再丢包"
PREFLIGHT
ORIGINAL_MODE="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["market_mode"])' "$OUT/raw/state-before.json")"
valid_market_mode "$ORIGINAL_MODE"
printf 'ORIGINAL_MODE=%s\n' "$ORIGINAL_MODE" >>"$OUT/run.env"
save_state PREPARING
DROP_ATTEMPTED=0
on_exit(){
  local rc=$?; trap - EXIT
  # Failed readback is not permission to replay or clear a real GAP.
  if test "$DROP_ATTEMPTED" = 1; then
    api_post replay '{"action":"PAUSE"}' >>"$OUT/raw/cleanup.txt" 2>&1 || true
  fi
  detach_owned >>"$OUT/raw/cleanup.txt" 2>&1 || true
  save_state NEEDS_MANUAL_RESTART || true
  printf '实验未完成（退出码 %s），未自动恢复行情。查看 %s，并按教师维护说明核对挂载与状态。\n' "$rc" "$OUT" >&2
  exit "$rc"
}
trap on_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
STAGE=准备行情接收器; STEP_LOG="$OUT/raw/feed-guardian.txt"
bash "$COMMON/feed-guardianctl.sh" direct --defer-feed-check >"$STEP_LOG" 2>&1
STAGE=分发过滤程序; STEP_LOG=
remote2 "set -Eeuo pipefail; ! ip -details link show dev ens64np1 | grep -q prog/xdp; mkdir '$REMOTE'"
cp "$ASSET/flle_xdp_mold_itch.c" "$ASSET/live-support/set-xdp-policy.py" "$ASSET/live-support/xdp-session.py" "$0" \
  "$COMMON/feed-guardianctl.sh" "$COMMON/wait-feed-state.py" \
  "$ASSET/live-support/xdp-run-state.sh" "$ASSET/live-support/wait-held-state.py" \
  "$ASSET/live-support/format-xdp-result.py" \
  "$OUT/source/"
timeout 45 scp -q "${FLLE_SSH_OPTS[@]}" "$ASSET/flle_xdp_mold_itch.c" "$ASSET/live-support/set-xdp-policy.py" "$ASSET/live-support/xdp-session.py" root@10.1.1.2:"$REMOTE/"

STAGE=编译并挂载XDP; STEP_LOG="$OUT/raw/attach.txt"
remote2 "set -Eeuo pipefail; cd '$REMOTE'; test \"\$(sha256sum flle_xdp_mold_itch.c | cut -d' ' -f1)\" = '$SOURCE_SHA'; clang -O2 -g -fdebug-prefix-map='$REMOTE'=/flle/ch07 -target bpf -D__TARGET_ARCH_x86 -I/usr/include/x86_64-linux-gnu -c flle_xdp_mold_itch.c -o flle_xdp_mold_itch.o; python3 xdp-session.py attach ens64np1" >"$STEP_LOG" 2>&1
STAGE=核对挂载身份; STEP_LOG=
printf '%s\n' '' 'vm-2522-02 / verify' '===== 查 XDP 挂载身份 =====' '[ens64np1] 对: prog/xdp / jited / native  证: 本次程序确实挂在客户端驱动接收口' '$ ip -details link show dev ens64np1'
remote2 "ip -details link show dev ens64np1" | tee "$OUT/raw/xdp-link-attached.txt" | python3 "$ASSET/live-support/format-xdp-result.py" link
grep -Eq ' mtu [0-9]+ xdp qdisc ' "$OUT/raw/xdp-link-attached.txt"
grep -Eq 'prog/xdp .* jited' "$OUT/raw/xdp-link-attached.txt"
! grep -Eq 'xdpgeneric|xdpoffload' "$OUT/raw/xdp-link-attached.txt"
PROG_ID="$(remote2 "python3 -c 'import json; print(json.load(open(\"$REMOTE/attachment.json\"))[\"program_id\"])'")"
[[ "$PROG_ID" =~ ^[0-9]+$ ]]
remote2 "bpftool -j prog show id '$PROG_ID'" >"$OUT/raw/xdp-program.json"
printf '%s\n' '' 'vm-2522-02 / verify' '===== 查初始放行策略 =====' '[policy] 对: remaining_drops=0  证: 接流时先全部放行，再观察健康基线' '$ python3 set-xdp-policy.py allow 0 5 "$PROG_ID"'
remote2 "cd '$REMOTE'; python3 set-xdp-policy.py allow 0 5 '$PROG_ID'"
STAGE=建立A路行情基线
api_post market '{"market_mode":"MULTICAST_A"}' >/dev/null

session_before="$(api_get | python3 -c 'import json,sys; print(json.load(sys.stdin)["session"])')"
api_post replay '{"action":"RESTART"}' >/dev/null
printf '%s\n' '' 'vm-2522-02 / verify' '===== 查行情放行基线 =====' '[Feed] 对: 新 Session / HEALTHY  证: 未武装时原行情可以穿过当前路径' '$ python3 "$COMMON/wait-feed-state.py" "$API/api/state" HEALTHY --timeout 25 --session-not "$session_before"'
python3 "$COMMON/wait-feed-state.py" "$API/api/state" HEALTHY --timeout 25 --session-not "$session_before" | tee "$OUT/raw/feed-baseline.json" | python3 "$ASSET/live-support/format-xdp-result.py" feed
api_get >"$OUT/raw/state-allow-all.json"

STAGE=丢一包并核对缺口
save_state DROPPING
DROP_ATTEMPTED=1
remote2 "cd '$REMOTE'; python3 set-xdp-policy.py block 1 5 '$PROG_ID'" >"$OUT/raw/policy-block.txt"
printf '%s\n' '' 'vm-2522-02 / verify' '===== 查行情缺口 =====' '[Feed] 对: GAP / gap_size=1 / 闸门关闭  证: 策略执行后接收器自己发现序号缺失' '$ python3 "$COMMON/wait-feed-state.py" "$API/api/state" GAP --timeout 12'
python3 "$COMMON/wait-feed-state.py" "$API/api/state" GAP --timeout 12 | tee "$OUT/raw/feed-gap.json" | python3 "$ASSET/live-support/format-xdp-result.py" feed
# Stop automatic replay loops from replacing this session while the reader observes.
api_post replay '{"action":"PAUSE"}' >"$OUT/raw/replay-paused.json"
api_get >"$OUT/raw/state-gap.json"
remote2 "python3 '$REMOTE/xdp-session.py' dump counters" >"$OUT/raw/xdp-counters.json"
remote2 "python3 '$REMOTE/xdp-session.py' dump drop_audit" >"$OUT/raw/xdp-drop-audit.json"
remote2 "ip -details link show dev ens64np1" >"$OUT/raw/xdp-link.txt"
timeout 45 scp -q "${FLLE_SSH_OPTS[@]}" root@10.1.1.2:"$REMOTE/flle_xdp_mold_itch.o" "$OUT/artifacts/"
printf 'OBJECT_SHA256=%s\n' "$(sha256sum "$OUT/artifacts/flle_xdp_mold_itch.o" | awk '{print $1}')" >>"$OUT/run.env"
printf '%s\n' '' 'vm-2522-02 / verify' '===== 查被丢序号与 Feed 对账 =====' '[XDP audit] 对: 恰好一包 / Locate 8095 / Sequence 等于 next_expected  证: 计数与行情缺口指向同一条消息' '$ python3 - <counters.json> <drop-audit.json> <feed-gap.json>'
python3 - "$OUT/raw/xdp-counters.json" "$OUT/raw/xdp-drop-audit.json" "$OUT/raw/feed-gap.json" <<'PY' | tee "$OUT/raw/drop-proof.txt" | python3 "$ASSET/live-support/format-xdp-result.py" proof
import json, sys
counters = json.load(open(sys.argv[1], encoding="utf-8"))
audit = json.load(open(sys.argv[2], encoding="utf-8"))[0]["formatted"]["value"]
gap = json.load(open(sys.argv[3], encoding="utf-8"))["feed"]
policy = next(row for row in counters if row["formatted"]["key"] == 6)
drops = sum(item["value"] for item in policy["formatted"]["values"])
assert gap["integrity"] == "GAP" and gap["trading_gate"] == "INHIBITED_FEED_GAP", gap
assert drops == 1, f"expected exactly one XDP drop, got {drops}"
assert audit["drops"] == 1, audit
assert audit["first_drop_sequence"] > 0, audit
assert audit["first_drop_locate"] == 8095, audit
assert audit["first_drop_sequence"] == gap["next_expected"], (audit, gap)
print(f'xdp_drop_packets={drops} sequence={audit["first_drop_sequence"]} locate={audit["first_drop_locate"]}')
PY

STAGE=卸载本次XDP并保留缺口
remote2 "cat '$REMOTE/attachment.json'" >"$OUT/raw/attachment.json"
detach_owned | tee "$OUT/raw/detach.txt"
remote2 'ip -details link show dev ens64np1' >"$OUT/raw/xdp-link-detached.txt"
! grep -q prog/xdp "$OUT/raw/xdp-link-detached.txt"
python3 "$ASSET/live-support/wait-held-state.py" "$API/api/state" "$OUT/raw/feed-gap.json" >"$OUT/raw/state-held.json"
printf '\n现场状态：行情有缺口，交易闸门暂停下单，回放已暂停。\n'
printf 'RECEIVER=10.1.1.2\nIFACE=ens64np1\nPROGRAM_ID=%s\n' "$PROG_ID" >>"$OUT/run.env"
save_state GAP_HELD
(cd "$OUT" && find raw artifacts source -type f -print0 | sort -z | xargs -0 sha256sum; sha256sum run.env) >"$OUT/SHA256SUMS"
trap - EXIT INT TERM ERR
printf 'result=GAP_HELD\n本次 XDP 已卸载，行情缺口保留；丢包后未重放或重启服务。\n打开 http://10.1.1.101:8088/ 观察 FEED GAP、冻结的订单簿和禁用的下单按钮。\n看完后在网页点击“重新开始并清空交易”；行情恢复后可再次运行本脚本。\nevidence=%s\n' "$OUT"
