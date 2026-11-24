#!/usr/bin/env bash
# Teacher live C2: send real Socket orders through a shared, contended egress;
# compare unmarked Q1 with DSCP 46 -> TC5 -> explicitly strict Q5, then restore.
set -Eeuo pipefail
cd /financial-low-latency

ASSET=Documents/newDoc/assets/07-arista-time
COMMON=Documents/newDoc/assets/common
SUPPORT="$ASSET/live-support"
SUPPORT_MANIFEST="$ASSET/LIVE-SUPPORT-SHA256SUMS"
ENTRY_SCRIPT="$ASSET/11-qos-real-order-contention-live.sh"
EOS_CLI="$COMMON/eos_cli.py"
TREX_TEMPLATE="$SUPPORT/lanz/remote-lanz-trex-control.sh"
TREX_CLIENT="$SUPPORT/qos/trex_qos_contention_client.py"
TREX_CFG="$SUPPORT/lanz/trex-dual.yaml"
. Documents/reports/run-state/ch06-four-path.env
PARENT_RUN_ID="$RUN_ID"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-07-qos-contention-live"
OUT="Documents/reports/course-runs/$RUN_ID"
RAW="$OUT/raw"
DERIVED="$OUT/derived"
TMP="$(mktemp -d)"
API=http://10.1.1.101:8088
CAPTURE_DIR="/run/flle-ch07-qos/$RUN_ID"
TREX_DIR="/run/flle-qos-contention-$RUN_ID"
TREX_CTL="$TREX_DIR/remote-qos-trex-control.sh"
RULE_TAG="FLLE_CH07_QOS_${RUN_ID}"
FAKE_MAC_DOTTED=0200.0007.0001
FAKE_MAC_COLON=02:00:00:07:00:01
ORDER_COUNT=64
LOAD_PPS_PER_INGRESS=600000
LOAD_DURATION_SECONDS=8
SOURCE_PORT=""
SWITCH_CONFIGURED=0
HOST_RULE_ADDED=0
CAPTURE_REMOTE_CREATED=0
TREX_REMOTE_DEPLOYED=0
TREX_INSTALLED=0

test ! -e "$OUT"
mkdir -p "$RAW/source" "$DERIVED"
SUPPORT_MANIFEST_SHA256="$(sha256sum "$SUPPORT_MANIFEST" | awk '{print $1}')"
ENTRY_SCRIPT_SHA256="$(sha256sum "$ENTRY_SCRIPT" | awk '{print $1}')"
EOS_CLI_SHA256="$(sha256sum "$EOS_CLI" | awk '{print $1}')"
printf 'RUN_ID=%s\nPARENT_RUN_ID=%s\nRESULT_KIND=FRESH_LIVE_REAL_ORDER_QOS_CONTENTION\nDSCP=46\nTRAFFIC_CLASS=5\nTX_QUEUE=5\nORDER_COUNT=%s\nLOAD_PPS_PER_INGRESS=%s\nLOAD_DURATION_SECONDS=%s\nSUPPORT_MANIFEST_SHA256=%s\nENTRY_SCRIPT_SHA256=%s\nEOS_CLI_SHA256=%s\nPHASE=STARTED\n' \
  "$RUN_ID" "$PARENT_RUN_ID" "$ORDER_COUNT" "$LOAD_PPS_PER_INGRESS" \
  "$LOAD_DURATION_SECONDS" "$SUPPORT_MANIFEST_SHA256" "$ENTRY_SCRIPT_SHA256" \
  "$EOS_CLI_SHA256" >"$OUT/run.env"
install -m 0644 "$ENTRY_SCRIPT" "$RAW/source/11-qos-real-order-contention-live.sh"
install -m 0644 "$EOS_CLI" "$RAW/source/eos_cli.py"
install -m 0644 "$SUPPORT_MANIFEST" "$RAW/LIVE-SUPPORT-SHA256SUMS"
(cd "$ASSET" && sha256sum -c LIVE-SUPPORT-SHA256SUMS) \
  >"$RAW/local-support-sha256.txt"

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

