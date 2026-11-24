#!/usr/bin/env bash
# Chapter 06 four-path order-entry controller.  Run on Low-Latency-Ops.
set -Eeuo pipefail

ACTION="${1:-}"
RUN_ID="${2:-}"
TARGET="${3:-}"
EXPORT_DIR="${4:-}"
case "$RUN_ID" in
  ""|*[!A-Za-z0-9._-]*)
    echo "usage: $0 {preflight|deploy|start|sfc|dpdk|measure|attest|native-receipt|status|verify|stop} RUN_ID [TARGET [LOCAL_EXPORT_DIR]]" >&2
    exit 2
    ;;
esac

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd -- "$APP_DIR/../.." && pwd)"
BASE_CTL="$SCRIPT_DIR/labctl.sh"
EXCHANGE_HOST="${FLLE_EXCHANGE_HOST:-root@10.1.1.1}"
TRADER_HOST="${FLLE_TRADER_HOST:-root@10.1.1.2}"
OBSERVER_HOST="${FLLE_OBSERVER_HOST:-root@10.1.1.101}"
TELEMETRY_HOST="${FLLE_TELEMETRY_HOST:-10.1.1.101}"
CONTROLLER_IP="${FLLE_CONTROLLER_IP:-10.1.1.111}"
RUN_DIR="/var/tmp/flle-trading-lab-$RUN_ID"
CONTROL_DIR="/var/tmp/flle-transport-controller-$RUN_ID"
CONTROLLER_UNIT="flle-transport-controller-${RUN_ID//_/-}"
RUNTIME_BLOB="$REPO_ROOT/artifacts/blobs/x2522/ch06-four-path/v5/flle-ch06-four-path-v5-x86_64-jammy-runtime.tgz"
RUNTIME_SHA="1a3c0766dac04774f0d4ed0d3a910de409f52964fb219519ecf326e6fe8e93aa"
RUNTIME_ROOT="$RUN_DIR/transport-runtime/flle-ch06-four-path"
DPDK_USER_REF_ROOT=3900000000
DPDK_USER_REF_SLOT_SPAN=1000000
SFC_SOCKET_USER_REF_ROOT=2100000000
SFC_ONLOAD_USER_REF_ROOT=2500000000
SFC_TCPDIRECT_USER_REF_ROOT=2900000000
SFC_USER_REF_SLOT_STRIDE=2000000
SFC_USER_REF_NAMESPACE_SPAN=100000
SSH=(ssh -o BatchMode=yes -o StrictHostKeyChecking=yes)
SCP=(scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes)

assert_runtime_blob() {
  test -s "$RUNTIME_BLOB"
  test "$(sha256sum "$RUNTIME_BLOB" | awk '{print $1}')" = "$RUNTIME_SHA"
}

management_command() {
  local port="$1" line="$2"
  timeout 2 bash -c '
    port="$1"; line="$2"
    exec 3<>/dev/tcp/10.1.1.2/"$port"
    printf "%s\n" "$line" >&3
    IFS= read -r reply <&3
    printf "%s" "$reply"
  ' bash "$port" "$line"
}

wait_state() {
  local port="$1" required="$2" reply=""
  for _ in $(seq 1 120); do
    reply="$(management_command "$port" STATE 2>/dev/null || true)"
    if [[ "$reply" == *'"status":"ONLINE"'* && "$reply" == *"$required"* ]]; then
      printf '%s\n' "$reply"
      return 0
    fi
    sleep 0.25
  done
  return 1
}

stop_remote_process() {
  local host="$1" name="$2" expected="$3"
  "${SSH[@]}" "$host" "set -eu; pidfile='$RUN_DIR/$name.pid'; test -s \"\$pidfile\" || exit 0; pid=\$(<\"\$pidfile\"); if test -r /proc/\$pid/cmdline; then command=\$(tr '\\0' ' ' </proc/\$pid/cmdline); case \"\$command\" in *'$expected'*) kill -INT \"\$pid\";; *) echo 'refusing mismatched $name pid' >&2; exit 1;; esac; for _ in \$(seq 1 40); do kill -0 \"\$pid\" 2>/dev/null || break; sleep 0.25; done; kill -0 \"\$pid\" 2>/dev/null && kill -KILL \"\$pid\" || true; fi; rm -f \"\$pidfile\""
}

start_remote_process() {
  local host="$1" name="$2" command="$3"
  "${SSH[@]}" "$host" "set -eu; cd '$RUN_DIR'; test ! -s '$name.pid' || { old=\$(<'$name.pid'); ! kill -0 \"\$old\" 2>/dev/null || { echo '$name already running'; exit 0; }; }; nohup $command </dev/null >'$name.log' 2>&1 & echo \$! >'$name.pid'"
}

wait_remote_listener() {
  local host="$1" name="$2" expected="$3" port="$4"
  "${SSH[@]}" "$host" "set -eu; cd '$RUN_DIR'; for _ in \$(seq 1 80); do pid=\$(sed -n '1p' '$name.pid' 2>/dev/null || true); test -n \"\$pid\" && test -r /proc/\$pid/cmdline || { sleep 0.25; continue; }; command=\$(tr '\\0' ' ' </proc/\$pid/cmdline); case \"\$command\" in *'$expected'*) ;; *) echo '$name pid mismatch' >&2; exit 1;; esac; listeners=\$(ss -ltnpH '( sport = :$port )' 2>/dev/null || true); case \"\$listeners\" in *\"pid=\$pid,\"*) exit 0;; esac; sleep 0.25; done; tail -n 30 '$name.log' >&2 || true; echo '$name did not own port $port' >&2; exit 1"
}

stop_foreign_course_listener() {
  local host="$1" port="$2" expected="$3"
  "${SSH[@]}" "$host" "set -eu; listener=\$(ss -ltnpH '( sport = :$port )' 2>/dev/null || true); test -n \"\$listener\" || exit 0; pid=\$(printf '%s\n' \"\$listener\" | sed -n 's/.*pid=\([0-9][0-9]*\).*/\1/p' | head -n1); test -n \"\$pid\"; command=\$(tr '\\0' ' ' </proc/\$pid/cmdline); case \"\$command\" in *'$RUN_DIR'*) exit 0;; *flle-trading-lab-*'$expected'*) kill -INT \"\$pid\";; *) echo 'port $port belongs to an unrecognized process: '\"\$command\" >&2; exit 1;; esac; for _ in \$(seq 1 40); do kill -0 \"\$pid\" 2>/dev/null || exit 0; sleep 0.25; done; exit 1"
}

wait_hugepages_zero() {
  "${SSH[@]}" "$TRADER_HOST" "set -eu; for _ in \$(seq 1 60); do sysctl -w vm.nr_hugepages=0 >/dev/null; test \"\$(cat /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages)\" = 0 && exit 0; sleep 1; done; exit 1"
}

stop_sfc_clients() {
  stop_remote_process "$TRADER_HOST" trader-tcpdirect /flle-trader-tcpdirect
  stop_remote_process "$TRADER_HOST" trader-onload /flle-trader
  stop_remote_process "$TRADER_HOST" trader-socket /flle-trader
  "${SSH[@]}" "$TRADER_HOST" "test ! -d '$RUN_DIR/active-receipts' || rm -f -- '$RUN_DIR/active-receipts/socket' '$RUN_DIR/active-receipts/onload' '$RUN_DIR/active-receipts/tcpdirect'"
}

stop_dpdk_client() {
  "${SSH[@]}" "$TRADER_HOST" "set -eu; test -d '$RUN_DIR' || exit 0; touch '$RUN_DIR/dpdk.stop'; if test -s '$RUN_DIR/trader-dpdk-gate.pid'; then pid=\$(<'$RUN_DIR/trader-dpdk-gate.pid'); for _ in \$(seq 1 240); do kill -0 \"\$pid\" 2>/dev/null || break; sleep 0.25; done; if kill -0 \"\$pid\" 2>/dev/null; then command=\$(tr '\\0' ' ' </proc/\$pid/cmdline); case \"\$command\" in *x2522-dpdk-trader-remote.sh*) kill -INT \"\$pid\";; *) echo 'refusing mismatched DPDK gate pid' >&2; exit 1;; esac; fi; rm -f '$RUN_DIR/trader-dpdk-gate.pid'; fi"
  "${SSH[@]}" "$EXCHANGE_HOST" "set -eu; touch '$RUN_DIR/dpdk-prime.stop' 2>/dev/null || true; if test -s '$RUN_DIR/dpdk-prime.pid'; then pid=\$(<'$RUN_DIR/dpdk-prime.pid'); kill \"\$pid\" 2>/dev/null || true; rm -f '$RUN_DIR/dpdk-prime.pid'; fi"
  "${SSH[@]}" "$TRADER_HOST" "test ! -d '$RUN_DIR/active-receipts' || rm -f -- '$RUN_DIR/active-receipts/dpdk'"
}

