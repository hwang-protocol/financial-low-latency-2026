#!/usr/bin/env bash
# Fresh LANZ no-event/event A/B. Reuses audited generators, never old measurements.
set -Eeuo pipefail
cd /financial-low-latency

RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-07-lanz-live-ab"
OUT="Documents/reports/course-runs/$RUN_ID"
RAW="$OUT/raw"
DERIVED="$OUT/derived"
COMMON="Documents/newDoc/assets/common"
ASSET_ROOT="Documents/newDoc/assets/07-arista-time"
SUPPORT="$ASSET_ROOT/live-support/lanz"
SUPPORT_MANIFEST="$ASSET_ROOT/LIVE-SUPPORT-SHA256SUMS"
REMOTE_DIR="/run/flle-lanz-lower-$RUN_ID"
REMOTE_CTL="$REMOTE_DIR/remote-lanz-trex-control.sh"
TMP="$(mktemp -d)"
SWITCH_CONFIGURED=0
REMOTE_DEPLOYED=0
TREX_INSTALLED=0

test ! -e "$OUT"
mkdir -p "$RAW" "$DERIVED"
SUPPORT_MANIFEST_SHA256="$(sha256sum "$SUPPORT_MANIFEST" | awk '{print $1}')"
printf 'RUN_ID=%s\nRESULT_KIND=FRESH_LIVE_TRAFFIC\nSUPPORT_MANIFEST_SHA256=%s\n' \
  "$RUN_ID" "$SUPPORT_MANIFEST_SHA256" >"$OUT/run.env"
install -m 0644 "$SUPPORT_MANIFEST" "$RAW/LIVE-SUPPORT-SHA256SUMS"
(cd "$ASSET_ROOT" && sha256sum -c LIVE-SUPPORT-SHA256SUMS) \
  >"$RAW/local-support-sha256.txt"