remove_host_rule() {
  test "$HOST_RULE_ADDED" -eq 1 || return 0
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
    bash -s -- "$SOURCE_PORT" "$RULE_TAG" <<'REMOTE'
set -eu
if iptables -t mangle -C OUTPUT -o ens64np1 -p tcp \
    -s 20.1.1.2 -d 20.1.1.1 --sport "$1" --dport 43120 \
    -m comment --comment "$2" -j DSCP --set-dscp 46 2>/dev/null; then
  iptables -t mangle -D OUTPUT -o ens64np1 -p tcp \
    -s 20.1.1.2 -d 20.1.1.1 --sport "$1" --dport 43120 \
    -m comment --comment "$2" -j DSCP --set-dscp 46
fi
REMOTE
  HOST_RULE_ADDED=0
}

restore_switch() {
  test "$SWITCH_CONFIGURED" -eq 1 || return 0
  switch_config switch-restore \
    'configure terminal' \
    'no mac address-table static 0200.0007.0001 vlan 20 interface Ethernet1' \
    'interface Ethernet1' \
    'default queue-monitor length thresholds' \
    'tx-queue 0' 'default bandwidth percent' 'default priority' 'exit' \
    'tx-queue 1' 'default bandwidth percent' 'default priority' 'exit' \
    'tx-queue 2' 'default bandwidth percent' 'default priority' 'exit' \
    'tx-queue 3' 'default bandwidth percent' 'default priority' 'exit' \
    'tx-queue 5' 'default priority' 'exit' \
    'interface Ethernet2' 'default qos trust' \
    'end' \
    'configure terminal' 'default queue-monitor length' 'end' \
    'show qos interfaces Ethernet1' \
    'show qos interfaces Ethernet2' \
    'show queue-monitor length status' \
    'show mac address-table static' \
    'show running-config interfaces Ethernet1' \
    'show running-config interfaces Ethernet2'
  SWITCH_CONFIGURED=0
}