attest_sfc_receipts() {
  local target="${1:?SFC receipt target is required}"
  case "$target" in LAUNCH|SOCKET|OPENONLOAD|TCPDIRECT) ;; *) return 2;; esac
  "${SSH[@]}" "$TRADER_HOST" bash -s -- "$RUN_DIR" "$RUNTIME_ROOT" "$target" <<'REMOTE'
set -Eeuo pipefail
run_dir="$1"; runtime_root="$2"; target="$3"
receipt_dir="$run_dir/active-receipts"
mkdir -p "$receipt_dir"

process_identity() {
  local name="$1" expected="$2" port="$3" pid command listeners start_ticks
  mapfile -t pid_lines <"$run_dir/$name.pid"
  test "${#pid_lines[@]}" -eq 1
  pid="${pid_lines[0]}"
  case "$pid" in ''|*[!0-9]*) return 1;; esac
  test -r "/proc/$pid/cmdline"
  command="$(tr '\0' ' ' <"/proc/$pid/cmdline")"
  case "$command" in *"$expected"*) ;; *) return 1;; esac
  listeners="$(ss -ltnpH "( sport = :$port )" 2>/dev/null || true)"
  case "$listeners" in *"pid=$pid,"*) ;; *) return 1;; esac
  start_ticks="$(awk '{print $22}' "/proc/$pid/stat")"
  case "$start_ticks" in ''|*[!0-9]*) return 1;; esac
  printf '%s %s\n' "$pid" "$start_ticks"
}

read -r socket_pid socket_start < <(process_identity trader-socket flle-trader 48122)
read -r onload_pid onload_start < <(process_identity trader-onload flle-trader 48123)
read -r tcpdirect_pid tcpdirect_start < <(process_identity trader-tcpdirect flle-trader-tcpdirect 48124)

state_for() {
  local port="$1"
  timeout 2 bash -c '
    port="$1"; exec 3<>/dev/tcp/10.1.1.2/"$port"
    printf "STATE\n" >&3; IFS= read -r reply <&3; printf "%s" "$reply"
  ' bash "$port"
}
socket_state="$(state_for 48122)"
onload_state="$(state_for 48123)"
tcpdirect_state="$(state_for 48124)"
[[ "$socket_state" == *'"status":"ONLINE"'* &&
   "$socket_state" == *'"order_transport":"POSIX_SOCKET"'* ]]
[[ "$onload_state" == *'"status":"ONLINE"'* &&
   "$onload_state" == *'"order_transport":"OPENONLOAD"'* ]]
[[ "$tcpdirect_state" == *'"status":"ONLINE"'* &&
   "$tcpdirect_state" == *'"order_transport":"TCPDIRECT_ZF"'* ]]

onload_dump="$receipt_dir/.onload-stackdump.$BASHPID"
zf_list="$receipt_dir/.zf-list.$BASHPID"
zf_attr="$receipt_dir/.zf-attr.$BASHPID"
zf_dump="$receipt_dir/.zf-dump.$BASHPID"
cleanup(){ rm -f -- "$onload_dump" "$zf_list" "$zf_attr" "$zf_dump"; }
trap cleanup EXIT
path_counter=0
case "$target" in
  LAUNCH)
    ;;
  SOCKET)
    socket_connections="$(ss -tnpH state established 2>/dev/null || true)"
    awk -v target="$socket_pid" '
      index($0, "20.1.1.1:43120") > 0 &&
      index($0, "pid=" target ",") > 0 { found = 1 }
      END { exit(found ? 0 : 1) }
    ' <<<"$socket_connections"
    path_counter="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["stats"]["orders"])' <<<"$socket_state")"
    ;;
  OPENONLOAD)
    onload_stackdump lots >"$onload_dump" 2>&1
    awk -v target="$onload_pid" '
      /^  Onload .* pid=[0-9]+ / {
        active = index($0, " pid=" target " ") > 0
        established = 0
        valid = 0
      }
      active && /^TCP .*lcl=20[.]1[.]1[.]2:[0-9]+ rmt=20[.]1[.]1[.]1:43120 ESTABLISHED/ {
        established = 1
      }
      active && /Onloaded[(]Valid[)]/ { valid = 1 }
      active && established && valid { found = 1 }
      END { exit(found ? 0 : 1) }
    ' "$onload_dump"
    path_counter="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["stats"]["orders"])' <<<"$onload_state")"
    ;;
  TCPDIRECT)
    "$runtime_root/bin/zf_stackdump" list >"$zf_list" 2>&1
    mapfile -t stack_ids < <(awk -v target="$tcpdirect_pid" '
      $1 == "flle-tcpdirect" && $NF == "pid=" target {
        for (i = 1; i <= NF; ++i) {
          if ($i ~ /^id=[0-9]+$/) {
            sub(/^id=/, "", $i)
            print $i
          }
        }
      }
    ' "$zf_list")
    test "${#stack_ids[@]}" -eq 1
    stack_id="${stack_ids[0]}"
    "$runtime_root/bin/zf_stackdump" attr "$stack_id" >"$zf_attr" 2>&1
    "$runtime_root/bin/zf_stackdump" dump "$stack_id" >"$zf_dump" 2>&1
    grep -Fxq 'ctpio=3' "$zf_attr"
    grep -Fxq 'ctpio_mode=sf-np' "$zf_attr"
    grep -Eq '^TCP flle-tcpdirect:[0-9]+ lcl=20[.]1[.]1[.]2:[0-9]+ rmt=20[.]1[.]1[.]1:43120 .*ESTABLISHED$' "$zf_dump"
    mapfile -t txq_added < <(awk '
      /^  txq:/ {
        for (i = 1; i <= NF; ++i) {
          if ($i ~ /^added=[0-9]+$/) {
            sub(/^added=/, "", $i)
            print $i
          }
        }
      }
    ' "$zf_dump")
    test "${#txq_added[@]}" -eq 1
    path_counter="${txq_added[0]}"
    ;;
esac
case "$path_counter" in ''|*[!0-9]*) exit 1;; esac

attested_ns="$(python3 -c 'import time; print(time.monotonic_ns())')"
boot_id="$(cat /proc/sys/kernel/random/boot_id)"
write_receipt() {
  local name="$1" pid="$2" start_ticks="$3" counter="$4" verification="$5"
  local tmp="$receipt_dir/.$name.$BASHPID"
  printf 'pid=%s start_ticks=%s boot_id=%s generation=%s-%s-%s attested_monotonic_ns=%s path_counter=%s verification=%s\n' \
    "$pid" "$start_ticks" "$boot_id" "$name" "$pid" "$start_ticks" \
    "$attested_ns" "$counter" "$verification" >"$tmp"
  mv "$tmp" "$receipt_dir/$name"
}
case "$target" in
  LAUNCH)
    write_receipt socket "$socket_pid" "$socket_start" 0 LAUNCH_POSIX_CURRENT_PID
    write_receipt onload "$onload_pid" "$onload_start" 0 LAUNCH_ONLOAD_CURRENT_PID
    write_receipt tcpdirect "$tcpdirect_pid" "$tcpdirect_start" 0 LAUNCH_ZF_CURRENT_PID
    ;;
  SOCKET)
    write_receipt socket "$socket_pid" "$socket_start" "$path_counter" PATH_POSIX_ESTABLISHED_CURRENT_PID
    ;;
  OPENONLOAD)
    write_receipt onload "$onload_pid" "$onload_start" "$path_counter" PATH_ONLOADED_VALID_ESTABLISHED_CURRENT_PID
    ;;
  TCPDIRECT)
    write_receipt tcpdirect "$tcpdirect_pid" "$tcpdirect_start" "$path_counter" PATH_ZF_CTPIO3_ESTABLISHED_CURRENT_PID
    ;;
