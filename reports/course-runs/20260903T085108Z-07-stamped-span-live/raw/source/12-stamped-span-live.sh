#!/usr/bin/env bash
# 交易保持在线：用真实行情测「交换机入口戳 → .2 网卡 PHC RX」。
# 7150 做 PTP GM，.2 跟随；mac timestamp 只写 Et11；不保存 startup-config。
set -Eeuo pipefail
cd /financial-low-latency

ASSET=Documents/newDoc/assets/07-arista-time
COMMON=Documents/newDoc/assets/common
SUPPORT="$ASSET/live-support/stamped-span"
SUPPORT_MANIFEST="$ASSET/LIVE-SUPPORT-SHA256SUMS"
ENTRY_SCRIPT="$ASSET/12-stamped-span-live.sh"
EOS_CLI="$COMMON/eos_cli.py"
. Documents/reports/run-state/ch06-four-path.env
PARENT_RUN_ID="$RUN_ID"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-07-stamped-span-live"
OUT="Documents/reports/course-runs/$RUN_ID"
RAW="$OUT/raw"
DERIVED="$OUT/derived"
TMP="$(mktemp -d)"
API=http://10.1.1.101:8088
REMOTE_DIR="/run/flle-ch07-span/$RUN_ID"
CAPTURE_SECONDS=8
SWITCH_CONFIGURED=0
DOT2_DEPLOYED=0
DOT11_DEPLOYED=0
DOT11_LINK_UP=0
BASE_TX=0
BASE_RX=0

test ! -e "$OUT"
mkdir -p "$RAW/source" "$DERIVED"
SUPPORT_MANIFEST_SHA256="$(sha256sum "$SUPPORT_MANIFEST" | awk '{print $1}')"
ENTRY_SCRIPT_SHA256="$(sha256sum "$ENTRY_SCRIPT" | awk '{print $1}')"
EOS_CLI_SHA256="$(sha256sum "$EOS_CLI" | awk '{print $1}')"
printf 'RUN_ID=%s\nPARENT_RUN_ID=%s\nRESULT_KIND=FRESH_LIVE_STAMPED_SPAN\nCAPTURE_SECONDS=%s\nSUPPORT_MANIFEST_SHA256=%s\nENTRY_SCRIPT_SHA256=%s\nEOS_CLI_SHA256=%s\nTRADING_ONLINE=1\nPHASE=STARTED\n' \
  "$RUN_ID" "$PARENT_RUN_ID" "$CAPTURE_SECONDS" \
  "$SUPPORT_MANIFEST_SHA256" "$ENTRY_SCRIPT_SHA256" "$EOS_CLI_SHA256" \
  >"$OUT/run.env"
install -m 0644 "$ENTRY_SCRIPT" "$RAW/source/12-stamped-span-live.sh"
install -m 0644 "$EOS_CLI" "$RAW/source/eos_cli.py"
install -m 0644 "$SUPPORT_MANIFEST" "$RAW/LIVE-SUPPORT-SHA256SUMS"
install -m 0644 "$SUPPORT/analyze_stamped_span.py" "$RAW/source/analyze_stamped_span.py"
install -m 0644 "$SUPPORT/ptp-switch-slave.cfg" "$RAW/source/ptp-switch-slave.cfg"
install -m 0644 "$SUPPORT/cleanup-stamped-span-node.sh" "$RAW/source/cleanup-stamped-span-node.sh"
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

trading_state() {
  curl -fsS -m 5 "$API/api/state" | python3 -c \
    'import json,sys; d=json.load(sys.stdin); print(d["data_plane_mode"], d["data_plane_transition"], d["data_plane_owner"])'
}

