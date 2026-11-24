#!/usr/bin/env bash
# Teacher live C: mark the current Kernel Socket order flow with DSCP 46,
# prove the FM6000 DSCP -> traffic class 5 -> egress queue 5 path,
# explicitly configure queue 5 as strict priority, then restore.
set -Eeuo pipefail
cd /qyt-fll

ASSET=assets/06-arista-time
COMMON=assets/common
ENTRY_SCRIPT="$ASSET/10-qos-real-order-live.sh"
EOS_CLI="$COMMON/eos_cli.py"
. reports/run-state/02-trading-baseline.env
PARENT_RUN_ID="$RUN_ID"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-07-qos-real-order-live"
OUT="reports/course-runs/$RUN_ID"
RAW="$OUT/raw"
TMP="$(mktemp -d)"
API=http://10.1.1.101:8088
REMOTE_DIR="/run/flle-ch07-qos/$RUN_ID"
ORDER_COUNT=16
SWITCH_CONFIGURED=0
source "$ASSET/order-dscp-control.sh"
REMOTE_CREATED=0
SOURCE_PORT=""
test ! -e "$OUT"
mkdir -p "$RAW/source"
ENTRY_SCRIPT_SHA256="$(sha256sum "$ENTRY_SCRIPT" | awk '{print $1}')"
EOS_CLI_SHA256="$(sha256sum "$EOS_CLI" | awk '{print $1}')"
printf 'RUN_ID=%s\nPARENT_RUN_ID=%s\nRESULT_KIND=FRESH_LIVE_REAL_ORDER_QOS\nDSCP=46\nTRAFFIC_CLASS=5\nTX_QUEUE=5\nORDER_COUNT=%s\nORDER_MARKING=SETSOCKOPT_IP_TOS\nENTRY_SCRIPT_SHA256=%s\nEOS_CLI_SHA256=%s\nQOS_TRANSPORT=%s\nPHASE=STARTED\n' \
  "$RUN_ID" "$PARENT_RUN_ID" "$ORDER_COUNT" "$ENTRY_SCRIPT_SHA256" "$EOS_CLI_SHA256" "$QOS_TRANSPORT" \
  >"$OUT/run.env"
install -m 0644 "$ENTRY_SCRIPT" "$RAW/source/10-qos-real-order-live.sh"
install -m 0644 "$EOS_CLI" "$RAW/source/eos_cli.py"
install -m 0644 "$ASSET/order-dscp-control.sh" "$RAW/source/"
install -m 0644 "$QOS_TOOL" "$RAW/source/"

switch_config() {
  local name="$1"; shift
  printf '%s\n' "$@" >"$TMP/$name.plan"
  python3 "$EOS_CLI" --mode controlled-config \
    --plan "$TMP/$name.plan" --output "$RAW/$name.txt" >/dev/null
}

switch_show() {
  local name="$1"; shift
  printf '%s\n' "$@" >"$TMP/$name.plan"
  python3 "$EOS_CLI" --mode show \
    --plan "$TMP/$name.plan" --output "$RAW/$name.txt" >/dev/null
}

restore_switch() {
  test "$SWITCH_CONFIGURED" -eq 1 || return 0
  switch_config switch-restore \
    'configure terminal' \
    'interface Ethernet2' \
    'default qos trust' \
    'interface Ethernet1' \
    'tx-queue 0' 'default bandwidth percent' 'default priority' 'exit' \
    'tx-queue 1' 'default bandwidth percent' 'default priority' 'exit' \
    'tx-queue 2' 'default bandwidth percent' 'default priority' 'exit' \
    'tx-queue 3' 'default bandwidth percent' 'default priority' 'exit' \
    'tx-queue 5' 'default priority' 'exit' \
    'end' \
    'show qos interfaces Ethernet1' \
    'show qos interfaces Ethernet2' \
    'show running-config interfaces Ethernet1' \
    'show running-config interfaces Ethernet2'
  SWITCH_CONFIGURED=0
}