esac
printf 'attested_monotonic_ns=%s mode=SFC target=%s path_counter=%s socket_pid=%s onload_pid=%s tcpdirect_pid=%s\n' \
  "$attested_ns" "$target" "$path_counter" "$socket_pid" "$onload_pid" "$tcpdirect_pid" \
  >>"$run_dir/hardware-receipt.attestations"
REMOTE
}

attest_dpdk_receipt() {
  local target="${1:?DPDK receipt target is required}"
  case "$target" in LAUNCH|DPDK) ;; *) return 2;; esac
  "${SSH[@]}" "$TRADER_HOST" bash -s -- "$RUN_DIR" "$target" <<'REMOTE'
set -Eeuo pipefail
run_dir="$1"; target="$2"; receipt_dir="$run_dir/active-receipts"
mkdir -p "$receipt_dir"
mapfile -t pid_lines <"$run_dir/dpdk-session/trader.pid"
test "${#pid_lines[@]}" -eq 1
pid="${pid_lines[0]}"
case "$pid" in ''|*[!0-9]*) exit 1;; esac
test -r "/proc/$pid/cmdline"
command="$(tr '\0' ' ' <"/proc/$pid/cmdline")"
case "$command" in *flle-trader-dpdk*) ;; *) exit 1;; esac
start_ticks="$(awk '{print $22}' "/proc/$pid/stat")"
case "$start_ticks" in ''|*[!0-9]*) exit 1;; esac
state="$(timeout 2 bash -c '
  exec 3<>/dev/tcp/10.1.1.2/48125
  printf "STATE\n" >&3; IFS= read -r reply <&3; printf "%s" "$reply"
')"
[[ "$state" == *'"status":"ONLINE"'* &&
   "$state" == *'"order_transport":"DPDK_FSTACK"'* ]]
if test "$target" = DPDK; then
  python3 -c 'import json,sys
s=json.load(sys.stdin)
if not (type(s["stats"]["orders"]) is int and s["stats"]["orders"] > 0 and
        type(s["stats"]["fills"]) is int and s["stats"]["fills"] > 0):
    raise SystemExit("DPDK STATE has no completed order/fill")
' <<<"$state"
fi
path_counter="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["stats"]["orders"])' <<<"$state")"
case "$path_counter" in ''|*[!0-9]*) exit 1;; esac
grep -Fq 'Using IOMMU type 1' "$run_dir/dpdk-session/fstack.log"
grep -Fq 'Probe PCI driver: net_sfc_efx' "$run_dir/dpdk-session/fstack.log"
grep -Fq 'running FW variant is ultra-low-latency' "$run_dir/dpdk-session/fstack.log"
attested_ns="$(python3 -c 'import time; print(time.monotonic_ns())')"
boot_id="$(cat /proc/sys/kernel/random/boot_id)"
tmp="$receipt_dir/.dpdk.$BASHPID"
if test "$target" = LAUNCH; then
  verification=LAUNCH_IOMMU_TYPE1_NET_SFC_EFX_ULL_CURRENT_PID
else
  verification=PATH_TRUE_ORDER_IOMMU_TYPE1_NET_SFC_EFX_ULL_CURRENT_PID
fi
printf 'pid=%s start_ticks=%s boot_id=%s generation=dpdk-%s-%s attested_monotonic_ns=%s path_counter=%s verification=%s\n' \
  "$pid" "$start_ticks" "$boot_id" "$pid" "$start_ticks" "$attested_ns" \
  "$path_counter" "$verification" >"$tmp"
mv "$tmp" "$receipt_dir/dpdk"
printf 'attested_monotonic_ns=%s mode=DPDK target=%s path_counter=%s dpdk_pid=%s\n' \
  "$attested_ns" "$target" "$path_counter" "$pid" >>"$run_dir/hardware-receipt.attestations"
REMOTE
}

capture_native_receipt() {
  local spec="${1:?native receipt target is required}"
  local target round_number position phase extra cell
  IFS=: read -r target round_number position phase extra <<<"$spec"
  case "$target" in SOCKET|OPENONLOAD|TCPDIRECT|DPDK) ;; *) return 2;; esac
  if test "$round_number" = standalone && test "$phase" = evidence; then
    case "$position" in ''|*[!A-Za-z0-9._-]*) return 2;; esac
    cell="standalone-${target,,}-$position"
  else
    case "$round_number" in 1|2|3|4) ;; *) return 2;; esac
    case "$position" in 1|2|3|4) ;; *) return 2;; esac
    case "$phase" in pre|post) ;; *) return 2;; esac
    cell="$round_number-$position-${target,,}"
  fi
  test -z "${extra:-}" || return 2
  "${SSH[@]}" "$TRADER_HOST" bash -s -- \
    "$RUN_DIR" "$RUNTIME_ROOT" "$target" "$cell" "$phase" <<'REMOTE'
set -Eeuo pipefail
run_dir="$1"; runtime_root="$2"; target="$3"; cell="$4"; phase="$5"
if test "$phase" = evidence; then
  root="$run_dir/standalone-native-receipts"
else
  root="$run_dir/native-receipts"
fi
final="$root/$cell/$phase"
tmp="$root/.$cell.$phase.$BASHPID"
test ! -e "$final"
mkdir -p "$root" "$(dirname "$final")" "$tmp"
cleanup(){ test ! -e "$tmp" || find "$tmp" -depth -delete; }
trap cleanup EXIT

case "$target" in
  SOCKET) name=trader-socket; expected=flle-trader; port=48122; label=POSIX_SOCKET;;
  OPENONLOAD) name=trader-onload; expected=flle-trader; port=48123; label=OPENONLOAD;;
  TCPDIRECT) name=trader-tcpdirect; expected=flle-trader-tcpdirect; port=48124; label=TCPDIRECT_ZF;;
  DPDK) name=dpdk-session/trader; expected=flle-trader-dpdk; port=48125; label=DPDK_FSTACK;;
esac
mapfile -t pid_lines <"$run_dir/$name.pid"
test "${#pid_lines[@]}" -eq 1
pid="${pid_lines[0]}"
case "$pid" in ''|*[!0-9]*) exit 1;; esac
test -r "/proc/$pid/cmdline"
command="$(tr '\0' ' ' <"/proc/$pid/cmdline")"
case "$command" in *"$expected"*) ;; *) exit 1;; esac
start_ticks="$(awk '{print $22}' "/proc/$pid/stat")"
case "$start_ticks" in ''|*[!0-9]*) exit 1;; esac
boot_id="$(cat /proc/sys/kernel/random/boot_id)"
listeners="$(ss -ltnpH "( sport = :$port )" 2>/dev/null || true)"
case "$listeners" in *"pid=$pid,"*) ;; *) exit 1;; esac
state="$(timeout 2 bash -c '
  port="$1"; exec 3<>/dev/tcp/10.1.1.2/"$port"
  printf "STATE\n" >&3; IFS= read -r reply <&3; printf "%s" "$reply"
' bash "$port")"
python3 -c 'import json,sys
s=json.load(sys.stdin)
if s.get("status") != "ONLINE" or s.get("order_transport") != sys.argv[1]:
    raise SystemExit("native STATE identity is not ONLINE on the requested path")
stats=s.get("stats", {})
if not (type(stats.get("orders")) is int and stats["orders"] > 0 and
        type(stats.get("fills")) is int and stats["fills"] > 0):
    raise SystemExit("native STATE has no completed order/fill")
' "$label" <<<"$state"
printf '%s\n' "$state" >"$tmp/state.json"
printf 'pid=%s\nstart_ticks=%s\nboot_id=%s\ncmdline=%s\n' \
  "$pid" "$start_ticks" "$boot_id" "$command" >"$tmp/process.txt"

