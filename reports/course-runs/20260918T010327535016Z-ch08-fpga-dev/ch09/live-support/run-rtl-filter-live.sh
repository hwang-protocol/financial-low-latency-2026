#!/usr/bin/env bash
# Chapter 10: let a local Verilated RTL model decide PASS/DROP for the same
# real multicast feed, then restore the Trader's direct receiver profile.
set -Eeuo pipefail
cd /financial-low-latency
source Documents/newDoc/assets/common/flle-remote.sh
ROOT=/financial-low-latency
ASSET="$ROOT/Documents/newDoc/assets/09-verilator"
COMMON="$ROOT/Documents/newDoc/assets/common"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-10-rtl-filter-live"
OUT="$ROOT/Documents/reports/course-runs/$RUN_ID"; REMOTE="/var/tmp/$RUN_ID"
API=http://10.1.1.101:8088
test ! -e "$OUT"; mkdir -p "$OUT/raw" "$OUT/artifacts" "$OUT/source"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
printf 'BUILD_HOST=10.1.1.2\nRTL_HOST=10.1.1.2\n' >>"$OUT/run.env"
cp "$OUT/run.env" "$ROOT/Documents/reports/run-state/10-rtl-filter-live.env"
printf '完整日志：%s/raw/\n' "$OUT"
remote2(){ ssh -n "${FLLE_SSH_OPTS[@]}" root@10.1.1.2 "$@"; }

exec 9>/var/tmp/flle-ch08-10.lock
flock -n 9 || exit 1
bash "$COMMON/check-filter-handoff.sh" bridge >"$OUT/raw/handoff-before.txt"
bash "$COMMON/feed-guardianctl.sh" direct >"$OUT/raw/feed-guardian.txt"
ORIGINAL_MODE="$(curl -fsS "$API/api/state" | python3 -c 'import json,sys; print(json.load(sys.stdin)["market_mode"])')"
ARMED=1
cleanup(){
  set +e
  remote2 "printf 'allow\n' > /var/tmp/flle-market-filter.cmd"
  curl -fsS -X POST -H 'Content-Type: application/json' -d "{\"market_mode\":\"$ORIGINAL_MODE\"}" "$API/api/market" >/dev/null
  remote2 "if test -s '$REMOTE/adapter.pid' && test -s '$REMOTE/adapter.identity'; then pid=\$(cat '$REMOTE/adapter.pid'); read -r pf sf bf extra <'$REMOTE/adapter.identity'; test -z \"\${extra:-}\"; test \"\$pf\" = \"pid=\$pid\"; if test -r /proc/\$pid/cmdline; then test \"\$(awk '{print \$22}' /proc/\$pid/stat)\" = \"\${sf#start_ticks=}\"; test \"\$(cat /proc/sys/kernel/random/boot_id)\" = \"\${bf#boot_id=}\"; tr '\\0' ' ' </proc/\$pid/cmdline | grep -Fq '$REMOTE/mold_filter_adapter'; kill \"\$pid\" 2>/dev/null || true; for n in 1 2 3 4 5; do kill -0 \"\$pid\" 2>/dev/null || break; sleep 1; done; fi; fi; rm -f /var/tmp/flle-market-filter.cmd; find '$REMOTE' -mindepth 1 -delete 2>/dev/null; rmdir '$REMOTE' 2>/dev/null || true"
  curl -fsS -X POST -H 'Content-Type: application/json' -d '{"action":"RESTART"}' "$API/api/replay" >/dev/null
  bash "$COMMON/feed-guardianctl.sh" direct >"$OUT/raw/feed-guardian-restored.txt" 2>&1
  set -e
}
trap 'if [ "$ARMED" = 1 ]; then cleanup; fi' EXIT INT TERM

curl -fsS "$API/api/state" >"$OUT/raw/state-before.json"
remote2 "test ! -e /var/tmp/flle-market-filter.cmd; ! ps -eo args | grep -q '[m]old_filter_adapter'"
remote2 "mkdir '$REMOTE'"
scp -q "${FLLE_SSH_OPTS[@]}" "$ASSET/market_filter.sv" "$ASSET/mold_filter_adapter.cpp" root@10.1.1.2:"$REMOTE/"
printf '%s\n' '' 'vm-2522-02 / build' '===== 查RTL 构建与六项自测 =====' '[Verilator] 对: 构建成功 / 六个case均为1  证: 先验证周期逻辑，再把模型接到真实行情' '$ verilator --cc --exe --build ...；obj_dir/mold_filter_adapter --selftest'
remote2 "set -Eeuo pipefail; cd '$REMOTE'; verilator --cc --exe --build --Wall -Wno-fatal --top-module market_filter -o mold_filter_adapter market_filter.sv mold_filter_adapter.cpp; test -x obj_dir/mold_filter_adapter; obj_dir/mold_filter_adapter --selftest" 2>&1 | tee "$OUT/raw/build-and-selftest.txt" | python3 "$ASSET/live-support/classroom-output.py" selftest
grep -Fq 'rtl_selftest=PASS' "$OUT/raw/build-and-selftest.txt"
scp -q "${FLLE_SSH_OPTS[@]}" root@10.1.1.2:"$REMOTE/obj_dir/mold_filter_adapter" "$OUT/artifacts/"
remote2 "cp '$REMOTE/obj_dir/mold_filter_adapter' '$REMOTE/mold_filter_adapter'"
cp "$ASSET/market_filter.sv" "$ASSET/mold_filter_adapter.cpp" "$ASSET/live-support/classroom-output.py" "$0" \
  "$COMMON/feed-guardianctl.sh" "$COMMON/wait-feed-state.py" \
  "$COMMON/assert-feed-order-gate.py" "$COMMON/assert-feed-gap-ui.py" \
  "$COMMON/prove-trading-recovered.py" \
  "$OUT/source/"

