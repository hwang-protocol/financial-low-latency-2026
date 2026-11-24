#!/usr/bin/env bash
# Push LANZ S/U/E to the .101 collector while the 8088 page stays up.
set -Eeuo pipefail
cd /qyt-fll

RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-07-lanz-stream-ab"
OUT="reports/course-runs/$RUN_ID"
RAW="$OUT/raw"
DERIVED="$OUT/derived"
COMMON="assets/common"
CTL="apps/flle-trading-lab/scripts/transport_labctl.sh"
ASSET_ROOT="assets/06-arista-time"
ENTRY_SCRIPT="$ASSET_ROOT/04b-lanz-stream-ab.sh"
EOS_CLI="$COMMON/eos_cli.py"
SUPPORT="$ASSET_ROOT/live-support/lanz"
SUPPORT_MANIFEST="$ASSET_ROOT/LIVE-SUPPORT-SHA256SUMS"
COLLECTOR="$ASSET_ROOT/lanz_stream_collector.py"
READER=artifacts/blobs/arista/lanz-reader-v1/flle-lanz-reader-linux-amd64
READER_SHA256=e6f58a6bd287f7776de936c8b82d5629c4b9afb14b92b721605eb783a0490083
FORMATTER="$ASSET_ROOT/format_lanz_result.py"
PARENT_RUN_ID="$(sed -n 's/^RUN_ID=//p' reports/run-state/02-trading-baseline.env)"
WEB_ROOT="/var/tmp/flle-trading-lab-$PARENT_RUN_ID/web"
COLLECTOR_DIR="/run/flle-lanz-stream"
COLLECTOR_PID_FILE="$COLLECTOR_DIR/collector.pid"
COLLECTOR_URL="http://10.1.1.101:8089/api/lanz"
FAKE_MAC_DOTTED="0200.0007.0002"
FAKE_MAC_COLON="02:00:00:07:00:02"
REMOTE_DIR="/run/flle-lanz-lower-$RUN_ID"
REMOTE_CTL="$REMOTE_DIR/remote-lanz-trex-control.sh"
TMP="$(mktemp -d)"
SWITCH_CONFIGURED=0
REMOTE_DEPLOYED=0
TREX_INSTALLED=0
PANEL_RESTORE_ARMED=0

[[ "$PARENT_RUN_ID" =~ ^[A-Za-z0-9._-]+-(02-trading-platform|06-four-path-orders)$ ]]
test ! -e "$OUT"
mkdir -p "$RAW/source" "$DERIVED"
printf 'RUN_ID=%s\nPARENT_RUN_ID=%s\nRESULT_DIR=%s\n' "$RUN_ID" "$PARENT_RUN_ID" "$OUT" \
  > reports/run-state/06-lanz-stream-ab.env
SUPPORT_MANIFEST_SHA256="$(sha256sum "$SUPPORT_MANIFEST" | awk '{print $1}')"
ENTRY_SCRIPT_SHA256="$(sha256sum "$ENTRY_SCRIPT" | awk '{print $1}')"
EOS_CLI_SHA256="$(sha256sum "$EOS_CLI" | awk '{print $1}')"
printf 'RUN_ID=%s\nPARENT_RUN_ID=%s\nRESULT_KIND=FRESH_LIVE_STREAM\nSUPPORT_MANIFEST_SHA256=%s\nENTRY_SCRIPT_SHA256=%s\nEOS_CLI_SHA256=%s\nKEEP_TRADING=1\nLOAD_PROTOCOL=MOLDUDP64_ITCH_5_0_TO_TEST_MAC\n' \
  "$RUN_ID" "$PARENT_RUN_ID" "$SUPPORT_MANIFEST_SHA256" \
  "$ENTRY_SCRIPT_SHA256" "$EOS_CLI_SHA256" >"$OUT/run.env"