case "$target" in
  SOCKET)
    ss -tnpH state established >"$tmp/ss-established.txt"
    awk -v target="$pid" '
      index($0, "20.1.1.2:") > 0 &&
      index($0, "20.1.1.1:43120") > 0 &&
      index($0, "pid=" target ",") > 0 { found = 1 }
      END { exit(found ? 0 : 1) }
    ' "$tmp/ss-established.txt"
    ;;
  OPENONLOAD)
    onload_stackdump lots >"$tmp/onload-stackdump.txt" 2>&1
    awk -v target="$pid" '
      /^  Onload .* pid=[0-9]+ / { active = index($0, " pid=" target " ") > 0 }
      active && /^TCP .*lcl=20[.]1[.]1[.]2:[0-9]+ rmt=20[.]1[.]1[.]1:43120 ESTABLISHED/ {
        in_target_tcp = 1; found_endpoint = 1; next
      }
      active && in_target_tcp && /^TCP / { in_target_tcp = 0 }
      active && in_target_tcp && /Onloaded[(]Valid[)]/ { found_valid = 1 }
      END { exit(found_endpoint && found_valid ? 0 : 1) }
    ' "$tmp/onload-stackdump.txt"
    ;;
  TCPDIRECT)
    "$runtime_root/bin/zf_stackdump" list >"$tmp/zf-list.txt" 2>&1
    mapfile -t stack_ids < <(awk -v target="$pid" '
      $1 == "flle-tcpdirect" && $NF == "pid=" target {
        for (i = 1; i <= NF; ++i) if ($i ~ /^id=[0-9]+$/) {
          sub(/^id=/, "", $i); print $i
        }
      }
    ' "$tmp/zf-list.txt")
    test "${#stack_ids[@]}" -eq 1
    stack_id="${stack_ids[0]}"
    "$runtime_root/bin/zf_stackdump" attr "$stack_id" >"$tmp/zf-attr.txt" 2>&1
    "$runtime_root/bin/zf_stackdump" dump "$stack_id" >"$tmp/zf-dump.txt" 2>&1
    grep -Fxq 'ctpio=3' "$tmp/zf-attr.txt"
    grep -Fxq 'ctpio_mode=sf-np' "$tmp/zf-attr.txt"
    grep -Eq '^TCP flle-tcpdirect:[0-9]+ lcl=20[.]1[.]1[.]2:[0-9]+ rmt=20[.]1[.]1[.]1:43120 .*ESTABLISHED$' "$tmp/zf-dump.txt"
    test "$(grep -Ec '^  txq: .*added=[0-9]+' "$tmp/zf-dump.txt")" -eq 1
    ;;
  DPDK)
    cp -- "$run_dir/dpdk-session/fstack.log" "$tmp/fstack.log"
    driver="$(basename "$(readlink /sys/bus/pci/devices/0000:03:00.0/driver)")"
    iommu_group="$(basename "$(readlink -f /sys/bus/pci/devices/0000:03:00.0/iommu_group)")"
    mapfile -t group_devices < <(find "/sys/kernel/iommu_groups/$iommu_group/devices" \
      -mindepth 1 -maxdepth 1 -printf '%f\n' | sort)
    test "$driver" = vfio-pci
    test "${#group_devices[@]}" -eq 1
    test "${group_devices[0]}" = 0000:03:00.0
    unsafe_noiommu="$(cat /sys/module/vfio/parameters/enable_unsafe_noiommu_mode 2>/dev/null || echo N)"
    test "$unsafe_noiommu" = N
    printf 'driver=%s\niommu_group=%s\ngroup_device=%s\nunsafe_noiommu=%s\n' \
      "$driver" "$iommu_group" "${group_devices[0]}" "$unsafe_noiommu" \
      >"$tmp/owner.txt"
    grep -Fq 'Using IOMMU type 1' "$tmp/fstack.log"
    grep -Fq 'Probe PCI driver: net_sfc_efx' "$tmp/fstack.log"
    grep -Fq 'running FW variant is ultra-low-latency' "$tmp/fstack.log"
    ;;
esac

manifest="$(python3 - "$run_dir" "$tmp" "$final" "$target" <<'PY'
import hashlib
import json
import re
import sys
from pathlib import Path

run_dir = Path(sys.argv[1])
directory = Path(sys.argv[2])
published_directory = Path(sys.argv[3])
target = sys.argv[4]
relative_root = published_directory.relative_to(run_dir)
files = []
texts = {}
for path in sorted(directory.iterdir()):
    payload = path.read_bytes()
    relative = (relative_root / path.name).as_posix()
    files.append({
        "path": relative,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
    })
    texts[path.name] = payload.decode("utf-8", errors="strict")

state = json.loads(texts["state.json"])
process_lines = dict(
    line.split("=", 1) for line in texts["process.txt"].splitlines()
)
pid = int(process_lines["pid"])
excerpts = [{"path": (relative_root / "process.txt").as_posix(),
             "text": f"pid={pid}"}]
if target == "SOCKET":
    matches = [line for line in texts["ss-established.txt"].splitlines()
               if "20.1.1.2:" in line and "20.1.1.1:43120" in line
               and f"pid={pid}," in line]
    if len(matches) != 1:
        raise SystemExit("Socket native endpoint/PID match is not unique")
    excerpts.append({"path": (relative_root / "ss-established.txt").as_posix(),
                     "text": matches[0]})
    counter_kind = "trader_orders"
    counter_value = state["stats"]["orders"]
elif target == "OPENONLOAD":
    lines = texts["onload-stackdump.txt"].splitlines()
    headers = [(index, int(match.group(1)))
               for index, line in enumerate(lines)
               if (match := re.match(r"^  Onload .* pid=([0-9]+) ", line))]
    stack_indexes = [index for index, stack_pid in headers if stack_pid == pid]
    if len(stack_indexes) != 1:
        raise SystemExit("Onload current PID stack is not unique")
    stack_start = stack_indexes[0]
    stack_end = next((index for index, _ in headers if index > stack_start), len(lines))
    endpoint_indexes = [index for index in range(stack_start + 1, stack_end)
                        if re.match(r"^TCP .*lcl=20\.1\.1\.2:[0-9]+ "
                                    r"rmt=20\.1\.1\.1:43120 ESTABLISHED$", lines[index])]
    if len(endpoint_indexes) != 1:
        raise SystemExit("Onload target endpoint is not unique in current PID stack")
    endpoint_index = endpoint_indexes[0]
    end = next((index for index in range(endpoint_index + 1, stack_end)
                if lines[index].startswith("TCP ") or lines[index].startswith("-----")),
               stack_end)
    valid_lines = [line for line in lines[endpoint_index:end]
                   if "Onloaded(Valid)" in line]
    if len(valid_lines) != 1:
        raise SystemExit("Onload target TCP block has no unique Onloaded(Valid)")
    valid = valid_lines[0]
    ctpio_pkts = [line for line in lines[stack_start:stack_end]
                  if re.fullmatch(r"ctpio_pkts: [0-9]+", line)]
    ctpio_fallbacks = [line for line in lines[stack_start:stack_end]
                       if re.fullmatch(r"ctpio_dma_fallbacks: [0-9]+", line)]
    if len(ctpio_pkts) != 1 or len(ctpio_fallbacks) != 1:
        raise SystemExit("Onload CTPIO stack counters are not unique")
    excerpts.extend([
        {"path": (relative_root / "onload-stackdump.txt").as_posix(), "text": lines[stack_start]},
        {"path": (relative_root / "onload-stackdump.txt").as_posix(), "text": lines[endpoint_index]},
        {"path": (relative_root / "onload-stackdump.txt").as_posix(), "text": valid},
        {"path": (relative_root / "onload-stackdump.txt").as_posix(), "text": ctpio_pkts[0]},
        {"path": (relative_root / "onload-stackdump.txt").as_posix(), "text": ctpio_fallbacks[0]},
    ])
    counter_kind = "trader_orders"
    counter_value = state["stats"]["orders"]
