#!/usr/bin/env bash
# Fresh PTP/TC OFF/ON capture on the current X2522 -> 7150 -> X2522 path.
set -Eeuo pipefail
cd /financial-low-latency

RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-07-ptp-tc-live-ab"
OUT="Documents/reports/course-runs/$RUN_ID"
RAW="$OUT/raw"
DERIVED="$OUT/derived"
COMMON="Documents/newDoc/assets/common"
ASSET_ROOT="Documents/newDoc/assets/07-arista-time"
SUPPORT="$ASSET_ROOT/live-support/ptp"
SUPPORT_MANIFEST="$ASSET_ROOT/LIVE-SUPPORT-SHA256SUMS"
ENTRY_SCRIPT="$ASSET_ROOT/09-ptp-tc-live-ab.sh"
REMOTE_DIR="/root/flle-ptp-live-$RUN_ID"
TMP="$(mktemp -d)"
SWITCH_CONFIGURED=0
REMOTE_DEPLOYED=0
ACTIVE_STAGE=''

test ! -e "$OUT"
mkdir -p "$RAW/source" "$DERIVED"
SUPPORT_MANIFEST_SHA256="$(sha256sum "$SUPPORT_MANIFEST" | awk '{print $1}')"
ENTRY_SCRIPT_SHA256="$(sha256sum "$ENTRY_SCRIPT" | awk '{print $1}')"
printf 'RUN_ID=%s\nRESULT_KIND=PTP_TC_LIVE_AB_ATTEMPT\nSUPPORT_MANIFEST_SHA256=%s\nENTRY_SCRIPT_SHA256=%s\n' \
  "$RUN_ID" "$SUPPORT_MANIFEST_SHA256" "$ENTRY_SCRIPT_SHA256" >"$OUT/run.env"
install -m 0644 "$SUPPORT_MANIFEST" "$RAW/LIVE-SUPPORT-SHA256SUMS"
install -m 0644 "$ENTRY_SCRIPT" "$RAW/source/09-ptp-tc-live-ab.sh"
(cd "$ASSET_ROOT" && sha256sum -c LIVE-SUPPORT-SHA256SUMS) \
  >"$RAW/local-support-sha256.txt"

remote_cleanup() {
  local host="$1" role="$2" iface="$3" data_ip="$4" peer="$5"
  test -n "$ACTIVE_STAGE" || return 0
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes "root@$host" \
    "/usr/bin/bash '$REMOTE_DIR/cleanup-ptp-node.sh' '$iface' '$data_ip' '$peer' '$REMOTE_DIR/$ACTIVE_STAGE-$role-ptp.pid' '$REMOTE_DIR/$ACTIVE_STAGE-$role-tcpdump.pid' 0 '$REMOTE_DIR/$ACTIVE_STAGE-$role-trap-cleanup.log' '$RUN_ID-$ACTIVE_STAGE-$role'" \
    >/dev/null 2>&1
}