install -m 0644 "$SUPPORT_MANIFEST" "$RAW/LIVE-SUPPORT-SHA256SUMS"
install -m 0644 "$ENTRY_SCRIPT" "$RAW/source/04b-lanz-stream-ab.sh"
install -m 0644 "$FORMATTER" "$RAW/source/format_lanz_result.py"
install -m 0644 "$EOS_CLI" "$RAW/source/eos_cli.py"
(cd "$ASSET_ROOT" && sha256sum -c LIVE-SUPPORT-SHA256SUMS) \
  >"$RAW/local-support-sha256.txt"
printf '%s  %s\n' "$READER_SHA256" "$READER" | sha256sum -c - >"$RAW/official-reader-sha256.txt"
"$READER" -version | tee "$RAW/official-reader-version.txt"
bash apps/flle-trading-lab/scripts/prepare-lanz-reader.sh --check >"$RAW/prepared-reader.txt"
printf 'LANZ_CLIENT=ARISTA_GOARISTA\nLANZ_READER_SHA256=%s\n' "$READER_SHA256" >>"$OUT/run.env"
install -m 0644 "$COLLECTOR" "$RAW/source/"
install -m 0644 "$ASSET_ROOT/lanz-reader/main.go" "$ASSET_ROOT/lanz-reader/go.mod" \
  "$ASSET_ROOT/lanz-reader/go.sum" "$RAW/source/"

remove_trex_install() {
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
    'set -eu; if test -e /opt/trex/v3.08 || test -L /opt/trex/v3.08; then test -d /opt/trex/v3.08 && test ! -L /opt/trex/v3.08; find /opt/trex/v3.08 -depth -delete; fi; if test -e /opt/trex/v3.08.tar.gz || test -L /opt/trex/v3.08.tar.gz; then test -L /opt/trex/v3.08.tar.gz; test "$(readlink /opt/trex/v3.08.tar.gz)" = /opt/flle/prewarm/trex/v3.08.tar.gz; unlink /opt/trex/v3.08.tar.gz; fi; rmdir /opt/trex 2>/dev/null || true; test ! -e /opt/trex && test ! -L /opt/trex'
}

snapshot_panel() {
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.101 \
    "set -eu; cd '/var/tmp/flle-trading-lab-$PARENT_RUN_ID'; sha256sum -c source.sha256 >/dev/null; test -d '$WEB_ROOT'; test -f '$WEB_ROOT/index.html'"
  mkdir -p "$RAW/web-before"
  scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes \
    "root@10.1.1.101:$WEB_ROOT/index.html" \
    "root@10.1.1.101:$WEB_ROOT/terminal.js" \
    "root@10.1.1.101:$WEB_ROOT/terminal.css" "$RAW/web-before/"
  PANEL_RESTORE_ARMED=1
}

deploy_panel() {
  scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes \
    apps/flle-trading-lab/web/index.html \
    apps/flle-trading-lab/web/terminal.js \
    apps/flle-trading-lab/web/terminal.css \
    "root@10.1.1.101:$WEB_ROOT/"
}

restore_panel() {
  test "$PANEL_RESTORE_ARMED" -eq 1 || return 0
  scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes \
    "$RAW/web-before/index.html" "$RAW/web-before/terminal.js" \
    "$RAW/web-before/terminal.css" "root@10.1.1.101:$WEB_ROOT/"
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.101 \
    "set -eu; cd '/var/tmp/flle-trading-lab-$PARENT_RUN_ID'; sha256sum -c source.sha256 >/dev/null; echo observer_source_restore=PASS" \
    >"$RAW/web-restore.txt"
  PANEL_RESTORE_ARMED=0
}