cleanup_capture_remote() {
  test "$CAPTURE_REMOTE_CREATED" -eq 1 || return 0
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.1 \
    bash -s -- "$CAPTURE_DIR" <<'REMOTE'
set -eu
case "$1" in /run/flle-ch07-qos/*) ;; *) exit 91;; esac
if test -d "$1"; then
  for pidfile in "$1"/*.pid; do
    test -f "$pidfile" || continue
    pid="$(cat "$pidfile")"
    kill -INT "$pid" 2>/dev/null || true
  done
  find "$1" -depth -delete
fi
REMOTE
  CAPTURE_REMOTE_CREATED=0
}

remove_trex_install() {
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
    'set -eu; if test -e /opt/trex/v3.08 || test -L /opt/trex/v3.08; then test -d /opt/trex/v3.08 && test ! -L /opt/trex/v3.08; find /opt/trex/v3.08 -depth -delete; fi; if test -e /opt/trex/v3.08.tar.gz || test -L /opt/trex/v3.08.tar.gz; then test -L /opt/trex/v3.08.tar.gz; test "$(readlink /opt/trex/v3.08.tar.gz)" = /opt/flle/prewarm/trex/v3.08.tar.gz; unlink /opt/trex/v3.08.tar.gz; fi; rmdir /opt/trex 2>/dev/null || true; test ! -e /opt/trex && test ! -L /opt/trex'
}

recover_trex() {
  if test "$TREX_REMOTE_DEPLOYED" -eq 1; then
    ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
      /usr/bin/bash "$TREX_CTL" recover >"$RAW/vm11-explicit-recover.txt" 2>&1
    ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
      /usr/bin/bash "$TREX_CTL" disarm-deadman >"$RAW/vm11-deadman-disarm.txt" 2>&1
  fi
  if test "$TREX_INSTALLED" -eq 1; then
    remove_trex_install >"$RAW/vm11-remove-trex.txt" 2>&1
    TREX_INSTALLED=0
  fi
}

cleanup_trex_remote() {
  test "$TREX_REMOTE_DEPLOYED" -eq 1 || return 0
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
    bash -s -- "$TREX_DIR" <<'REMOTE'
set -eu
case "$1" in /run/flle-qos-contention-*-07-qos-contention-live) ;; *) exit 91;; esac
test -d "$1"
find "$1" -depth -delete
test ! -e "$1"
REMOTE
  TREX_REMOTE_DEPLOYED=0
}

cleanup() {
  local original_rc=$? cleanup_failed=0
  trap - EXIT INT TERM HUP
  set +e
  recover_trex || cleanup_failed=1
  remove_host_rule || cleanup_failed=1
  cleanup_capture_remote || cleanup_failed=1
  restore_switch || cleanup_failed=1
  cleanup_trex_remote || cleanup_failed=1
  find "$TMP" -depth -delete
  if test "$cleanup_failed" -ne 0; then
    printf 'QOS_CONTENTION_CLEANUP=FAIL original_rc=%s\n' "$original_rc" >&2
    exit 125
  fi
  if test "$original_rc" -ne 0; then exit "$original_rc"; fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

start_capture() {
  local stage="$1"
  CAPTURE_REMOTE_CREATED=1
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.1 \
    bash -s -- "$CAPTURE_DIR" "$stage" <<'REMOTE'
set -eu
dir="$1"; stage="$2"
case "$dir" in /run/flle-ch07-qos/*) ;; *) exit 91;; esac
mkdir -p "$dir"
test ! -e "$dir/$stage.pid"
nohup tcpdump -ni ens64np0 -s 0 -U -w "$dir/$stage.pcap" \
  'src host 20.1.1.2 and dst host 20.1.1.1 and tcp dst port 43120' \
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
    bash -s -- "$CAPTURE_DIR" "$stage" <<'REMOTE'
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
    "root@10.1.1.1:$CAPTURE_DIR/$stage.pcap" \
    "root@10.1.1.1:$CAPTURE_DIR/$stage-tcpdump.txt" \
    "root@10.1.1.1:$CAPTURE_DIR/$stage-decode.txt" "$RAW/"
}

issue_orders() {
  local stage="$1" count="$2" require_load="${3:-1}" replies="$RAW/$stage-orders-issued.ndjson"
  local ids="$RAW/$stage-order-ids.txt" response oid state ready=0
  : >"$replies"
  : >"$ids"
  for _ in $(seq 1 "$count"); do
    response="$(curl -fsS -X POST -H 'Content-Type: application/json' \
      -d '{"symbol":"AAPL","side":"BUY","quantity":1,"limit_price_x10000":999999999999,"transport":"SOCKET"}' \
      "$API/api/order")"
    oid="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["client_order_id"])' <<<"$response")"
    printf '%s\n' "$response" >>"$replies"
    printf '%s\n' "$oid" >>"$ids"
    sleep 0.01
  done
  if test "$require_load" -eq 1; then
    ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
      "set -eu; pid=\$(cat '$TREX_DIR/$stage-load.pid'); kill -0 \"\$pid\""
  fi
  for _ in $(seq 1 250); do
    state="$(curl -fsS "$API/api/state")"
    if python3 - "$ids" "$state" <<'PY'
import json, pathlib, sys
ids = {int(line) for line in pathlib.Path(sys.argv[1]).read_text().splitlines()}
rows = {int(row.get("client_order_id", 0)): row for row in json.loads(sys.argv[2]).get("orders", [])}
raise SystemExit(not all(
    oid in rows
    and rows[oid].get("result") == "ORDER_EXECUTED"
    and int(rows[oid].get("order_rtt_ns", 0)) > 0
    for oid in ids
))
PY
    then
      ready=1
      printf '%s' "$state" >"$RAW/$stage-state.json"
      break
    fi
    sleep 0.1
  done
  test "$ready" -eq 1
  python3 - "$ids" "$RAW/$stage-state.json" "$DERIVED/$stage-order-stats.json" <<'PY'
import json, math, pathlib, statistics, sys
ids = [int(line) for line in pathlib.Path(sys.argv[1]).read_text().splitlines()]
state = json.load(open(sys.argv[2], encoding="utf-8"))
by_id = {int(row.get("client_order_id", 0)): row for row in state.get("orders", [])}
rows = [by_id[oid] for oid in ids]
values = sorted(int(row["order_rtt_ns"]) for row in rows)
def nearest_rank(q):
    return values[max(0, math.ceil(q * len(values)) - 1)]
out = {
    "status": "PASS",
    "orders_executed": len(rows),
    "first_client_order_id": ids[0],
    "last_client_order_id": ids[-1],
    "rtt_ns": {
        "min": values[0],
        "p50": int(statistics.median(values)),
        "p99_nearest_rank": nearest_rank(0.99),
        "max": values[-1],
    },
    "rows": rows,
}
json.dump(out, open(sys.argv[3], "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print(f"orders_executed={len(rows)}")
print(f"rtt_ns_min_p50_p99_max={values[0]}/{out['rtt_ns']['p50']}/{out['rtt_ns']['p99_nearest_rank']}/{values[-1]}")
PY
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

lanz_count() {
  awk '
    /^Interface[[:space:]]+Traffic Class[[:space:]]+Count/ {table=1; next}
    /^Global Hit Count/ {table=0}
    table && $1=="Et1" && $2 ~ /^[0-9]+$/ && $3 ~ /^[0-9]+$/ {sum+=$3}
    END {print sum+0}
  ' "$1"
}

capture_tos_count() {
  local file="$1" tos="$2"
  grep -Ec "tos $tos([, ])" "$file"
}

capture_frame_count() {
  grep -Ec '^[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]+ ' "$1"
}

switch_snapshot() {
  local name="$1"
  switch_show "$name" \
    'show queue-monitor length statistics' \
    'show queue-monitor length Ethernet 1' \
    'show queue-monitor length drops' \
    'show platform fm6000 counters interface Ethernet1' \
    'show interfaces Ethernet1 counters errors' \
    'show interfaces Ethernet1 counters discards'
}

start_load() {
  local stage="$1"
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
    bash -s -- "$TREX_DIR" "$stage" "$RUN_ID" "$FAKE_MAC_COLON" \
    "$LOAD_PPS_PER_INGRESS" "$LOAD_DURATION_SECONDS" <<'REMOTE'
set -eu
dir="$1"; stage="$2"; run_id="$3"; dst="$4"; pps="$5"; duration="$6"
case "$dir" in /run/flle-qos-contention-*) ;; *) exit 91;; esac
rm -f -- "$dir/$stage-ready.json" "$dir/$stage-load.json" "$dir/$stage-load.pid"
nohup /usr/bin/python3 "$dir/trex_qos_contention_client.py" \
  --run-id "$run_id" --mode load --stage "$stage" --dst-mac "$dst" \
  --pps "$pps" --duration "$duration" --packet-size 1514 \
  --ready "$dir/$stage-ready.json" --summary "$dir/$stage-load.json" \
  >"$dir/$stage-load.txt" 2>&1 </dev/null &
printf '%s\n' "$!" >"$dir/$stage-load.pid"
REMOTE
  for _ in $(seq 1 100); do
    if ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
      "test -s '$TREX_DIR/$stage-ready.json'"; then
      scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes \
        "root@10.1.1.11:$TREX_DIR/$stage-ready.json" "$RAW/"
      return 0
    fi
    sleep 0.1
  done
  return 1
}

finish_load() {
  local stage="$1"
  for _ in $(seq 1 300); do
    if ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
      "test -s '$TREX_DIR/$stage-load.json'"; then
      scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes \
        "root@10.1.1.11:$TREX_DIR/$stage-load.json" \
        "root@10.1.1.11:$TREX_DIR/$stage-load.txt" "$RAW/"
      python3 - "$RAW/$stage-load.json" <<'PY'
import json, sys
row = json.load(open(sys.argv[1], encoding="utf-8"))
assert row["status"] == "PASS"
assert row["actual_total_opackets_delta"] > 0
assert not any(row["io_error_deltas"].values())
PY
      return 0
    fi
    sleep 0.1
  done
  return 1
}

run_stage() {
  local stage="$1" tos="$2" tagged="$3"
  if test "$tagged" -eq 1; then
    HOST_RULE_ADDED=1
    ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
      bash -s -- "$SOURCE_PORT" "$RULE_TAG" <<'REMOTE'
set -eu
iptables -t mangle -A OUTPUT -o ens64np1 -p tcp \
  -s 20.1.1.2 -d 20.1.1.1 --sport "$1" --dport 43120 \
  -m comment --comment "$2" -j DSCP --set-dscp 46
iptables-save -t mangle | grep -F "$2"
REMOTE
  fi
  switch_snapshot "$stage-before"
  start_capture "$stage"
  start_load "$stage"
  sleep 0.2
  issue_orders "$stage" "$ORDER_COUNT" | tee "$RAW/$stage-orders-summary.txt"
  finish_load "$stage"
  sleep 1
  stop_capture "$stage"
  switch_snapshot "$stage-after"
  if test "$tagged" -eq 1; then remove_host_rule; fi

  local frames tos_count p1_before p1_after p5_before p5_after events_before events_after
  frames="$(capture_frame_count "$RAW/$stage-decode.txt")"
  tos_count="$(capture_tos_count "$RAW/$stage-decode.txt" "$tos")"
  p1_before="$(queue_counter "$RAW/$stage-before.txt" 1)"
  p1_after="$(queue_counter "$RAW/$stage-after.txt" 1)"
  p5_before="$(queue_counter "$RAW/$stage-before.txt" 5)"
  p5_after="$(queue_counter "$RAW/$stage-after.txt" 5)"
  events_before="$(lanz_count "$RAW/$stage-before.txt")"
  events_after="$(lanz_count "$RAW/$stage-after.txt")"
  test "$frames" -ge "$ORDER_COUNT"
  test "$tos_count" -eq "$frames"
  test "$events_after" -gt "$events_before"
  test "$p1_after" -gt "$p1_before"
  if test "$tagged" -eq 1; then
    test $((p5_after - p5_before)) -ge "$frames"
  else
    test $((p5_after - p5_before)) -eq 0
  fi
  python3 - "$RAW/$stage-load.json" "$DERIVED/$stage-order-stats.json" \
    "$frames" "$tos_count" "$((p1_after - p1_before))" \
    "$((p5_after - p5_before))" "$((events_after - events_before))" \
    "$DERIVED/$stage.json" <<'PY'
import json, sys
load = json.load(open(sys.argv[1], encoding="utf-8"))
orders = json.load(open(sys.argv[2], encoding="utf-8"))
out = {
    "status": "PASS",
    "load": load,
    "orders": orders,
    "captured_order_frames": int(sys.argv[3]),
    "captured_expected_tos_frames": int(sys.argv[4]),
    "et1_priority_1_delta": int(sys.argv[5]),
    "et1_priority_5_delta": int(sys.argv[6]),
    "et1_lanz_event_delta": int(sys.argv[7]),
}
json.dump(out, open(sys.argv[8], "w", encoding="utf-8"), ensure_ascii=False, indent=2)
PY
}

# Fail closed unless the current Chapter 6 Socket path and physical data path are healthy.
status="$(bash apps/flle-trading-lab/scripts/transport_labctl.sh status "$PARENT_RUN_ID")"
python3 - "$status" <<'PY'
import json, sys
s = json.loads(sys.argv[1])
assert s["mode"] == "SFC" and s["transition"] == "READY" and s["owner"] == "sfc"
assert s["data_ip_present"] is True
assert s["hardware_receipts"]["socket"]["verified"] is True
PY
socket_pid="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["hardware_receipts"]["socket"]["pid"])' "$status")"
socket_line="$(ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
  "ss -Htnp | grep -F '20.1.1.1:43120' | grep -F 'pid=$socket_pid,'")"
test "$(printf '%s\n' "$socket_line" | wc -l)" -eq 1
local_endpoint="$(awk '{print $4}' <<<"$socket_line")"
SOURCE_PORT="${local_endpoint##*:}"
[[ "$SOURCE_PORT" =~ ^[0-9]+$ ]]
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
  "set -eu; test \"\$(basename \"\$(readlink /sys/bus/pci/devices/0000:03:00.0/driver)\")\" = sfc; ip -4 addr show dev ens64np1 | grep -Fq '20.1.1.2/24'; ! iptables-save -t mangle | grep -F '$RULE_TAG'; ping -q -I ens64np1 -c 3 -W 1 20.1.1.1" \
  >"$RAW/vm2-preflight.txt"
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
  "iptables-save -t mangle | sed -E '/^# (Generated|Completed) /d'" \
  >"$RAW/vm2-iptables-before.txt"

switch_show switch-before \
  'show version' \
  'show interfaces Ethernet1, Ethernet2, Ethernet11, Ethernet12 status' \
  'show qos interfaces Ethernet1' \
  'show qos interfaces Ethernet2' \
  'show qos maps' \
  'show queue-monitor length status' \
  'show mac address-table static' \
  'show running-config | include ^queue-monitor|^qos map|mac address-table static' \
  'show startup-config | include ^queue-monitor|^qos map|mac address-table static' \
  'show running-config interfaces Ethernet1' \
  'show running-config interfaces Ethernet2' \
  'show startup-config interfaces Ethernet1' \
  'show startup-config interfaces Ethernet2'
grep -Fq 'queue-monitor length disabled' "$RAW/switch-before.txt"
! grep -Fq "$FAKE_MAC_DOTTED" "$RAW/switch-before.txt"
if grep -Eq '^   (qos|tx-queue|queue-monitor)' "$RAW/switch-before.txt"; then
  printf 'pre-existing QoS/queue-monitor config on Et1/Et2; refusing to overwrite\n' >&2
  exit 1
fi

# Reuse the already-audited BCM/TRex bootstrap; only the bounded load client differs.
sed \
  -e "s/readonly run_id=20260721T053935Z/readonly run_id=$RUN_ID/" \
  -e 's#/run/flle-lanz-lower-#/run/flle-qos-contention-#g' \
  -e 's/trex_lanz_lower_client.py/trex_qos_contention_client.py/g' \
  -e 's/fllelanzlower53935/flleqoscontention/g' \
  -e 's/flle-lanz-lower-recovery-/flle-qos-contention-recovery-/g' \
  -e 's#/opt/trex/v3.08.tar.gz#/opt/flle/prewarm/trex/v3.08.tar.gz#g' \
  "$TREX_TEMPLATE" >"$TMP/remote-qos-trex-control.sh"
install -m 0755 "$TREX_CLIENT" "$TMP/trex_qos_contention_client.py"
install -m 0644 "$TREX_CFG" "$TMP/trex-dual.yaml"
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
  "set -eu; test ! -e '$TREX_DIR'; mkdir -m 700 '$TREX_DIR'"
TREX_REMOTE_DEPLOYED=1
scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes \
  "$TMP/remote-qos-trex-control.sh" "$TMP/trex_qos_contention_client.py" \
  "$TMP/trex-dual.yaml" "root@10.1.1.11:$TREX_DIR/"
TREX_INSTALLED=1
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
  'set -eu; test ! -e /opt/trex && test ! -L /opt/trex; archive=/opt/flle/prewarm/trex/v3.08.tar.gz; test "$(stat -c %s "$archive")" = 284092535; test "$(sha256sum "$archive" | cut -d" " -f1)" = d2ac73627906c4ce01127c1c6954464fab373463966ea9592509446e74972b5f; install -d -m 0755 /opt/trex; tar -xzf "$archive" -C /opt/trex; test -x /opt/trex/v3.08/t-rex-64'
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
  "/usr/bin/bash '$TREX_CTL' preflight" >"$RAW/vm11-preflight.txt"
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
  "/usr/bin/bash '$TREX_CTL' arm-deadman 900" >"$RAW/vm11-deadman-arm.txt"
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
  "/usr/bin/bash '$TREX_CTL' start" >"$RAW/vm11-trex-start.txt"
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
  "/usr/bin/python3 '$TREX_DIR/trex_qos_contention_client.py' --run-id '$RUN_ID' --mode prepare --summary '$TREX_DIR/prepare.json'" \
  >"$RAW/vm11-trex-prepare.txt" 2>&1
scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes \
  "root@10.1.1.11:$TREX_DIR/prepare.json" "$RAW/trex-prepare.json"
python3 - "$RAW/trex-prepare.json" <<'PY'
import json, sys
assert json.load(open(sys.argv[1], encoding="utf-8"))["status"] == "PASS"
PY

SWITCH_CONFIGURED=1
switch_config switch-qos-active \
  'configure terminal' \
  'queue-monitor length' \
  'mac address-table static 0200.0007.0001 vlan 20 interface Ethernet1' \
  'interface Ethernet2' 'qos trust dscp' \
  'interface Ethernet1' \
  'queue-monitor length thresholds 64 32' \
  'tx-queue 5' 'priority strict' 'exit' \
  'tx-queue 3' 'no priority' 'bandwidth percent 40' 'exit' \
  'tx-queue 2' 'bandwidth percent 30' 'exit' \
  'tx-queue 1' 'bandwidth percent 20' 'exit' \
  'tx-queue 0' 'bandwidth percent 10' 'exit' \
  'end' \
  'show qos interfaces Ethernet1' \
  'show qos interfaces Ethernet2' \
  'show qos maps' \
  'show queue-monitor length status' \
  'show mac address-table static' \
  'show running-config interfaces Ethernet1' \
  'show running-config interfaces Ethernet2'
grep -Fq 'Trust Mode: DSCP' "$RAW/switch-qos-active.txt"
grep -Eq '^   5 +[-0-9 /().]+SP / SP' "$RAW/switch-qos-active.txt"
grep -A2 -F 'tx-queue 5' "$RAW/switch-qos-active.txt" | grep -Fq 'priority strict'
grep -Eq '^   3 +40 / 40 +[-0-9 /().]+RR / RR' "$RAW/switch-qos-active.txt"
grep -Fq 'tc:   1  0  2  3  4  5  6  7' "$RAW/switch-qos-active.txt"
grep -Fq 'tx-queue:  0  1  2  3  4  5  6  7' "$RAW/switch-qos-active.txt"
grep -Fq "$FAKE_MAC_DOTTED" "$RAW/switch-qos-active.txt"

ready=0
for attempt in $(seq 1 24); do
  switch_show "switch-lanz-ready-$attempt" \
    'show agent uptime | include AltaLanz' 'show queue-monitor length statistics'
  if grep -Fq 'AltaLanz' "$RAW/switch-lanz-ready-$attempt.txt" && \
      ! grep -Fq '! Lanz agent not running.' "$RAW/switch-lanz-ready-$attempt.txt"; then
    cp "$RAW/switch-lanz-ready-$attempt.txt" "$RAW/switch-lanz-ready.txt"
    ready=1
    break
  fi
  sleep 3
done
test "$ready" -eq 1

run_stage baseline 0x0 0
run_stage tagged 0xb8 1

# Compare like-for-like load and require the tagged strict queue to improve p99.
python3 - "$DERIVED/baseline.json" "$DERIVED/tagged.json" "$OUT/result.json" <<'PY'
import json, sys
a = json.load(open(sys.argv[1], encoding="utf-8"))
b = json.load(open(sys.argv[2], encoding="utf-8"))
a_pkts = a["load"]["actual_total_opackets_delta"]
b_pkts = b["load"]["actual_total_opackets_delta"]
ratio = min(a_pkts, b_pkts) / max(a_pkts, b_pkts)
a99 = a["orders"]["rtt_ns"]["p99_nearest_rank"]
b99 = b["orders"]["rtt_ns"]["p99_nearest_rank"]
assert ratio >= 0.90, (a_pkts, b_pkts, ratio)
assert b99 < a99, (a99, b99)
out = {
    "result": "PASS",
    "evidence_kind": "fresh_live_real_orders_with_shared_egress_contention",
    "load_packet_count_similarity_ratio": ratio,
    "baseline": a,
    "tagged": b,
    "p99_improvement_ratio": a99 / b99,
}
json.dump(out, open(sys.argv[3], "w", encoding="utf-8"), ensure_ascii=False, indent=2)
PY

# Stop synthetic load infrastructure before restoring the switch and proving business health.
recover_trex
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
  "/usr/bin/bash '$TREX_CTL' final-assert" >"$RAW/vm11-final.txt"
mkdir -p "$RAW/vm11-artifacts"
scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes \
  "root@10.1.1.11:$TREX_DIR/"'*' "$RAW/vm11-artifacts/"
cleanup_trex_remote
remove_host_rule
restore_switch
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
  "iptables-save -t mangle | sed -E '/^# (Generated|Completed) /d'" \
  >"$RAW/vm2-iptables-after.txt"
cmp "$RAW/vm2-iptables-before.txt" "$RAW/vm2-iptables-after.txt"
switch_show switch-after \
  'show interfaces Management1 status' \
  'show switching mode' \
  'show qos interfaces Ethernet1' \
  'show qos interfaces Ethernet2' \
  'show queue-monitor length status' \
  'show mac address-table static' \
  'show running-config | include ^queue-monitor|^qos map|mac address-table static' \
  'show startup-config | include ^queue-monitor|^qos map|mac address-table static' \
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
grep -Fq 'connected' "$RAW/switch-after.txt"
grep -Fq 'cut through' "$RAW/switch-after.txt"
grep -Fq 'queue-monitor length disabled' "$RAW/switch-after.txt"
! grep -Fq "$FAKE_MAC_DOTTED" "$RAW/switch-after.txt"
test "$(grep -c 'SP / SP' "$RAW/switch-after.txt")" -eq 16
post_restore_summary="$(issue_orders post-restore 1 0)"
printf '%s\n' "$post_restore_summary" >"$RAW/post-restore-order-summary.txt"
cleanup_capture_remote

python3 - "$OUT/result.json" "$RAW/result.txt" "$OUT" <<'PY'
import json, sys
r = json.load(open(sys.argv[1], encoding="utf-8"))
a, b = r["baseline"], r["tagged"]
lines = [
    "===== 教师现场 C2 · 真实订单共享出口 QoS A/B =====",
    "result=PASS",
    "platform=DCS-7150S-24-F / EOS 4.23.16M-2GB / FM6000",
    "background=Et11+Et12 untagged 1514B -> static test MAC -> Et1 -> TC1/Q1",
    f"background_configured={a['load']['configured_pps_per_ingress']} pps/ingress x2 for {a['load']['configured_duration_seconds']}s",
    f"background_actual_packets={a['load']['actual_total_opackets_delta']} / {b['load']['actual_total_opackets_delta']}",
    f"baseline=unmarked orders in Q1; executed={a['orders']['orders_executed']}; p50/p99={a['orders']['rtt_ns']['p50']}/{a['orders']['rtt_ns']['p99_nearest_rank']} ns",
    f"baseline_queue=P1 +{a['et1_priority_1_delta']}; P5 +{a['et1_priority_5_delta']}; LANZ +{a['et1_lanz_event_delta']}",
    f"tagged=DSCP46 -> TC5 -> Q5 explicit priority strict; executed={b['orders']['orders_executed']}; p50/p99={b['orders']['rtt_ns']['p50']}/{b['orders']['rtt_ns']['p99_nearest_rank']} ns",
    f"tagged_queue=P1 +{b['et1_priority_1_delta']}; P5 +{b['et1_priority_5_delta']}; LANZ +{b['et1_lanz_event_delta']}",
    f"p99_improvement_ratio={r['p99_improvement_ratio']:.2f}x",
    "host_restore=iptables mangle table byte-identical",
    "switch_restore=temporary static MAC, LANZ and QoS removed; startup unchanged; Management1 connected",
    "post_restore_order=ORDER_EXECUTED",
    "save_config=NO",
    f"evidence={sys.argv[3]}",
]
open(sys.argv[2], "w", encoding="utf-8").write("\n".join(lines) + "\n")
PY
printf 'PHASE=COMPLETE\n' >>"$OUT/run.env"
cat "$RAW/result.txt"
(cd "$OUT" && find raw derived -type f -print0 | sort -z | xargs -0 sha256sum >SHA256SUMS)
ROOT_SHA256="$(sha256sum "$OUT/SHA256SUMS" | awk '{print $1}')"
printf 'ROOT_SHA256=%s\n' "$ROOT_SHA256" >>"$OUT/run.env"
printf 'root_sha256=%s\n' "$ROOT_SHA256"
trap - EXIT INT TERM HUP
find "$TMP" -depth -delete