cleanup() {
  local original_rc=$? cleanup_failed=0
  trap - EXIT INT TERM HUP
  set +e
  if test "$REMOTE_DEPLOYED" -eq 1; then
    remote_cleanup 10.1.1.1 master ens64np0 20.1.1.1/24 20.1.1.2 || cleanup_failed=1
    remote_cleanup 10.1.1.2 client ens64np1 20.1.1.2/24 20.1.1.1 || cleanup_failed=1
  fi
  if test "$SWITCH_CONFIGURED" -eq 1; then
    printf '%s\n' \
      'configure terminal' 'interface Ethernet1' 'default ptp enable' 'end' \
      'configure terminal' 'interface Ethernet2' 'default ptp enable' 'end' \
      'configure terminal' 'default ptp mode' 'end' \
      'show clock' 'show running-config | include ^ptp|ptp enable' \
      'show startup-config | include ^ptp|ptp enable' 'show ptp' \
      >"$TMP/switch-cleanup.plan"
    python3 "$COMMON/eos_cli.py" --mode controlled-config \
      --plan "$TMP/switch-cleanup.plan" --output "$RAW/switch-trap-cleanup.txt" \
      >/dev/null || cleanup_failed=1
  fi
  find "$TMP" -depth -delete
  if test "$cleanup_failed" -ne 0; then
    printf 'PTP_TC_CLEANUP=FAIL original_rc=%s\n' "$original_rc" >&2
    exit 125
  fi
  if test "$original_rc" -ne 0; then exit "$original_rc"; fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

remote_preflight() {
  local host="$1" iface="$2" data_ip="$3" peer="$4"
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes "root@$host" \
    bash -s -- "$iface" "$data_ip" "$peer" <<'REMOTE'
iface="$1"
data_ip="$2"
peer="$3"
node="$(hostname 2>/dev/null || printf unknown)"
failed=0
fail() {
  printf 'PRECHECK_FAIL host=%s check=%s detail=%s\n' "$node" "$1" "$2" >&2
  failed=1
}
for tool in /usr/sbin/ptp4l /usr/sbin/pmc /usr/sbin/hwstamp_ctl /usr/bin/tcpdump; do
  test -x "$tool" || fail tool "$tool missing-or-not-executable"
done
driver="$(basename "$(readlink /sys/bus/pci/devices/0000:03:00.0/driver 2>/dev/null)" 2>/dev/null)"
test "$driver" = sfc || fail driver "expected=sfc actual=${driver:-missing}"
ip -4 addr show dev "$iface" 2>/dev/null | grep -Fq "$data_ip" || \
  fail data_ip "interface=$iface expected=$data_ip"
hugepages="$(cat /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages 2>/dev/null || printf missing)"
case "$hugepages" in
  0) ;;
  ''|*[!0-9]*) fail hugepages_probe "expected=integer actual=${hugepages:-empty}" ;;
  *) fail trading_hugepages "expected=0 actual=$hugepages" ;;
esac
for stack_file in /proc/driver/onload/stacks /proc/driver/onload/stacks_k /proc/driver/onload/stacks_ul; do
  if grep -q '[^[:space:]]' "$stack_file" 2>/dev/null; then
    fail trading_onload_stack "file=$stack_file content_bytes=$(wc -c <"$stack_file")"
  fi
done
trading_processes="$(pgrep -af '[f]lle-(trader|exchange)' 2>/dev/null | tr '\n' ';')"
if test -n "$trading_processes"; then
  fail trading_process "$trading_processes"
fi
for process in ptp4l phc2sys ts2phc sfptpd tcpdump; do
  if pgrep -x "$process" >/dev/null; then
    fail residual_process "$(pgrep -ax "$process" | tr '\n' ';')"
  fi
done
test -c /dev/ptp0 || fail phc_node /dev/ptp0-missing
ethtool -T "$iface" || fail timestamp_capability "ethtool-T-$iface-failed"
ping -q -I "$iface" -c 3 -W 1 "$peer" || fail data_link "ping-$peer-failed"
if test "$failed" -eq 0; then
  printf 'PRECHECK_OK host=%s interface=%s\n' "$node" "$iface"
fi
exit "$failed"
REMOTE
}

finalize_refusal() {
  local reason="$1"
  {
    printf 'result=REFUSED_BEFORE_MUTATION\n'
    printf 'reason=%s\n' "$reason"
    printf 'switch_configured=NO\nremote_deployed=NO\n'
    printf 'evidence=%s\n' "$OUT"
  } | tee "$OUT/REFUSED.txt"
  (cd "$OUT" && find . -type f ! -name SHA256SUMS -print0 | sort -z | \
    xargs -0 sha256sum >SHA256SUMS)
  printf 'root_sha256=%s\n' "$(sha256sum "$OUT/SHA256SUMS" | awk '{print $1}')"
  exit 2
}

preflight_failed=0
for spec in '10.1.1.1 ens64np0 20.1.1.1/24 20.1.1.2' \
            '10.1.1.2 ens64np1 20.1.1.2/24 20.1.1.1'; do
  read -r host iface data_ip peer <<<"$spec"
  set +e
  remote_preflight "$host" "$iface" "$data_ip" "$peer" 2>&1 | \
    tee "$RAW/preflight-$host.txt"
  preflight_rc=${PIPESTATUS[0]}
  set -e
  if test "$preflight_rc" -ne 0; then
    preflight_failed=1
  fi
