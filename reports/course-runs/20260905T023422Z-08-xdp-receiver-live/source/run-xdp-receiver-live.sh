#!/usr/bin/env bash
# Chapter 08: native XDP on the Trader .2; no BMv2 or EOS changes.
# clear the policy, replay, and prove the Chapter 07 trading system is healthy.
set -Eeuo pipefail
cd /financial-low-latency
source Documents/newDoc/assets/common/flle-remote.sh
ROOT=/financial-low-latency
ASSET="$ROOT/Documents/newDoc/assets/08-xdp"
COMMON="$ROOT/Documents/newDoc/assets/common"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-08-xdp-receiver-live"
OUT="$ROOT/Documents/reports/course-runs/$RUN_ID"; REMOTE="/var/tmp/$RUN_ID"
API=http://10.1.1.101:8088
SOURCE_SHA="$(sha256sum "$ASSET/flle_xdp_mold_itch.c" | awk '{print $1}')"
test ! -e "$OUT"; mkdir -p "$OUT/raw" "$OUT/artifacts" "$OUT/source"
printf 'RUN_ID=%s\nSOURCE_SHA256=%s\n' "$RUN_ID" "$SOURCE_SHA" >"$OUT/run.env"
remote2(){ ssh -n "${FLLE_SSH_OPTS[@]}" root@10.1.1.2 "$@"; }

exec 9>/var/tmp/flle-ch08-10.lock
flock -n 9 || exit 1
bash "$COMMON/check-filter-handoff.sh" receiver >"$OUT/raw/handoff-before.txt"
bash "$COMMON/feed-guardianctl.sh" direct >"$OUT/raw/feed-guardian.txt"
ORIGINAL_MODE="$(curl -fsS "$API/api/state" | python3 -c 'import json,sys; print(json.load(sys.stdin)["market_mode"])')"
ARMED=1
cleanup(){
  local result=0
  remote2 "if test -f '$REMOTE/xdp-session.py'; then python3 '$REMOTE/xdp-session.py' detach; fi" >>"$OUT/raw/cleanup.txt" 2>&1 || result=1
  curl -fsS -X POST -H 'Content-Type: application/json' -d "{\"market_mode\":\"$ORIGINAL_MODE\"}" "$API/api/market" >>"$OUT/raw/cleanup.txt" || result=1
  bash "$COMMON/feed-guardianctl.sh" direct >"$OUT/raw/feed-guardian-restored.txt" 2>&1 || result=1
  curl -fsS -X POST -H 'Content-Type: application/json' -d '{"action":"RESTART"}' "$API/api/replay" >>"$OUT/raw/cleanup.txt" || result=1
  if test "$result" = 0; then
    remote2 "if test -d '$REMOTE'; then test ! -e '$REMOTE/attachment.json' && find '$REMOTE' -mindepth 1 -type f -delete && rmdir '$REMOTE'; fi" >>"$OUT/raw/cleanup.txt" 2>&1 || result=1
  fi
  return "$result"
}
on_exit(){ local rc=$?; trap - EXIT; if test "$ARMED" = 1; then cleanup || rc=1; fi; exit "$rc"; }
trap on_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

curl -fsS "$API/api/state" >"$OUT/raw/state-before.json"
remote2 "set -Eeuo pipefail; ! ip -details link show dev ens64np1 | grep -q prog/xdp; mkdir '$REMOTE'"
cp "$ASSET/flle_xdp_mold_itch.c" "$ASSET/live-support/set-xdp-policy.py" "$ASSET/live-support/xdp-session.py" "$0" \
  "$COMMON/feed-guardianctl.sh" "$COMMON/wait-feed-state.py" \
  "$COMMON/assert-feed-order-gate.py" "$COMMON/assert-feed-gap-ui.py" \
  "$COMMON/prove-trading-recovered.py" \
  "$OUT/source/"
scp -q "${FLLE_SSH_OPTS[@]}" "$ASSET/flle_xdp_mold_itch.c" "$ASSET/live-support/set-xdp-policy.py" "$ASSET/live-support/xdp-session.py" root@10.1.1.2:"$REMOTE/"

remote2 "set -Eeuo pipefail; cd '$REMOTE'; test \"\$(sha256sum flle_xdp_mold_itch.c | cut -d' ' -f1)\" = '$SOURCE_SHA'; clang -O2 -g -fdebug-prefix-map='$REMOTE'=/flle/ch08 -target bpf -D__TARGET_ARCH_x86 -I/usr/include/x86_64-linux-gnu -c flle_xdp_mold_itch.c -o flle_xdp_mold_itch.o; python3 xdp-session.py attach ens64np1" >"$OUT/raw/attach.txt" 2>&1
remote2 "ip -details link show dev ens64np1" | tee "$OUT/raw/xdp-link-attached.txt"
grep -Eq ' mtu [0-9]+ xdp qdisc ' "$OUT/raw/xdp-link-attached.txt"
grep -Eq 'prog/xdp .* jited' "$OUT/raw/xdp-link-attached.txt"
! grep -Eq 'xdpgeneric|xdpoffload' "$OUT/raw/xdp-link-attached.txt"
PROG_ID="$(remote2 "python3 -c 'import json; print(json.load(open(\"$REMOTE/attachment.json\"))[\"program_id\"])'")"
remote2 "bpftool -j prog show id '$PROG_ID'" >"$OUT/raw/xdp-program.json"
remote2 "cd '$REMOTE'; python3 set-xdp-policy.py allow 0 5 '$PROG_ID'"
curl -fsS -X POST -H 'Content-Type: application/json' -d '{"market_mode":"MULTICAST"}' "$API/api/market" >/dev/null