elif target == "TCPDIRECT":
    list_lines = [line for line in texts["zf-list.txt"].splitlines()
                  if re.fullmatch(rf"flle-tcpdirect\s+id=[0-9]+\s+pid={pid}", line)]
    ctpio_lines = [line for line in texts["zf-attr.txt"].splitlines()
                   if line == "ctpio=3"]
    mode_lines = [line for line in texts["zf-attr.txt"].splitlines()
                  if line == "ctpio_mode=sf-np"]
    endpoint_lines = [line for line in texts["zf-dump.txt"].splitlines()
                      if re.match(r"^TCP flle-tcpdirect:[0-9]+ "
                                  r"lcl=20\.1\.1\.2:[0-9]+ "
                                  r"rmt=20\.1\.1\.1:43120 .*ESTABLISHED$", line)]
    txq_lines = [line for line in texts["zf-dump.txt"].splitlines()
                 if line.startswith("  txq:") and re.search(r"\badded=[0-9]+\b", line)]
    if not all(len(group) == 1 for group in (
        list_lines, ctpio_lines, mode_lines, endpoint_lines, txq_lines
    )):
        raise SystemExit("TCPDirect native path matches are not unique")
    list_line = list_lines[0]
    ctpio = ctpio_lines[0]
    mode = mode_lines[0]
    endpoint = endpoint_lines[0]
    txq = txq_lines[0]
    counter_value = int(re.search(r"\badded=([0-9]+)\b", txq).group(1))
    excerpts.extend([
        {"path": (relative_root / "zf-list.txt").as_posix(), "text": list_line},
        {"path": (relative_root / "zf-attr.txt").as_posix(), "text": ctpio},
        {"path": (relative_root / "zf-attr.txt").as_posix(), "text": mode},
        {"path": (relative_root / "zf-dump.txt").as_posix(), "text": endpoint},
        {"path": (relative_root / "zf-dump.txt").as_posix(), "text": txq},
    ])
    counter_kind = "zf_txq_added"
else:
    required = (
        "Using IOMMU type 1",
        "Probe PCI driver: net_sfc_efx",
        "running FW variant is ultra-low-latency",
    )
    for needle in required:
        line = next(line for line in texts["fstack.log"].splitlines()
                    if needle in line)
        excerpts.append({"path": (relative_root / "fstack.log").as_posix(),
                         "text": line})
    for needle in (
        "driver=vfio-pci",
        "iommu_group=7",
        "group_device=0000:03:00.0",
        "unsafe_noiommu=N",
    ):
        line = next(line for line in texts["owner.txt"].splitlines()
                    if line == needle)
        excerpts.append({"path": (relative_root / "owner.txt").as_posix(),
                         "text": line})
    counter_kind = "trader_orders"
    counter_value = state["stats"]["orders"]

print(json.dumps({
    "files": files,
    "counter_kind": counter_kind,
    "counter_value": counter_value,
    "matching_excerpts": excerpts,
}, separators=(",", ":")))
PY
)"
mv "$tmp" "$final"
trap - EXIT
printf '%s\n' "$manifest"
REMOTE
}

allocate_sfc_user_ref_slot() {
  "${SSH[@]}" "$TRADER_HOST" bash -s -- \
    "$RUN_DIR" "$SFC_SOCKET_USER_REF_ROOT" "$SFC_ONLOAD_USER_REF_ROOT" \
    "$SFC_TCPDIRECT_USER_REF_ROOT" "$SFC_USER_REF_SLOT_STRIDE" \
    "$SFC_USER_REF_NAMESPACE_SPAN" <<'REMOTE'
set -Eeuo pipefail
run_dir="$1"; socket_root="$2"; onload_root="$3"; tcpdirect_root="$4"
stride="$5"; namespace_span="$6"; uint32_limit=4294967296
test -d "$run_dir"
for value in "$socket_root" "$onload_root" "$tcpdirect_root" "$stride" "$namespace_span"; do
  case "$value" in ''|*[!0-9]*) echo "invalid SFC user-ref allocator value=$value" >&2; exit 1;; esac
  test "${#value}" -le 10