start_collector() {
  local stage collector_sha
  collector_sha="$(sha256sum "$COLLECTOR" | cut -d' ' -f1)"
  printf '===== 启动已准备的 Arista 官方 LANZ 客户端与网页采集器 =====\n'
  stage="$(ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.101 \
    "set -eu; mkdir -p '$COLLECTOR_DIR'; mktemp -d '$COLLECTOR_DIR/.stage.XXXXXX'")"
  [[ "$stage" = "$COLLECTOR_DIR"/.stage.* ]]
  scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes \
    "$COLLECTOR" "root@10.1.1.101:$stage/"
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.101 \
    bash -s -- "$COLLECTOR_DIR" "$stage" "$READER_SHA256" "$collector_sha" <<'REMOTE'
set -eu
dir="$1"; stage="$2"
cd "$stage"
reader=/opt/flle/lanz-reader-v1/flle-lanz-reader
printf '%s  %s\n%s  lanz_stream_collector.py\n' "$3" "$reader" "$4" | sha256sum -c -
"$reader" -version
if test -s "$dir/collector.pid"; then
  old="$(cat "$dir/collector.pid")"
  case "$old" in ''|*[!0-9]*) echo '采集器 PID 文件无效' >&2; exit 1;; esac
  if kill -0 "$old" 2>/dev/null; then
    command="$(tr '\0' ' ' <"/proc/$old/cmdline")"
    case "$command" in *"$dir/lanz_stream_collector.py"*) ;; *) echo '采集器 PID 已被其他进程使用' >&2; exit 1;; esac
    kill -TERM "$old"
    for _ in $(seq 1 40); do
      kill -0 "$old" 2>/dev/null || break
      sleep 0.2
    done
    ! kill -0 "$old" 2>/dev/null || { echo '旧采集器仍未退出' >&2; exit 1; }
  fi
fi
mv lanz_stream_collector.py "$dir/lanz_stream_collector.py"
cd "$dir"
rmdir "$stage"
nohup python3 "$dir/lanz_stream_collector.py" >"$dir/collector.log" 2>&1 </dev/null &
printf '%s\n' "$!" >"$dir/collector.pid"
REMOTE
  for _ in $(seq 1 30); do
    # 接收器刚启动时连接被拒是正常现象，轮询期间不输出 curl 报错
    if curl -fsS --connect-timeout 1 --max-time 2 "$COLLECTOR_URL" >"$RAW/collector-ready.json" 2>/dev/null \
      && python3 -c 'import json,sys; s=json.load(open(sys.argv[1])); sys.exit(s.get("decoder")!="arista-goarista-lanz")' "$RAW/collector-ready.json"; then
      printf '[采集器就绪] HTTP 8089 已启动；官方读取程序使用 /opt/flle/lanz-reader-v1/flle-lanz-reader。\n'
      return 0
    fi
    sleep 0.2
  done
  printf '[采集器启动失败] HTTP 8089 未就绪，下面显示远端启动日志：\n' >&2
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=8 root@10.1.1.101 \
    "tail -n 40 '$COLLECTOR_DIR/collector.log'" >"$RAW/collector-start.log" 2>&1 || true
  cat "$RAW/collector-start.log" >&2
  printf '[完整日志] %s/collector-start.log\n' "$RAW" >&2
  return 1
}

fetch_collector() {
  local label="$1"
  curl -fsS "$COLLECTOR_URL" >"$RAW/collector-$label.json"
  python3 - "$RAW/collector-$label.json" "$DERIVED/collector-$label.json" <<'PY'
import json, sys
src = json.load(open(sys.argv[1], encoding="utf-8"))
events = [row for row in src.get("events", []) if row.get("kind") == "congestion"]
et2 = [
    row for row in events
    if str(row.get("intf_name", "")).replace("Ethernet", "Et") in ("Et2",)
]
counts = {"START": 0, "UPDATE": 0, "END": 0, "POLLING": 0, "OTHER": 0}
for row in et2:
    key = row.get("entry_type") if row.get("entry_type") in counts else "OTHER"
    counts[key] += 1
out = {
    "connected": bool(src.get("connected")),
    "error": src.get("error") or "",
    "segment_size": (src.get("config") or {}).get("segment_size"),
    "et2_events": et2,
    "et2_counts": counts,
    "et2_tc1_counts": src.get("counts_by_queue", {}).get("Ethernet2/TC1", dict.fromkeys(counts, 0)),
    "all_counts": src.get("counts") or {},
}
json.dump(out, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=2)
PY
}