session_before="$(curl -fsS "$API/api/state" | python3 -c 'import json,sys; print(json.load(sys.stdin)["session"])')"
curl -fsS -X POST -H 'Content-Type: application/json' -d '{"action":"RESTART"}' "$API/api/replay" >/dev/null
python3 "$COMMON/wait-feed-state.py" "$API/api/state" HEALTHY --timeout 25 --session-not "$session_before" | tee "$OUT/raw/feed-baseline.json"
curl -fsS "$API/api/state" >"$OUT/raw/state-allow-all.json"

remote2 "cd '$REMOTE'; python3 set-xdp-policy.py block 1 5 '$PROG_ID'" >"$OUT/raw/policy-block.txt"
python3 "$COMMON/wait-feed-state.py" "$API/api/state" GAP --timeout 12 | tee "$OUT/raw/feed-gap.json"
curl -fsS "$API/api/state" >"$OUT/raw/state-gap.json"
python3 "$COMMON/assert-feed-order-gate.py" "$API" | tee "$OUT/raw/order-gate.json"
python3 "$COMMON/assert-feed-gap-ui.py" "$API" "$OUT/raw" | tee "$OUT/raw/gui-gap-contract.json"
remote2 "bpftool -j map dump name counters" >"$OUT/raw/xdp-counters.json"
remote2 "bpftool -j map dump name drop_audit" >"$OUT/raw/xdp-drop-audit.json"
remote2 "ip -details link show dev ens64np1" >"$OUT/raw/xdp-link.txt"
scp -q "${FLLE_SSH_OPTS[@]}" root@10.1.1.2:"$REMOTE/flle_xdp_mold_itch.o" "$OUT/artifacts/"
printf 'OBJECT_SHA256=%s\n' "$(sha256sum "$OUT/artifacts/flle_xdp_mold_itch.o" | awk '{print $1}')" >>"$OUT/run.env"
python3 - "$OUT/raw/xdp-counters.json" "$OUT/raw/xdp-drop-audit.json" "$OUT/raw/feed-gap.json" <<'PY'
import json, sys
counters = json.load(open(sys.argv[1], encoding="utf-8"))
audit = json.load(open(sys.argv[2], encoding="utf-8"))[0]["formatted"]["value"]
gap = json.load(open(sys.argv[3], encoding="utf-8"))["feed"]
policy = next(row for row in counters if row["formatted"]["key"] == 6)
drops = sum(item["value"] for item in policy["formatted"]["values"])
assert drops == 1, f"expected exactly one XDP drop, got {drops}"
assert audit["drops"] == 1, audit
assert audit["first_drop_sequence"] > 0, audit
assert audit["first_drop_locate"] == 8095, audit
assert audit["first_drop_sequence"] == gap["next_expected"], (audit, gap)
print(f'xdp_drop_packets={drops} sequence={audit["first_drop_sequence"]} locate={audit["first_drop_locate"]}')
PY

remote2 "cd '$REMOTE'; python3 set-xdp-policy.py allow 0 5 '$PROG_ID'" >"$OUT/raw/policy-allow.txt"
gap_session="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["session"])' "$OUT/raw/state-gap.json")"
curl -fsS -X POST -H 'Content-Type: application/json' -d '{"action":"RESTART"}' "$API/api/replay" >/dev/null
python3 "$COMMON/wait-feed-state.py" "$API/api/state" HEALTHY --timeout 25 --session-not "$gap_session" | tee "$OUT/raw/feed-recovered-inline.json"

cleanup; ARMED=0; trap - EXIT INT TERM
final_old_session="$(curl -fsS "$API/api/state" | python3 -c 'import json,sys; print(json.load(sys.stdin)["session"])')"
curl -fsS -X POST -H 'Content-Type: application/json' -d '{"action":"RESTART"}' "$API/api/replay" >/dev/null
python3 "$COMMON/wait-feed-state.py" "$API/api/state" HEALTHY --timeout 25 --session-not "$final_old_session" | tee "$OUT/raw/feed-final.json"
python3 "$COMMON/prove-trading-recovered.py" "$API" "$OUT/raw/post-restore-orders" | tee "$OUT/raw/post-restore-orders.json"
curl -fsS "$API/api/state" >"$OUT/raw/state-after.json"
bash "$COMMON/check-filter-handoff.sh" receiver >"$OUT/raw/handoff-after.txt"
printf 'ORIGINAL_MODE=%s\nRECEIVER=10.1.1.2\nIFACE=ens64np1\nPROGRAM_ID=%s\n' "$ORIGINAL_MODE" "$PROG_ID" >>"$OUT/run.env"
(cd "$OUT" && find raw artifacts source -type f -print0 | sort -z | xargs -0 sha256sum; sha256sum run.env) >"$OUT/SHA256SUMS"
printf '===== 第 08 章 inline XDP 实验 =====\nresult=PASS\npolicy=NVDA Type A locate 8095 one-shot DROP\nfeed=GAP -> replay -> HEALTHY\norder_gate=FEED_NOT_HEALTHY\npost_restore_orders=2/2 ORDER_EXECUTED; AAPL position unchanged\nevidence=%s\n' "$OUT"