done
socket_root=$((10#$socket_root)); onload_root=$((10#$onload_root))
tcpdirect_root=$((10#$tcpdirect_root)); stride=$((10#$stride))
namespace_span=$((10#$namespace_span))
test "$socket_root" -gt 0; test "$socket_root" -lt "$onload_root"
test "$onload_root" -lt "$tcpdirect_root"; test "$tcpdirect_root" -lt "$uint32_limit"
test "$stride" -gt "$namespace_span"; test "$namespace_span" -gt 0

slot_file="$run_dir/sfc-user-ref.next-slot"
lock_file="$run_dir/sfc-user-ref.slot.lock"
exec 9>"$lock_file"
flock -x 9
slot=0
if test -e "$slot_file"; then
  test -s "$slot_file"
  mapfile -t slot_lines <"$slot_file"
  test "${#slot_lines[@]}" -eq 1
  slot="${slot_lines[0]}"
fi
case "$slot" in ''|*[!0-9]*) echo "invalid persisted SFC slot=$slot" >&2; exit 1;; esac
test "${#slot}" -le 10
slot=$((10#$slot))

# Every restart receives a disjoint, bounded namespace.  The unused part of
# stride prevents one restart slot from reaching the next slot's namespace.
socket_base=$((socket_root + slot * stride))
onload_base=$((onload_root + slot * stride))
tcpdirect_base=$((tcpdirect_root + slot * stride))
test "$((socket_base + stride))" -le "$onload_root"
test "$((onload_base + stride))" -le "$tcpdirect_root"
test "$((tcpdirect_base + stride))" -le 3200000000
test "$((tcpdirect_base + namespace_span))" -le "$uint32_limit"

next_slot=$((slot + 1))
slot_tmp="$slot_file.tmp.$BASHPID"
trap 'rm -f -- "$slot_tmp"' EXIT
printf '%s\n' "$next_slot" >"$slot_tmp"
mv "$slot_tmp" "$slot_file"
printf 'slot=%s socket_base=%s onload_base=%s tcpdirect_base=%s namespace_span=%s stride=%s\n' \
  "$slot" "$socket_base" "$onload_base" "$tcpdirect_base" "$namespace_span" "$stride" \
  >>"$run_dir/sfc-user-ref.allocations"
printf '%s %s %s %s %s\n' \
  "$slot" "$socket_base" "$onload_base" "$tcpdirect_base" "$namespace_span"
REMOTE
}

start_sfc_clients() {
  local allocation sfc_slot socket_base onload_base tcpdirect_base namespace_span
  local extra common socket_ready onload_ready tcpdirect_ready state lock
  allocation="$(allocate_sfc_user_ref_slot)"
  read -r sfc_slot socket_base onload_base tcpdirect_base namespace_span extra <<<"$allocation"
  test -n "$sfc_slot"; test -n "$socket_base"; test -n "$onload_base"
  test -n "$tcpdirect_base"; test -n "$namespace_span"; test -z "${extra:-}"
  common="--role MANUAL --data-ip 20.1.1.2 --exchange-data-ip 20.1.1.1 --management-ip 10.1.1.2 --telemetry-host $TELEMETRY_HOST --book-checkpoint $RUN_DIR/opening-book.checkpoint --market-receiver 0 --order-queue DEQUE_CV --lock-order-queue 1 --order-cpu 2 --management-cpu 3"
  start_remote_process "$TRADER_HOST" trader-socket \
    "taskset -c 2,3 '$RUNTIME_ROOT/bin/flle-trader' $common --management-port 48122 --user-ref-base $socket_base --user-ref-span $namespace_span --clordid-prefix SOCK --order-transport-label POSIX_SOCKET"
  start_remote_process "$TRADER_HOST" trader-onload \
    "taskset -c 2,3 onload --profile=latency '$RUNTIME_ROOT/bin/flle-trader' $common --management-port 48123 --user-ref-base $onload_base --user-ref-span $namespace_span --clordid-prefix ONLD --order-transport-label OPENONLOAD"
  start_remote_process "$TRADER_HOST" trader-tcpdirect \
    "taskset -c 2,3 '$RUNTIME_ROOT/bin/flle-trader-tcpdirect' $common --management-port 48124 --user-ref-base $tcpdirect_base --user-ref-span $namespace_span --clordid-prefix TCPD --order-transport-label TCPDIRECT_ZF"
  wait_remote_listener "$TRADER_HOST" trader-socket /flle-trader 48122
  wait_remote_listener "$TRADER_HOST" trader-onload /flle-trader 48123
  wait_remote_listener "$TRADER_HOST" trader-tcpdirect /flle-trader-tcpdirect 48124
  socket_ready="$(wait_state 48122 '"order_transport":"POSIX_SOCKET"')"
  onload_ready="$(wait_state 48123 '"order_transport":"OPENONLOAD"')"
  tcpdirect_ready="$(wait_state 48124 '"order_transport":"TCPDIRECT_ZF"')"
  [[ "$socket_ready" == *"\"user_ref_base\":$socket_base"* &&
     "$socket_ready" == *"\"user_ref_span\":$namespace_span"* &&
     "$socket_ready" == *"\"user_ref_next\":$socket_base"* ]]
  [[ "$onload_ready" == *"\"user_ref_base\":$onload_base"* &&
     "$onload_ready" == *"\"user_ref_span\":$namespace_span"* &&
     "$onload_ready" == *"\"user_ref_next\":$onload_base"* ]]
  [[ "$tcpdirect_ready" == *"\"user_ref_base\":$tcpdirect_base"* &&
     "$tcpdirect_ready" == *"\"user_ref_span\":$namespace_span"* &&
     "$tcpdirect_ready" == *"\"user_ref_next\":$tcpdirect_base"* ]]
  for port in 48122 48123 48124; do
    state="$(management_command "$port" STATE)"
    [[ "$state" == *'"queue_mode":"DEQUE_CV"'* ]]
    [[ "$state" == *'"queue_locked":true'* ]]
    lock="$(management_command "$port" 'SOFTWARE_PROFILE|SPSC_SPIN')"
    [[ "$lock" == *'locks order_queue to DEQUE_CV'* ]]
  done
  attest_sfc_receipts LAUNCH
}

allocate_dpdk_user_ref_slot() {
  "${SSH[@]}" "$TRADER_HOST" bash -s -- \
    "$RUN_DIR" "$DPDK_USER_REF_ROOT" "$DPDK_USER_REF_SLOT_SPAN" <<'REMOTE'
set -Eeuo pipefail
run_dir="$1"; root="$2"; span="$3"; uint32_limit=4294967296
test -d "$run_dir"
case "$root" in ''|*[!0-9]*) echo "invalid user_ref root=$root" >&2; exit 1;; esac
case "$span" in ''|*[!0-9]*) echo "invalid user_ref span=$span" >&2; exit 1;; esac
test "${#root}" -le 10
test "${#span}" -le 10
root=$((10#$root))
span=$((10#$span))
test "$root" -gt 0
test "$root" -lt "$uint32_limit"
test "$span" -gt 0
test "$span" -le "$((uint32_limit - root))"

slot_file="$run_dir/dpdk-user-ref.next-slot"
lock_file="$run_dir/dpdk-user-ref.slot.lock"
exec 9>"$lock_file"
flock -x 9
slot=0
if test -e "$slot_file"; then
  test -s "$slot_file"
  mapfile -t slot_lines <"$slot_file"
  test "${#slot_lines[@]}" -eq 1
  slot="${slot_lines[0]}"
fi
case "$slot" in ''|*[!0-9]*) echo "invalid persisted DPDK slot=$slot" >&2; exit 1;; esac
test "${#slot}" -le 10
slot=$((10#$slot))

max_slots=$(((uint32_limit - root) / span))
test "$slot" -lt "$max_slots"
base=$((root + slot * span))
end=$((base + span))
test "$base" -ge "$root"
test "$end" -le "$uint32_limit"

next_slot=$((slot + 1))
slot_tmp="$slot_file.tmp.$BASHPID"
trap 'rm -f -- "$slot_tmp"' EXIT
printf '%s\n' "$next_slot" >"$slot_tmp"
mv "$slot_tmp" "$slot_file"
printf 'slot=%s base=%s span=%s end_exclusive=%s\n' \
  "$slot" "$base" "$span" "$end" >>"$run_dir/dpdk-user-ref.allocations"
printf '%s %s %s\n' "$slot" "$base" "$span"
REMOTE
}

start_dpdk_client() {
  local allocation user_ref_slot user_ref_base user_ref_span user_ref_end
  local extra dpdk_ready
  allocation="$(allocate_dpdk_user_ref_slot)"
  read -r user_ref_slot user_ref_base user_ref_span extra <<<"$allocation"
  test -n "$user_ref_slot"; test -n "$user_ref_base"; test -n "$user_ref_span"
  test -z "${extra:-}"
  user_ref_end=$((user_ref_base + user_ref_span))
  "${SSH[@]}" "$EXCHANGE_HOST" "set -eu; cd '$RUN_DIR'; rm -f dpdk-prime.stop; nohup bash -c 'while test ! -f \"$RUN_DIR/dpdk-prime.stop\"; do ip neigh del 20.1.1.2 dev ens64np0 2>/dev/null || true; ping -I ens64np0 -c 1 -W 1 20.1.1.2 >/dev/null 2>&1 || true; sleep 0.1; done' >dpdk-prime.log 2>&1 </dev/null & echo \$! >dpdk-prime.pid"
  "${SSH[@]}" "$TRADER_HOST" "set -eu; cd '$RUN_DIR'; rm -f dpdk.stop; mkdir -p dpdk-session; nohup env FLLE_DPDK_DEADMAN=1800 FLLE_DPDK_USER_REF_SLOT='$user_ref_slot' FLLE_DPDK_USER_REF_BASE='$user_ref_base' FLLE_DPDK_USER_REF_SPAN='$user_ref_span' '$RUN_DIR/x2522-dpdk-trader-remote.sh' '$RUNTIME_ROOT/etc/f-stack-x2522.ini' '$RUNTIME_ROOT/bin/flle-trader-dpdk' '$RUN_DIR/dpdk-session' '$RUN_DIR/dpdk.stop' >trader-dpdk-gate.log 2>&1 </dev/null & echo \$! >trader-dpdk-gate.pid"
  dpdk_ready="$(wait_state 48125 '"order_transport":"DPDK_FSTACK"')"
  [[ "$dpdk_ready" == *"\"user_ref_base\":$user_ref_base"* ]]
  [[ "$dpdk_ready" == *"\"user_ref_span\":$user_ref_span"* ]]
  [[ "$dpdk_ready" == *"\"user_ref_end_exclusive\":$user_ref_end"* ]]
  [[ "$dpdk_ready" == *"\"user_ref_next\":$user_ref_base"* ]]
  attest_dpdk_receipt LAUNCH
  "${SSH[@]}" "$EXCHANGE_HOST" "touch '$RUN_DIR/dpdk-prime.stop'; if test -s '$RUN_DIR/dpdk-prime.pid'; then pid=\$(<'$RUN_DIR/dpdk-prime.pid'); kill \"\$pid\" 2>/dev/null || true; rm -f '$RUN_DIR/dpdk-prime.pid'; fi"
}

start_exchange() {
  start_remote_process "$EXCHANGE_HOST" exchange \
    "taskset -c 2 '$RUN_DIR/flle-exchange' --telemetry-host '$TELEMETRY_HOST' --replay-file '$RUN_DIR/AAPL_NVDA.itch' --book-checkpoint '$RUN_DIR/opening-book.checkpoint' --market-date 2026-06-12 --market-mode UNICAST --replay-speed 1"
  wait_remote_listener "$EXCHANGE_HOST" exchange /flle-exchange 43120
  wait_remote_listener "$EXCHANGE_HOST" exchange /flle-exchange 48120
}

start_controller() {
  mkdir -p "$CONTROL_DIR"
  if systemctl is-active --quiet "$CONTROLLER_UNIT"; then return 0; fi
  systemd-run --quiet --collect --unit "$CONTROLLER_UNIT" \
    --property="WorkingDirectory=$REPO_ROOT" \
    /usr/bin/python3 "$APP_DIR/flle_trading/transport_controller.py" \
      --bind-ip "$CONTROLLER_IP" --allowed-peer 10.1.1.101 \
      --control-script "$SCRIPT_DIR/transport_labctl.sh" --run-id "$RUN_ID"
  for _ in $(seq 1 40); do
    systemctl is-active --quiet "$CONTROLLER_UNIT" || break
    ss -ltn | grep -q ':48606 ' && return 0
    sleep 0.25
  done
  journalctl -u "$CONTROLLER_UNIT" -n 30 --no-pager >&2 || true
  return 1
}

start_gateway() {
  start_remote_process "$OBSERVER_HOST" gateway \
    "env PYTHONPATH='$RUN_DIR' python3 -m flle_trading.gateway --web-root '$RUN_DIR/web' --transport-lab --data-plane-controller-url 'http://$CONTROLLER_IP:48606'"
  wait_remote_listener "$OBSERVER_HOST" gateway flle_trading.gateway 8088
}

collect_status() {
  local driver mode owner transition socket_state onload_state tcpdirect_state dpdk_state
  local active_receipts name receipt socket_receipt="" onload_receipt=""
  local tcpdirect_receipt="" dpdk_receipt=""
  driver="$("${SSH[@]}" "$TRADER_HOST" "basename \"\$(readlink /sys/bus/pci/devices/0000:03:00.0/driver)\"" 2>/dev/null || echo UNKNOWN)"
  if [[ "$driver" == vfio-pci ]]; then mode=DPDK; owner=vfio-pci; else mode=SFC; owner="$driver"; fi
  socket_state="$(management_command 48122 STATE 2>/dev/null || true)"
  onload_state="$(management_command 48123 STATE 2>/dev/null || true)"
  tcpdirect_state="$(management_command 48124 STATE 2>/dev/null || true)"
  dpdk_state="$(management_command 48125 STATE 2>/dev/null || true)"
  active_receipts="$("${SSH[@]}" "$TRADER_HOST" bash -s -- "$RUN_DIR" <<'REMOTE'
set -u
run_dir="$1"
emit_if_current() {
  local name="$1" pidfile="$2" expected="$3" port="$4"
  local line pid_field start_field boot_field generation_field attested_field counter_field verification_field extra
  local pid start_ticks boot_id current_pid current_start current_boot command listeners
  test -s "$run_dir/active-receipts/$name" || return 0
  IFS= read -r line <"$run_dir/active-receipts/$name" || return 0
  read -r pid_field start_field boot_field generation_field attested_field counter_field verification_field extra <<<"$line"
  test -z "${extra:-}" || return 0
  case "$pid_field" in pid=*) pid="${pid_field#pid=}";; *) return 0;; esac
  case "$start_field" in start_ticks=*) start_ticks="${start_field#start_ticks=}";; *) return 0;; esac
  case "$boot_field" in boot_id=*) boot_id="${boot_field#boot_id=}";; *) return 0;; esac
  case "$generation_field" in generation=*) ;; *) return 0;; esac
  case "$attested_field" in attested_monotonic_ns=*) ;; *) return 0;; esac
  case "$counter_field" in path_counter=*) ;; *) return 0;; esac
  case "$verification_field" in verification=*) ;; *) return 0;; esac
  case "$pid" in ''|*[!0-9]*) return 0;; esac
  case "$start_ticks" in ''|*[!0-9]*) return 0;; esac
  test -s "$pidfile" || return 0
  IFS= read -r current_pid <"$pidfile" || return 0
  test "$current_pid" = "$pid" || return 0
  test -r "/proc/$pid/cmdline" || return 0
  command="$(tr '\0' ' ' <"/proc/$pid/cmdline")"
  case "$command" in *"$expected"*) ;; *) return 0;; esac
  current_start="$(awk '{print $22}' "/proc/$pid/stat" 2>/dev/null || true)"
  test "$current_start" = "$start_ticks" || return 0
  current_boot="$(cat /proc/sys/kernel/random/boot_id 2>/dev/null || true)"
  test "$current_boot" = "$boot_id" || return 0
  if test "$port" != none; then
    listeners="$(ss -ltnpH "( sport = :$port )" 2>/dev/null || true)"
    case "$listeners" in *"pid=$pid,"*) ;; *) return 0;; esac
  fi
  printf '%s|%s\n' "$name" "$line"
}
emit_if_current socket "$run_dir/trader-socket.pid" flle-trader 48122
emit_if_current onload "$run_dir/trader-onload.pid" flle-trader 48123
emit_if_current tcpdirect "$run_dir/trader-tcpdirect.pid" flle-trader-tcpdirect 48124
emit_if_current dpdk "$run_dir/dpdk-session/trader.pid" flle-trader-dpdk none
REMOTE
)"
  while IFS='|' read -r name receipt; do
    case "$name" in
      socket) socket_receipt="$receipt";;
      onload) onload_receipt="$receipt";;
      tcpdirect) tcpdirect_receipt="$receipt";;
      dpdk) dpdk_receipt="$receipt";;
    esac
  done <<<"$active_receipts"

  transition=READY
  if [[ "$mode" == SFC ]]; then
    [[ "$socket_state" == *'"queue_locked":true'* && -n "$socket_receipt" &&
       "$onload_state" == *'"queue_locked":true'* && -n "$onload_receipt" &&
       "$tcpdirect_state" == *'"queue_locked":true'* && -n "$tcpdirect_receipt" ]] || transition=DEGRADED
  else
    [[ "$dpdk_state" == *'"queue_locked":true'* && -n "$dpdk_receipt" ]] || transition=DEGRADED
  fi
  python3 - "$mode" "$transition" "$owner" "$socket_receipt" "$onload_receipt" "$tcpdirect_receipt" "$dpdk_receipt" <<'PY'