done
if test "$preflight_failed" -ne 0; then
  if grep -Eq 'check=trading_(onload_stack|hugepages|process)' "$RAW"/preflight-*.txt; then
    printf '%s\n' '检测到交易系统仍在线：Onload stack 非空、HugePages 非零或 flle-trader / flle-exchange 进程仍在。请先按第六章正常停机后再运行本卡。'
    if grep -Fq 'check=trading_hugepages' "$RAW"/preflight-*.txt; then
      printf '%s\n' '在线 TCPDirect 状态下 .2 的 HugePages=128 是正常业务占用，不是应单独清零的残留；请通过第六章正常停机流程释放。'
    fi
    finalize_refusal TRADING_SYSTEM_STILL_ONLINE
  fi
  printf '%s\n' 'PTP/TC 维护窗前置检查失败；请根据 PRECHECK_FAIL 逐项修复后重试。'
  finalize_refusal PRECONDITION_FAILED
fi

printf '%s\n' 'show clock' 'show running-config | include ^ptp|ptp enable' \
  'show startup-config | include ^ptp|ptp enable' 'show ptp' \
  'show interfaces Ethernet1, Ethernet2 status' \
  'show interfaces Ethernet1, Ethernet2 counters errors' \
  >"$TMP/switch-baseline.plan"
python3 "$COMMON/eos_cli.py" --mode show --plan "$TMP/switch-baseline.plan" \
  --output "$RAW/switch-baseline.txt" >/dev/null
grep -Eq 'PTP Mode: Disabled|PTP is not configured' "$RAW/switch-baseline.txt"
! grep -Eq '^ptp mode|^[[:space:]]+ptp enable' "$RAW/switch-baseline.txt"

sed \
  -e "s#readonly CLEANUP_SCRIPT=\"/root/flle-preflight/cleanup-ptp-node.sh\"#readonly CLEANUP_SCRIPT=\"$REMOTE_DIR/cleanup-ptp-node.sh\"#" \
  -e 's/readonly DURATION_SECONDS="70"/readonly DURATION_SECONDS="40"/' \
  "$SUPPORT/run-guarded-ptp-node.sh" >"$TMP/run-guarded-ptp-node.sh"
install -m 0755 "$SUPPORT/cleanup-ptp-node.sh" "$TMP/cleanup-ptp-node.sh"
install -m 0644 "$SUPPORT/ptp-master.cfg" "$TMP/ptp-master.cfg"
install -m 0644 "$SUPPORT/ptp-client.cfg" "$TMP/ptp-client.cfg"
for host in 10.1.1.1 10.1.1.2; do
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes "root@$host" \
    "set -eu; test ! -e '$REMOTE_DIR'; mkdir -m 700 '$REMOTE_DIR'"
  scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes \
    "$TMP/run-guarded-ptp-node.sh" "$TMP/cleanup-ptp-node.sh" \
    "$TMP/ptp-master.cfg" "$TMP/ptp-client.cfg" "root@$host:$REMOTE_DIR/"
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes "root@$host" \
    "chmod 700 '$REMOTE_DIR/run-guarded-ptp-node.sh' '$REMOTE_DIR/cleanup-ptp-node.sh'"
done
REMOTE_DEPLOYED=1

