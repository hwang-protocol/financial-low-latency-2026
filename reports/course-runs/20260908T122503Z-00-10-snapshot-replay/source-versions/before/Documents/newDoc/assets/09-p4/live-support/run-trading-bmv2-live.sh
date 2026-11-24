#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
source Documents/newDoc/assets/common/flle-remote.sh
ROOT=/financial-low-latency
ASSET="$ROOT/Documents/newDoc/assets/09-p4"
EOS="$ROOT/Documents/newDoc/assets/common/eos_cli.py"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-09-trading-bmv2-live"
OUT="$ROOT/Documents/reports/course-runs/$RUN_ID"; REMOTE="/var/tmp/$RUN_ID"
MARKET_PCAP="/var/tmp/$RUN_ID-market.pcap"; API=http://10.1.1.101:8088
mkdir -p "$OUT/raw" "$OUT/artifacts"; printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
ORIGINAL_MODE="$(curl -fsS "$API/api/state" | python3 -c 'import json,sys; print(json.load(sys.stdin)["market_mode"])')"
ARMED=1; DEADMAN_PID=
remote11(){ ssh -n "${FLLE_SSH_OPTS[@]}" root@10.1.1.11 "$@"; }
cleanup(){
  set +e
  if test -n "$DEADMAN_PID"; then kill "$DEADMAN_PID" 2>/dev/null; wait "$DEADMAN_PID" 2>/dev/null; fi
  curl -fsS -X POST -H 'Content-Type: application/json' -d "{\"market_mode\":\"$ORIGINAL_MODE\"}" "$API/api/market" >/dev/null
  python3 "$EOS" --plan "$ASSET/p4-trading-restore-endpoints.plan" --output "$OUT/raw/eos-restore-endpoints.txt" --mode controlled-config
  remote11 "if test -s '$REMOTE/simple_switch.pid'; then pid=\$(cat '$REMOTE/simple_switch.pid'); kill \"\$pid\" 2>/dev/null || true; for n in 1 2 3 4 5; do kill -0 \"\$pid\" 2>/dev/null || break; sleep 1; done; fi; ip link set dev ens64f0np0 down; ip link set dev ens64f1np1 down; find '$REMOTE' -type f -delete 2>/dev/null; rmdir '$REMOTE' 2>/dev/null || true"
  python3 "$EOS" --plan "$ASSET/p4-trading-restore-final.plan" --output "$OUT/raw/eos-restore-final.txt" --mode controlled-config
  ssh -n "${FLLE_SSH_OPTS[@]}" root@10.1.1.2 "find /var/tmp -maxdepth 1 -type f -name '${MARKET_PCAP##*/}' -delete" || true
  ssh -n "${FLLE_SSH_OPTS[@]}" root@10.1.1.101 "find /var/tmp -maxdepth 1 -type f -name '${RUN_ID}.*' -delete" || true
  set -e
}
trap 'if [ "$ARMED" = 1 ]; then cleanup; fi' EXIT INT TERM

curl -fsS "$API/api/state" >"$OUT/raw/state-before.json"
python3 "$EOS" --plan "$ASSET/p4-trading-show.plan" --output "$OUT/raw/eos-before.txt" --mode show
grep -q 'VLAN 100 not found' "$OUT/raw/eos-before.txt"; grep -q 'VLAN 200 not found' "$OUT/raw/eos-before.txt"
remote11 "set -Eeuo pipefail; ! pgrep -x simple_switch; ! ip -details link show dev ens64f0np0 | grep -q prog/xdp; ! ip -details link show dev ens64f1np1 | grep -q prog/xdp; ! ip -o addr show dev ens64f0np0 | grep -q .; ! ip -o addr show dev ens64f1np1 | grep -q .; mkdir '$REMOTE'"
FLLE_DEADMAN_DELAY=240 nohup bash "$ASSET/live-support/deadman-restore.sh" "$RUN_ID" "$ORIGINAL_MODE" >"$OUT/raw/deadman.log" 2>&1 & DEADMAN_PID=$!

scp -q "${FLLE_SSH_OPTS[@]}" "$ASSET/trading_l2_bridge.p4" root@10.1.1.101:"$REMOTE.p4"
ssh -n "${FLLE_SSH_OPTS[@]}" root@10.1.1.101 "p4c-bm2-ss --p4v 16 --p4runtime-files '$REMOTE.p4info.txt' -o '$REMOTE.json' '$REMOTE.p4'"
scp -q "${FLLE_SSH_OPTS[@]}" root@10.1.1.101:"$REMOTE.json" "$OUT/artifacts/trading_l2_bridge.json"
scp -q "${FLLE_SSH_OPTS[@]}" "$OUT/artifacts/trading_l2_bridge.json" root@10.1.1.11:"$REMOTE/"