import json, sys
mode, transition, owner, socket_raw, onload_raw, tcpdirect_raw, dpdk_raw = sys.argv[1:]
def receipt(raw, summary):
    if not raw:
        return {
            "launch_verified": False,
            "verified": False,
            "summary": "当前进程代收据待采集",
        }
    fields = dict(item.split("=", 1) for item in raw.split())
    path_verified = fields["verification"].startswith("PATH_")
    return {
        "launch_verified": True,
        "verified": path_verified,
        "summary": summary if path_verified else "当前进程身份已验；路径收据待首笔 warmup",
        "pid": int(fields["pid"]),
        "start_ticks": int(fields["start_ticks"]),
        "boot_id": fields["boot_id"],
        "generation": fields["generation"],
        "attested_monotonic_ns": int(fields["attested_monotonic_ns"]),
        "path_counter": int(fields["path_counter"]),
        "verification": fields["verification"],
    }
print(json.dumps({
    "mode": mode,
    "transition": transition,
    "owner": owner,
    "hardware_receipts": {
        "socket": receipt(socket_raw, "当前 PID 的 sfc netdev + Kernel TCP"),
        "onload": receipt(onload_raw, "当前 PID 的 Established Onloaded(Valid) + X2522 VI"),
        "tcpdirect": receipt(tcpdirect_raw, "当前 PID 的 ZF stack；CTPIO 由代码合同另验"),
        "dpdk": receipt(dpdk_raw, "当前 PID 的 IOMMU type 1 + net_sfc_efx + ULL firmware"),
    },
}, separators=(",", ":")))
PY
}