run_stage() {
  local stage="$1" master_pid client_pid ready=0
  ACTIVE_STAGE="$stage"
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.1 \
    "env RUN_TAG='$RUN_ID-$stage-master' ROLE=master IFACE=ens64np0 MGMT_IP_CIDR=10.1.1.1/24 DATA_IP_CIDR=20.1.1.1/24 PEER_IP=20.1.1.2 CONFIG_PATH='$REMOTE_DIR/ptp-master.cfg' PTP_LOG='$REMOTE_DIR/$stage-master-ptp4l.log' PCAP_PATH='$REMOTE_DIR/$stage-master.pcap' TCPDUMP_LOG='$REMOTE_DIR/$stage-master-tcpdump.log' PTP_PIDFILE='$REMOTE_DIR/$stage-master-ptp.pid' TCPDUMP_PIDFILE='$REMOTE_DIR/$stage-master-tcpdump.pid' READY_MARKER='$REMOTE_DIR/$stage-master.ready' CLEANUP_LOG='$REMOTE_DIR/$stage-master-cleanup.log' /usr/bin/bash '$REMOTE_DIR/run-guarded-ptp-node.sh'" \
    >"$RAW/$stage-master-runner.txt" 2>&1 &
  master_pid=$!
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
    "env RUN_TAG='$RUN_ID-$stage-client' ROLE=client IFACE=ens64np1 MGMT_IP_CIDR=10.1.1.2/24 DATA_IP_CIDR=20.1.1.2/24 PEER_IP=20.1.1.1 CONFIG_PATH='$REMOTE_DIR/ptp-client.cfg' PTP_LOG='$REMOTE_DIR/$stage-client-ptp4l.log' PCAP_PATH='$REMOTE_DIR/$stage-client.pcap' TCPDUMP_LOG='$REMOTE_DIR/$stage-client-tcpdump.log' PTP_PIDFILE='$REMOTE_DIR/$stage-client-ptp.pid' TCPDUMP_PIDFILE='$REMOTE_DIR/$stage-client-tcpdump.pid' READY_MARKER='$REMOTE_DIR/$stage-client.ready' CLEANUP_LOG='$REMOTE_DIR/$stage-client-cleanup.log' /usr/bin/bash '$REMOTE_DIR/run-guarded-ptp-node.sh'" \
    >"$RAW/$stage-client-runner.txt" 2>&1 &
  client_pid=$!

  for _ in $(seq 1 100); do
    if ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.1 \
        "test -s '$REMOTE_DIR/$stage-master.ready'" 2>/dev/null && \
       ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
        "test -s '$REMOTE_DIR/$stage-client.ready'" 2>/dev/null; then
      ready=1
      break
    fi
    kill -0 "$master_pid" 2>/dev/null
    kill -0 "$client_pid" 2>/dev/null
    sleep 0.25
  done
  test "$ready" -eq 1
  sleep 12
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
    "set -eu; for dataset in CURRENT_DATA_SET PARENT_DATA_SET TIME_STATUS_NP PORT_DATA_SET; do printf '=== %s ===\\n' \"\$dataset\"; /usr/sbin/pmc -u -b 0 -d 24 \"GET \$dataset\"; done" \
    >"$RAW/$stage-client-pmc.txt"
  if test "$stage" = tc; then
    printf '%s\n' 'show clock' 'show ptp' 'show ptp interface' \
      'show interfaces Ethernet1, Ethernet2 counters errors' \
      >"$TMP/switch-tc-active.plan"
    python3 "$COMMON/eos_cli.py" --mode show --plan "$TMP/switch-tc-active.plan" \
      --output "$RAW/switch-tc-active.txt" >/dev/null
  fi
  wait "$master_pid"
  wait "$client_pid"

  for host_role in '10.1.1.1 master' '10.1.1.2 client'; do
    read -r host role <<<"$host_role"
    scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes \
      "root@$host:$REMOTE_DIR/$stage-$role-ptp4l.log" "$RAW/$stage-$role.ptp4l.log"
    scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes \
      "root@$host:$REMOTE_DIR/$stage-$role.pcap" "$RAW/$stage-$role.pcap"
    scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes \
      "root@$host:$REMOTE_DIR/$stage-$role-tcpdump.log" "$RAW/$stage-$role.tcpdump.log"
    scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes \
      "root@$host:$REMOTE_DIR/$stage-$role-cleanup.log" "$RAW/$stage-$role.cleanup.log"
    scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes \
      "root@$host:$REMOTE_DIR/$stage-$role.ready" "$RAW/$stage-$role.ready"
    scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes \
      "root@$host:$REMOTE_DIR/$stage-$role-ptp.pid" "$RAW/$stage-$role.ptp.pid"
    scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes \
      "root@$host:$REMOTE_DIR/$stage-$role-tcpdump.pid" "$RAW/$stage-$role.tcpdump.pid"
  done
  tcpdump -tttt -nn -vvv -r "$RAW/$stage-client.pcap" \
    '(udp port 319 or udp port 320)' >"$RAW/$stage-client-decode.txt" 2>&1
  python3 "$SUPPORT/analyze_ptp_log.py" "$RAW/$stage-client.ptp4l.log" \
    >"$DERIVED/$stage-client-stats.json"
  python3 "$SUPPORT/analyze_ptp_decode.py" "$RAW/$stage-client-decode.txt" \
    >"$DERIVED/$stage-client-pcap.json"
  python3 - "$DERIVED/$stage-client-stats.json" <<'PY'
import json, sys
x = json.load(open(sys.argv[1], encoding="utf-8"))
assert x["locked_sample_count"] >= 5, x
PY
}