# Restart flle-feed-receiver with --multicast-receiver 0; the Guardian consumes
# feed.sock. Multicast must traverse the adapter and then UDP port 42121.
bash "$COMMON/feed-guardianctl.sh" unicast-only >"$OUT/raw/feed-guardian-unicast-only.txt"
remote2 "set -Eeuo pipefail; chmod +x '$REMOTE/mold_filter_adapter'; rm -f /var/tmp/flle-market-filter.cmd; cd /; nohup env FLLE_FILTER_MODE=allow FLLE_REMAINING_DROPS=1 '$REMOTE/mold_filter_adapter' >'$REMOTE/adapter.log' 2>&1 </dev/null & pid=\$!; start=\$(awk '{print \$22}' /proc/\$pid/stat); boot=\$(cat /proc/sys/kernel/random/boot_id); printf '%s\\n' \"\$pid\" >'$REMOTE/adapter.pid'; printf 'pid=%s start_ticks=%s boot_id=%s\\n' \"\$pid\" \"\$start\" \"\$boot\" >'$REMOTE/adapter.identity'; for n in 1 2 3 4 5; do grep -Fq adapter_ready '$REMOTE/adapter.log' && exit 0; sleep 1; done; cat '$REMOTE/adapter.log' >&2; exit 1"
curl -fsS -X POST -H 'Content-Type: application/json' -d '{"market_mode":"MULTICAST_A"}' "$API/api/market" >/dev/null

session_before="$(curl -fsS "$API/api/state" | python3 -c 'import json,sys; print(json.load(sys.stdin)["session"])')"
curl -fsS -X POST -H 'Content-Type: application/json' -d '{"action":"RESTART"}' "$API/api/replay" >/dev/null
printf '%s\n' '' 'vm-2522-02 / verify' '===== 查行情放行基线 =====' '[Feed] 对: 新 Session / HEALTHY  证: 未武装时原行情可以穿过当前路径' '$ python3 "$COMMON/wait-feed-state.py" "$API/api/state" HEALTHY --timeout 25 --session-not "$session_before"'
python3 "$COMMON/wait-feed-state.py" "$API/api/state" HEALTHY --timeout 25 --session-not "$session_before" | tee "$OUT/raw/feed-baseline.json" | python3 "$ASSET/live-support/classroom-output.py" feed
curl -fsS "$API/api/state" >"$OUT/raw/state-allow-all.json"

remote2 "printf 'block\n' > /var/tmp/flle-market-filter.cmd"
printf '%s\n' '' 'vm-2522-02 / verify' '===== 查行情缺口 =====' '[Feed] 对: GAP / gap_size=1 / 闸门关闭  证: 策略执行后接收器自己发现序号缺失' '$ python3 "$COMMON/wait-feed-state.py" "$API/api/state" GAP --timeout 12'
python3 "$COMMON/wait-feed-state.py" "$API/api/state" GAP --timeout 12 | tee "$OUT/raw/feed-gap.json" | python3 "$ASSET/live-support/classroom-output.py" feed
curl -fsS "$API/api/state" >"$OUT/raw/state-gap.json"
printf '%s\n' '' 'vm-2522-02 / verify' '===== 查缺口期间拒单 =====' '[订单 API] 对: HTTP 400 / FEED_NOT_HEALTHY  证: 行情不完整时交易闸门确实拒绝下单' '$ python3 "$COMMON/assert-feed-order-gate.py" "$API"'
python3 "$COMMON/assert-feed-order-gate.py" "$API" | tee "$OUT/raw/order-gate.json" | python3 "$ASSET/live-support/classroom-output.py" gate
printf '%s\n' '' 'vm-2522-02 / verify' '===== 查界面与 GAP 状态合同 =====' '[GUI] 对: 红条、灰簿、按钮合同通过  证: 页面源与 live 状态一致；不是浏览器截图' '$ python3 "$COMMON/assert-feed-gap-ui.py" "$API" "$OUT/raw"'
python3 "$COMMON/assert-feed-gap-ui.py" "$API" "$OUT/raw" | tee "$OUT/raw/gui-gap-contract.json" | python3 "$ASSET/live-support/classroom-output.py" gui
remote2 "printf 'allow\n' > /var/tmp/flle-market-filter.cmd; for n in 1 2 3 4 5; do test ! -e /var/tmp/flle-market-filter.cmd && exit 0; sleep 1; done; exit 1"