restore_switch() {
  test "$SWITCH_CONFIGURED" -eq 1 || return 0
  switch_config switch-restore \
    'configure terminal' \
    'no platform fm6000 keyframe FLLETS' \
    'no monitor session FLLETS' \
    'interface Ethernet11' \
    'no mac timestamp' \
    'switchport access vlan 20' \
    'end' \
    'configure terminal' \
    'interface Ethernet2' \
    'default ptp enable' \
    'end' \
    'configure terminal' \
    'default ptp mode' \
    'end' \
    'configure terminal' \
    'no vlan 3101' \
    'end' \
    'show ptp' \
    'show monitor session' \
    'show platform fm6000 keyframe' \
    'show vlan id 20' \
    'show running-config interfaces Ethernet11' \
    'show running-config interfaces Ethernet2' \
    'show interfaces Ethernet1, Ethernet2, Ethernet11, Ethernet12 status'
  SWITCH_CONFIGURED=0
}

cleanup_dot2() {
  test "$DOT2_DEPLOYED" -eq 1 || return 0
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
    "/usr/bin/bash '$REMOTE_DIR/cleanup-stamped-span-node.sh' ens64np1 \
      '$REMOTE_DIR/ptp4l.pid' '$REMOTE_DIR/tcpdump.pid' \
      '$BASE_TX' '$BASE_RX' '$REMOTE_DIR/cleanup.log'" || true
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
    bash -s -- "$REMOTE_DIR" <<'REMOTE' || true
set -eu
case "$1" in /run/flle-ch07-span/*) ;; *) exit 91;; esac
if test -d "$1"; then find "$1" -depth -delete; fi
REMOTE
  DOT2_DEPLOYED=0
}

cleanup_dot11() {
  test "$DOT11_LINK_UP" -eq 1 || test "$DOT11_DEPLOYED" -eq 1 || return 0
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
    bash -s -- "$REMOTE_DIR" <<'REMOTE' || true
set -eu
case "$1" in /run/flle-ch07-span/*) ;; *) exit 91;; esac
if test -f "$1/tcpdump.pid"; then
  pid="$(cat "$1/tcpdump.pid")"
  kill -INT "$pid" 2>/dev/null || true
  sleep 0.2
  kill -9 "$pid" 2>/dev/null || true
fi
ip link set ens64f0np0 down || true
if test -d "$1"; then find "$1" -depth -delete; fi
REMOTE
  DOT11_LINK_UP=0
  DOT11_DEPLOYED=0
}

cleanup() {
  local original_rc=$? cleanup_failed=0
  trap - EXIT INT TERM HUP
  set +e
  cleanup_dot2 || cleanup_failed=1
  cleanup_dot11 || cleanup_failed=1
  restore_switch || cleanup_failed=1
  find "$TMP" -depth -delete
  if test "$cleanup_failed" -ne 0; then
    printf 'STAMPED_SPAN_CLEANUP=FAIL original_rc=%s\n' "$original_rc" >&2
    exit 125
  fi
  if test "$original_rc" -ne 0; then exit "$original_rc"; fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

test "$(trading_state)" = "SFC READY sfc"
printf '%s\n' "$(trading_state)" >"$RAW/trading-before.txt"

ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
  "set -eu; test -x /usr/sbin/ptp4l; test -x /usr/sbin/pmc; test -x /usr/sbin/hwstamp_ctl; test -x /usr/bin/tcpdump; test -c /dev/ptp0; test \"\$(basename \"\$(readlink /sys/class/net/ens64np1/device/driver)\")\" = sfc; ip -4 addr show dev ens64np1 | grep -Fq 20.1.1.2/24; for p in ptp4l phc2sys ts2phc sfptpd tcpdump; do pgrep -x \"\$p\" >/dev/null && exit 1 || :; done; ping -q -I ens64np1 -c 3 -W 1 20.1.1.1" \
  >"$RAW/preflight-10.1.1.2.txt"
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
  "set -eu; test -x /usr/bin/tcpdump; test \"\$(cat /sys/class/net/ens64f0np0/address)\" = 00:0a:f7:f8:48:a0; test \"\$(cat /sys/class/net/ens64f0np0/operstate)\" = down; test \"\$(cat /sys/class/net/ens64f1np1/operstate)\" = down; pgrep -x tcpdump >/dev/null && exit 1 || :" \
  >"$RAW/preflight-10.1.1.11.txt"

ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
  '/usr/sbin/hwstamp_ctl -i ens64np1' >"$RAW/hwstamp-baseline.txt"
BASE_TX="$(awk '/tx_type/{print $2; exit}' "$RAW/hwstamp-baseline.txt")"
BASE_RX="$(awk '/rx_filter/{print $2; exit}' "$RAW/hwstamp-baseline.txt")"

switch_show switch-before \
  'show switch forwarding-mode' \
  'show ptp' \
  'show monitor session' \
  'show platform fm6000 keyframe' \
  'show vlan id 20' \
  'show interfaces Ethernet1, Ethernet2, Ethernet11, Ethernet12 status' \
  'show running-config interfaces Ethernet11' \
  'show running-config interfaces Ethernet2'
grep -Fq 'cut through' "$RAW/switch-before.txt"
grep -Fq 'PTP Mode: Disabled' "$RAW/switch-before.txt"
grep -Fq 'No sessions created' "$RAW/switch-before.txt"
grep -Fq 'No Keyframes configured' "$RAW/switch-before.txt"

SWITCH_CONFIGURED=1
switch_config switch-sink \
  'configure terminal' \
  'vlan 3101' \
  'name FLLE_TS_SINK_20260903' \
  'interface Ethernet11' \
  'mac timestamp before-fcs' \
  'switchport access vlan 3101' \
  'end' \
  'show running-config interfaces Ethernet11' \
  'show vlan id 3101'

ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
  'ip link set ens64f0np0 up'
DOT11_LINK_UP=1
for _ in 1 2 3 4 5 6 7 8 9 10; do
  switch_show switch-et11-link 'show interfaces Ethernet11 status'
  grep -q 'Et11 .* connected' "$RAW/switch-et11-link.txt" && break
  sleep 1
done
grep -q 'Et11 .* connected' "$RAW/switch-et11-link.txt"

switch_config switch-mirror \
  'configure terminal' \
  'monitor session FLLETS source Ethernet1 rx' \
  'monitor session FLLETS destination Ethernet11' \
  'end' \
  'show monitor session'
grep -Fq 'FLLETS' "$RAW/switch-mirror.txt"
grep -Fq 'Ethernet1' "$RAW/switch-mirror.txt"
grep -Fq 'Ethernet11' "$RAW/switch-mirror.txt"

switch_config switch-ptp \
  'configure terminal' \
  'ptp mode boundary' \
  'interface Ethernet2' \
  'ptp enable' \
  'end' \
  'show ptp'
grep -Fq 'PTP Mode: Boundary' "$RAW/switch-ptp.txt"

ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
  bash -s -- "$REMOTE_DIR" <<'REMOTE'
set -eu
install -d -m 0755 "$1"
REMOTE
scp -o BatchMode=yes -o StrictHostKeyChecking=yes \
  "$SUPPORT/ptp-switch-slave.cfg" \
  "$SUPPORT/cleanup-stamped-span-node.sh" \
  root@10.1.1.2:"$REMOTE_DIR/"
DOT2_DEPLOYED=1
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
  bash -s -- "$REMOTE_DIR" <<'REMOTE'
set -eu
rm -f /var/run/ptp4l-stamped-span
/usr/sbin/ptp4l -f "$1/ptp-switch-slave.cfg" -i ens64np1 -s -m -q \
  >"$1/ptp4l.log" 2>&1 &
echo $! >"$1/ptp4l.pid"
sleep 0.3
kill -0 "$(cat "$1/ptp4l.pid")"
REMOTE

locked=0
for _ in $(seq 1 45); do
  if ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
    "grep -E 'to SLAVE' '$REMOTE_DIR/ptp4l.log'" >"$RAW/ptp-slave-hit.txt" 2>/dev/null; then
    locked=1
    break
  fi
  sleep 1
done
test "$locked" -eq 1
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
  "/usr/sbin/pmc -u -b 0 -s /var/run/ptp4l-stamped-span 'GET PORT_DATA_SET'; echo '---'; /usr/sbin/pmc -u -b 0 -s /var/run/ptp4l-stamped-span 'GET CURRENT_DATA_SET'; echo '---'; /usr/sbin/hwstamp_ctl -i ens64np1" \
  >"$RAW/ptp-pmc.txt"
grep -Fq SLAVE "$RAW/ptp-pmc.txt"

switch_config switch-keyframe \
  'configure terminal' \
  'platform fm6000 keyframe FLLETS interface Ethernet11 21.1.1.11 000a.f7f8.48a0' \
  'platform fm6000 keyframe FLLETS source ip 20.1.1.254' \
  'platform fm6000 keyframe FLLETS fields skew' \
  'end' \
  'show platform fm6000 keyframe'
grep -Fq 'FLLETS' "$RAW/switch-keyframe.txt"

ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
  bash -s -- "$REMOTE_DIR" <<'REMOTE'
set -eu
install -d -m 0755 "$1"
REMOTE
DOT11_DEPLOYED=1

test "$(trading_state)" = "SFC READY sfc"
printf '%s\n' "$(trading_state)" >"$RAW/trading-mid.txt"

ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
  bash -s -- "$REMOTE_DIR" <<'REMOTE'
set -eu
/usr/bin/tcpdump -i ens64f0np0 -nn --time-stamp-precision=nano -s 0 \
  -w "$1/copy.pcap" 'udp or ip proto 253' \
  >"$1/tcpdump.log" 2>&1 &
echo $! >"$1/tcpdump.pid"
REMOTE
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
  bash -s -- "$REMOTE_DIR" <<'REMOTE'
set -eu
/usr/bin/tcpdump -i ens64np1 -nn -j adapter_unsynced --time-stamp-precision=nano -s 0 \
  -w "$1/live.pcap" 'udp and src host 20.1.1.1 and src port 38622' \
  >"$1/tcpdump.log" 2>&1 &
echo $! >"$1/tcpdump.pid"
REMOTE
sleep "$CAPTURE_SECONDS"
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
  "kill -INT \"\$(cat '$REMOTE_DIR/tcpdump.pid')\"" || true
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
  "kill -INT \"\$(cat '$REMOTE_DIR/tcpdump.pid')\"" || true
sleep 1

scp -o BatchMode=yes -o StrictHostKeyChecking=yes \
  root@10.1.1.2:"$REMOTE_DIR/live.pcap" "$RAW/live.pcap"
scp -o BatchMode=yes -o StrictHostKeyChecking=yes \
  root@10.1.1.2:"$REMOTE_DIR/ptp4l.log" "$RAW/ptp4l.log"
scp -o BatchMode=yes -o StrictHostKeyChecking=yes \
  root@10.1.1.11:"$REMOTE_DIR/copy.pcap" "$RAW/copy.pcap"
test -s "$RAW/live.pcap"
test -s "$RAW/copy.pcap"

python3 "$SUPPORT/analyze_stamped_span.py" \
  "$RAW/copy.pcap" "$RAW/live.pcap" "$DERIVED/analysis.json" \
  | tee "$RAW/analyze.txt"
python3 - "$DERIVED/analysis.json" <<'PY'
import json, sys
result = json.load(open(sys.argv[1], encoding="utf-8"))
assert result["pass"], result["gates"]
assert result["paired"] >= 1000, result["paired"]
PY

python3 - "$RAW/ptp4l.log" "$DERIVED/ptp4l-summary.json" <<'PY'
import json, re, sys
from pathlib import Path
text = Path(sys.argv[1]).read_text(encoding="utf-8", errors="replace")
offsets = [float(item) for item in re.findall(r"master offset\s+(-?\d+)", text)]
delays = [float(item) for item in re.findall(r"path delay\s+(-?\d+)", text)]
Path(sys.argv[2]).write_text(json.dumps({
    "slave_lines": len(re.findall(r"to SLAVE", text)),
    "offset_ns_last": offsets[-1] if offsets else None,
    "offset_ns_n": len(offsets),
    "path_delay_ns_last": delays[-1] if delays else None,
    "path_delay_ns_n": len(delays),
}, indent=2) + "\n", encoding="utf-8")
PY

cleanup_dot2
cleanup_dot11
restore_switch
test "$(trading_state)" = "SFC READY sfc"
printf '%s\n' "$(trading_state)" >"$RAW/trading-after.txt"
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
  'ping -q -I ens64np1 -c 3 -W 1 20.1.1.1; for p in ptp4l phc2sys ts2phc sfptpd tcpdump; do pgrep -x "$p" >/dev/null && exit 1 || :; done; /usr/sbin/hwstamp_ctl -i ens64np1' \
  >"$RAW/post-10.1.1.2.txt"
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
  'test "$(cat /sys/class/net/ens64f0np0/operstate)" = down; test "$(cat /sys/class/net/ens64f1np1/operstate)" = down; pgrep -x tcpdump >/dev/null && exit 1 || :' \
  >"$RAW/post-10.1.1.11.txt"
switch_show switch-after \
  'show switch forwarding-mode' \
  'show ptp' \
  'show monitor session' \
  'show platform fm6000 keyframe' \
  'show vlan id 20' \
  'show running-config interfaces Ethernet11' \
  'show running-config interfaces Ethernet2' \
  'show interfaces Ethernet1, Ethernet2, Ethernet11, Ethernet12 status'
grep -Fq 'cut through' "$RAW/switch-after.txt"
grep -Fq 'PTP Mode: Disabled' "$RAW/switch-after.txt"
grep -Fq 'No sessions created' "$RAW/switch-after.txt"
grep -Fq 'No Keyframes configured' "$RAW/switch-after.txt"
grep -Fq 'switchport access vlan 20' "$RAW/switch-after.txt"

python3 - "$DERIVED/analysis.json" "$DERIVED/ptp4l-summary.json" "$RAW/result.txt" "$OUT" "$PARENT_RUN_ID" <<'PY'
import json, sys
from pathlib import Path
analysis = json.load(open(sys.argv[1], encoding="utf-8"))
ptp = json.load(open(sys.argv[2], encoding="utf-8"))
delay = analysis["delay_ns"]
freq = analysis["freq"]
lines = [
    "===== 教师现场 D · 真实行情带戳副本 =====",
    "result=PASS",
    "path=.1 --Et1--> 7150 --Et2--> .2 ; copy Et1 rx + mac timestamp --> Et11 --> .11",
    f"parent_trading={sys.argv[5]}",
    f"paired={analysis['paired']}/{analysis['copy_market']}",
    f"keyframes={analysis['keyframes']}",
    f"last_sync={analysis['keyframe_last_sync'][0]}",
    f"ptp_slave_lines={ptp['slave_lines']}",
    f"ptp_offset_ns_last={ptp['offset_ns_last']}",
    f"ptp_path_delay_ns_last={ptp['path_delay_ns_last']}",
    f"T_live-T_in_ns min/p50/p99/max={delay['min']:.0f}/{delay['p50']:.0f}/{delay['p99']:.0f}/{delay['max']:.0f}",
    f"freq_resid_abs_p99_ns={freq['resid_ns']['abs_p99']:.0f}",
    "clock_note=7150 PTP is software-timestamped local GM; last_sync=0; not datasheet 350ns",
    "trading=SFC/READY/sfc throughout; save_config=NO",
    f"evidence={sys.argv[4]}",
]
Path(sys.argv[3]).write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
printf 'PHASE=COMPLETE\n' >>"$OUT/run.env"
cat "$RAW/result.txt"
(cd "$OUT" && find raw derived -type f -print0 | sort -z | xargs -0 sha256sum >SHA256SUMS)
ROOT_SHA256="$(sha256sum "$OUT/SHA256SUMS" | awk '{print $1}')"
printf 'ROOT_SHA256=%s\n' "$ROOT_SHA256" >>"$OUT/run.env"
printf 'root_sha256=%s\n' "$ROOT_SHA256"
trap - EXIT INT TERM HUP
find "$TMP" -depth -delete