run_stage baseline
python3 - "$DERIVED/baseline-client-pcap.json" <<'PY'
import json, sys
x = json.load(open(sys.argv[1], encoding="utf-8"))
for name in ("follow up msg", "delay resp msg"):
    assert x["correction_fields"][name]["count"] > 0, x
    assert x["correction_fields"][name]["nonzero_count"] == 0, x
PY

printf '%s\n' 'show clock' 'configure terminal' 'ptp mode e2etransparent' 'end' \
  'configure terminal' 'interface Ethernet1' 'ptp enable' 'end' \
  'configure terminal' 'interface Ethernet2' 'ptp enable' 'end' \
  'show clock' 'show running-config | include ^ptp|ptp enable' \
  'show startup-config | include ^ptp|ptp enable' 'show ptp' \
  >"$TMP/switch-tc-enable.plan"
python3 "$COMMON/eos_cli.py" --mode controlled-config --plan "$TMP/switch-tc-enable.plan" \
  --output "$RAW/switch-tc-enable.txt" >/dev/null
SWITCH_CONFIGURED=1

tc_ready=0
for attempt in $(seq 1 20); do
  printf '%s\n' 'show clock' 'show ptp' 'show ptp interface' >"$TMP/switch-tc-ready.plan"
  python3 "$COMMON/eos_cli.py" --mode show --plan "$TMP/switch-tc-ready.plan" \
    --output "$RAW/switch-tc-ready-$attempt.txt" >/dev/null
  if grep -Fq 'PTP Mode: E2E Transparent Clock' "$RAW/switch-tc-ready-$attempt.txt" && \
      test "$(grep -Fxc 'PTP: Enabled' "$RAW/switch-tc-ready-$attempt.txt")" -ge 2; then
    cp "$RAW/switch-tc-ready-$attempt.txt" "$RAW/switch-tc-ready.txt"
    tc_ready=1
    break
  fi
  sleep 2
done
test "$tc_ready" -eq 1

run_stage tc
python3 - "$DERIVED/tc-client-pcap.json" <<'PY'
import json, sys
x = json.load(open(sys.argv[1], encoding="utf-8"))
for name in ("follow up msg", "delay resp msg"):
    item = x["correction_fields"][name]
    assert item["count"] > 0, x
    assert item["nonzero_count"] == item["count"], x
PY
grep -Eq 'Sync messages (sent|received): [1-9][0-9]*' "$RAW/switch-tc-active.txt"
grep -Eq 'Delay (request|response) messages (sent|received): [1-9][0-9]*' "$RAW/switch-tc-active.txt"

ACTIVE_STAGE=tc
remote_cleanup 10.1.1.1 master ens64np0 20.1.1.1/24 20.1.1.2
remote_cleanup 10.1.1.2 client ens64np1 20.1.1.2/24 20.1.1.1

printf '%s\n' \
  'configure terminal' 'interface Ethernet1' 'default ptp enable' 'end' \
  'configure terminal' 'interface Ethernet2' 'default ptp enable' 'end' \
  'configure terminal' 'default ptp mode' 'end' \
  'show clock' 'show running-config | include ^ptp|ptp enable' \
  'show startup-config | include ^ptp|ptp enable' 'show ptp' \
  'show interfaces Ethernet1, Ethernet2 status' \
  'show interfaces Ethernet1, Ethernet2 counters errors' \
  >"$TMP/switch-final.plan"
python3 "$COMMON/eos_cli.py" --mode controlled-config --plan "$TMP/switch-final.plan" \
  --output "$RAW/switch-final.txt" >/dev/null
grep -Eq 'PTP Mode: Disabled|PTP is not configured' "$RAW/switch-final.txt"
! grep -Eq '^ptp mode|^[[:space:]]+ptp enable' "$RAW/switch-final.txt"
SWITCH_CONFIGURED=0

for spec in '10.1.1.1 ens64np0 20.1.1.1/24 20.1.1.2' \
            '10.1.1.2 ens64np1 20.1.1.2/24 20.1.1.1'; do
  read -r host iface data_ip peer <<<"$spec"
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes "root@$host" \
    "set -eu; test \"\$(basename \"\$(readlink /sys/bus/pci/devices/0000:03:00.0/driver)\")\" = sfc; ip -4 addr show dev '$iface' | grep -Fq '$data_ip'; test \"\$(cat /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages)\" = 0; for p in ptp4l phc2sys ts2phc sfptpd tcpdump; do pgrep -x \"\$p\" >/dev/null && exit 1 || :; done; ping -q -I '$iface' -c 3 -W 1 '$peer'" \
    >"$RAW/final-$host.txt"