restore_switch() {
  test "$SWITCH_CONFIGURED" -eq 1 || return 0
  printf '%s\n' \
    'configure terminal' 'queue-monitor streaming' 'shutdown' 'end' \
    >"$TMP/switch-restore-stream-off.plan"
  python3 "$COMMON/eos_cli.py" --mode controlled-config \
    --plan "$TMP/switch-restore-stream-off.plan" \
    --output "$RAW/switch-restore-stream-off.txt" >/dev/null
  printf '%s\n' 'configure terminal' 'default queue-monitor streaming' 'end' \
    >"$TMP/switch-restore-stream-default.plan"
  python3 "$COMMON/eos_cli.py" --mode controlled-config \
    --plan "$TMP/switch-restore-stream-default.plan" \
    --output "$RAW/switch-restore-stream-default.txt" >/dev/null \
    || true
  printf '%s\n' 'configure terminal' 'no queue-monitor streaming' 'end' \
    >"$TMP/switch-restore-stream-no.plan"
  python3 "$COMMON/eos_cli.py" --mode controlled-config \
    --plan "$TMP/switch-restore-stream-no.plan" \
    --output "$RAW/switch-restore-stream-no.txt" >/dev/null \
    || true
  printf '%s\n' \
    'configure terminal' 'interface Ethernet2' \
    'default queue-monitor length thresholds' 'end' \
    "configure terminal" \
    "no mac address-table static $FAKE_MAC_DOTTED vlan 20 interface Ethernet2" \
    "end" \
    'configure terminal' 'default queue-monitor length' 'end' \
    'show clock' \
    'show running-config | include queue-monitor' \
    'show startup-config | include queue-monitor' \
    'show queue-monitor length status' \
    'show queue-monitor streaming clients' \
    'show mac address-table static' \
    >"$TMP/switch-restore-length.plan"
  python3 "$COMMON/eos_cli.py" --mode controlled-config \
    --plan "$TMP/switch-restore-length.plan" --output "$1" >/dev/null
  SWITCH_CONFIGURED=0
}