case "$ACTION" in
  preflight)
    assert_runtime_blob
    "$BASE_CTL" preflight "$RUN_ID"
    "${SSH[@]}" "$TRADER_HOST" "set -eu; test -c /dev/onload; test -c /dev/sfc_char; test \"\$(basename \"\$(readlink /sys/bus/pci/devices/0000:03:00.0/driver)\")\" = sfc; test \"\$(basename \"\$(readlink -f /sys/bus/pci/devices/0000:03:00.0/iommu_group)\")\" = 7; test \"\$(cat /sys/module/vfio/parameters/enable_unsafe_noiommu_mode 2>/dev/null || echo N)\" = N"
    echo "transport_preflight=PASS runtime_sha256=$RUNTIME_SHA queue=DEQUE_CV"
    ;;
  deploy)
    assert_runtime_blob
    "$BASE_CTL" deploy "$RUN_ID"
    "${SCP[@]}" "$RUNTIME_BLOB" "$TRADER_HOST:$RUN_DIR/transport-runtime.tgz"
    "${SCP[@]}" "$SCRIPT_DIR/x2522-dpdk-trader-remote.sh" "$TRADER_HOST:$RUN_DIR/x2522-dpdk-trader-remote.sh"
    "${SSH[@]}" "$TRADER_HOST" "set -eu; cd '$RUN_DIR'; printf '%s  %s\n' '$RUNTIME_SHA' transport-runtime.tgz | sha256sum -c -; test ! -e transport-runtime || find transport-runtime -depth -delete; mkdir transport-runtime; tar -xzf transport-runtime.tgz -C transport-runtime; cd '$RUNTIME_ROOT'; sha256sum -c MANIFEST.sha256; chmod 0755 '$RUN_DIR/x2522-dpdk-trader-remote.sh'; sha256sum '$RUN_DIR/x2522-dpdk-trader-remote.sh' '$RUN_DIR/transport-runtime.tgz' >'$RUN_DIR/transport.deployed.sha256'"
    ;;
  start)
    stop_foreign_course_listener "$EXCHANGE_HOST" 43120 /flle-exchange
    stop_foreign_course_listener "$TRADER_HOST" 48121 /flle-trader
    stop_foreign_course_listener "$TRADER_HOST" 48122 /flle-trader
    stop_foreign_course_listener "$TRADER_HOST" 48123 /flle-trader
    stop_foreign_course_listener "$TRADER_HOST" 48124 /flle-trader-tcpdirect
    stop_foreign_course_listener "$TRADER_HOST" 48125 /flle-trader-dpdk
    stop_foreign_course_listener "$OBSERVER_HOST" 8088 flle_trading.gateway
    start_exchange
    "$0" sfc "$RUN_ID" >/dev/null
    start_controller
    start_gateway
    collect_status
    ;;
  sfc)
    current="$(collect_status)"
    if [[ "$current" == *'"mode":"SFC"'* &&
          "$current" == *'"transition":"READY"'* ]]; then
      printf '%s\n' "$current"
      exit 0
    fi
    stop_dpdk_client
    stop_sfc_clients
    wait_hugepages_zero
    "${SSH[@]}" "$TRADER_HOST" "set -eu; test \"\$(basename \"\$(readlink /sys/bus/pci/devices/0000:03:00.0/driver)\")\" = sfc; ip -4 -o addr show dev ens64np1 | grep -Fq ' 20.1.1.2/24 '; sysctl -w vm.nr_hugepages=128 >/dev/null; test \"\$(cat /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages)\" = 128"
    start_sfc_clients
    collect_status
    ;;
  dpdk)
    current="$(collect_status)"
    if [[ "$current" == *'"mode":"DPDK"'* &&
          "$current" == *'"transition":"READY"'* ]]; then
      printf '%s\n' "$current"
      exit 0
    fi
    stop_sfc_clients
    stop_dpdk_client
    wait_hugepages_zero
    start_dpdk_client
    collect_status
    ;;
  measure)
    stop_remote_process "$OBSERVER_HOST" gateway flle_trading.gateway
    measure_rc=0
    python3 "$SCRIPT_DIR/measure_four_transports.py" --run-id "$RUN_ID" \
      --control-script "$0" \
      --output-root "$REPO_ROOT/Documents/reports/course-runs" || measure_rc=$?
    start_gateway
    test "$measure_rc" -eq 0
    ;;
  attest)
    driver="$("${SSH[@]}" "$TRADER_HOST" "basename \"\$(readlink /sys/bus/pci/devices/0000:03:00.0/driver)\"")"
    if [[ "$driver" == sfc ]]; then
      case "$TARGET" in SOCKET|OPENONLOAD|TCPDIRECT) ;; *) echo "invalid SFC attestation target: $TARGET" >&2; exit 2;; esac
      attest_sfc_receipts "$TARGET"
    elif [[ "$driver" == vfio-pci ]]; then
      [[ "$TARGET" == DPDK ]] || { echo "invalid DPDK attestation target: $TARGET" >&2; exit 2; }
      attest_dpdk_receipt DPDK
    else
      echo "unsupported X2522 owner during attestation: $driver" >&2
      exit 1
    fi
    if test -n "$EXPORT_DIR"; then
      case "$EXPORT_DIR" in /*) ;; *) echo "attest export path must be absolute" >&2; exit 2;; esac
      test ! -e "$EXPORT_DIR" || { echo "attest export path already exists: $EXPORT_DIR" >&2; exit 1; }
      capture_id="$(date -u +%Y%m%dT%H%M%SZ)-$$"
      manifest="$(capture_native_receipt "$TARGET:standalone:$capture_id:evidence")"
      remote_relative="$(python3 -c 'import json,sys,pathlib; print(pathlib.PurePosixPath(json.loads(sys.argv[1])["files"][0]["path"]).parent)' "$manifest")"
      case "$remote_relative" in standalone-native-receipts/standalone-*) ;; *) echo "invalid standalone native receipt path" >&2; exit 1;; esac
      mkdir -p "$(dirname -- "$EXPORT_DIR")"
      "${SCP[@]}" -r \
        "$TRADER_HOST:$RUN_DIR/$remote_relative" \
        "$EXPORT_DIR"
      python3 - "$manifest" "$EXPORT_DIR" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

manifest = json.loads(sys.argv[1])
output = Path(sys.argv[2])
expected_names = {Path(item["path"]).name for item in manifest["files"]}
if len(expected_names) != len(manifest["files"]):
    raise SystemExit("standalone native manifest has colliding file names")
actual_names = {
    path.relative_to(output).as_posix()
    for path in output.rglob("*")
    if path.is_file()
}
if actual_names != expected_names:
    raise SystemExit(
        "standalone native file set mismatch: "
        f"missing={sorted(expected_names - actual_names)} "
        f"unexpected={sorted(actual_names - expected_names)}"
    )
for item in manifest["files"]:
    target = output / Path(item["path"]).name
    payload = target.read_bytes()
    if len(payload) != item["bytes"]:
        raise SystemExit(f"standalone native byte count mismatch: {target}")
    if hashlib.sha256(payload).hexdigest() != item["sha256"]:
        raise SystemExit(f"standalone native SHA mismatch: {target}")
manifest_path = output / "manifest.json"
manifest_path.write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
sealed_files = sorted(path for path in output.iterdir() if path.is_file())
sha_path = output / "SHA256SUMS"
sha_path.write_text(
    "".join(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}\n"
        for path in sealed_files
    ),
    encoding="utf-8",
)
print(json.dumps({
    "local_directory": str(output),
    "manifest_file": str(manifest_path),
    "sha256sums_file": str(sha_path),
    "native_receipt": manifest,
}, separators=(",", ":")))
PY
    else
      state="$(collect_status)"
      [[ "$state" == *'"transition":"READY"'* ]]
      printf '%s\n' "$state"
    fi
    ;;
  native-receipt)
    case "$TARGET" in
      SOCKET:*|OPENONLOAD:*|TCPDIRECT:*)
        driver="$("${SSH[@]}" "$TRADER_HOST" "basename \"\$(readlink /sys/bus/pci/devices/0000:03:00.0/driver)\"")"
        [[ "$driver" == sfc ]] || { echo "SFC native receipt requested while owner=$driver" >&2; exit 1; }
        receipt_target="${TARGET%%:*}"
        attest_sfc_receipts "$receipt_target"
        ;;
      DPDK:*)
        driver="$("${SSH[@]}" "$TRADER_HOST" "basename \"\$(readlink /sys/bus/pci/devices/0000:03:00.0/driver)\"")"
        [[ "$driver" == vfio-pci ]] || { echo "DPDK native receipt requested while owner=$driver" >&2; exit 1; }
        attest_dpdk_receipt DPDK
        ;;
      *) echo "invalid native receipt target: $TARGET" >&2; exit 2;;
    esac
    capture_native_receipt "$TARGET"
    ;;
  status)
    collect_status
    ;;
  verify)
    state="$(collect_status)"
    [[ "$state" == *'"transition":"READY"'* ]]
    "${SSH[@]}" "$TRADER_HOST" "set -eu; cd '$RUNTIME_ROOT'; sha256sum -c MANIFEST.sha256 >/dev/null; cd '$RUN_DIR'; sha256sum -c transport.deployed.sha256 >/dev/null"
    printf '%s\n' "$state"
    ;;
  stop)
    stop_dpdk_client
    stop_sfc_clients
    wait_hugepages_zero
    stop_remote_process "$OBSERVER_HOST" gateway flle_trading.gateway
    stop_remote_process "$EXCHANGE_HOST" exchange /flle-exchange
    systemctl stop "$CONTROLLER_UNIT" 2>/dev/null || true
    "${SSH[@]}" "$TRADER_HOST" "set -eu; test \"\$(basename \"\$(readlink /sys/bus/pci/devices/0000:03:00.0/driver)\")\" = sfc; ip -4 -o addr show dev ens64np1 | grep -Fq ' 20.1.1.2/24 '; test \"\$(cat /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages)\" = 0"
    echo '{"mode":"SFC","transition":"STOPPED","owner":"sfc","hardware_receipts":{}}'
    ;;
  *)
    echo "usage: $0 {preflight|deploy|start|sfc|dpdk|measure|attest|native-receipt|status|verify|stop} RUN_ID [TARGET [LOCAL_EXPORT_DIR]]" >&2
    exit 2
    ;;
esac