cleanup_remote() {
  test "$REMOTE_CREATED" -eq 1 || return 0
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.1 \
    bash -s -- "$REMOTE_DIR" <<'REMOTE'
set -eu
case "$1" in /run/flle-ch07-qos/*) ;; *) exit 91;; esac
if test -d "$1"; then
  for pidfile in "$1"/*.pid; do
    test -f "$pidfile" || continue
    pid="$(cat "$pidfile")"
    kill -INT "$pid" 2>/dev/null || true
  done
  rm -rf -- "$1"
fi
REMOTE
  REMOTE_CREATED=0
}

cleanup() {
  rc=$?
  trap - EXIT INT TERM HUP
  qos_restore || rc=1
  restore_switch || rc=1
  cleanup_remote || rc=1
  rm -rf -- "$TMP"
  exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

run_orders() {
  local stage="$1" count="$2" replies index side limit payload
  replies="$RAW/$stage-orders.ndjson"
  : >"$replies"
  # SELL/BUY 成对下单，净持仓不变；连续 BUY 会撞到 paper 持仓上限（PIT-190）
  for index in $(seq 1 "$count"); do
    if (( index % 2 == 1 )); then
      side=SELL
      limit=1
    else
      side=BUY
      limit=999999999999
    fi
    payload="{\"symbol\":\"AAPL\",\"side\":\"$side\",\"quantity\":1,\"limit_price_x10000\":$limit,\"transport\":\"$QOS_TRANSPORT\"}"
    reply="$(curl -fsS -X POST -H 'Content-Type: application/json' \
      -d "$payload" \
      "$API/api/order")"
    oid="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["client_order_id"])' <<<"$reply")"
    executed=0
    for _ in $(seq 1 40); do
      state="$(curl -fsS "$API/api/state")"
      if python3 -c 'import json,sys; oid=int(sys.argv[1]); rows=[o for o in json.loads(sys.argv[2]).get("orders",[]) if int(o.get("client_order_id",0))==oid]; raise SystemExit(not(rows and rows[0].get("result")=="ORDER_EXECUTED" and int(rows[0].get("order_rtt_ns",0))>0))' "$oid" "$state"; then
        executed=1
        break
      fi
      sleep 0.1
    done
    test "$executed" -eq 1
    python3 -c 'import json,sys; oid=int(sys.argv[1]); row=next(o for o in json.loads(sys.argv[2])["orders"] if int(o["client_order_id"])==oid); print(json.dumps(row,separators=(",",":"),sort_keys=True))' \
      "$oid" "$state" >>"$replies"
  done
  python3 - "$replies" "$count" <<'PY'
import json, pathlib, sys
rows = [json.loads(line) for line in pathlib.Path(sys.argv[1]).read_text().splitlines()]
expected = int(sys.argv[2])
assert len(rows) == expected
assert all(row["result"] == "ORDER_EXECUTED" for row in rows)
assert all(int(row["order_rtt_ns"]) > 0 for row in rows)
print(f"orders_executed={len(rows)}")
print(f"first_client_order_id={rows[0]['client_order_id']}")
print(f"last_client_order_id={rows[-1]['client_order_id']}")
PY
}

start_capture() {
  local stage="$1"
  REMOTE_CREATED=1
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.1 \
    bash -s -- "$REMOTE_DIR" "$stage" "$SOURCE_PORT" <<'REMOTE'
set -eu
dir="$1"; stage="$2"
case "$dir" in /run/flle-ch07-qos/*) ;; *) exit 91;; esac
mkdir -p "$dir"
test ! -e "$dir/$stage.pid"
nohup tcpdump -ni ens64np0 -s 0 -U -w "$dir/$stage.pcap" \
  "src host 20.1.1.2 and dst host 20.1.1.1 and tcp dst port 43120 and src port $3" \
  >"$dir/$stage-tcpdump.txt" 2>&1 </dev/null &
pid=$!
printf '%s\n' "$pid" >"$dir/$stage.pid"
for _ in $(seq 1 30); do
  kill -0 "$pid" 2>/dev/null && test -f "$dir/$stage.pcap" && exit 0
  sleep 0.1
done
exit 92
REMOTE
}

stop_capture() {
  local stage="$1"
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.1 \
    bash -s -- "$REMOTE_DIR" "$stage" <<'REMOTE'
set -eu
dir="$1"; stage="$2"
case "$dir" in /run/flle-ch07-qos/*) ;; *) exit 91;; esac
pid="$(cat "$dir/$stage.pid")"
kill -INT "$pid" 2>/dev/null || true
for _ in $(seq 1 50); do
  kill -0 "$pid" 2>/dev/null || break
  sleep 0.1
done
! kill -0 "$pid" 2>/dev/null
tcpdump -nn -e -vv -r "$dir/$stage.pcap" >"$dir/$stage-decode.txt" 2>&1
REMOTE
  scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes \
    "root@10.1.1.1:$REMOTE_DIR/$stage.pcap" \
    "root@10.1.1.1:$REMOTE_DIR/$stage-tcpdump.txt" \
    "root@10.1.1.1:$REMOTE_DIR/$stage-decode.txt" "$RAW/"
}

queue_counter() {
  local file="$1" priority="$2"
  python3 - "$file" "$priority" <<'PY'
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
match = re.search(r"Ethernet1\s+tx frames with priority_%s\s+(\d+)" % re.escape(sys.argv[2]), text)
if not match:
    raise SystemExit("priority counter not found")
print(match.group(1))
PY
}

capture_tos_count() {
  local file="$1" tos="$2"
  grep -Ec "tos $tos([, ])" "$file"
}

capture_frame_count() {
  local file="$1"
  grep -Ec '^[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]+ ' "$file"
}

# A fresh Chapter 05 client has a launch receipt; verify its path after connecting.
qos_check_platform
qos_connect(){ run_orders qos-connect 2; }
qos_preflight >"$RAW/order-dscp-preflight.txt"
cat "$RAW/order-dscp-preflight.txt"
qos_verify_path
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
  "set -eu; test \"\$(basename \"\$(readlink /sys/bus/pci/devices/0000:03:00.0/driver)\")\" = sfc; ip -4 addr show dev ens64np1 | grep -Fq '20.1.1.2/24'; ping -q -I ens64np1 -c 3 -W 1 20.1.1.1" \
  >"$RAW/vm2-preflight.txt"
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
  "iptables-save -t mangle | sed -E '/^# (Generated|Completed) /d'" \
  >"$RAW/vm2-iptables-before.txt"

switch_show switch-before \
  'show version' \
  'show interfaces Ethernet1 status' \
  'show interfaces Ethernet2 status' \
  'show qos interfaces Ethernet1' \
  'show qos interfaces Ethernet2' \
  'show qos maps' \
  'show running-config interfaces Ethernet1' \
  'show running-config interfaces Ethernet2' \
  'show startup-config interfaces Ethernet1' \
  'show startup-config interfaces Ethernet2'
if grep -Eq '^   (qos|tx-queue)' "$RAW/switch-before.txt"; then
  printf 'pre-existing QoS config on Et1/Et2; refusing to overwrite\n' >&2
  exit 1
fi

# A: same real orders, no marking, switched ingress defaults to CoS trust.
switch_show baseline-counter-before 'show platform fm6000 counters interface Ethernet1'
start_capture baseline
run_orders baseline "$ORDER_COUNT" | tee "$RAW/baseline-orders-summary.txt"
sleep 0.5
stop_capture baseline
switch_show baseline-counter-after 'show platform fm6000 counters interface Ethernet1'

# B: setsockopt(IP_TOS) marks only the selected order TCP connection; trust DSCP at Et2;
# explicitly put queue 5 in strict priority and queues 0-3 in RR.
SWITCH_CONFIGURED=1
switch_config switch-qos-active \
  'configure terminal' \
  'interface Ethernet2' 'qos trust dscp' \
  'interface Ethernet1' \
  'tx-queue 5' 'priority strict' 'exit' \
  'tx-queue 3' 'no priority' 'bandwidth percent 40' 'exit' \
  'tx-queue 2' 'bandwidth percent 30' 'exit' \
  'tx-queue 1' 'bandwidth percent 20' 'exit' \
  'tx-queue 0' 'bandwidth percent 10' 'exit' \
  'end' \
  'show qos interfaces Ethernet1' \
  'show qos interfaces Ethernet2' \
  'show qos maps' \
  'show running-config interfaces Ethernet1' \
  'show running-config interfaces Ethernet2'
qos_mark
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
  'iptables-save -t mangle' >"$RAW/vm2-iptables-active.txt"

switch_show tagged-counter-before 'show platform fm6000 counters interface Ethernet1'
start_capture tagged
run_orders tagged "$ORDER_COUNT" | tee "$RAW/tagged-orders-summary.txt"
sleep 0.5
stop_capture tagged
switch_show tagged-counter-after 'show platform fm6000 counters interface Ethernet1'

baseline_p1_before="$(queue_counter "$RAW/baseline-counter-before.txt" 1)"
baseline_p1_after="$(queue_counter "$RAW/baseline-counter-after.txt" 1)"
baseline_p5_before="$(queue_counter "$RAW/baseline-counter-before.txt" 5)"
baseline_p5_after="$(queue_counter "$RAW/baseline-counter-after.txt" 5)"
tagged_p1_before="$(queue_counter "$RAW/tagged-counter-before.txt" 1)"
tagged_p1_after="$(queue_counter "$RAW/tagged-counter-after.txt" 1)"
tagged_p5_before="$(queue_counter "$RAW/tagged-counter-before.txt" 5)"
tagged_p5_after="$(queue_counter "$RAW/tagged-counter-after.txt" 5)"
baseline_p1_delta=$((baseline_p1_after - baseline_p1_before))
baseline_p5_delta=$((baseline_p5_after - baseline_p5_before))
tagged_p1_delta=$((tagged_p1_after - tagged_p1_before))
tagged_p5_delta=$((tagged_p5_after - tagged_p5_before))
baseline_tos0="$(capture_tos_count "$RAW/baseline-decode.txt" 0x0)"
tagged_tos46="$(capture_tos_count "$RAW/tagged-decode.txt" 0xb8)"
baseline_captured_frames="$(capture_frame_count "$RAW/baseline-decode.txt")"
tagged_captured_frames="$(capture_frame_count "$RAW/tagged-decode.txt")"
test "$baseline_captured_frames" -ge "$ORDER_COUNT"
test "$tagged_captured_frames" -ge "$ORDER_COUNT"
test "$baseline_tos0" -eq "$baseline_captured_frames"
test "$tagged_tos46" -eq "$tagged_captured_frames"
test "$baseline_p1_delta" -ge "$baseline_captured_frames"
test "$tagged_p5_delta" -ge "$tagged_captured_frames"
grep -Fq 'Trust Mode: DSCP' "$RAW/switch-qos-active.txt"
grep -Eq '^   5 +[-0-9 /().]+SP / SP' "$RAW/switch-qos-active.txt"
grep -A2 -F 'tx-queue 5' "$RAW/switch-qos-active.txt" | grep -Fq 'priority strict'
grep -Eq '^   3 +40 / 40 +[-0-9 /().]+RR / RR' "$RAW/switch-qos-active.txt"
grep -Fq 'tc:   1  0  2  3  4  5  6  7' "$RAW/switch-qos-active.txt"
grep -Fq 'tx-queue:  0  1  2  3  4  5  6  7' "$RAW/switch-qos-active.txt"

# Restore before the final business transaction, then prove both host and switch state.
qos_restore
restore_switch
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
  "iptables-save -t mangle | sed -E '/^# (Generated|Completed) /d'" \
  >"$RAW/vm2-iptables-after.txt"
cmp "$RAW/vm2-iptables-before.txt" "$RAW/vm2-iptables-after.txt"
qos_verify_restored
switch_show switch-after \
  'show qos interfaces Ethernet1' \
  'show qos interfaces Ethernet2' \
  'show running-config interfaces Ethernet1' \
  'show running-config interfaces Ethernet2' \
  'show startup-config interfaces Ethernet1' \
  'show startup-config interfaces Ethernet2' \
  'show interfaces Ethernet1 counters errors' \
  'show interfaces Ethernet2 counters errors'
python3 - "$RAW/switch-before.txt" "$RAW/switch-after.txt" <<'PY'
import re, sys
def sections(path):
    text = open(path, encoding="utf-8").read()
    return re.findall(r"\$ show (?:running|startup)-config interfaces Ethernet[12]\n(.*?)(?=\n\$ |\Z)", text, re.S)
before, after = sections(sys.argv[1]), sections(sys.argv[2])
assert len(before) == len(after) == 4
assert before == after
PY
grep -q 'Trust Mode: COS' "$RAW/switch-after.txt"
test "$(grep -c 'SP / SP' "$RAW/switch-after.txt")" -eq 16
post_restore_summary="$(run_orders post-restore 2)"
printf '%s\n' "$post_restore_summary" >"$RAW/post-restore-order-summary.txt"

cleanup_remote
printf 'PHASE=COMPLETE\n' >>"$OUT/run.env"
python3 - "$RAW/result.txt" <<PY
from pathlib import Path
Path("$RAW/result.txt").write_text("""===== 实验一快速映射 · 真实订单 QoS A/B =====
result=PASS
platform=DCS-7150S-24-F / EOS 4.23.16M-2GB / FM6000
baseline=unmarked IPv4 TOS 0x0; default CoS 0 -> Traffic Class 1 -> tx priority 1
baseline_orders_executed=$ORDER_COUNT
baseline_captured_frames=$baseline_captured_frames
baseline_priority_1_delta=$baseline_p1_delta
baseline_priority_5_delta=$baseline_p5_delta
tagged=DSCP 46 (TOS 0xb8) -> Traffic Class 5 -> tx priority 5
tagged_orders_executed=$ORDER_COUNT
tagged_captured_frames=$tagged_captured_frames
tagged_priority_1_delta=$tagged_p1_delta
tagged_priority_5_delta=$tagged_p5_delta
scheduler=queue 5 explicitly priority strict; queues 4-7 SP; queues 0-3 RR at 10/20/30/40 percent during tagged stage
host_restore=order DSCP restored to original value; iptables unchanged
switch_restore=Et1/Et2 running config byte-identical; startup config unchanged; 16/16 queues SP
post_restore_orders=2/2 ORDER_EXECUTED; AAPL position unchanged
save_config=NO
evidence=$OUT
""", encoding="utf-8")
PY
cat "$RAW/result.txt"
(cd "$OUT" && find raw -type f -print0 | sort -z | xargs -0 sha256sum >SHA256SUMS)
ROOT_SHA256="$(sha256sum "$OUT/SHA256SUMS" | awk '{print $1}')"
printf 'ROOT_SHA256=%s\n' "$ROOT_SHA256" >>"$OUT/run.env"
printf 'root_sha256=%s\n' "$ROOT_SHA256"
trap - EXIT INT TERM HUP
rm -rf -- "$TMP"