done
REMOTE_DEPLOYED=0
for host in 10.1.1.1 10.1.1.2; do
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes "root@$host" \
    "set -eu; case '$REMOTE_DIR' in /root/flle-ptp-live-*-07-ptp-tc-live-ab) ;; *) exit 2;; esac; find '$REMOTE_DIR' -depth -delete; test ! -e '$REMOTE_DIR'"
done

python3 - "$DERIVED/baseline-client-pcap.json" "$DERIVED/tc-client-pcap.json" \
  "$DERIVED/baseline-client-stats.json" "$DERIVED/tc-client-stats.json" \
  >"$OUT/result.json" <<'PY'
import json, sys
baseline_pcap, tc_pcap, baseline_stats, tc_stats = [
    json.load(open(path, encoding="utf-8")) for path in sys.argv[1:]
]
def selected(x):
    return {name: x["correction_fields"][name] for name in ("follow up msg", "delay resp msg")}
print(json.dumps({
    "result": "PASS",
    "evidence_kind": "fresh_live_capture",
    "baseline_correction": selected(baseline_pcap),
    "tc_correction": selected(tc_pcap),
    "baseline_locked_samples": baseline_stats["locked_sample_count"],
    "tc_locked_samples": tc_stats["locked_sample_count"],
    "switch_restored": True,
    "startup_unchanged": True,
    "hosts_restored": True,
    "phc2sys_used": False,
}, ensure_ascii=False, indent=2))
PY
(cd "$OUT" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum >SHA256SUMS)
python3 - "$OUT/result.json" "$OUT" "$RAW/switch-final.txt" <<'PY'
import json, sys
x = json.load(open(sys.argv[1], encoding="utf-8"))
b = x["baseline_correction"]; t = x["tc_correction"]
status = []
take = False
for line in open(sys.argv[3], encoding="utf-8"):
    if line.startswith("$ show ptp") and "interface" not in line:
        take = True
        continue
    if take and line.startswith("$ "):
        break
    if take and line.startswith("show ptp"):
        continue
    if take and line.strip():
        status.append(line.rstrip())
        if len(status) >= 3:
            break
print("vm-2522-02 / baseline")
print("===== 查TC关闭 correction =====")
print("[Follow_Up / Delay_Resp] 对: 全是 0/N  证: 关掉 TC 时 correction 没有被写入")
print("$ python3 analyze_ptp_decode.py baseline-client-decode.txt")
print("Follow_Up nonzero=%s/%s" % (b["follow up msg"]["nonzero_count"], b["follow up msg"]["count"]))
print("Delay_Resp nonzero=%s/%s" % (b["delay resp msg"]["nonzero_count"], b["delay resp msg"]["count"]))
print("vm-2522-02 / TC")
print("===== 查TC打开 correction =====")
print("[Follow_Up / Delay_Resp] 对: 全是 N/N  证: 打开 TC 后每条都带了修正")
print("$ python3 analyze_ptp_decode.py tc-client-decode.txt")
print("Follow_Up nonzero=%s/%s" % (t["follow up msg"]["nonzero_count"], t["follow up msg"]["count"]))
print("Delay_Resp nonzero=%s/%s" % (t["delay resp msg"]["nonzero_count"], t["delay resp msg"]["count"]))
print("===== 查锁定样本 =====")
print("[ptp4l] 对: 两轮都有已锁定样本  证: 客户端进入过 SLAVE")
print("$ python3 analyze_ptp_log.py")
print("locked_samples baseline=%s tc=%s" % (x["baseline_locked_samples"], x["tc_locked_samples"]))
print("===== 查恢复 =====")
print("[ptp] 对: PTP Mode: Disabled 或 PTP is not configured  证: running-config 已撤，startup 未写")
print("$ show ptp")
if not status:
    raise SystemExit("missing show ptp output in switch-final.txt")
print("\n".join(status))
print("evidence="+sys.argv[2])
PY
