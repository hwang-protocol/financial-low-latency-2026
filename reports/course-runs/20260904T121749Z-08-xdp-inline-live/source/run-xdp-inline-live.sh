#!/usr/bin/env bash
# Chapter 08: put XDP inline, drop one real NVDA Type A packet, observe GAP,
# clear the policy, replay, and prove the Chapter 07 trading system is healthy.
set -Eeuo pipefail
cd /financial-low-latency
source Documents/newDoc/assets/common/flle-remote.sh
ROOT=/financial-low-latency
ASSET="$ROOT/Documents/newDoc/assets/08-xdp"
P4="$ROOT/Documents/newDoc/assets/09-p4"
COMMON="$ROOT/Documents/newDoc/assets/common"
EOS="$COMMON/eos_cli.py"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-08-xdp-inline-live"
OUT="$ROOT/Documents/reports/course-runs/$RUN_ID"; REMOTE="/var/tmp/$RUN_ID"
API=http://10.1.1.101:8088
test ! -e "$OUT"; mkdir -p "$OUT/raw" "$OUT/artifacts" "$OUT/source"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
remote11(){ ssh -n "${FLLE_SSH_OPTS[@]}" root@10.1.1.11 "$@"; }

bash "$COMMON/feed-guardianctl.sh" direct >"$OUT/raw/feed-guardian.txt"
ORIGINAL_MODE="$(curl -fsS "$API/api/state" | python3 -c 'import json,sys; print(json.load(sys.stdin)["market_mode"])')"
ARMED=1; DEADMAN_PID=
cleanup(){
  set +e
  if test -n "$DEADMAN_PID"; then kill "$DEADMAN_PID" 2>/dev/null; wait "$DEADMAN_PID" 2>/dev/null; fi
  remote11 "cd '$REMOTE' 2>/dev/null && python3 set-xdp-policy.py allow 0 5 >/dev/null 2>&1 || true"
  python3 "$EOS" --plan "$P4/p4-trading-restore-endpoints.plan" --output "$OUT/raw/eos-restore-endpoints.txt" --mode controlled-config >/dev/null
  remote11 "ip link set dev ens64f0np0 xdp off 2>/dev/null || true; if test -s '$REMOTE/simple_switch.pid'; then pid=\$(cat '$REMOTE/simple_switch.pid'); kill \"\$pid\" 2>/dev/null || true; for n in 1 2 3 4 5; do kill -0 \"\$pid\" 2>/dev/null || break; sleep 1; done; fi; ip link set dev ens64f0np0 down; ip link set dev ens64f1np1 down; find '$REMOTE' -mindepth 1 -delete 2>/dev/null; rmdir '$REMOTE' 2>/dev/null || true"
  python3 "$EOS" --plan "$P4/p4-trading-restore-final.plan" --output "$OUT/raw/eos-restore-final.txt" --mode controlled-config >/dev/null
  curl -fsS -X POST -H 'Content-Type: application/json' -d "{\"market_mode\":\"$ORIGINAL_MODE\"}" "$API/api/market" >/dev/null
  curl -fsS -X POST -H 'Content-Type: application/json' -d '{"action":"RESTART"}' "$API/api/replay" >/dev/null
  bash "$COMMON/feed-guardianctl.sh" direct >"$OUT/raw/feed-guardian-restored.txt" 2>&1
  set -e
}
trap 'if [ "$ARMED" = 1 ]; then cleanup; fi' EXIT INT TERM

curl -fsS "$API/api/state" >"$OUT/raw/state-before.json"
python3 "$EOS" --plan "$P4/p4-trading-show.plan" --output "$OUT/raw/eos-before.txt" --mode show >/dev/null
grep -q 'VLAN 100 not found' "$OUT/raw/eos-before.txt"
grep -q 'VLAN 200 not found' "$OUT/raw/eos-before.txt"
remote11 "set -Eeuo pipefail; ! pgrep -x simple_switch; ! ip -details link show dev ens64f0np0 | grep -q prog/xdp; ! ip -o addr show dev ens64f0np0 | grep -q .; ! ip -o addr show dev ens64f1np1 | grep -q .; mkdir '$REMOTE'"
FLLE_DEADMAN_DELAY=240 nohup bash "$P4/live-support/deadman-restore.sh" "$RUN_ID" "$ORIGINAL_MODE" >"$OUT/raw/deadman.log" 2>&1 & DEADMAN_PID=$!