python3 "$EOS" --plan "$ASSET/p4-trading-isolate-tools.plan" --output "$OUT/raw/eos-isolate-tools.txt" --mode controlled-config
remote11 "set -Eeuo pipefail; ip link set dev ens64f0np0 up; ip link set dev ens64f1np1 up; cd '$REMOTE'; nohup simple_switch --log-console --interface 1@ens64f0np0 --interface 2@ens64f1np1 --thrift-port 9090 trading_l2_bridge.json >simple_switch.log 2>&1 </dev/null & echo \$! >simple_switch.pid; sleep 2; kill -0 \$(cat simple_switch.pid)"
printf '%s\n' \
  'table_add IngressImpl.unicast_dst IngressImpl.forward 00:0f:53:d3:af:20 => 1' \
  'table_add IngressImpl.unicast_dst IngressImpl.forward 00:0f:53:d3:af:21 => 2' \
  'table_dump IngressImpl.unicast_dst' | ssh "${FLLE_SSH_OPTS[@]}" root@10.1.1.11 "simple_switch_CLI --thrift-port 9090" | tee "$OUT/raw/table-install.txt"
python3 "$EOS" --plan "$ASSET/p4-trading-cut-endpoints.plan" --output "$OUT/raw/eos-cut-endpoints.txt" --mode controlled-config
sleep 3

remote11 "set +e; timeout 8 tcpdump -Q out -ni ens64f0np0 -s 0 -c 1 -w '$REMOTE/bpdu-left-out.pcap' 'ether dst 01:80:c2:00:00:00' >'$REMOTE/bpdu-left.log' 2>&1 & p0=\$!; timeout 8 tcpdump -Q out -ni ens64f1np1 -s 0 -c 1 -w '$REMOTE/bpdu-right-out.pcap' 'ether dst 01:80:c2:00:00:00' >'$REMOTE/bpdu-right.log' 2>&1 & p1=\$!; wait \$p0; r0=\$?; wait \$p1; r1=\$?; set -e; printf 'bpdu_out_left_rc=%s bpdu_out_right_rc=%s expected=124\n' \"\$r0\" \"\$r1\"; test \"\$r0\" -eq 124; test \"\$r1\" -eq 124" | tee "$OUT/raw/bpdu-guard.txt"
scp -q "${FLLE_SSH_OPTS[@]}" root@10.1.1.11:"$REMOTE/bpdu-left-out.pcap" root@10.1.1.11:"$REMOTE/bpdu-right-out.pcap" "$OUT/artifacts/"
ssh -n "${FLLE_SSH_OPTS[@]}" root@10.1.1.1 'ping -c 3 -W 2 20.1.1.2' | tee "$OUT/raw/ping-bmv2.txt"
curl -fsS -X POST -H 'Content-Type: application/json' -d '{"market_mode":"MULTICAST"}' "$API/api/market" >/dev/null
ssh -n "${FLLE_SSH_OPTS[@]}" root@10.1.1.2 "timeout 12 tcpdump -ni ens64np1 -s 0 -c 200 -w '$MARKET_PCAP' 'udp dst port 31032 and dst host 233.74.125.32'" 2>&1 | tee "$OUT/raw/market-tcpdump.txt"
scp -q "${FLLE_SSH_OPTS[@]}" root@10.1.1.2:"$MARKET_PCAP" "$OUT/artifacts/market-over-bmv2.pcap"
python3 Documents/newDoc/assets/03-live-traffic/inspect_market_pcap.py "$OUT/artifacts/market-over-bmv2.pcap" | tee "$OUT/raw/market-decoded.txt"
bash Documents/newDoc/assets/07-arista-time/13-trading-online-final.sh | tee "$OUT/raw/trading-during-bmv2.txt"
sleep 3
printf '%s\n' 'counter_read IngressImpl.frame_class 0' 'counter_read IngressImpl.frame_class 1' 'counter_read IngressImpl.frame_class 2' | ssh "${FLLE_SSH_OPTS[@]}" root@10.1.1.11 "simple_switch_CLI --thrift-port 9090" | tee "$OUT/raw/counters.txt"
python3 "$EOS" --plan "$ASSET/p4-trading-show.plan" --output "$OUT/raw/eos-live-final.txt" --mode show
remote11 "cat '$REMOTE/simple_switch.log'" >"$OUT/raw/simple_switch.log"

cleanup; ARMED=0; DEADMAN_PID=; trap - EXIT INT TERM
grep -q 'VLAN 100 not found' "$OUT/raw/eos-restore-final.txt"
grep -q 'VLAN 200 not found' "$OUT/raw/eos-restore-final.txt"
! grep -q '^+no ip igmp snooping vlan' "$OUT/raw/eos-restore-final.txt"
bash Documents/newDoc/assets/07-arista-time/13-trading-online-final.sh | tee "$OUT/raw/trading-after-restore.txt"
curl -fsS "$API/api/state" >"$OUT/raw/state-after.json"
remote11 "! pgrep -x simple_switch; ! ip -details link show dev ens64f0np0 | grep -q prog/xdp; ! ip -o addr show dev ens64f0np0 | grep -q .; test \"\$(cat /sys/class/net/ens64f0np0/operstate)\" = down; test \"\$(cat /sys/class/net/ens64f1np1/operstate)\" = down"
printf 'ORIGINAL_MODE=%s\nLEFT=ens64f0np0\nRIGHT=ens64f1np1\n' "$ORIGINAL_MODE" >>"$OUT/run.env"
sha256sum "$ASSET/trading_l2_bridge.p4" "$OUT"/raw/* "$OUT"/artifacts/* "$OUT/run.env" >"$OUT/SHA256SUMS"
printf 'evidence=%s\n' "$OUT"