cleanup() {
  local original_rc=$? cleanup_failed=0
  trap - EXIT INT TERM HUP
  set +e
  if test "$REMOTE_DEPLOYED" -eq 1; then
    ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
      /usr/bin/bash "$REMOTE_CTL" recover >"$RAW/trap-vm11-recover.txt" 2>&1 || cleanup_failed=1
    ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
      /usr/bin/bash "$REMOTE_CTL" disarm-deadman >"$RAW/trap-vm11-disarm.txt" 2>&1 || cleanup_failed=1
  fi
  if test "$TREX_INSTALLED" -eq 1; then
    remove_trex_install >"$RAW/trap-vm11-remove-trex.txt" 2>&1 || cleanup_failed=1
  fi
  if test "$SWITCH_CONFIGURED" -eq 1; then
    restore_switch "$RAW/switch-trap-cleanup.txt" || cleanup_failed=1
  fi
  if test "$PANEL_RESTORE_ARMED" -eq 1; then
    restore_panel || cleanup_failed=1
  fi
  find "$TMP" -depth -delete
  if test "$cleanup_failed" -ne 0; then
    printf 'LANZ_STREAM_CLEANUP=FAIL original_rc=%s\n' "$original_rc" >&2
    exit 125
  fi
  if test "$original_rc" -ne 0; then exit "$original_rc"; fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

curl -fsS -o "$RAW/gui-pre.json" -w '%{http_code}\n' --max-time 3 \
  http://10.1.1.101:8088/api/transport-lab >"$RAW/gui-pre.http"
test "$(cat "$RAW/gui-pre.http")" = 200
bash "$CTL" status "$PARENT_RUN_ID" >"$RAW/trading-pre.json"
python3 - "$RAW/trading-pre.json" "$RAW/gui-pre.json" <<'PY'
import json, sys
control, gui = [json.load(open(path, encoding="utf-8")) for path in sys.argv[1:]]
assert (control["mode"], control["transition"], control["owner"]) == ("SFC", "READY", "sfc")
assert control["hardware_receipts"]["socket"]["verified"] is True
assert all(gui["clients"][name]["health"]["status"] == "ONLINE"
           for name in ("trader_manual", "trader_onload", "trader_tcpdirect"))
PY

printf '%s\n' \
  'show clock' 'show version' \
  'show running-config | include queue-monitor' \
  'show startup-config | include queue-monitor' \
  'show queue-monitor length status' \
  'show queue-monitor streaming clients' \
  'show mac address-table static' \
  'show interfaces Ethernet2, Ethernet11, Ethernet12 status' \
  >"$TMP/switch-baseline.plan"
python3 "$COMMON/eos_cli.py" --mode show --plan "$TMP/switch-baseline.plan" \
  --output "$RAW/switch-baseline.txt" >/dev/null
grep -Fq 'queue-monitor length disabled' "$RAW/switch-baseline.txt"
! grep -Eq '^queue-monitor( length| streaming)' "$RAW/switch-baseline.txt"
! grep -Fq "$FAKE_MAC_DOTTED" "$RAW/switch-baseline.txt"

python3 -m py_compile "$COLLECTOR"
snapshot_panel
deploy_panel
start_collector
scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes \
  root@10.1.1.101:$COLLECTOR_DIR/collector.log "$RAW/collector-start.log" || true

sed "s/readonly run_id=20260721T053935Z/readonly run_id=$RUN_ID/" \
  "$SUPPORT/remote-lanz-trex-control.sh" \
  | sed 's#/opt/trex/v3.08.tar.gz#/opt/flle/prewarm/trex/v3.08.tar.gz#g' \
  >"$TMP/remote-lanz-trex-control.sh"
install -m 0755 "$SUPPORT/trex_lanz_lower_client.py" "$TMP/trex_lanz_lower_client.py"
install -m 0644 "$SUPPORT/trex-dual.yaml" "$TMP/trex-dual.yaml"
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
  "set -eu; test ! -e '$REMOTE_DIR'; mkdir -m 700 '$REMOTE_DIR'"
scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes \
  "$TMP/remote-lanz-trex-control.sh" "$TMP/trex_lanz_lower_client.py" \
  "$TMP/trex-dual.yaml" "root@10.1.1.11:$REMOTE_DIR/"
REMOTE_DEPLOYED=1
TREX_INSTALLED=1
bash assets/common/ensure-trex-archive.sh >"$RAW/trex-archive-prep.txt" 2>&1

ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
  'set -eu; test ! -e /opt/trex && test ! -L /opt/trex; archive=/opt/flle/prewarm/trex/v3.08.tar.gz; test "$(stat -c %s "$archive")" = 284092535; test "$(sha256sum "$archive" | cut -d" " -f1)" = d2ac73627906c4ce01127c1c6954464fab373463966ea9592509446e74972b5f; install -d -m 0755 /opt/trex; tar -xzf "$archive" -C /opt/trex; test -x /opt/trex/v3.08/t-rex-64'
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
  "/usr/bin/bash '$REMOTE_CTL' preflight" >"$RAW/vm11-preflight.txt"

printf '%s\n' \
  'show clock' 'configure terminal' 'queue-monitor length' \
  "mac address-table static $FAKE_MAC_DOTTED vlan 20 interface Ethernet2" \
  'interface Ethernet2' 'queue-monitor length thresholds 64 32' 'end' \
  'configure terminal' 'queue-monitor streaming' 'no shutdown' 'end' \
  'show clock' 'show queue-monitor length status' \
  'show queue-monitor streaming clients' \
  'show running-config | include queue-monitor' \
  >"$TMP/switch-enable.plan"
SWITCH_CONFIGURED=1
python3 "$COMMON/eos_cli.py" --mode controlled-config --plan "$TMP/switch-enable.plan" \
  --output "$RAW/switch-enable.txt" >/dev/null
grep -Fq 'queue-monitor length enabled' "$RAW/switch-enable.txt"

ready=0
for attempt in $(seq 1 24); do
  printf '%s\n' 'show clock' 'show agent uptime | include AltaLanz' \
    'show queue-monitor length statistics' \
    'show queue-monitor streaming clients' >"$TMP/switch-ready.plan"
  python3 "$COMMON/eos_cli.py" --mode show --plan "$TMP/switch-ready.plan" \
    --output "$RAW/switch-ready-$attempt.txt" >/dev/null
  if grep -Fq 'AltaLanz' "$RAW/switch-ready-$attempt.txt" && \
      ! grep -Fq '! Lanz agent not running.' "$RAW/switch-ready-$attempt.txt"; then
    cp "$RAW/switch-ready-$attempt.txt" "$RAW/switch-ready.txt"
    ready=1
    break
  fi
  sleep 3
done
test "$ready" -eq 1

connected=0
for _ in $(seq 1 20); do
  fetch_collector wait >/dev/null
  if python3 - "$DERIVED/collector-wait.json" <<'PY'
import json, sys
src = json.load(open(sys.argv[1], encoding="utf-8"))
raise SystemExit(0 if src.get("connected") else 1)
PY
  then
    connected=1
    break
  fi
  sleep 0.5
done
test "$connected" -eq 1
fetch_collector pre
python3 - "$DERIVED/collector-pre.json" <<'PY'
import json, sys
src = json.load(open(sys.argv[1], encoding="utf-8"))
assert src["connected"] is True
assert src["et2_counts"]["START"] == 0
assert src["et2_counts"]["END"] == 0
PY

ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
  "/usr/bin/bash '$REMOTE_CTL' arm-deadman 900" >"$RAW/vm11-deadman-arm.txt" 2>&1
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
  "/usr/bin/bash '$REMOTE_CTL' start" >"$RAW/vm11-trex-start.txt"
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
  "/usr/bin/python3 '$REMOTE_DIR/trex_lanz_lower_client.py' --run-id '$RUN_ID' --mode prepare --summary '$REMOTE_DIR/prepare.json'" \
  >"$RAW/vm11-trex-prepare.txt" 2>&1
scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes \
  "root@10.1.1.11:$REMOTE_DIR/prepare.json" "$RAW/trex-prepare.json"
python3 - "$RAW/trex-prepare.json" <<'PY'
import json, sys
assert json.load(open(sys.argv[1], encoding="utf-8"))["status"] == "PASS"
PY

run_stage() {
  local stage="$1" pps="$2"
  printf '正在测试：每个入口 %s 包/秒。\n' "$pps"
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
    "/usr/bin/bash '$REMOTE_CTL' deadman-budget 195" >"$RAW/$stage-deadman.txt"
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
    "/usr/bin/python3 '$REMOTE_DIR/trex_lanz_lower_client.py' --run-id '$RUN_ID' --mode burst --stage '$stage' --ingress-mode dual --dst-mac '$FAKE_MAC_COLON' --pps '$pps' --count 4096 --packet-size 1514 --payload-kind mold-itch --summary '$REMOTE_DIR/$stage.json'" \
    >"$RAW/$stage-client.txt" 2>&1
  scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes \
    "root@10.1.1.11:$REMOTE_DIR/$stage.json" "$RAW/$stage-trex.json"
  python3 - "$RAW/$stage-trex.json" <<'PY'
import json, sys
row = json.load(open(sys.argv[1], encoding="utf-8"))
assert row["status"] == "PASS"
assert row["protocol_profile"] == "MOLDUDP64_ITCH_5_0_TO_TEST_MAC"
PY
  sleep 3
  fetch_collector "$stage"
}

run_stage dual-10k-4096 10000
python3 - "$DERIVED/collector-dual-10k-4096.json" <<'PY'
import json, sys
src = json.load(open(sys.argv[1], encoding="utf-8"))
assert src["et2_counts"]["START"] == 0
assert src["et2_counts"]["END"] == 0
PY

run_stage dual-25k-4096 25000
python3 - "$DERIVED/collector-dual-25k-4096.json" <<'PY'
import json, sys
src = json.load(open(sys.argv[1], encoding="utf-8"))
assert src["et2_counts"]["START"] > 0
assert src["et2_counts"]["END"] > 0
PY

printf '%s\n' 'show clock' 'show queue-monitor length statistics' \
  'show queue-monitor length Ethernet 2' \
  'show queue-monitor streaming clients' \
  >"$TMP/switch-post.plan"
python3 "$COMMON/eos_cli.py" --mode show --plan "$TMP/switch-post.plan" \
  --output "$RAW/switch-post.txt" >/dev/null
python3 "$FORMATTER" --verify "$OUT" >"$DERIVED/cross-check.json"

ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
  "/usr/bin/bash '$REMOTE_CTL' recover" >"$RAW/vm11-explicit-recover.txt"
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
  "/usr/bin/bash '$REMOTE_CTL' disarm-deadman" >"$RAW/vm11-deadman-disarm.txt"
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
  "/usr/bin/bash '$REMOTE_CTL' final-assert" >"$RAW/vm11-final.txt"
remove_trex_install >"$RAW/vm11-remove-trex.txt"
TREX_INSTALLED=0

restore_switch "$RAW/switch-final.txt"
grep -Fq 'queue-monitor length disabled' "$RAW/switch-final.txt"
! grep -Eq '^queue-monitor( length| streaming)' "$RAW/switch-final.txt"
! grep -Fq "$FAKE_MAC_DOTTED" "$RAW/switch-final.txt"

mkdir -p "$RAW/vm11-artifacts"
scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes \
  "root@10.1.1.11:$REMOTE_DIR/"'*' "$RAW/vm11-artifacts/"
REMOTE_DEPLOYED=0
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
  "set -eu; case '$REMOTE_DIR' in /run/flle-lanz-lower-*-07-lanz-stream-ab) ;; *) exit 2;; esac; find '$REMOTE_DIR' -depth -delete; test ! -e '$REMOTE_DIR'"

curl -fsS -o "$RAW/gui-post.json" -w '%{http_code}\n' --max-time 3 \
  http://10.1.1.101:8088/api/transport-lab >"$RAW/gui-post.http"
test "$(cat "$RAW/gui-post.http")" = 200
bash "$CTL" status "$PARENT_RUN_ID" >"$RAW/trading-post.json"
python3 - "$RAW/trading-post.json" "$RAW/gui-post.json" <<'PY'
import json, sys
control, gui = [json.load(open(path, encoding="utf-8")) for path in sys.argv[1:]]
assert (control["mode"], control["transition"], control["owner"]) == ("SFC", "READY", "sfc")
assert control["hardware_receipts"]["socket"]["verified"] is True
assert all(gui["clients"][name]["health"]["status"] == "ONLINE"
           for name in ("trader_manual", "trader_onload", "trader_tcpdirect"))
PY
fetch_collector final
scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes \
  root@10.1.1.101:$COLLECTOR_DIR/collector.log "$RAW/collector.log" || true
restore_panel
curl -fsS -o /dev/null --max-time 3 http://10.1.1.101:8088/api/transport-lab

python3 - "$DERIVED/collector-dual-10k-4096.json" \
  "$DERIVED/collector-dual-25k-4096.json" \
  "$DERIVED/collector-final.json" >"$OUT/result.json" <<'PY'
import json, sys
no_event = json.load(open(sys.argv[1], encoding="utf-8"))
event = json.load(open(sys.argv[2], encoding="utf-8"))
final = json.load(open(sys.argv[3], encoding="utf-8"))
print(json.dumps({
    "result": "PASS",
    "evidence_kind": "fresh_live_stream",
    "keep_trading": True,
    "protocol_profile": "MOLDUDP64_ITCH_5_0_TO_TEST_MAC",
    "no_event": {"pps_per_ingress": 10000, "et2_counts": no_event["et2_counts"]},
    "event": {"pps_per_ingress": 25000, "et2_counts": event["et2_counts"]},
    "final_panel_still_has_events": final["et2_counts"]["START"] > 0,
    "switch_restored": True,
    "startup_unchanged": True,
    "vm11_restored": True,
    "collector_left_running": True,
}, ensure_ascii=False, indent=2))
PY

python3 "$FORMATTER" "$OUT" >"$RAW/result-display.txt"
(cd "$OUT" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum >SHA256SUMS)
cat "$RAW/result-display.txt"