gap_session="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["session"])' "$OUT/raw/state-gap.json")"
curl -fsS -X POST -H 'Content-Type: application/json' -d '{"action":"RESTART"}' "$API/api/replay" >/dev/null
printf '%s\n' '' 'vm-2522-02 / verify' '===== 查撤销策略后重放 =====' '[Feed] 对: 新 Session / HEALTHY  证: 关闭丢包后重建完整订单簿' '$ python3 "$COMMON/wait-feed-state.py" "$API/api/state" HEALTHY --timeout 25 --session-not "$gap_session"'
python3 "$COMMON/wait-feed-state.py" "$API/api/state" HEALTHY --timeout 25 --session-not "$gap_session" | tee "$OUT/raw/feed-recovered-adapter.json" | python3 "$ASSET/live-support/classroom-output.py" feed
printf '%s\n' '' 'vm-2522-02 / verify' '===== 查模型武装与丢包日志 =====' '[adapter] 对: 初始额度0 / 武装1 / drop_count=1  证: 只有收到block后才开放一次性丢包额度' '$ cat <本次远端目录>/adapter.log'
remote2 "cat '$REMOTE/adapter.log'" | tee "$OUT/raw/adapter.log"
test "$(grep -c '^rtl_drop ' "$OUT/raw/adapter.log")" -eq 1
printf '%s\n' '' '跳板机 / verify' '===== 查RTL 序号对账 =====' '[Sequence] 对: rtl_drop sequence 等于 Feed next_expected  证: 模型丢弃与行情缺口指向同一包' '$ python3 - "$OUT/raw/adapter.log" "$OUT/raw/feed-gap.json"'
python3 - "$OUT/raw/adapter.log" "$OUT/raw/feed-gap.json" <<'PY'
import json, re, sys
line = next(x for x in open(sys.argv[1], encoding="utf-8") if x.startswith("rtl_drop "))
sequence = int(re.search(r"sequence=(\d+)", line).group(1))
gap = json.load(open(sys.argv[2], encoding="utf-8"))["feed"]
assert sequence == gap["next_expected"], (sequence, gap)
print(f"rtl_drop_sequence={sequence} matches_feed_next_expected")
PY

cleanup; ARMED=0; trap - EXIT INT TERM
final_old_session="$(curl -fsS "$API/api/state" | python3 -c 'import json,sys; print(json.load(sys.stdin)["session"])')"
curl -fsS -X POST -H 'Content-Type: application/json' -d '{"action":"RESTART"}' "$API/api/replay" >/dev/null
printf '%s\n' '' 'vm-2522-02 / verify' '===== 查清理后的行情 =====' '[Feed] 对: 新 Session / HEALTHY  证: 卸载过滤层后原订阅路径恢复' '$ python3 "$COMMON/wait-feed-state.py" "$API/api/state" HEALTHY --timeout 25 --session-not "$final_old_session"'
python3 "$COMMON/wait-feed-state.py" "$API/api/state" HEALTHY --timeout 25 --session-not "$final_old_session" | tee "$OUT/raw/feed-final.json" | python3 "$ASSET/live-support/classroom-output.py" feed
printf '%s\n' '' 'vm-2522-02 / verify' '===== 查恢复后两笔订单 =====' '[OUCH] 对: 两笔成交 / AAPL 净持仓不变  证: 业务恢复覆盖真实协议下单与回执' '$ python3 "$COMMON/prove-trading-recovered.py" "$API" "$OUT/raw/post-restore-orders"'
python3 "$COMMON/prove-trading-recovered.py" "$API" "$OUT/raw/post-restore-orders" | tee "$OUT/raw/post-restore-orders.json" | python3 "$ASSET/live-support/classroom-output.py" orders
curl -fsS "$API/api/state" >"$OUT/raw/state-after.json"
remote2 "test ! -e /var/tmp/flle-market-filter.cmd; ! ps -eo args | grep -q '[m]old_filter_adapter'"
printf 'ORIGINAL_MODE=%s\nADAPTER_PATH=multicast-31032-to-unicast-42121\n' "$ORIGINAL_MODE" >>"$OUT/run.env"
cp "$OUT/run.env" "$ROOT/Documents/reports/run-state/10-rtl-filter-live.env"
bash "$COMMON/check-filter-handoff.sh" bridge >"$OUT/raw/handoff-after.txt"
(cd "$OUT" && find raw artifacts source -type f -print0 | sort -z | xargs -0 sha256sum; sha256sum run.env) >"$OUT/SHA256SUMS"
printf '===== 第 09 章 Verilated RTL inline 实验 =====\nresult=PASS\npolicy=NVDA Type A locate 8095 one-shot DROP\nrtl_selftest=PASS\nfeed=GAP -> replay -> HEALTHY\norder_gate=FEED_NOT_HEALTHY\npost_restore_orders=2/2 ORDER_EXECUTED; AAPL position unchanged\nevidence=%s\n' "$OUT"