scp -q "${FLLE_SSH_OPTS[@]}" "$P4/trading_l2_bridge.p4" root@10.1.1.101:"$REMOTE.p4"
ssh -n "${FLLE_SSH_OPTS[@]}" root@10.1.1.101 "p4c-bm2-ss --p4v 16 --p4runtime-files '$REMOTE.p4info.txt' -o '$REMOTE.json' '$REMOTE.p4'"
scp -q "${FLLE_SSH_OPTS[@]}" root@10.1.1.101:"$REMOTE.json" "$OUT/artifacts/trading_l2_bridge.json"
cp "$ASSET/flle_xdp_mold_itch.c" "$ASSET/live-support/set-xdp-policy.py" "$0" "$OUT/source/"
scp -q "${FLLE_SSH_OPTS[@]}" "$OUT/artifacts/trading_l2_bridge.json" "$ASSET/flle_xdp_mold_itch.c" "$ASSET/live-support/set-xdp-policy.py" root@10.1.1.11:"$REMOTE/"

python3 "$EOS" --plan "$P4/p4-trading-isolate-tools.plan" --output "$OUT/raw/eos-isolate-tools.txt" --mode controlled-config >/dev/null
remote11 "set -Eeuo pipefail; ip link set dev ens64f0np0 up; ip link set dev ens64f1np1 up; cd '$REMOTE'; clang -O2 -g -target bpf -D__TARGET_ARCH_x86 -I/usr/include/x86_64-linux-gnu -c flle_xdp_mold_itch.c -o flle_xdp_mold_itch.o; ip link set dev ens64f0np0 xdp obj flle_xdp_mold_itch.o sec xdp; nohup simple_switch --log-console --interface 1@ens64f0np0 --interface 2@ens64f1np1 --thrift-port 9090 trading_l2_bridge.json >simple_switch.log 2>&1 </dev/null & echo \$! >simple_switch.pid; sleep 2; kill -0 \$(cat simple_switch.pid); ip -details link show dev ens64f0np0 | grep -q prog/xdp; python3 set-xdp-policy.py allow 0 5"
printf '%s\n' \
  'table_add IngressImpl.unicast_dst IngressImpl.forward 00:0f:53:d3:af:20 => 1' \
  'table_add IngressImpl.unicast_dst IngressImpl.forward 00:0f:53:d3:af:21 => 2' \
  'table_dump IngressImpl.unicast_dst' | ssh "${FLLE_SSH_OPTS[@]}" root@10.1.1.11 "simple_switch_CLI --thrift-port 9090" >"$OUT/raw/table-install.txt"
python3 "$EOS" --plan "$P4/p4-trading-cut-endpoints.plan" --output "$OUT/raw/eos-cut-endpoints.txt" --mode controlled-config >/dev/null
ssh -n "${FLLE_SSH_OPTS[@]}" root@10.1.1.1 'ping -c 3 -W 2 20.1.1.2' >"$OUT/raw/ping-allow-all.txt"
curl -fsS -X POST -H 'Content-Type: application/json' -d '{"market_mode":"MULTICAST"}' "$API/api/market" >/dev/null

session_before="$(curl -fsS "$API/api/state" | python3 -c 'import json,sys; print(json.load(sys.stdin)["session"])')"
curl -fsS -X POST -H 'Content-Type: application/json' -d '{"action":"RESTART"}' "$API/api/replay" >/dev/null
python3 "$COMMON/wait-feed-state.py" "$API/api/state" HEALTHY --timeout 25 --session-not "$session_before" | tee "$OUT/raw/feed-baseline.json"
curl -fsS "$API/api/state" >"$OUT/raw/state-allow-all.json"