remove_trex_install() {
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
    'set -eu; if test -e /opt/trex/v3.08 || test -L /opt/trex/v3.08; then test -d /opt/trex/v3.08 && test ! -L /opt/trex/v3.08; find /opt/trex/v3.08 -depth -delete; fi; if test -e /opt/trex/v3.08.tar.gz || test -L /opt/trex/v3.08.tar.gz; then test -L /opt/trex/v3.08.tar.gz; test "$(readlink /opt/trex/v3.08.tar.gz)" = /opt/flle/prewarm/trex/v3.08.tar.gz; unlink /opt/trex/v3.08.tar.gz; fi; rmdir /opt/trex 2>/dev/null || true; test ! -e /opt/trex && test ! -L /opt/trex'
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
    printf '%s\n' \
      'configure terminal' 'interface Ethernet2' \
      'default queue-monitor length thresholds' 'end' \
      'configure terminal' 'default queue-monitor length' 'end' \
      'show clock' 'show running-config | include ^queue-monitor|queue-monitor length thresholds' \
      'show startup-config | include ^queue-monitor|queue-monitor length thresholds' \
      'show queue-monitor length status' 'show queue-monitor length' \
      >"$TMP/switch-cleanup.plan"
    python3 "$COMMON/eos_cli.py" --mode controlled-config \
      --plan "$TMP/switch-cleanup.plan" --output "$RAW/switch-trap-cleanup.txt" \
      >/dev/null || cleanup_failed=1
  fi
  find "$TMP" -depth -delete
  if test "$cleanup_failed" -ne 0; then
    printf 'LANZ_CLEANUP=FAIL original_rc=%s\n' "$original_rc" >&2
    exit 125
  fi
  if test "$original_rc" -ne 0; then exit "$original_rc"; fi
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

# This historical maintenance-window card also requires both FLLE endpoints quiet.
for host in 10.1.1.1 10.1.1.2; do
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@"$host" \
    'set -eu; if pgrep -f '\''[f]lle-(trader|exchange)'\'' >/dev/null; then exit 1; fi'
done

# The receiver must be quiet so its hardware size bin can exactly match TRex TX.
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
  'set -eu; test "$(basename "$(readlink /sys/bus/pci/devices/0000:03:00.0/driver)")" = sfc; test "$(cat /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages)" = 0; for f in /proc/driver/onload/stacks /proc/driver/onload/stacks_k /proc/driver/onload/stacks_ul; do if grep -q '\''[^[:space:]]'\'' "$f" 2>/dev/null; then exit 1; fi; done; pgrep -f '\''[f]lle-(trader|exchange)'\'' >/dev/null && exit 1 || :; pgrep -x ptp4l >/dev/null && exit 1 || :; ping -q -I ens64np1 -c 3 -W 1 20.1.1.1' \
  >"$RAW/vm2-preflight.txt"

printf '%s\n' \
  'show clock' 'show running-config | include ^queue-monitor|queue-monitor length thresholds' \
  'show startup-config | include ^queue-monitor|queue-monitor length thresholds' \
  'show queue-monitor length status' 'show queue-monitor length' \
  'show interfaces Ethernet2, Ethernet11, Ethernet12 status' \
  >"$TMP/switch-baseline.plan"
python3 "$COMMON/eos_cli.py" --mode show --plan "$TMP/switch-baseline.plan" \
  --output "$RAW/switch-baseline.txt" >/dev/null
grep -Fq 'queue-monitor length disabled' "$RAW/switch-baseline.txt"
! grep -Eq '^queue-monitor length$|^[[:space:]]+queue-monitor length thresholds' "$RAW/switch-baseline.txt"

# Materialize the tracked, audited control template with this fresh RUN_ID. The
# packet generator and receiver parser are programs only; no report is read.
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
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
  'set -eu; test ! -e /opt/trex && test ! -L /opt/trex; archive=/opt/flle/prewarm/trex/v3.08.tar.gz; test "$(stat -c %s "$archive")" = 284092535; test "$(sha256sum "$archive" | cut -d" " -f1)" = d2ac73627906c4ce01127c1c6954464fab373463966ea9592509446e74972b5f; install -d -m 0755 /opt/trex; tar -xzf "$archive" -C /opt/trex; test -x /opt/trex/v3.08/t-rex-64'
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
  "/usr/bin/bash '$REMOTE_CTL' preflight" >"$RAW/vm11-preflight.txt"

printf '%s\n' \
  'show clock' 'configure terminal' 'queue-monitor length' \
  'interface Ethernet2' 'queue-monitor length thresholds 64 32' 'end' \
  'show clock' 'show queue-monitor length status' \
  >"$TMP/switch-enable.plan"
python3 "$COMMON/eos_cli.py" --mode controlled-config --plan "$TMP/switch-enable.plan" \
  --output "$RAW/switch-enable.txt" >/dev/null
SWITCH_CONFIGURED=1
grep -Fq 'queue-monitor length enabled' "$RAW/switch-enable.txt"
grep -Eq '^Et2[[:space:]]+64[[:space:]]+32' "$RAW/switch-enable.txt"

ready=0
for attempt in $(seq 1 24); do
  printf '%s\n' 'show clock' 'show agent uptime | include AltaLanz' \
    'show queue-monitor length statistics' >"$TMP/switch-ready.plan"
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

ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
  "/usr/bin/bash '$REMOTE_CTL' arm-deadman 900" >"$RAW/vm11-deadman-arm.txt"
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

switch_snapshot() {
  local label="$1"
  printf '%s\n' 'show clock' 'show queue-monitor length statistics' \
    'show queue-monitor length Ethernet 2' 'show queue-monitor length drops' \
    'show interfaces Ethernet2 counters' 'show interfaces Ethernet2 counters errors' \
    'show interfaces Ethernet2 counters discards' \
    'show platform fm6000 danz-processor | include Lanz is|Written records|Read records|Failed transfers' \
    >"$TMP/switch-$label.plan"
  python3 "$COMMON/eos_cli.py" --mode show --plan "$TMP/switch-$label.plan" \
    --output "$RAW/switch-$label.txt" >/dev/null
}

lanz_count() {
  awk '
    /^Interface[[:space:]]+Traffic Class[[:space:]]+Count/ {table=1; next}
    /^Global Hit Count/ {table=0}
    table && $1=="Et2" && $2 ~ /^[0-9]+$/ && $3 ~ /^[0-9]+$/ {sum+=$3}
    END {print sum+0}
  ' "$1"
}

run_stage() {
  local stage="$1" pps="$2"
  switch_snapshot "$stage-pre"
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
    "/usr/bin/bash '$REMOTE_CTL' deadman-budget 195" >"$RAW/$stage-deadman.txt"
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
    /usr/bin/bash -s -- "$stage-before" \
    <"$SUPPORT/vm2-snapshot.sh" >"$RAW/$stage-vm2-before.txt"
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
    "/usr/bin/python3 '$REMOTE_DIR/trex_lanz_lower_client.py' --run-id '$RUN_ID' --mode burst --stage '$stage' --ingress-mode dual --dst-mac 00:0f:53:d3:af:21 --pps '$pps' --count 4096 --packet-size 1514 --summary '$REMOTE_DIR/$stage.json'" \
    >"$RAW/$stage-client.txt" 2>&1
  scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes \
    "root@10.1.1.11:$REMOTE_DIR/$stage.json" "$RAW/$stage-trex.json"
  sleep 3
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
    /usr/bin/bash -s -- "$stage-delayed" \
    <"$SUPPORT/vm2-snapshot.sh" >"$RAW/$stage-vm2-delayed.txt"
  python3 "$SUPPORT/derive-stage.py" \
    --trex "$RAW/$stage-trex.json" --before "$RAW/$stage-vm2-before.txt" \
    --after "$RAW/$stage-vm2-delayed.txt" --output "$DERIVED/$stage.json" \
    >"$RAW/$stage-derive.txt"
  python3 - "$DERIVED/$stage.json" <<'PY'
import json, sys
assert json.load(open(sys.argv[1], encoding="utf-8"))["status"] == "PASS"
PY
  sleep 3
  switch_snapshot "$stage-post"
}

run_stage dual-10k-4096 10000
NO_PRE="$(lanz_count "$RAW/switch-dual-10k-4096-pre.txt")"
NO_POST="$(lanz_count "$RAW/switch-dual-10k-4096-post.txt")"
test "$NO_PRE" -eq 0
test "$NO_POST" -eq 0

run_stage dual-25k-4096 25000
EV_PRE="$(lanz_count "$RAW/switch-dual-25k-4096-pre.txt")"
EV_POST="$(lanz_count "$RAW/switch-dual-25k-4096-post.txt")"
test "$EV_PRE" -eq 0
test "$EV_POST" -gt 0
grep -Eq '^Et2[[:space:]]+0[[:space:]]+0[[:space:]]*$' \
  "$RAW/switch-dual-25k-4096-post.txt"

ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
  "/usr/bin/bash '$REMOTE_CTL' recover" >"$RAW/vm11-explicit-recover.txt"
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
  "/usr/bin/bash '$REMOTE_CTL' disarm-deadman" >"$RAW/vm11-deadman-disarm.txt"
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
  "/usr/bin/bash '$REMOTE_CTL' final-assert" >"$RAW/vm11-final.txt"
remove_trex_install >"$RAW/vm11-remove-trex.txt"
TREX_INSTALLED=0

printf '%s\n' 'configure terminal' 'interface Ethernet2' \
  'default queue-monitor length thresholds' 'end' \
  'configure terminal' 'default queue-monitor length' 'end' \
  'show clock' 'show running-config | include ^queue-monitor|queue-monitor length thresholds' \
  'show startup-config | include ^queue-monitor|queue-monitor length thresholds' \
  'show queue-monitor length status' 'show queue-monitor length' \
  'show interfaces Ethernet2, Ethernet11, Ethernet12 status' \
  >"$TMP/switch-final.plan"
python3 "$COMMON/eos_cli.py" --mode controlled-config --plan "$TMP/switch-final.plan" \
  --output "$RAW/switch-final.txt" >/dev/null
grep -Fq 'queue-monitor length disabled' "$RAW/switch-final.txt"
grep -Fq '! Lanz agent not running.' "$RAW/switch-final.txt"
! grep -Eq '^queue-monitor length$|^[[:space:]]+queue-monitor length thresholds' "$RAW/switch-final.txt"
SWITCH_CONFIGURED=0

mkdir -p "$RAW/vm11-artifacts"
scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes \
  "root@10.1.1.11:$REMOTE_DIR/"'*' "$RAW/vm11-artifacts/"
REMOTE_DEPLOYED=0
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
  "set -eu; case '$REMOTE_DIR' in /run/flle-lanz-lower-*-07-lanz-live-ab) ;; *) exit 2;; esac; find '$REMOTE_DIR' -depth -delete; test ! -e '$REMOTE_DIR'"
python3 - "$DERIVED/dual-10k-4096.json" "$DERIVED/dual-25k-4096.json" \
  "$NO_POST" "$EV_POST" >"$OUT/result.json" <<'PY'
import json, sys
no_event = json.load(open(sys.argv[1], encoding="utf-8"))
event = json.load(open(sys.argv[2], encoding="utf-8"))
print(json.dumps({
    "result": "PASS",
    "evidence_kind": "fresh_live_traffic",
    "profile": "dual ingress, 1514 B without FCS, 4096 packets/ingress, Et2 64/32 segments",
    "no_event": {"pps_per_ingress": 10000, "lanz_count": int(sys.argv[3]), "rx_packets": no_event["vm2"]["target_size_packets"]},
    "event": {"pps_per_ingress": 25000, "lanz_count": int(sys.argv[4]), "rx_packets": event["vm2"]["target_size_packets"]},
    "switch_restored": True,
    "startup_unchanged": True,
    "vm11_restored": True,
}, ensure_ascii=False, indent=2))
PY
(cd "$OUT" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum >SHA256SUMS)
eos_show() {
  awk -v cmd="$2" '
    $0 == "$ " cmd {p=1; found=1; next}
    p && /^\$ / {exit}
    p && $0 == cmd " | no-more" {next}
    p {print}
    END {if (!found) exit 1}
  ' "$1"
}
{
  printf 'fll-arista / 10k\n===== 查10k LANZ统计 =====\n[statistics] 对: 表头之下没有 Et2 行  证: 本轮未跨当前高阈值\n$ show queue-monitor length statistics\n'
  eos_show "$RAW/switch-dual-10k-4096-post.txt" 'show queue-monitor length statistics'
  printf 'fll-arista / 25k\n===== 查25k LANZ统计 =====\n[Et2] 对: Et2 / 1 / 正计数  证: 25k 档跨过了当前阈值\n$ show queue-monitor length statistics\n'
  eos_show "$RAW/switch-dual-25k-4096-post.txt" 'show queue-monitor length statistics'
  printf '===== 查25k Et2队列事件 =====\n[Et2] 对: 成对的 S/E 行  证: 能看到短队列的开始和结束；完整表在 raw\n$ show queue-monitor length Ethernet 2\n'
  awk -v cmd='show queue-monitor length Ethernet 2' '
    $0 == "$ " cmd {p=1; found=1; next}
    p && /^\$ / {exit}
    p && $0 == cmd " | no-more" {next}
    p && $1=="E" {print; e++}
    p && $1=="S" {print; s++; if (e>=1 && s>=1) exit}
    END {if (!found) exit 1}
  ' "$RAW/switch-dual-25k-4096-post.txt"
  printf '===== 查恢复 =====\n[status] 对: queue-monitor length disabled  证: running-config 已撤，startup 未写\n$ show queue-monitor length status\n'
  awk -v cmd='show queue-monitor length status' '
    $0 == "$ " cmd {p=1; found=1; next}
    p && /^\$ / {exit}
    p && $0 == cmd " | no-more" {next}
    p && NF {print; n++; if (n>=4) exit}
    END {if (!found) exit 1}
  ' "$RAW/switch-final.txt"
  printf 'evidence=%s\n' "$OUT"
}
