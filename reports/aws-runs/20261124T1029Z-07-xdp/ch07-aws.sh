#!/usr/bin/env bash
# Chapter 07 on AWS (run on flle-tr2 with sudo): native XDP on ENA, drop exactly one NVDA Add Order,
# verify the feed receiver detects the gap. Adapted from assets/07-xdp/live-support/run-xdp-receiver-live.sh.
set -Eeuo pipefail
D=/home/ubuntu/flle/ch07
cd "$D"
IF=enp39s0
API=http://172.31.12.156:8088
log(){ printf '\n===== %s =====\n' "$*"; }

log "toolchain"
clang --version | head -1
bpftool version | head -1
ip -V

log "build BPF object"
clang -O2 -g -target bpf -D__TARGET_ARCH_x86 -I/usr/include/x86_64-linux-gnu \
  -c flle_xdp_mold_itch.c -o flle_xdp_mold_itch.o
llvm-objdump -h flle_xdp_mold_itch.o
sha256sum flle_xdp_mold_itch.c flle_xdp_mold_itch.o

ORIG_MTU=$(cat /sys/class/net/$IF/mtu)
ORIG_CH=$(ethtool -l $IF | awk '/Current hardware/{f=1} f&&/Combined/{print $2; exit}')
echo "original mtu=$ORIG_MTU combined_channels=$ORIG_CH"
restore() {
  log "restore NIC"
  python3 xdp-session.py detach 2>/dev/null || ip link set dev $IF xdpdrv off 2>/dev/null || true
  ip link set dev $IF mtu "$ORIG_MTU" || true
  ethtool -L $IF combined "$ORIG_CH" 2>/dev/null || true
  ip -details link show dev $IF | head -2
  ethtool -l $IF | tail -5
}
trap restore EXIT

log "prepare ENA for native XDP (MTU <= 3498, half of the queues)"
ip link set dev $IF mtu 1500
ethtool -L $IF combined 2 || echo "channel change refused (continuing)"
ethtool -l $IF | tail -5
sleep 3

log "attach native XDP (xdpdrv)"
python3 xdp-session.py attach $IF
ip -details link show dev $IF | grep -oE 'xdp.*|prog/xdp.*' | head -3
PROG_ID=$(python3 -c 'import json;print(json.load(open("attachment.json"))["program_id"])')
bpftool prog show id "$PROG_ID"

log "policy allow, then restart replay (NIC reconfiguration above drops packets -> fresh session)"
python3 set-xdp-policy.py allow 0 5 "$PROG_ID"
SESSION_BEFORE=$(curl -fsS $API/api/state | python3 -c 'import json,sys; print(json.load(sys.stdin)["session"])')
curl -fsS -X POST -H 'Content-Type: application/json' -d '{"action":"RESTART"}' $API/api/replay > replay-restart.json
python3 wait-feed-state.py $API/api/state HEALTHY --timeout 30 --session-not "$SESSION_BEFORE" | tee feed-baseline.json
sleep 2
log "observe 5 s with policy allow"
python3 xdp-session.py dump counters > counters-t0.json
sleep 5
python3 xdp-session.py dump counters > counters-allow.json
python3 summarize-counters.py counters-t0.json counters-allow.json
curl -fsS $API/api/state | python3 -c 'import json,sys; f=json.load(sys.stdin)["feed"]; print("feed integrity=%s next_expected=%s gaps=%s gate=%s" % (f["integrity"], f["next_expected"], f["gaps"], f["trading_gate"]))'

log "policy block ONE NVDA Add Order"
python3 set-xdp-policy.py block 1 5 "$PROG_ID"
python3 wait-feed-state.py $API/api/state GAP --timeout 12 | tee feed-gap.json
curl -fsS -X POST -H 'Content-Type: application/json' -d '{"action":"PAUSE"}' $API/api/replay > replay-paused.json || true
python3 xdp-session.py dump counters > counters-block.json
python3 xdp-session.py dump drop_audit > drop-audit.json
python3 summarize-counters.py counters-allow.json counters-block.json

log "match XDP audit against feed gap"
python3 - <<'PY'
import json
def unwrap(v):
    return v.get("formatted", v)
audit = unwrap(json.load(open("drop-audit.json"))[0])["value"]
gap = json.load(open("feed-gap.json"))["feed"]
print("xdp drop_audit:", audit)
print("feed gap: integrity=%s next_expected=%s gap_size=%s pending=%s trading_gate=%s" % (
    gap["integrity"], gap["next_expected"], gap.get("gap_size"), gap.get("pending"), gap.get("trading_gate")))
ok = (audit["drops"] == 1 and audit["first_drop_locate"] == 8095
      and audit["first_drop_sequence"] == gap["next_expected"] and gap["integrity"] == "GAP")
print("verdict=" + ("XDP_DROP_GAP_MATCH_PASS" if ok else "MISMATCH"))
PY
log "detach (restore runs on exit)"