remote11 "cd '$REMOTE'; python3 set-xdp-policy.py block 1 5" >"$OUT/raw/policy-block.txt"
python3 "$COMMON/wait-feed-state.py" "$API/api/state" GAP --timeout 12 | tee "$OUT/raw/feed-gap.json"
curl -fsS "$API/api/state" >"$OUT/raw/state-gap.json"
python3 "$COMMON/assert-feed-order-gate.py" "$API" | tee "$OUT/raw/order-gate.json"
remote11 "bpftool -j map dump name counters" >"$OUT/raw/xdp-counters.json"
remote11 "bpftool -j map dump name drop_audit" >"$OUT/raw/xdp-drop-audit.json"
remote11 "ip -details link show dev ens64f0np0" >"$OUT/raw/xdp-link.txt"
python3 - "$OUT/raw/xdp-counters.json" "$OUT/raw/xdp-drop-audit.json" <<'PY'
import json, sys
counters = json.load(open(sys.argv[1], encoding="utf-8"))
audit = json.load(open(sys.argv[2], encoding="utf-8"))[0]["formatted"]["value"]
policy = next(row for row in counters if row["formatted"]["key"] == 6)
drops = sum(item["value"] for item in policy["formatted"]["values"])
assert drops == 1, f"expected exactly one XDP drop, got {drops}"
assert audit["drops"] == 1, audit
assert audit["first_drop_sequence"] > 0, audit
assert audit["first_drop_locate"] == 8095, audit
print(f'xdp_drop_packets={drops} sequence={audit["first_drop_sequence"]} locate={audit["first_drop_locate"]}')
PY

remote11 "cd '$REMOTE'; python3 set-xdp-policy.py allow 0 5" >"$OUT/raw/policy-allow.txt"
gap_session="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["session"])' "$OUT/raw/state-gap.json")"
curl -fsS -X POST -H 'Content-Type: application/json' -d '{"action":"RESTART"}' "$API/api/replay" >/dev/null
python3 "$COMMON/wait-feed-state.py" "$API/api/state" HEALTHY --timeout 25 --session-not "$gap_session" | tee "$OUT/raw/feed-recovered-inline.json"

cleanup; ARMED=0; DEADMAN_PID=; trap - EXIT INT TERM
grep -q 'VLAN 100 not found' "$OUT/raw/eos-restore-final.txt"
grep -q 'VLAN 200 not found' "$OUT/raw/eos-restore-final.txt"
final_old_session="$(curl -fsS "$API/api/state" | python3 -c 'import json,sys; print(json.load(sys.stdin)["session"])')"
curl -fsS -X POST -H 'Content-Type: application/json' -d '{"action":"RESTART"}' "$API/api/replay" >/dev/null
python3 "$COMMON/wait-feed-state.py" "$API/api/state" HEALTHY --timeout 25 --session-not "$final_old_session" | tee "$OUT/raw/feed-final.json"
python3 "$COMMON/prove-trading-recovered.py" "$API" "$OUT/raw/post-restore-orders" | tee "$OUT/raw/post-restore-orders.json"
curl -fsS "$API/api/state" >"$OUT/raw/state-after.json"
remote11 "! pgrep -x simple_switch; ! ip -details link show dev ens64f0np0 | grep -q prog/xdp; ! ip -o addr show dev ens64f0np0 | grep -q .; test \"\$(cat /sys/class/net/ens64f0np0/operstate)\" = down; test \"\$(cat /sys/class/net/ens64f1np1/operstate)\" = down"
printf 'ORIGINAL_MODE=%s\nLEFT=ens64f0np0\nRIGHT=ens64f1np1\n' "$ORIGINAL_MODE" >>"$OUT/run.env"
(cd "$OUT" && find raw artifacts source -type f -print0 | sort -z | xargs -0 sha256sum; sha256sum run.env) >"$OUT/SHA256SUMS"
printf '===== 第 08 章 inline XDP 实验 =====\nresult=PASS\npolicy=NVDA Type A locate 8095 one-shot DROP\nfeed=GAP -> replay -> HEALTHY\norder_gate=FEED_NOT_HEALTHY\npost_restore_orders=2/2 ORDER_EXECUTED; AAPL position unchanged\nevidence=%s\n' "$OUT"
