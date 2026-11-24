#!/usr/bin/env bash
# Deploy from Low-Latency-Ops; runtime controller and device mutations run on .2.
set -Eeuo pipefail

ACTION="${1:-}"
RUN_ID="${2:-}"
TARGET="${3:-}"
EXPORT_DIR="${4:-}"
case "$RUN_ID" in
  ""|*[!A-Za-z0-9._-]*)
    echo "usage: $0 {preflight|deploy|start|sfc|dpdk|reset-paper|measure|attest|native-receipt|reuse-state|status|verify|stop} RUN_ID [TARGET [LOCAL_EXPORT_DIR]]" >&2
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
CONTROLLER_IP="${FLLE_CONTROLLER_IP:-10.1.1.2}"
RUN_DIR="/var/tmp/flle-trading-lab-$RUN_ID"
CONTROL_DIR="/var/tmp/flle-transport-controller-$RUN_ID"
CONTROLLER_UNIT="flle-transport-controller-${RUN_ID//_/-}"
RUNTIME_BLOB="$REPO_ROOT/artifacts/blobs/x2522/ch05-four-path/v13/flle-ch05-four-path-v13-x86_64-jammy-runtime.tgz"
RUNTIME_SHA="0e5d77fef1e4891b9f2220681c18162da6c605ea5619ea00e28022f23281dc00"
RUNTIME_ROOT="$RUN_DIR/transport-runtime/flle-ch05-four-path"
PREPARED_RUNTIME="/opt/flle/prepared-runtime/$RUNTIME_SHA"
DPDK_USER_REF_ROOT=3900000000
DPDK_USER_REF_SLOT_SPAN=1000000
SFC_SOCKET_USER_REF_ROOT=2100000000
SFC_ONLOAD_USER_REF_ROOT=2500000000
SFC_TCPDIRECT_USER_REF_ROOT=2900000000
SFC_USER_REF_SLOT_STRIDE=2000000
SFC_USER_REF_NAMESPACE_SPAN=100000
SSH=(ssh -o BatchMode=yes -o StrictHostKeyChecking=yes)
SCP=(scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes)

source "$SCRIPT_DIR/control-host.sh"

# Chapter 02 prepares the comparison client and selection marker. The ordinary
# Chapter 02–04 software client remains a separate executable.
posix_runtime_root() {
  "${SSH[@]}" "$TRADER_HOST" python3 \
    "$CONTROL_WORKSPACE/apps/flle-trading-lab/scripts/posix-qos-package.py" runtime-root "$RUN_DIR"
}

posix_clients_current() {
  local root
  root="$(posix_runtime_root)" || return 1
  "${SSH[@]}" "$TRADER_HOST" bash -s -- "$RUN_DIR" "$root" <<'REMOTE'
set -eu
for name in trader-socket trader-onload; do
  pid="$(cat "$1/$name.pid")"
  test "$(readlink -f "/proc/$pid/exe")" = "$2/bin/flle-trader"
  test "$(sha256sum "/proc/$pid/exe" | awk '{print $1}')" = "$(sha256sum "$2/bin/flle-trader" | awk '{print $1}')"
done
REMOTE
}

# Serialize every operation that can change this physical X2522 owner.  The
# lock is deliberately BDF-scoped rather than RUN-scoped: stale and current
# course runs must never mutate the same function concurrently.  The descriptor is
# inherited by ssh children, so a killed controller process group cannot leave a
# remote mutation running after a second switch has acquired the lock.
case "$ACTION" in
  reset-paper|baseline|start|sfc|dpdk|measure|stop|retire-snapshot-controller|feed-profile|boot|boot-enable)
    if [[ "${FLLE_TRANSPORT_LOCK_HELD:-0}" != 1 ]]; then
      exec 8>"/run/lock/flle-transport-0000_03_00_0.lock"
      flock -w 620 8 || {
        echo "timed out waiting for the transport ownership lock" >&2
        exit 75
      }
      export FLLE_TRANSPORT_LOCK_HELD=1
    fi
    ;;
esac

assert_runtime_blob() {
  test -s "$RUNTIME_BLOB"
  test "$(sha256sum "$RUNTIME_BLOB" | awk '{print $1}')" = "$RUNTIME_SHA"
}

verify_prepared_runtime_on_host() {
  local host="${1:?runtime target host is required}"
  "${SSH[@]}" "$host" bash -s -- "$PREPARED_RUNTIME" "$RUNTIME_SHA" <<'REMOTE'
set -Eeuo pipefail
prepared="$1"; expected="$2"
if ! test -d "$prepared/flle-ch05-four-path"; then
  echo 'DPDK/F-Stack 软件尚未准备；请先在 .111 运行准备 B2：' >&2
  echo 'bash Documents/newDoc/assets/02-trading-baseline/00b-dpdk-software-prep.sh' >&2
  exit 1
fi
printf '%s  %s\n' "$expected" "$prepared/runtime.tgz" | sha256sum -c - >/dev/null
(cd "$prepared/flle-ch05-four-path" && sha256sum -c MANIFEST.sha256 >/dev/null)
REMOTE
}

install_runtime_on_host() {
  local host="${1:?runtime target host is required}"
  "${SSH[@]}" "$host" bash -s -- \
    "$RUN_DIR" "$RUNTIME_ROOT" "$RUNTIME_SHA" "$PREPARED_RUNTIME" <<'REMOTE'
set -Eeuo pipefail
run_dir="$1"; runtime_root="$2"; runtime_sha="$3"; prepared="$4"
# Restore a session from B2's verified software; do not rebuild or reinstall it.
printf '%s  %s\n' "$runtime_sha" "$prepared/runtime.tgz" | sha256sum -c -
(cd "$prepared/flle-ch05-four-path" && sha256sum -c MANIFEST.sha256 >/dev/null)
cd "$run_dir"
cp "$prepared/runtime.tgz" transport-runtime.tgz
printf '%s  %s\n' "$runtime_sha" transport-runtime.tgz | sha256sum -c -
test ! -e transport-runtime || find transport-runtime -depth -delete
mkdir transport-runtime
cp -a "$prepared/flle-ch05-four-path" transport-runtime/
cd "$runtime_root"
sha256sum -c MANIFEST.sha256
test -x bin/flle-exchange
test -x bin/flle-book-checkpoint
test -x bin/flle-trader
test -x bin/flle-trader-tcpdirect
test -x bin/flle-trader-dpdk
test -x bin/x2522-dpdk-trader-remote.sh
REMOTE
}

verify_deployed_inputs() {
  assert_runtime_blob
  "${SSH[@]}" "$EXCHANGE_HOST" bash -s -- \
    "$RUN_DIR" "$RUNTIME_ROOT" "$RUNTIME_SHA" <<'REMOTE'
set -Eeuo pipefail
run_dir="$1"; runtime_root="$2"; runtime_sha="$3"
cd "$runtime_root"; sha256sum -c MANIFEST.sha256 >/dev/null
manifest_sha="$(sha256sum MANIFEST.sha256 | awk '{print $1}')"
cd "$run_dir"; sha256sum -c transport.deployed.sha256 >/dev/null
grep -Fxq "runtime_sha256=$runtime_sha" data-plane-input.receipt
grep -Fxq "runtime_manifest_sha256=$manifest_sha" data-plane-input.receipt
checkpoint_sha="$(sha256sum opening-book.checkpoint | awk '{print $1}')"
itch_sha="$(sha256sum AAPL_NVDA.itch | awk '{print $1}')"
grep -Fxq "opening_book_sha256=$checkpoint_sha" data-plane-input.receipt
grep -Fxq "itch_sha256=$itch_sha" data-plane-input.receipt
REMOTE
  "${SSH[@]}" "$TRADER_HOST" bash -s -- \
    "$RUN_DIR" "$RUNTIME_ROOT" "$RUNTIME_SHA" <<'REMOTE'
set -Eeuo pipefail
run_dir="$1"; runtime_root="$2"; runtime_sha="$3"
cd "$runtime_root"; sha256sum -c MANIFEST.sha256 >/dev/null
manifest_sha="$(sha256sum MANIFEST.sha256 | awk '{print $1}')"
cd "$run_dir"; sha256sum -c transport.deployed.sha256 >/dev/null
grep -Fxq "runtime_sha256=$runtime_sha" data-plane-input.receipt
grep -Fxq "runtime_manifest_sha256=$manifest_sha" data-plane-input.receipt
checkpoint_sha="$(sha256sum opening-book.checkpoint | awk '{print $1}')"
grep -Fxq "opening_book_sha256=$checkpoint_sha" data-plane-input.receipt
REMOTE
  "${SSH[@]}" "$OBSERVER_HOST" \
    "set -eu; cd '$RUN_DIR'; sha256sum -c source.sha256 >/dev/null"
  "${SSH[@]}" "$TRADER_HOST" "cd '$RUN_DIR' && sha256sum -c deployed.sha256 >/dev/null"
  echo "DEPLOYED_INPUTS_VERIFIED runtime_sha256=$RUNTIME_SHA"
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

exchange_playing_session() {
  python3 - "$EXCHANGE_HOST" <<'PY'
import json
import socket
import sys

host = sys.argv[1].split("@", 1)[-1]
with socket.create_connection((host, 48120), timeout=3) as connection:
    connection.sendall(b"STATE\n")
    payload = bytearray()
    while not payload.endswith(b"\n"):
        chunk = connection.recv(65536)
        if not chunk:
            break
        payload.extend(chunk)
state = json.loads(payload.decode("ascii"))
if state.get("status") != "ONLINE" or state.get("replay_status") != "PLAYING":
    raise SystemExit(f"Exchange replay is not PLAYING before formal run: {state}")
session = state.get("session")
if not isinstance(session, str) or not session:
    raise SystemExit("Exchange returned no stable session identity")
print(session)
PY
}

reconcile_exchange_playing() {
  local expected_session="${1:?expected Exchange session is required}"
  python3 - "$EXCHANGE_HOST" "$expected_session" <<'PY'
import json
import socket
import sys
import time

host = sys.argv[1].split("@", 1)[-1]
expected_session = sys.argv[2]

def command(line: str) -> dict:
    with socket.create_connection((host, 48120), timeout=2) as connection:
        connection.sendall((line + "\n").encode("ascii"))
        payload = bytearray()
        while not payload.endswith(b"\n"):
            chunk = connection.recv(65536)
            if not chunk:
                break
            payload.extend(chunk)
    value = json.loads(payload.decode("ascii"))
    if not isinstance(value, dict):
        raise RuntimeError("Exchange management response is not an object")
    return value

last = {}
last_error = None
for _ in range(80):
    try:
        last = command("STATE")
        if last.get("session") != expected_session:
            raise RuntimeError("Exchange session changed during outer recovery")
        if last.get("replay_status") == "PLAYING":
            print("EXCHANGE_REPLAY_RESTORED status=PLAYING")
            raise SystemExit(0)
        if last.get("replay_status") == "PAUSED":
            command("REPLAY|RESUME")
    except (OSError, ValueError, RuntimeError) as error:
        last_error = error
    time.sleep(0.05)
raise SystemExit(
    f"Exchange replay recovery failed: last={last!r} error={last_error!r}"
)
PY
}

wait_state() {
  local port="$1" required="$2" attempts="${3:-120}" reply=""
  case "$attempts" in ''|*[!0-9]*) return 2;; esac
  for _ in $(seq 1 "$attempts"); do
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
  shift 3
  "${SSH[@]}" "$host" bash -s -- "$RUN_DIR" "$name" "$expected" "$@" <<'REMOTE'
set -Eeuo pipefail
run_dir="$1"; name="$2"; expected="$3"; shift 3
pidfile="$run_dir/$name.pid"
identity="$run_dir/$name.identity"

assert_ports_absent() {
  local port listeners
  for port in "$@"; do
    listeners="$(ss -ltnpH "( sport = :$port )" 2>/dev/null || true)"
    test -z "$listeners" || {
      echo "$name left a listener on port $port: $listeners" >&2
      return 1
    }
  done
}

if ! test -s "$pidfile"; then
  assert_ports_absent "$@"
  test ! -e "$identity" || {
    echo "$name has an identity envelope but no pidfile" >&2
    exit 1
  }
  exit 0
fi
mapfile -t pid_lines <"$pidfile"
test "${#pid_lines[@]}" -eq 1
pid="${pid_lines[0]}"
case "$pid" in ''|*[!0-9]*) echo "invalid $name pid" >&2; exit 1;; esac

if ! test -r "/proc/$pid/cmdline"; then
  rm -f -- "$pidfile" "$identity"
  assert_ports_absent "$@"
  exit 0
fi
test -s "$identity" || {
  echo "refusing to signal $name without its identity envelope" >&2
  exit 1
}
IFS= read -r envelope <"$identity"
read -r pid_field start_field boot_field extra <<<"$envelope"
test -z "${extra:-}"
test "$pid_field" = "pid=$pid"
case "$start_field" in start_ticks=*) expected_start="${start_field#start_ticks=}";; *) exit 1;; esac
case "$boot_field" in boot_id=*) expected_boot="${boot_field#boot_id=}";; *) exit 1;; esac

# A new boot can reuse an old numeric PID for an unrelated system process.
# The old identity is dead; check listeners, discard only its records, never signal it.
if test "$expected_boot" != "$(cat /proc/sys/kernel/random/boot_id)"; then
  assert_ports_absent "$@"
  rm -f -- "$pidfile" "$identity"
  exit 0
fi

verify_identity() {
  local current_start current_boot command
  test -r "/proc/$pid/cmdline" || return 1
  current_start="$(awk '{print $22}' "/proc/$pid/stat")" || return 1
  current_boot="$(cat /proc/sys/kernel/random/boot_id)" || return 1
  command="$(tr '\0' ' ' <"/proc/$pid/cmdline")" || return 1
  test "$current_start" = "$expected_start" || return 1
  test "$current_boot" = "$expected_boot" || return 1
  case "$command" in *"$expected"*) return 0;; *) return 1;; esac
}

verify_identity || {
  echo "refusing mismatched or reused $name pid=$pid" >&2
  exit 1
}
kill -INT "$pid"
for _ in $(seq 1 40); do
  kill -0 "$pid" 2>/dev/null || break
  sleep 0.25
done
if kill -0 "$pid" 2>/dev/null; then
  verify_identity || {
    echo "refusing SIGKILL after $name identity changed" >&2
    exit 1
  }
  kill -KILL "$pid"
  for _ in $(seq 1 40); do
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.1
  done
fi
kill -0 "$pid" 2>/dev/null && {
  echo "$name pid=$pid survived shutdown" >&2
  exit 1
}
assert_ports_absent "$@"
rm -f -- "$pidfile" "$identity"
REMOTE
}

start_remote_process() {
  local host="$1" name="$2" command="$3" existing
  existing="$("${SSH[@]}" "$host" python3 - "$RUN_DIR" "$name" <<'PYCODE'
from pathlib import Path
import sys

run, name = Path(sys.argv[1]), sys.argv[2]
pidfile, envelope = run / (name + '.pid'), run / (name + '.identity')
if pidfile.exists():
    pid = int(pidfile.read_text().strip())
    if pid <= 1:
        raise SystemExit('invalid process pid')
    proc = Path('/proc') / str(pid)
    if proc.exists():
        fields = dict(x.split('=', 1) for x in envelope.read_text().split())
        if fields.get('pid') != str(pid):
            raise SystemExit('process identity pid mismatch')
        boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        if not fields.get('boot_id'):
            raise SystemExit('process identity missing boot ID')
        if fields['boot_id'] == boot:
            ticks = (proc / 'stat').read_text().rsplit(')', 1)[1].split()[19]
            if fields.get('start_ticks') != ticks:
                raise SystemExit('refusing reused process pid in the same boot')
            print('RUNNING')
            raise SystemExit(0)
    pidfile.unlink()
    envelope.unlink(missing_ok=True)
elif envelope.exists():
    raise SystemExit('process identity exists without pidfile')
print('STOPPED')
PYCODE
)" || return 1
  if test "$existing" = RUNNING; then echo "$name already running"; return; fi
  "${SSH[@]}" "$host" "set -eu; cd '$RUN_DIR'; nohup $command </dev/null >'$name.log' 2>&1 & pid=\$!; start=\$(awk '{print \$22}' /proc/\$pid/stat); boot=\$(cat /proc/sys/kernel/random/boot_id); printf '%s\n' \"\$pid\" >'$name.pid.tmp'; printf 'pid=%s start_ticks=%s boot_id=%s\n' \"\$pid\" \"\$start\" \"\$boot\" >'$name.identity.tmp'; mv '$name.pid.tmp' '$name.pid'; mv '$name.identity.tmp' '$name.identity'"
}

wait_remote_listener() {
  local host="$1" name="$2" expected="$3" port="$4"
  "${SSH[@]}" "$host" bash -s -- "$RUN_DIR" "$name" "$expected" "$port" <<'REMOTE'
set -Eeuo pipefail
run="$1"; name="$2"; expected="$3"; port="$4"
cd "$run"
IFS= read -r pid <"$name.pid"
read -r pid_field start_field boot_field extra <"$name.identity"
case "$pid" in ''|*[!0-9]*) exit 1;; esac
test -z "${extra:-}"
test "$pid_field" = "pid=$pid"
case "$start_field" in start_ticks=*) start="${start_field#start_ticks=}";; *) exit 1;; esac
case "$boot_field" in boot_id=*) boot="${boot_field#boot_id=}";; *) exit 1;; esac
same_process() {
  test "$(cat /proc/sys/kernel/random/boot_id)" = "$boot" &&
    test "$(awk '{print $22}' "/proc/$pid/stat" 2>/dev/null)" = "$start"
}
for _ in $(seq 1 80); do
  same_process || { echo "$name exited or changed identity pid=$pid" >&2; exit 1; }
  # nohup/taskset/Onload may still be executing their launcher. An exec keeps
  # PID/start time, but cmdline can temporarily be empty or name the wrapper.
  command="$(tr '\0' ' ' <"/proc/$pid/cmdline" 2>/dev/null || true)"
  case "$command" in
    *"$expected"*)
      listeners="$(ss -ltnpH "( sport = :$port )" 2>/dev/null || true)"
      case "$listeners" in *"pid=$pid,"*) same_process && exit 0;; esac
      ;;
  esac
  sleep 0.25
done
tail -n 30 "$name.log" >&2 || true
printf '%s did not become %s and own port %s; pid=%s command=%s\n' \
  "$name" "$expected" "$port" "$pid" "$command" >&2
exit 1
REMOTE
}

stop_foreign_course_listener() {
  local host="$1" port="$2" expected="$3"
  "${SSH[@]}" "$host" bash -s -- "$RUN_DIR" "$port" "$expected" <<'REMOTE'
set -Eeuo pipefail
run_dir="$1"; port="$2"; expected="$3"
listener="$(ss -ltnpH "( sport = :$port )" 2>/dev/null || true)"
test -n "$listener" || exit 0
mapfile -t pids < <(
  sed -n 's/.*pid=\([0-9][0-9]*\).*/\1/p' <<<"$listener" | sort -u
)
test "${#pids[@]}" -eq 1
pid="${pids[0]}"
case "$pid" in ''|*[!0-9]*) exit 1;; esac
test -r "/proc/$pid/cmdline"
command="$(tr '\0' ' ' <"/proc/$pid/cmdline")"
case "$command" in
  *"$run_dir"*) exit 0;;
esac
case "$command" in *flle-trading-lab-*) ;; *)
  printf 'port %s belongs to an unrecognized process: %s\n' \
    "$port" "$command" >&2
  exit 1;;
esac
case "$command" in *"$expected"*) ;; *)
  printf 'port %s belongs to an unrecognized process: %s\n' \
    "$port" "$command" >&2
  exit 1;;
esac
start_ticks="$(awk '{print $22}' "/proc/$pid/stat")"
case "$start_ticks" in ''|*[!0-9]*) exit 1;; esac

# Re-read the listener, start time and command immediately before signalling.
# A recycled PID must never inherit permission from the process inspected above.
current_listener="$(ss -ltnpH "( sport = :$port )" 2>/dev/null || true)"
case "$current_listener" in *"pid=$pid,"*) ;; *) exit 1;; esac
test "$(awk '{print $22}' "/proc/$pid/stat")" = "$start_ticks"
test "$(tr '\0' ' ' <"/proc/$pid/cmdline")" = "$command"
kill -INT "$pid"
for _ in $(seq 1 40); do
  kill -0 "$pid" 2>/dev/null || exit 0
  sleep 0.25
done
echo "recognized course listener pid=$pid did not stop" >&2
exit 1
REMOTE
}

wait_hugepages_zero() {
  "${SSH[@]}" "$TRADER_HOST" "set -eu; for _ in \$(seq 1 60); do sysctl -w vm.nr_hugepages=0 >/dev/null; test \"\$(cat /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages)\" = 0 && exit 0; sleep 1; done; exit 1"
}

stop_sfc_clients() {
  stop_remote_process "$TRADER_HOST" trader-tcpdirect /flle-trader-tcpdirect 48124
  stop_remote_process "$TRADER_HOST" trader-onload /flle-trader 48123
  stop_remote_process "$TRADER_HOST" trader-socket /flle-trader 48122
  "${SSH[@]}" "$TRADER_HOST" "test ! -d '$RUN_DIR/active-receipts' || rm -f -- '$RUN_DIR/active-receipts/socket' '$RUN_DIR/active-receipts/onload' '$RUN_DIR/active-receipts/tcpdirect'"
}

stop_dpdk_client() {
  "${SSH[@]}" "$TRADER_HOST" bash -s -- "$RUN_DIR" "$RUNTIME_ROOT" <<'REMOTE'
set -Eeuo pipefail
run_dir="$1"; runtime_root="$2"
test -d "$run_dir" || exit 0
stop_file="$run_dir/dpdk.stop"
pid_file="$run_dir/trader-dpdk-gate.pid"
session_dir="$run_dir/dpdk-session"
gate_receipt="$session_dir/gate-exit.receipt"
trader_receipt="$session_dir/trader-exit.receipt"
stop_gate_failure() {
  rc=$?; failed_command="$BASH_COMMAND"; failed_line="${BASH_LINENO[0]}"
  trap - ERR
  printf 'DPDK_STOP_HARD_GATE_FAILED rc=%s line=%s command=%q\n' \
    "$rc" "$failed_line" "$failed_command" >&2
  exit "$rc"
}
trap stop_gate_failure ERR
touch "$stop_file"

find_gate_pid() {
  local command expected proc pid
  local -a candidates=()
  if test -s "$pid_file"; then
    mapfile -t pid_lines <"$pid_file"
    test "${#pid_lines[@]}" -eq 1
    pid="${pid_lines[0]}"
    case "$pid" in ''|*[!0-9]*) return 2;; esac
    if test -r "/proc/$pid/cmdline"; then printf '%s\n' "$pid"; return 0; fi
  fi
  expected="$runtime_root/bin/x2522-dpdk-trader-remote.sh $runtime_root/etc/f-stack-x2522.ini $runtime_root/bin/flle-trader-dpdk $session_dir $stop_file"
  for proc in /proc/[0-9]*; do
    test -r "$proc/cmdline" || continue
    command="$(tr '\0' ' ' 2>/dev/null <"$proc/cmdline" || true)"
    test -n "$command" || continue
    case "$command" in
      *"$expected"*) candidates+=("${proc##*/}");;
    esac
  done
  test "${#candidates[@]}" -le 1 || {
    echo "multiple exact DPDK ownership wrappers found: ${candidates[*]}" >&2
    return 2
  }
  test "${#candidates[@]}" -eq 1 || return 1
  printf '%s\n' "${candidates[0]}"
}

verify_gate_identity() {
  local envelope pid_field start_field boot_field token_field extra
  local expected_start expected_boot current_start current_boot command expected
  test -s "$session_dir/gate.identity" || return 1
  IFS= read -r envelope <"$session_dir/gate.identity" || return 1
  read -r pid_field start_field boot_field token_field extra <<<"$envelope" \
    || return 1
  test -z "${extra:-}" || return 1
  test "$pid_field" = "pid=$pid" || return 1
  case "$start_field" in
    start_ticks=*) expected_start="${start_field#start_ticks=}";;
    *) return 1;;
  esac
  case "$boot_field" in
    boot_id=*) expected_boot="${boot_field#boot_id=}";;
    *) return 1;;
  esac
  case "$token_field" in lease_token=*) ;; *) return 1;; esac
  test -r "/proc/$pid/cmdline" || return 1
  current_start="$(awk '{print $22}' "/proc/$pid/stat")" || return 1
  current_boot="$(cat /proc/sys/kernel/random/boot_id)" || return 1
  command="$(tr '\0' ' ' <"/proc/$pid/cmdline")" || return 1
  expected="$runtime_root/bin/x2522-dpdk-trader-remote.sh $runtime_root/etc/f-stack-x2522.ini $runtime_root/bin/flle-trader-dpdk $session_dir $stop_file"
  test "$current_start" = "$expected_start" || return 1
  test "$current_boot" = "$expected_boot" || return 1
  case "$command" in *"$expected"*) return 0;; *) return 1;; esac
}

pid=""
for _ in $(seq 1 40); do
  if pid="$(find_gate_pid)"; then break; else rc=$?; fi
  test "$rc" -eq 1 || exit "$rc"
  sleep 0.1
done
if test -n "$pid"; then
  verify_gate_identity || {
    echo 'refusing mismatched or reused DPDK gate identity' >&2
    exit 1
  }
  command="$(tr '\0' ' ' <"/proc/$pid/cmdline")"
  expected="$runtime_root/bin/x2522-dpdk-trader-remote.sh $runtime_root/etc/f-stack-x2522.ini $runtime_root/bin/flle-trader-dpdk $session_dir $stop_file"
  case "$command" in *"$expected"*) ;; *) echo 'refusing mismatched DPDK gate pid' >&2; exit 1;; esac
  test "$(awk '/^Cpus_allowed_list:/ {print $2}' "/proc/$pid/status")" = 0
  for _ in $(seq 1 240); do
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.25
  done
  if kill -0 "$pid" 2>/dev/null; then
    verify_gate_identity || {
      echo 'refusing to signal a changed DPDK gate identity' >&2
      exit 1
    }
    kill -INT "$pid"
    for _ in $(seq 1 400); do
      kill -0 "$pid" 2>/dev/null || break
      sleep 0.25
    done
    kill -0 "$pid" 2>/dev/null && {
      echo 'DPDK gate did not stop after SIGINT; invoking independent recovery' >&2
    }
  fi
fi
driver="$(basename "$(readlink /sys/bus/pci/devices/0000:03:00.0/driver)" 2>/dev/null || true)"
orphan_pid=""
for process in /proc/[0-9]*; do
  if test "$(readlink -f "$process/exe" 2>/dev/null || true)" = \
      "$runtime_root/bin/flle-trader-dpdk"; then
    test -z "$orphan_pid" || {
      echo "multiple orphan DPDK traders found" >&2
      exit 1
    }
    orphan_pid="${process##*/}"
  fi
done
# An SFC-only run has no DPDK ownership session.  In that case this helper
# only proves that no DPDK process survived; the caller owns the later
# hugepage transition.  Requiring zero hugepages here would make a normal
# SFC stop fail merely because its three clients legitimately use 128 pages.
if test -z "$pid" && test -z "$orphan_pid" && \
    test ! -s "$session_dir/lease-start.receipt" && \
    test ! -s "$session_dir/gate-start.receipt"; then
  test "$(basename "$(readlink /sys/bus/pci/devices/0000:03:00.0/driver)")" = sfc
  ip -4 -o addr show dev ens64np1 | grep -Fq ' 20.1.1.2/24 '
  rm -f "$pid_file"
  exit 0
fi
if test -s "$session_dir/lease.token"; then
  test -s "$session_dir/lease.token"
  mapfile -t token_lines <"$session_dir/lease.token"
  test "${#token_lines[@]}" -eq 1
  lease_token="${token_lines[0]}"
  case "$lease_token" in ''|*[!A-Za-z0-9._-]*) exit 1;; esac
  "$runtime_root/bin/x2522-dpdk-trader-remote.sh" --recover-only \
    "$runtime_root" "$session_dir" "$stop_file" "$pid_file" "$lease_token"
fi

if test -s "$session_dir/lease-recovery.receipt"; then
  test -s "$session_dir/lease-start.receipt"
  expected_token="$(sed -n 's/^lease_token=//p' "$session_dir/lease-start.receipt")"
  test "$(grep -Fxc "lease_token=$expected_token" \
    "$session_dir/lease-recovery.receipt")" -eq 1
  grep -Fxq 'recovery=PASS' "$session_dir/lease-recovery.receipt"
  grep -Fxq 'ownership_state=CONSUMED' "$session_dir/lease-recovery.receipt"
  echo 'DPDK_STOP_RECEIPT independent_lease_recovery=PASS restore=PASS'
elif test -s "$gate_receipt"; then
  grep -Fxq 'restore_state=PASS' "$gate_receipt"
  grep -Fxq 'ownership_state=CONSUMED' "$gate_receipt"
  wrapper_status="$(sed -n 's/^wrapper_exit_status=//p' "$gate_receipt")"
  case "$wrapper_status" in ''|*[!0-9]*) exit 1;; esac
  if test "$wrapper_status" -eq 0; then
    test -s "$trader_receipt" || { echo 'DPDK trader exit receipt missing' >&2; exit 1; }
    grep -Fxq 'trader_exit_status=0' "$trader_receipt"
    grep -Fxq 'trader_termination=SIGINT' "$trader_receipt"
    grep -Fxq 'cleanup_mode=PROCESS_EXIT_BYPASS_INCOMPLETE_FSTACK_CLEANUP' "$trader_receipt"
    grep -Fxq 'shutdown_rc=0' "$trader_receipt"
    grep -Fxq 'peer_eof=1' "$trader_receipt"
    echo 'DPDK_STOP_RECEIPT wrapper=0 trader=0 termination=SIGINT cleanup=process-exit peer_eof=1 independent_lease=disarmed restore=PASS'
  else
    printf 'DPDK_STOP_RECEIPT failed_gate_status=%s independent_lease=disarmed restore=PASS\n' \
      "$wrapper_status"
  fi
elif test -s "$session_dir/gate-start.receipt"; then
  driver="$(basename "$(readlink /sys/bus/pci/devices/0000:03:00.0/driver)")"
  test "$driver" = sfc
  ip -4 -o addr show dev ens64np1 | grep -Fq ' 20.1.1.2/24 '
  test "$(cat /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages)" = 0
  echo 'DPDK_STOP_RECEIPT launch_aborted_before_device_mutation=1 restore=PASS'
fi
test "$(basename "$(readlink /sys/bus/pci/devices/0000:03:00.0/driver)")" = sfc
mapfile -t final_ipv4 < <(ip -4 -o addr show dev ens64np1 scope global)
test "${#final_ipv4[@]}" -eq 1
test "$(awk '{print $4}' <<<"${final_ipv4[0]}")" = 20.1.1.2/24
pages=-1
for _ in $(seq 1 400); do
  sysctl -w vm.nr_hugepages=0 >/dev/null
  pages="$(cat /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages)"
  test "$pages" = 0 && break
  sleep 0.1
done
test "$pages" = 0 || {
  free_pages="$(cat /sys/kernel/mm/hugepages/hugepages-2048kB/free_hugepages)"
  reserved_pages="$(cat /sys/kernel/mm/hugepages/hugepages-2048kB/resv_hugepages)"
  surplus_pages="$(cat /sys/kernel/mm/hugepages/hugepages-2048kB/surplus_hugepages)"
  printf 'DPDK hugepages remained allocated after client stop: total=%s free=%s reserved=%s surplus=%s\n' \
    "$pages" "$free_pages" "$reserved_pages" "$surplus_pages" >&2
  exit 1
}
for process in /proc/[0-9]*; do
  test "$(readlink -f "$process/exe" 2>/dev/null || true)" != \
    "$runtime_root/bin/flle-trader-dpdk"
  test -r "$process/cmdline" || continue
  command="$(tr '\0' ' ' 2>/dev/null <"$process/cmdline")" || continue
  case "$command" in
    *"$runtime_root/bin/x2522-dpdk-trader-remote.sh"*"$session_dir"*)
      echo "DPDK ownership wrapper survived cleanup: ${process##*/}" >&2
      exit 1;;
  esac
done
if test -s "$session_dir/lease-start.receipt"; then
  lease_unit="$(sed -n 's/^lease_unit=//p' "$session_dir/lease-start.receipt")"
  [[ "$lease_unit" =~ ^flle-x2522-lease-[0-9a-f]{20}$ ]]
  expected_token="$(sed -n 's/^lease_token=//p' "$session_dir/lease-start.receipt")"
  test -n "$expected_token"
  case "$expected_token" in ''|*[!A-Za-z0-9._-]*) exit 1;; esac
  test "$(grep -Fxc "lease_token=$expected_token" \
    "$session_dir/gate-start.receipt")" -eq 1
  if test -s "$gate_receipt"; then
    test "$(grep -Fxc "lease_token=$expected_token" "$gate_receipt")" -eq 1
  fi
  test ! -e "$session_dir/lease.token"
  test "$(<"$session_dir/lease.token.consumed")" = "$expected_token"
  grep -Fxq 'state=CONSUMED' "$session_dir/ownership.state"
  grep -Fxq "lease_token=$expected_token" "$session_dir/ownership.state"
  systemctl stop "$lease_unit.timer" "$lease_unit.service" >/dev/null 2>&1 \
    || true
  for _ in $(seq 1 80); do
    timer_load="$(systemctl show -p LoadState --value "$lease_unit.timer" \
      2>/dev/null || true)"
    service_load="$(systemctl show -p LoadState --value "$lease_unit.service" \
      2>/dev/null || true)"
    timer_state="$(systemctl show -p ActiveState --value "$lease_unit.timer" \
      2>/dev/null || true)"
    service_state="$(systemctl show -p ActiveState --value "$lease_unit.service" \
      2>/dev/null || true)"
    { test "$timer_load" = not-found || test "$timer_state" = inactive; } && \
      { test "$service_load" = not-found || test "$service_state" = inactive; } \
      && break
    sleep 0.25
  done
  test "$timer_load" = not-found || test "$timer_state" = inactive
  test "$service_load" = not-found || test "$service_state" = inactive
  mount_baseline="$(<"$session_dir/hugetlbfs.mount.baseline")"
  mount_final="$(findmnt -rn --mountpoint /dev/hugepages \
    -o FSTYPE,TARGET,SOURCE,OPTIONS 2>/dev/null || true)"
  test "${mount_final:-ABSENT}" = "$mount_baseline"
  if test -s "$session_dir/lease-recovery.receipt"; then
    cmp -s "$session_dir/hugetlbfs-files.baseline" \
      "$session_dir/hugetlbfs-files.recovery-final"
  else
    cmp -s "$session_dir/hugetlbfs-files.baseline" \
      "$session_dir/hugetlbfs-files.final"
  fi
fi
exec 8>"/run/lock/flle-x2522-0000_03_00_0.lock"
# The wrapper writes PASS before its process has necessarily released the
# descriptor.  Give that final close a short bounded grace period.
flock -w 30 8 || {
  echo 'timed out waiting for the DPDK wrapper to release the X2522 lock' >&2
  exit 1
}
rm -f "$pid_file"
REMOTE
  "${SSH[@]}" "$TRADER_HOST" "set -eu; for _ in \$(seq 1 40); do listener=\$(ss -ltnpH '( sport = :48125 )' 2>/dev/null || true); test -z \"\$listener\" && break; sleep 0.1; done; test -z \"\${listener:-}\" || { echo 'DPDK management listener remained LISTEN after client stop:' >&2; printf '%s\n' \"\$listener\" >&2; exit 1; }; echo 'DPDK_MANAGEMENT_LISTENER_CLOSED listen=0'"
  stop_dpdk_prime
  "${SSH[@]}" "$EXCHANGE_HOST" "set -eu; for _ in \$(seq 1 40); do endpoint=\$(ss -ntH state established '( sport = :43120 )' | grep -F '20.1.1.2:' || true); test -z \"\$endpoint\" && break; sleep 0.1; done; test -z \"\${endpoint:-}\" || { echo 'DPDK Exchange endpoint remained ESTABLISHED after client stop:' >&2; printf '%s\n' \"\$endpoint\" >&2; exit 1; }; echo 'DPDK_EXCHANGE_ENDPOINT_CLOSED established=0'"
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
  local envelope pid_field start_field boot_field extra expected_start expected_boot
  local current_boot identity="$run_dir/$name.identity"
  test -s "$run_dir/$name.pid" || return 1
  test -s "$identity" || return 1
  mapfile -t pid_lines <"$run_dir/$name.pid" || return 1
  test "${#pid_lines[@]}" -eq 1 || return 1
  pid="${pid_lines[0]}"
  case "$pid" in ''|*[!0-9]*) return 1;; esac
  IFS= read -r envelope <"$identity" || return 1
  read -r pid_field start_field boot_field extra <<<"$envelope" || return 1
  test -z "${extra:-}" || return 1
  test "$pid_field" = "pid=$pid" || return 1
  case "$start_field" in
    start_ticks=*) expected_start="${start_field#start_ticks=}";;
    *) return 1;;
  esac
  case "$boot_field" in
    boot_id=*) expected_boot="${boot_field#boot_id=}";;
    *) return 1;;
  esac
  test -r "/proc/$pid/cmdline" || return 1
  start_ticks="$(awk '{print $22}' "/proc/$pid/stat")" || return 1
  current_boot="$(cat /proc/sys/kernel/random/boot_id)" || return 1
  command="$(tr '\0' ' ' <"/proc/$pid/cmdline")" || return 1
  test "$start_ticks" = "$expected_start" || return 1
  test "$current_boot" = "$expected_boot" || return 1
  case "$command" in *"$expected"*) ;; *) return 1;; esac
  listeners="$(ss -ltnpH "( sport = :$port )" 2>/dev/null || true)"
  case "$listeners" in *"pid=$pid,"*) ;; *) return 1;; esac
  printf '%s %s\n' "$pid" "$start_ticks"
}

socket_identity="$(process_identity trader-socket flle-trader 48122)" || exit 1
onload_identity="$(process_identity trader-onload flle-trader 48123)" || exit 1
tcpdirect_identity="$(process_identity trader-tcpdirect flle-trader-tcpdirect 48124)" || exit 1
read -r socket_pid socket_start socket_extra <<<"$socket_identity"
read -r onload_pid onload_start onload_extra <<<"$onload_identity"
read -r tcpdirect_pid tcpdirect_start tcpdirect_extra <<<"$tcpdirect_identity"
test -z "${socket_extra:-}"
test -z "${onload_extra:-}"
test -z "${tcpdirect_extra:-}"

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
  "${SSH[@]}" "$TRADER_HOST" bash -s -- \
    "$RUN_DIR" "$RUNTIME_ROOT" "$target" <<'REMOTE'
set -Eeuo pipefail
run_dir="$1"; runtime_root="$2"; target="$3"
receipt_dir="$run_dir/active-receipts"
session_dir="$run_dir/dpdk-session"
mkdir -p "$receipt_dir"
mapfile -t pid_lines <"$session_dir/trader.pid"
test "${#pid_lines[@]}" -eq 1
pid="${pid_lines[0]}"
case "$pid" in ''|*[!0-9]*) exit 1;; esac
test -s "$session_dir/trader.identity"
IFS= read -r envelope <"$session_dir/trader.identity"
read -r pid_field start_field boot_field token_field extra <<<"$envelope"
test -z "${extra:-}"
test "$pid_field" = "pid=$pid"
case "$start_field" in
  start_ticks=*) expected_start="${start_field#start_ticks=}";;
  *) exit 1;;
esac
case "$boot_field" in
  boot_id=*) expected_boot="${boot_field#boot_id=}";;
  *) exit 1;;
esac
case "$token_field" in
  lease_token=*) lease_token="${token_field#lease_token=}";;
  *) exit 1;;
esac
test -n "$lease_token"
test "$(<"$session_dir/lease.token")" = "$lease_token"
grep -Fxq 'state=OWNED' "$session_dir/ownership.state"
grep -Fxq "lease_token=$lease_token" "$session_dir/ownership.state"
test -r "/proc/$pid/cmdline"
start_ticks="$(awk '{print $22}' "/proc/$pid/stat")"
case "$start_ticks" in ''|*[!0-9]*) exit 1;; esac
boot_id="$(cat /proc/sys/kernel/random/boot_id)"
test "$start_ticks" = "$expected_start"
test "$boot_id" = "$expected_boot"
binary="$runtime_root/bin/flle-trader-dpdk"
test "$(readlink -f "/proc/$pid/exe")" = "$(readlink -f "$binary")"
mapfile -d '' -t observed_argv <"/proc/$pid/cmdline"
expected_argv=(
  "$binary"
  --conf "$session_dir/f-stack.effective.ini"
  --proc-type=primary
  --proc-id=0
)
test "${#observed_argv[@]}" -eq "${#expected_argv[@]}"
for index in "${!expected_argv[@]}"; do
  test "${observed_argv[$index]}" = "${expected_argv[$index]}"
done
listeners="$(ss -ltnpH '( sport = :48125 )' 2>/dev/null || true)"
case "$listeners" in *"pid=$pid,"*) ;; *) exit 1;; esac
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
grep -Eq 'Probe PCI driver: net_sfc_efx .*device: 0000:03:00[.]0 ' \
  "$run_dir/dpdk-session/fstack.log"
grep -Eq 'sfc_efx 0000:03:00[.]0 .*running FW variant is ultra-low-latency' \
  "$run_dir/dpdk-session/fstack.log"
attested_ns="$(python3 -c 'import time; print(time.monotonic_ns())')"
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
  local exchange_stage=NONE
  if test "$target" = DPDK; then
    verify_exchange_runtime >/dev/null
    local exchange_final exchange_cell_stage
    exchange_final="$RUN_DIR/native-exchange-receipts/$cell/$phase"
    exchange_cell_stage="$RUN_DIR/native-exchange-staging/$cell/$phase"
    "${SSH[@]}" "$EXCHANGE_HOST" bash -s -- \
      "$RUN_DIR" "$RUNTIME_ROOT" "$exchange_final" \
      "$TELEMETRY_HOST" <<'REMOTE'
set -Eeuo pipefail
run_dir="$1"; runtime_root="$2"; final="$3"; telemetry_host="$4"
tmp="${final}.tmp.$BASHPID"
case "$final" in "$run_dir"/native-exchange-receipts/*) ;; *) exit 2;; esac
test ! -e "$final"
mkdir -p "$(dirname "$final")" "$tmp"
cleanup(){ test ! -e "$tmp" || find "$tmp" -depth -delete; }
trap cleanup EXIT
mapfile -t pid_lines <"$run_dir/exchange.pid"
test "${#pid_lines[@]}" -eq 1
pid="${pid_lines[0]}"
case "$pid" in ''|*[!0-9]*) exit 1;; esac
test -r "/proc/$pid/cmdline"
command="$(tr '\0' ' ' <"/proc/$pid/cmdline")"
exe_path="$(readlink -f "/proc/$pid/exe")"
exchange_contract=FROZEN_V13
start_mode=UNICAST
manifest="$runtime_root/MANIFEST.sha256"; manifest_key=bin/flle-exchange
if test -f "$run_dir/deployed.sha256"; then
  exchange_contract=NATIVE_AB_V1; start_mode=MULTICAST_A
  manifest="$run_dir/deployed.sha256"; manifest_key=flle-exchange
  test "$exe_path" = "$run_dir/flle-exchange"
  (cd "$run_dir" && sha256sum -c deployed.sha256 >/dev/null)
else
  test "$exe_path" = "$runtime_root/bin/flle-exchange"
fi
mapfile -d '' -t observed_argv <"/proc/$pid/cmdline"
expected_argv=(
  "$exe_path"
  --telemetry-host "$telemetry_host"
  --replay-file "$run_dir/AAPL_NVDA.itch"
  --book-checkpoint "$run_dir/opening-book.checkpoint"
  --market-date 2026-06-12
  --market-mode "$start_mode"
  --replay-speed 1
)
test "${#observed_argv[@]}" -eq "${#expected_argv[@]}"
for index in "${!expected_argv[@]}"; do
  test "${observed_argv[$index]}" = "${expected_argv[$index]}"
done
exe_sha256="$(sha256sum "$exe_path" | awk '{print $1}')"
mapfile -t manifest_matches < <(awk -v key="$manifest_key" '$2==key {print $0}' "$manifest")
test "${#manifest_matches[@]}" -eq 1
manifest_entry="${manifest_matches[0]}"
exe_manifest_sha256="${manifest_entry%% *}"
test -n "$exe_manifest_sha256"; test "$exe_sha256" = "$exe_manifest_sha256"
checkpoint_path="$run_dir/opening-book.checkpoint"
checkpoint_sha256="$(sha256sum "$checkpoint_path" | awk '{print $1}')"
itch_sha256="$(sha256sum "$run_dir/AAPL_NVDA.itch" | awk '{print $1}')"
generator_sha256="$(sha256sum "$runtime_root/bin/flle-book-checkpoint" | awk '{print $1}')"
generator_manifest_sha256="$(awk '$2=="bin/flle-book-checkpoint" {print $1}' "$runtime_root/MANIFEST.sha256")"
test -n "$generator_manifest_sha256"
test "$generator_sha256" = "$generator_manifest_sha256"
grep -Fxq "opening_book_sha256=$checkpoint_sha256" "$run_dir/data-plane-input.receipt"
grep -Fxq "checkpoint_generator_sha256=$generator_sha256" "$run_dir/data-plane-input.receipt"
grep -Fxq "itch_sha256=$itch_sha256" "$run_dir/data-plane-input.receipt"
start_ticks="$(awk '{print $22}' "/proc/$pid/stat")"
case "$start_ticks" in ''|*[!0-9]*) exit 1;; esac
boot_id="$(cat /proc/sys/kernel/random/boot_id)"
mapfile -t listener_matches < <(
  ss -ltnpH '( sport = :43120 )' 2>/dev/null |
    awk -v target="$pid" '
      index($0, "pid=" target ",") > 0 {
        for (field = 1; field <= NF; ++field) {
          if ($field == "20.1.1.1:43120") { print; next }
        }
      }
    '
)
test "${#listener_matches[@]}" -ge 1
ss -tnpH state established >"$tmp/exchange-ss-established.txt"
awk -v target="$pid" '
  $3 == "20.1.1.1:43120" &&
  $4 ~ /^20[.]1[.]1[.]2:[0-9]+$/ &&
  index($0, "pid=" target ",") > 0 { ++matches }
  END { exit(matches >= 1 ? 0 : 1) }
' "$tmp/exchange-ss-established.txt"
{
  printf 'pid=%s\nstart_ticks=%s\nboot_id=%s\ncmdline=%s\nexe_path=%s\nexe_sha256=%s\nexe_manifest_sha256=%s\ncheckpoint_sha256=%s\ncheckpoint_generator_sha256=%s\ncheckpoint_generator_manifest_sha256=%s\nitch_sha256=%s\nlistener_count=%s\n' \
    "$pid" "$start_ticks" "$boot_id" "$command" "$exe_path" \
    "$exe_sha256" "$exe_manifest_sha256" "$checkpoint_sha256" \
    "$generator_sha256" "$generator_manifest_sha256" "$itch_sha256" \
    "${#listener_matches[@]}"
  for index in "${!listener_matches[@]}"; do
    printf 'listener_ss_line_%s=%s\n' "$((index + 1))" \
      "${listener_matches[$index]}"
  done
  printf 'argv_count=%s\n' "${#observed_argv[@]}"
  for index in "${!observed_argv[@]}"; do
    printf 'argv_%02d=%s\n' "$index" "${observed_argv[$index]}"
  done
  printf 'exchange_contract=%s\nexchange_manifest_entry=%s\n' "$exchange_contract" "$manifest_entry"
} >"$tmp/exchange-process.txt"
mv "$tmp" "$final"
trap - EXIT
REMOTE
    "${SSH[@]}" "$TRADER_HOST" \
      "set -eu; test ! -e '$exchange_cell_stage'; mkdir -p '$exchange_cell_stage'"
    "${SCP[@]}" -3 \
      "$EXCHANGE_HOST:$exchange_final/exchange-process.txt" \
      "$EXCHANGE_HOST:$exchange_final/exchange-ss-established.txt" \
      "$TRADER_HOST:$exchange_cell_stage/"
    exchange_stage="$exchange_cell_stage"
  fi
  local client_runtime="$RUNTIME_ROOT"
  case "$target" in SOCKET|OPENONLOAD) client_runtime="$(posix_runtime_root)";; esac
  "${SSH[@]}" "$TRADER_HOST" bash -s -- \
    "$RUN_DIR" "$client_runtime" "$target" "$cell" "$phase" \
    "$exchange_stage" "$RUNTIME_ROOT" <<'REMOTE'
set -Eeuo pipefail
run_dir="$1"; runtime_root="$2"; target="$3"; cell="$4"; phase="$5"
exchange_stage="$6"; input_runtime_root="$7"
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
exe_path="$(readlink -f "/proc/$pid/exe")"
expected_exe_path="$(readlink -f "$runtime_root/bin/$expected")"
test "$exe_path" = "$expected_exe_path"
mapfile -d '' -t observed_argv <"/proc/$pid/cmdline"
test "${#observed_argv[@]}" -gt 0
test "${observed_argv[0]}" = "$exe_path"
exe_sha256="$(sha256sum -- "/proc/$pid/exe" | awk '{print $1}')"
mapfile -t exe_manifest_matches < <(
  awk -v expected="bin/$expected" '$2 == expected { print $1 }' \
    "$runtime_root/MANIFEST.sha256"
)
test "${#exe_manifest_matches[@]}" -eq 1
exe_manifest_sha256="${exe_manifest_matches[0]}"
grep -Eq '^[0-9a-f]{64}$' <<<"$exe_manifest_sha256"
test "$exe_sha256" = "$exe_manifest_sha256"
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
read -r user_ref_base user_ref_span order_tid management_tid bridge_tid \
  measurement_generation measurement_ready_samples < <(
  python3 -c 'import json,sys
s=json.load(sys.stdin); software=s["software_latency"]
values=(s["user_ref_base"], s["user_ref_span"],
        software["order_thread_tid"], software["management_thread_tid"],
        software.get("bridge_thread_tid", 0),
        s["measurement_latency"]["generation"],
        s["measurement_latency"]["ready_samples"])
if any(type(value) is not int or value < 0 for value in values):
    raise SystemExit("native STATE contains an invalid integer contract field")
print(*values)' <<<"$state"
)
test "$user_ref_base" -gt 0; test "$user_ref_span" -gt 0
test "$order_tid" -gt 0; test "$management_tid" -gt 0

case "$target" in
  SOCKET|OPENONLOAD|TCPDIRECT)
    case "$target" in
      SOCKET) management_port=48122; clordid_prefix=SOCK;;
      OPENONLOAD) management_port=48123; clordid_prefix=ONLD;;
      TCPDIRECT) management_port=48124; clordid_prefix=TCPD;;
    esac
    expected_argv=(
      "$exe_path"
      --role MANUAL
      --data-ip 20.1.1.2
      --exchange-data-ip 20.1.1.1
      --management-ip 10.1.1.2
      --telemetry-host 10.1.1.101
      --book-checkpoint "$run_dir/opening-book.checkpoint"
      --market-receiver 0
      --order-queue DEQUE_CV
      --lock-order-queue 1
      --order-cpu 2
      --management-cpu 3
      --management-port "$management_port"
      --user-ref-base "$user_ref_base"
      --user-ref-span "$user_ref_span"
      --clordid-prefix "$clordid_prefix"
      --order-transport-label "$label"
    )
    ;;
  DPDK)
    expected_argv=(
      "$exe_path"
      --conf "$run_dir/dpdk-session/f-stack.effective.ini"
      --proc-type=primary
      --proc-id=0
    )
    ;;
esac
test "${#observed_argv[@]}" -eq "${#expected_argv[@]}"
for index in "${!expected_argv[@]}"; do
  test "${observed_argv[$index]}" = "${expected_argv[$index]}"
done

mapfile -t management_listeners < <(
  ss -ltnpH "( sport = :$port )" 2>/dev/null |
    awk -v target="$pid" -v endpoint="10.1.1.2:$port" '
      index($0, "pid=" target ",") > 0 {
        for (field = 1; field <= NF; ++field) {
          if ($field == endpoint) { print; next }
        }
      }
    '
)
test "${#management_listeners[@]}" -eq 1

thread_snapshot="$tmp/thread-snapshot.txt"
python3 - "$pid" "$target" "$order_tid" "$management_tid" \
  "$bridge_tid" >"$thread_snapshot" <<'PY'
import sys
from pathlib import Path

pid = int(sys.argv[1])
target = sys.argv[2]
roles = [("order", int(sys.argv[3])), ("management", int(sys.argv[4]))]
if target == "DPDK":
    roles.append(("bridge", int(sys.argv[5])))

expected_affinity = {"order": "2", "management": "3", "bridge": "3"}
for role, tid in roles:
    if tid < 1:
        raise SystemExit(f"invalid {role} thread tid")
    status_path = Path(f"/proc/{pid}/task/{tid}/status")
    fields = {}
    for line in status_path.read_text(encoding="ascii").splitlines():
        if ":" in line:
            name, value = line.split(":", 1)
            fields[name] = value.strip()
    affinity = fields.get("Cpus_allowed_list", "")
    if affinity != expected_affinity[role]:
        raise SystemExit(
            f"{role} thread affinity mismatch: {affinity!r}"
        )
    print(f"thread_{role}_tid={tid}")
    print(f"thread_{role}_name={fields.get('Name', '')}")
    print(f"thread_{role}_cpus_allowed_list={affinity}")
PY

environment_snapshot="$tmp/environment-snapshot.txt"
python3 - "$pid" "$target" "$run_dir" "$user_ref_base" \
  "$user_ref_span" >"$environment_snapshot" <<'PY'
import sys
from pathlib import Path

pid = int(sys.argv[1])
target = sys.argv[2]
run_dir = sys.argv[3]
user_ref_base = sys.argv[4]
user_ref_span = sys.argv[5]
entries = {}
for item in Path(f"/proc/{pid}/environ").read_bytes().split(b"\0"):
    if not item:
        continue
    name, separator, value = item.partition(b"=")
    if not separator:
        raise SystemExit("process environment entry has no equals delimiter")
    decoded_name = name.decode("ascii")
    if decoded_name in entries:
        raise SystemExit(f"duplicate process environment name: {decoded_name}")
    entries[decoded_name] = value.decode("utf-8")

if target == "DPDK":
    lease_token = (
        Path(run_dir) / "dpdk-session/lease.token"
    ).read_text(encoding="ascii").strip()
    if not lease_token or any(
        character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
        for character in lease_token
    ):
        raise SystemExit("DPDK lease token is invalid")
    required = {
        "FLLE_DPDK_GATE_PID_FILE": f"{run_dir}/trader-dpdk-gate.pid",
        "FLLE_DPDK_LEASE_TOKEN": lease_token,
        "FLLE_DPDK_DEADMAN": "1800",
        "FLLE_DPDK_USER_REF_BASE": user_ref_base,
        "FLLE_DPDK_USER_REF_SPAN": user_ref_span,
        "FLLE_MANAGEMENT_PORT": "48125",
        "FLLE_TELEMETRY_HOST": "10.1.1.101",
        "FLLE_DPDK_HELPER_CPU": "3",
        "FLLE_DPDK_HEARTBEAT": "0",
    }
    for name, expected in required.items():
        if entries.get(name) != expected:
            raise SystemExit(
                f"DPDK process environment mismatch: {name}="
                f"{entries.get(name)!r} expected={expected!r}"
            )
        print(f"env_{name}={expected}")
    for name in (
        "FLLE_DPDK_DATA_IP", "FLLE_EXCHANGE_DATA_IP", "FLLE_ORDER_PORT",
        "FLLE_MANAGEMENT_IP", "FLLE_TELEMETRY_PORT",
    ):
        if name in entries:
            raise SystemExit(f"unexpected DPDK network override: {name}")
        print(f"env_{name}=<ABSENT>")
elif target == "OPENONLOAD":
    required = {
        "EF_POLL_USEC": "100000",
        "EF_TCP_FASTSTART_INIT": "0",
        "EF_TCP_FASTSTART_IDLE": "0",
    }
    for name, expected in required.items():
        if entries.get(name) != expected:
            raise SystemExit(
                f"Onload latency profile mismatch: {name}="
                f"{entries.get(name)!r} expected={expected!r}"
            )
        print(f"env_{name}={expected}")
PY
checkpoint_sha256="$(sha256sum "$run_dir/opening-book.checkpoint" | awk '{print $1}')"
grep -Fxq "opening_book_sha256=$checkpoint_sha256" \
  "$run_dir/data-plane-input.receipt"
cp -- "$run_dir/data-plane-input.receipt" "$tmp/"
printf '%s\n' "$state" >"$tmp/state.json"
{
  printf 'pid=%s\nstart_ticks=%s\nboot_id=%s\ncmdline=%s\nexe_path=%s\nexe_sha256=%s\nexe_manifest_sha256=%s\ncheckpoint_sha256=%s\nmeasurement_generation=%s\nmeasurement_ready_samples=%s\nmanagement_listener_count=%s\n' \
    "$pid" "$start_ticks" "$boot_id" "$command" "$exe_path" \
    "$exe_sha256" "$exe_manifest_sha256" "$checkpoint_sha256" \
    "$measurement_generation" "$measurement_ready_samples" \
    "${#management_listeners[@]}"
  for index in "${!management_listeners[@]}"; do
    printf 'management_listener_ss_line_%s=%s\n' "$((index + 1))" \
      "${management_listeners[$index]}"
  done
  printf 'argv_count=%s\n' "${#observed_argv[@]}"
  for index in "${!observed_argv[@]}"; do
    printf 'argv_%02d=%s\n' "$index" "${observed_argv[$index]}"
  done
  cat "$thread_snapshot" "$environment_snapshot"
} >"$tmp/process.txt"
rm -f -- "$thread_snapshot" "$environment_snapshot"

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
    case "$exchange_stage" in "$run_dir"/native-exchange-staging/*) ;; *) exit 1;; esac
    mapfile -t exchange_stage_files < <(find "$exchange_stage" \
      -mindepth 1 -maxdepth 1 -type f -printf '%f\n' | sort)
    test "${#exchange_stage_files[@]}" -eq 2
    test "${exchange_stage_files[0]}" = exchange-process.txt
    test "${exchange_stage_files[1]}" = exchange-ss-established.txt
    cp -- "$exchange_stage/exchange-process.txt" \
      "$exchange_stage/exchange-ss-established.txt" "$tmp/"
    cp -- "$run_dir/dpdk-session/fstack.log" "$tmp/fstack.log"
    cp -- "$run_dir/dpdk-session/gate-start.receipt" \
      "$tmp/gate-start.receipt"
    cp -- "$run_dir/dpdk-session/lease-start.receipt" \
      "$tmp/lease-start.receipt"
    lease_unit="$(sed -n 's/^lease_unit=//p' \
      "$tmp/lease-start.receipt")"
    lease_token="$(sed -n 's/^lease_token=//p' \
      "$tmp/lease-start.receipt")"
    [[ "$lease_unit" =~ ^flle-x2522-lease-[0-9a-f]{20}$ ]]
    test -n "$lease_token"
    test "$(<"$run_dir/dpdk-session/lease.token")" = "$lease_token"
    grep -Fxq 'state=OWNED' "$run_dir/dpdk-session/ownership.state"
    grep -Fxq "lease_token=$lease_token" \
      "$run_dir/dpdk-session/ownership.state"
    timer_active="$(systemctl show -p ActiveState --value \
      "$lease_unit.timer")"
    timer_sub="$(systemctl show -p SubState --value "$lease_unit.timer")"
    service_active="$(systemctl show -p ActiveState --value \
      "$lease_unit.service")"
    test "$timer_active" = active
    test "$timer_sub" = waiting
    test "$service_active" = inactive
    printf 'lease_unit=%s\nlease_token=%s\nownership_state=OWNED\ntimer_active=%s\ntimer_sub=%s\nservice_active=%s\n' \
      "$lease_unit" "$lease_token" "$timer_active" "$timer_sub" \
      "$service_active" >"$tmp/lease-status.txt"
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
    grep -Eq 'Probe PCI driver: net_sfc_efx .*device: 0000:03:00[.]0 ' \
      "$tmp/fstack.log"
    grep -Eq 'sfc_efx 0000:03:00[.]0 .*running FW variant is ultra-low-latency' \
      "$tmp/fstack.log"
    ;;
esac

manifest="$(python3 - "$run_dir" "$tmp" "$final" "$target" \
  "$runtime_root" "$input_runtime_root" <<'PY'
import hashlib
import json
import re
import sys
from pathlib import Path

run_dir = Path(sys.argv[1])
directory = Path(sys.argv[2])
published_directory = Path(sys.argv[3])
target = sys.argv[4]
runtime_root = Path(sys.argv[5]).resolve()
input_runtime_root = Path(sys.argv[6]).resolve()
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
if "/posix-runtime/" in str(runtime_root):
    if (state.get("order_dscp_control") != "POSIX_QOS_V1" or
            state.get("order_dscp") != 0):
        raise SystemExit("four-path comparison requires verified POSIX QoS client with DSCP 0")

process_items = [
    line.split("=", 1) for line in texts["process.txt"].splitlines()
]
if any(len(item) != 2 for item in process_items):
    raise SystemExit("native process receipt contains a malformed line")
process_lines = dict(process_items)
if len(process_lines) != len(process_items):
    raise SystemExit("native process receipt contains a duplicate key")
pid = int(process_lines["pid"])
expected_binary = {
    "SOCKET": "flle-trader",
    "OPENONLOAD": "flle-trader",
    "TCPDIRECT": "flle-trader-tcpdirect",
    "DPDK": "flle-trader-dpdk",
}[target]
expected_exe_path = (runtime_root / "bin" / expected_binary).as_posix()
exe_path = process_lines.get("exe_path", "")
exe_sha256 = process_lines.get("exe_sha256", "")
exe_manifest_sha256 = process_lines.get("exe_manifest_sha256", "")
runtime_manifest_matches = []
for line in (runtime_root / "MANIFEST.sha256").read_text(
    encoding="utf-8"
).splitlines():
    fields = line.split()
    if len(fields) == 2 and fields[1] == f"bin/{expected_binary}":
        runtime_manifest_matches.append(fields[0])
if (exe_path != expected_exe_path
        or re.fullmatch(r"[0-9a-f]{64}", exe_sha256) is None
        or exe_sha256 != exe_manifest_sha256
        or runtime_manifest_matches != [exe_manifest_sha256]):
    raise SystemExit("native client executable/runtime manifest identity is invalid")

try:
    argv_count = int(process_lines["argv_count"])
except (KeyError, ValueError) as error:
    raise SystemExit("native client argv count is invalid") from error
argv_keys = {
    key for key in process_lines if re.fullmatch(r"argv_[0-9]{2}", key)
}
expected_argv_keys = {f"argv_{index:02d}" for index in range(argv_count)}
if argv_count < 1 or argv_keys != expected_argv_keys:
    raise SystemExit("native client argv keys are not contiguous and exact")
observed_argv = [
    process_lines[f"argv_{index:02d}"] for index in range(argv_count)
]
user_ref_base = state.get("user_ref_base")
user_ref_span = state.get("user_ref_span")
if any(type(value) is not int or value < 1
       for value in (user_ref_base, user_ref_span)):
    raise SystemExit("native STATE has no valid user_ref namespace")
if target == "DPDK":
    expected_argv = [
        exe_path,
        "--conf", (run_dir / "dpdk-session/f-stack.effective.ini").as_posix(),
        "--proc-type=primary",
        "--proc-id=0",
    ]
else:
    management_port = {
        "SOCKET": "48122",
        "OPENONLOAD": "48123",
        "TCPDIRECT": "48124",
    }[target]
    clordid_prefix = {
        "SOCKET": "SOCK",
        "OPENONLOAD": "ONLD",
        "TCPDIRECT": "TCPD",
    }[target]
    expected_argv = [
        exe_path,
        "--role", "MANUAL",
        "--data-ip", "20.1.1.2",
        "--exchange-data-ip", "20.1.1.1",
        "--management-ip", "10.1.1.2",
        "--telemetry-host", "10.1.1.101",
        "--book-checkpoint", (run_dir / "opening-book.checkpoint").as_posix(),
        "--market-receiver", "0",
        "--order-queue", "DEQUE_CV",
        "--lock-order-queue", "1",
        "--order-cpu", "2",
        "--management-cpu", "3",
        "--management-port", management_port,
        "--user-ref-base", str(user_ref_base),
        "--user-ref-span", str(user_ref_span),
        "--clordid-prefix", clordid_prefix,
        "--order-transport-label", {
            "SOCKET": "POSIX_SOCKET",
            "OPENONLOAD": "OPENONLOAD",
            "TCPDIRECT": "TCPDIRECT_ZF",
        }[target],
    ]
if observed_argv != expected_argv:
    raise SystemExit("native client argv does not match its exact transport contract")

management_port = {
    "SOCKET": 48122,
    "OPENONLOAD": 48123,
    "TCPDIRECT": 48124,
    "DPDK": 48125,
}[target]
try:
    listener_count = int(process_lines["management_listener_count"])
except (KeyError, ValueError) as error:
    raise SystemExit("native management listener count is invalid") from error
listener_items = sorted(
    (int(match.group(1)), value)
    for key, value in process_lines.items()
    if (match := re.fullmatch(r"management_listener_ss_line_([0-9]+)", key))
)
if (listener_count != 1 or len(listener_items) != 1
        or listener_items[0][0] != 1):
    raise SystemExit("native management listener receipt is not unique")
listener_fields = listener_items[0][1].split()
if (f"10.1.1.2:{management_port}" not in listener_fields
        or f"pid={pid}," not in listener_items[0][1]):
    raise SystemExit("native management listener does not match PID/IP/port")

software = state.get("software_latency", {})
expected_threads = {"order": (2, 1), "management": (3, 1)}
if target == "DPDK":
    expected_threads["bridge"] = (3, 1)
for role, (expected_cpu, expected_count) in expected_threads.items():
    tid = software.get(f"{role}_thread_tid")
    if (type(tid) is not int or tid < 1
            or process_lines.get(f"thread_{role}_tid") != str(tid)
            or process_lines.get(f"thread_{role}_cpus_allowed_list")
            != str(expected_cpu)
            or software.get(f"{role}_thread_cpu") != expected_cpu
            or software.get(f"{role}_thread_allowed_count") != expected_count):
        raise SystemExit(f"native {role} thread placement contract is invalid")

try:
    receipt_generation = int(process_lines["measurement_generation"])
    receipt_ready_samples = int(process_lines["measurement_ready_samples"])
except (KeyError, ValueError) as error:
    raise SystemExit("native measurement generation receipt is invalid") from error
measurement = state.get("measurement_latency", {})
if (measurement.get("generation") != receipt_generation
        or measurement.get("ready_samples") != receipt_ready_samples):
    raise SystemExit("native measurement generation differs from STATE")

if target == "OPENONLOAD":
    expected_environment = {
        "env_EF_POLL_USEC": "100000",
        "env_EF_TCP_FASTSTART_INIT": "0",
        "env_EF_TCP_FASTSTART_IDLE": "0",
    }
elif target == "DPDK":
    lease = dict(
        line.split("=", 1)
        for line in texts["lease-start.receipt"].splitlines()
    )
    lease_status = dict(
        line.split("=", 1)
        for line in texts["lease-status.txt"].splitlines()
    )
    lease_token = lease.get("lease_token", "")
    if lease_status != {
        "lease_unit": lease.get("lease_unit", ""),
        "lease_token": lease_token,
        "ownership_state": "OWNED",
        "timer_active": "active",
        "timer_sub": "waiting",
        "service_active": "inactive",
    }:
        raise SystemExit("native DPDK ownership lease is not live")
    expected_environment = {
        "env_FLLE_DPDK_GATE_PID_FILE":
            (run_dir / "trader-dpdk-gate.pid").as_posix(),
        "env_FLLE_DPDK_DEADMAN": "1800",
        "env_FLLE_DPDK_LEASE_TOKEN": lease_token,
        "env_FLLE_DPDK_USER_REF_BASE": str(user_ref_base),
        "env_FLLE_DPDK_USER_REF_SPAN": str(user_ref_span),
        "env_FLLE_MANAGEMENT_PORT": "48125",
        "env_FLLE_TELEMETRY_HOST": "10.1.1.101",
        "env_FLLE_DPDK_HELPER_CPU": "3",
        "env_FLLE_DPDK_HEARTBEAT": "0",
        "env_FLLE_DPDK_DATA_IP": "<ABSENT>",
        "env_FLLE_EXCHANGE_DATA_IP": "<ABSENT>",
        "env_FLLE_ORDER_PORT": "<ABSENT>",
        "env_FLLE_MANAGEMENT_IP": "<ABSENT>",
        "env_FLLE_TELEMETRY_PORT": "<ABSENT>",
    }
else:
    expected_environment = {}
if any(process_lines.get(name) != value
       for name, value in expected_environment.items()):
    raise SystemExit("native process environment contract is invalid")

expected_state = {
    "status": "ONLINE",
    "role": "MANUAL",
    "market_protocol": (
        "CENTRAL_GATEWAY_BOOK" if target == "DPDK"
        else "COMMON_GATEWAY_BOOK"
    ),
    "order_protocol": "OUCH_5.0_OVER_SOUPBINTCP",
    "order_transport": {
        "SOCKET": "POSIX_SOCKET",
        "OPENONLOAD": "OPENONLOAD",
        "TCPDIRECT": "TCPDIRECT_ZF",
        "DPDK": "DPDK_FSTACK",
    }[target],
    "market_receiver_ready": False,
}
if any(state.get(name) != value for name, value in expected_state.items()):
    raise SystemExit("native STATE business/transport contract is invalid")
expected_engine = {
    "SOCKET": "KERNEL_SOCKET",
    "OPENONLOAD": "ONLOAD_USER_STACK",
    "TCPDIRECT": "ZF_REACTOR_POLL",
    "DPDK": "FSTACK_POLL",
}[target]
observed_engine = software.get(
    "network_engine", software.get("network_reactor")
)
if (software.get("queue_mode") != "DEQUE_CV"
        or software.get("queue_locked") is not True
        or software.get("queue_full_drops") != 0
        or observed_engine != expected_engine):
    raise SystemExit("native STATE queue/network-engine contract is invalid")
if target == "TCPDIRECT":
    if (state.get("tcp_nodelay") is not None
            or state.get("nagle_semantics")
            != "ZF_API_NO_POSIX_TCP_NODELAY"):
        raise SystemExit("native TCPDirect Nagle contract is invalid")
elif (state.get("tcp_nodelay") is not True
      or state.get("nagle_semantics") != (
          "FSTACK_GETSOCKOPT_VERIFIED" if target == "DPDK"
          else "POSIX_CONNECT_GETSOCKOPT_VERIFIED"
      )):
    raise SystemExit("native TCP_NODELAY contract is invalid")
if target == "DPDK" and state.get("heartbeat_enabled") is not False:
    raise SystemExit("native DPDK heartbeat must be disabled")
if (state.get("user_ref_end_exclusive") != user_ref_base + user_ref_span
        or type(state.get("user_ref_next")) is not int
        or not user_ref_base <= state["user_ref_next"]
        <= state["user_ref_end_exclusive"]):
    raise SystemExit("native STATE user_ref namespace is inconsistent")
input_receipt = dict(
    line.split("=", 1)
    for line in texts["data-plane-input.receipt"].splitlines()
)
runtime_manifest_sha256 = hashlib.sha256(
    # The checkpoint belongs to the base runtime, even with an additive client.
    (input_runtime_root / "MANIFEST.sha256").read_bytes()
).hexdigest()
checkpoint_sha256 = process_lines.get("checkpoint_sha256", "")
if (re.fullmatch(r"[0-9a-f]{64}", input_receipt.get("runtime_sha256", ""))
        is None
        or input_receipt.get("runtime_manifest_sha256")
        != runtime_manifest_sha256
        or input_receipt.get("opening_book_sha256") != checkpoint_sha256):
    raise SystemExit("native base-runtime/checkpoint input identity is invalid")
hardware_counters = None
excerpts = [
    {"path": (relative_root / "process.txt").as_posix(), "text": line}
    for line in texts["process.txt"].splitlines()
]
for field in (
    "runtime_sha256",
    "runtime_manifest_sha256",
    "opening_book_sha256",
    "itch_sha256",
):
    excerpts.append({
        "path": (relative_root / "data-plane-input.receipt").as_posix(),
        "text": f"{field}={input_receipt[field]}",
    })
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
    gate = dict(
        line.split("=", 1)
        for line in texts["gate-start.receipt"].splitlines()
    )
    manifest_entries = {}
    for line in (runtime_root / "MANIFEST.sha256").read_text(
        encoding="utf-8"
    ).splitlines():
        fields = line.split()
        if len(fields) == 2:
            manifest_entries[fields[1]] = fields[0]
    lease = dict(
        line.split("=", 1)
        for line in texts["lease-start.receipt"].splitlines()
    )
    lease_status = dict(
        line.split("=", 1)
        for line in texts["lease-status.txt"].splitlines()
    )
    lease_token = gate.get("lease_token", "")
    if (gate.get("gate_cpus_allowed_list") != "0"
            or gate.get("runtime_manifest_sha256")
            != runtime_manifest_sha256
            or gate.get("wrapper_sha256")
            != manifest_entries.get("bin/x2522-dpdk-trader-remote.sh")
            or gate.get("binary_sha256")
            != manifest_entries.get("bin/flle-trader-dpdk")
            or gate.get("config_sha256")
            != manifest_entries.get("etc/f-stack-x2522.ini")
            or re.fullmatch(r"[A-Za-z0-9._-]+", lease_token) is None
            or lease != {
                "lease_unit": lease.get("lease_unit", ""),
                "lease_seconds": "1800",
                "lease_token": lease_token,
                "recovery_executor":
                    "systemd_timer_independent_of_wrapper",
            }
            or re.fullmatch(
                r"flle-x2522-lease-[0-9a-f]{20}",
                lease.get("lease_unit", ""),
            ) is None
            or lease_status != {
                "lease_unit": lease.get("lease_unit", ""),
                "lease_token": lease_token,
                "ownership_state": "OWNED",
                "timer_active": "active",
                "timer_sub": "waiting",
                "service_active": "inactive",
            }):
        raise SystemExit("DPDK ownership gate/runtime identity is invalid")
    for field in (
        "gate_pid",
        "gate_cpus_allowed_list",
        "runtime_manifest_sha256",
        "wrapper_sha256",
        "binary_sha256",
        "config_sha256",
        "lease_token",
    ):
        excerpts.append({
            "path": (relative_root / "gate-start.receipt").as_posix(),
            "text": f"{field}={gate[field]}",
        })
    for field in (
        "lease_unit", "lease_seconds", "lease_token", "recovery_executor",
    ):
        excerpts.append({
            "path": (relative_root / "lease-start.receipt").as_posix(),
            "text": f"{field}={lease[field]}",
        })
    for field in (
        "ownership_state", "timer_active", "timer_sub", "service_active",
    ):
        excerpts.append({
            "path": (relative_root / "lease-status.txt").as_posix(),
            "text": f"{field}={lease_status[field]}",
        })
    exchange_process = dict(
        line.split("=", 1)
        for line in texts["exchange-process.txt"].splitlines()
    )
    exchange_pid = int(exchange_process["pid"])
    argv_count = int(exchange_process.get("argv_count", "0"))
    exchange_argv = [
        exchange_process.get(f"argv_{index:02d}", "")
        for index in range(argv_count)
    ]
    contract = exchange_process.get("exchange_contract", "FROZEN_V13")
    if contract not in ("FROZEN_V13", "NATIVE_AB_V1"):
        raise SystemExit("unknown Exchange runtime contract")
    native = contract == "NATIVE_AB_V1"
    expected_exe = (run_dir / "flle-exchange" if native else runtime_root / "bin/flle-exchange").as_posix()
    if native and exchange_process.get("exchange_manifest_entry", "").split() != [exchange_process.get("exe_sha256"), "flle-exchange"]:
        raise SystemExit("native Exchange deployment manifest mismatch")
    expected_exchange_argv = [
        expected_exe,
        "--telemetry-host", "10.1.1.101",
        "--replay-file", (run_dir / "AAPL_NVDA.itch").as_posix(),
        "--book-checkpoint",
        (run_dir / "opening-book.checkpoint").as_posix(),
        "--market-date", "2026-06-12",
        "--market-mode", "MULTICAST_A" if native else "UNICAST",
        "--replay-speed", "1",
    ]
    if exchange_argv != expected_exchange_argv:
        raise SystemExit("DPDK Exchange process identity is invalid")
    exchange_exe = exchange_process.get("exe_path", "")
    exchange_sha = exchange_process.get("exe_sha256", "")
    generator_sha = exchange_process.get("checkpoint_generator_sha256", "")
    checkpoint_sha = exchange_process.get("checkpoint_sha256", "")
    itch_sha = exchange_process.get("itch_sha256", "")
    if (exchange_exe != expected_exe
            or exchange_sha != exchange_process.get("exe_manifest_sha256")
            or generator_sha != exchange_process.get(
                "checkpoint_generator_manifest_sha256")
            or checkpoint_sha != input_receipt.get("opening_book_sha256")
            or itch_sha != input_receipt.get("itch_sha256")
            or any(re.fullmatch(r"[0-9a-f]{64}", value) is None
                   for value in (
                       exchange_sha, generator_sha, checkpoint_sha, itch_sha
                   ))):
        raise SystemExit("DPDK Exchange fixed runtime/checkpoint identity is invalid")
    listener_count = int(exchange_process.get("listener_count", "0"))
    listener_items = sorted(
        (
            int(match.group(1)),
            key,
            value,
        )
        for key, value in exchange_process.items()
        if (match := re.fullmatch(r"listener_ss_line_([0-9]+)", key))
    )
    if listener_count < 1 or len(listener_items) != listener_count:
        raise SystemExit("DPDK Exchange listener snapshot is incomplete")
    for expected, (number, _key, line) in enumerate(listener_items, start=1):
        if (
            number != expected
            or "20.1.1.1:43120" not in line.split()
            or f"pid={exchange_pid}," not in line
        ):
            raise SystemExit("DPDK Exchange listener snapshot is invalid")
    exchange_endpoints = []
    for line in texts["exchange-ss-established.txt"].splitlines():
        fields = line.split()
        if (len(fields) >= 5 and fields[2] == "20.1.1.1:43120"
                and re.fullmatch(r"20\.1\.1\.2:[0-9]+", fields[3])
                and f"pid={exchange_pid}," in line):
            exchange_endpoints.append(line)
    if not exchange_endpoints:
        raise SystemExit(
            "DPDK Exchange-side current PID has no target endpoint"
        )
    excerpts.extend([
        {"path": (relative_root / "exchange-process.txt").as_posix(),
         "text": f"pid={exchange_pid}"},
        {"path": (relative_root / "exchange-process.txt").as_posix(),
         "text": f"exe_path={exchange_exe}"},
        {"path": (relative_root / "exchange-process.txt").as_posix(),
         "text": f"exe_sha256={exchange_sha}"},
        {"path": (relative_root / "exchange-process.txt").as_posix(),
         "text": f"checkpoint_generator_sha256={generator_sha}"},
        {"path": (relative_root / "exchange-process.txt").as_posix(),
         "text": f"checkpoint_sha256={checkpoint_sha}"},
        {"path": (relative_root / "exchange-process.txt").as_posix(),
         "text": f"itch_sha256={itch_sha}"},
        {"path": (relative_root / "exchange-process.txt").as_posix(),
         "text": f"listener_count={listener_count}"},
        {"path": (relative_root / "exchange-process.txt").as_posix(),
         "text": f"argv_count={argv_count}"},
    ])
    excerpts.extend(
        {"path": (relative_root / "exchange-process.txt").as_posix(),
         "text": f"argv_{index:02d}={value}"}
        for index, value in enumerate(exchange_argv)
    )
    excerpts.extend(
        {"path": (relative_root / "exchange-process.txt").as_posix(),
         "text": f"{key}={line}"}
        for _number, key, line in listener_items
    )
    excerpts.extend(
        {"path": (relative_root / "exchange-ss-established.txt").as_posix(),
         "text": endpoint}
        for endpoint in exchange_endpoints
    )
    required = (
        ("Using IOMMU type 1", r"Using IOMMU type 1"),
        ("X2522 PMD", r"Probe PCI driver: net_sfc_efx .*"
         r"device: 0000:03:00\.0(?: |$)"),
        ("X2522 ULL firmware / ultra-low-latency",
         r"sfc_efx 0000:03:00\.0 .*"
         r"running FW variant is ultra-low-latency"),
    )
    for label, pattern in required:
        matches = [line for line in texts["fstack.log"].splitlines()
                   if re.search(pattern, line)]
        if not matches:
            raise SystemExit(f"DPDK native log lacks {label}")
        line = matches[0]
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
    port_stats = state.get("dpdk_port_stats")
    required_port_fields = (
        "port_id", "ipackets", "opackets", "imissed",
        "ierrors", "oerrors", "rx_nombuf",
    )
    if not isinstance(port_stats, dict) or any(
        type(port_stats.get(field)) is not int or port_stats[field] < 0
        for field in required_port_fields
    ) or port_stats["port_id"] != 0:
        raise SystemExit("DPDK current STATE lacks valid rte_eth_stats")
    counter_kind = "dpdk_port_packets"
    counter_value = port_stats["ipackets"] + port_stats["opackets"]
    hardware_counters = port_stats

manifest = {
    "files": files,
    "counter_kind": counter_kind,
    "counter_value": counter_value,
    "matching_excerpts": excerpts,
}
if hardware_counters is not None:
    manifest["hardware_counters"] = hardware_counters
print(json.dumps(manifest, separators=(",", ":")))
PY
)"
mv "$tmp" "$final"
trap - EXIT
if test "$exchange_stage" != NONE; then
  find "$exchange_stage" -depth -delete
fi
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

start_accelerated_clients() {
  local onload_base="$1" tcpdirect_base="$2" namespace_span="$3" common posix_root
  posix_root="$(posix_runtime_root)"
  common="--role MANUAL --data-ip 20.1.1.2 --exchange-data-ip 20.1.1.1 --management-ip 10.1.1.2 --telemetry-host $TELEMETRY_HOST --book-checkpoint $RUN_DIR/opening-book.checkpoint --market-receiver 0 --order-queue DEQUE_CV --lock-order-queue 1 --order-cpu 2 --management-cpu 3"
  start_remote_process "$TRADER_HOST" trader-onload \
    "taskset -c 2,3 onload --profile=latency '$posix_root/bin/flle-trader' $common --management-port 48123 --user-ref-base $onload_base --user-ref-span $namespace_span --clordid-prefix ONLD --order-transport-label OPENONLOAD"
  start_remote_process "$TRADER_HOST" trader-tcpdirect \
    "taskset -c 2,3 '$RUNTIME_ROOT/bin/flle-trader-tcpdirect' $common --management-port 48124 --user-ref-base $tcpdirect_base --user-ref-span $namespace_span --clordid-prefix TCPD --order-transport-label TCPDIRECT_ZF"
  wait_remote_listener "$TRADER_HOST" trader-onload /flle-trader 48123
  wait_remote_listener "$TRADER_HOST" trader-tcpdirect /flle-trader-tcpdirect 48124
  wait_state 48123 '"order_transport":"OPENONLOAD"' >/dev/null
  wait_state 48124 '"order_transport":"TCPDIRECT_ZF"' >/dev/null
}

start_sfc_clients() {
  local allocation sfc_slot socket_base onload_base tcpdirect_base namespace_span
  local extra common socket_ready onload_ready tcpdirect_ready state lock posix_root
  posix_root="$(posix_runtime_root)"
  allocation="$(allocate_sfc_user_ref_slot)"
  read -r sfc_slot socket_base onload_base tcpdirect_base namespace_span extra <<<"$allocation"
  test -n "$sfc_slot"; test -n "$socket_base"; test -n "$onload_base"
  test -n "$tcpdirect_base"; test -n "$namespace_span"; test -z "${extra:-}"
  common="--role MANUAL --data-ip 20.1.1.2 --exchange-data-ip 20.1.1.1 --management-ip 10.1.1.2 --telemetry-host $TELEMETRY_HOST --book-checkpoint $RUN_DIR/opening-book.checkpoint --market-receiver 0 --order-queue DEQUE_CV --lock-order-queue 1 --order-cpu 2 --management-cpu 3"
  start_remote_process "$TRADER_HOST" trader-socket \
    "taskset -c 2,3 '$posix_root/bin/flle-trader' $common --management-port 48122 --user-ref-base $socket_base --user-ref-span $namespace_span --clordid-prefix SOCK --order-transport-label POSIX_SOCKET"
  start_accelerated_clients "$onload_base" "$tcpdirect_base" "$namespace_span"
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

start_dpdk_prime() {
  stop_dpdk_prime
  "${SSH[@]}" "$EXCHANGE_HOST" bash -s -- "$RUN_DIR" <<'REMOTE'
set -Eeuo pipefail
run_dir="$1"
stop_file="$run_dir/dpdk-prime.stop"
pidfile="$run_dir/dpdk-prime.pid"
identity="$run_dir/dpdk-prime.identity"
rm -f -- "$stop_file" "$pidfile" "$identity"
nohup bash -c '
  run_dir="$1"; stop_file="$2"
  deadline=$((SECONDS + 180))
  while (( SECONDS < deadline )) && test ! -f "$stop_file"; do
    ip neigh del 20.1.1.2 dev ens64np0 2>/dev/null || true
    ping -I ens64np0 -c 1 -W 1 20.1.1.2 >/dev/null 2>&1 || true
    sleep 0.1
  done
' flle-dpdk-prime "$run_dir" "$stop_file" \
  >"$run_dir/dpdk-prime.log" 2>&1 </dev/null &
pid=$!
start="$(awk '{print $22}' "/proc/$pid/stat")"
boot="$(cat /proc/sys/kernel/random/boot_id)"
command="$(tr '\0' ' ' <"/proc/$pid/cmdline")"
case "$command" in *"flle-dpdk-prime $run_dir $stop_file"*) ;; *) exit 1;; esac
printf '%s\n' "$pid" >"$pidfile.tmp.$BASHPID"
printf 'pid=%s start_ticks=%s boot_id=%s\n' "$pid" "$start" "$boot" \
  >"$identity.tmp.$BASHPID"
mv -- "$pidfile.tmp.$BASHPID" "$pidfile"
mv -- "$identity.tmp.$BASHPID" "$identity"
REMOTE
}

stop_dpdk_prime() {
  "${SSH[@]}" "$EXCHANGE_HOST" bash -s -- "$RUN_DIR" <<'REMOTE'
set -Eeuo pipefail
run_dir="$1"
stop_file="$run_dir/dpdk-prime.stop"
pidfile="$run_dir/dpdk-prime.pid"
identity="$run_dir/dpdk-prime.identity"
touch "$stop_file" 2>/dev/null || true
pid=""
if test -s "$pidfile"; then
  mapfile -t lines <"$pidfile"; test "${#lines[@]}" -eq 1
  pid="${lines[0]}"; case "$pid" in ''|*[!0-9]*) exit 1;; esac
  test -r "/proc/$pid/cmdline" || pid=""
fi
if test -z "$pid" && test -d "$run_dir"; then
  candidates=()
  for process in /proc/[0-9]*; do
    test -r "$process/cmdline" || continue
    command="$(tr '\0' ' ' <"$process/cmdline")" || continue
    case "$command" in *"flle-dpdk-prime $run_dir $stop_file"*)
      candidates+=("${process##*/}");;
    esac
  done
  test "${#candidates[@]}" -le 1 || {
    echo "multiple DPDK prime helpers found: ${candidates[*]}" >&2
    exit 1
  }
  test "${#candidates[@]}" -eq 0 || pid="${candidates[0]}"
fi
if test -n "$pid" && test -r "/proc/$pid/cmdline"; then
  if test -s "$identity"; then
    IFS= read -r envelope <"$identity"
    read -r pid_field start_field boot_field extra <<<"$envelope"
    test -z "${extra:-}"; test "$pid_field" = "pid=$pid"
    case "$start_field" in start_ticks=*) expected_start="${start_field#start_ticks=}";; *) exit 1;; esac
    case "$boot_field" in boot_id=*) expected_boot="${boot_field#boot_id=}";; *) exit 1;; esac
    case "$expected_start" in ''|*[!0-9]*) exit 1;; esac
  else
    expected_start="$(awk '{print $22}' "/proc/$pid/stat")"
    expected_boot="$(cat /proc/sys/kernel/random/boot_id)"
  fi
  verify() {
    test -r "/proc/$pid/cmdline" || return 1
    test "$(awk '{print $22}' "/proc/$pid/stat")" = "$expected_start" \
      || return 1
    test "$(cat /proc/sys/kernel/random/boot_id)" = "$expected_boot" \
      || return 1
    command="$(tr '\0' ' ' <"/proc/$pid/cmdline")" || return 1
    case "$command" in *"flle-dpdk-prime $run_dir $stop_file"*) return 0;; *) return 1;; esac
  }
  verify
  kill -TERM "$pid" 2>/dev/null || true
  for _ in $(seq 1 40); do
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.1
  done
  if kill -0 "$pid" 2>/dev/null; then
    verify
    kill -KILL "$pid"
  fi
fi
for process in /proc/[0-9]*; do
  test -r "$process/cmdline" || continue
  command="$(tr '\0' ' ' <"$process/cmdline")" || continue
  case "$command" in *"flle-dpdk-prime $run_dir $stop_file"*)
    echo "DPDK prime helper survived cleanup: ${process##*/}" >&2; exit 1;;
  esac
done
rm -f -- "$pidfile" "$identity"
REMOTE
}

start_dpdk_client() {
  local allocation user_ref_slot user_ref_base user_ref_span user_ref_end
  local extra dpdk_ready lease_token
  dpdk_start_failure() {
    local original_rc=$? failed_command="$BASH_COMMAND"
    local failed_line="${BASH_LINENO[0]}" cleanup_failed=0
    trap - ERR
    printf 'DPDK_START_FAILURE rc=%s line=%s command=%q\n' \
      "$original_rc" "$failed_line" "$failed_command" >&2
    set +e
    stop_dpdk_prime || cleanup_failed=1
    stop_dpdk_client || cleanup_failed=1
    set -e
    if [[ "$cleanup_failed" -ne 0 ]]; then
      echo "DPDK start failed (rc=$original_rc) and recovery was incomplete" >&2
      exit 125
    fi
    return "$original_rc"
  }
  trap dpdk_start_failure ERR
  allocation="$(allocate_dpdk_user_ref_slot)"
  read -r user_ref_slot user_ref_base user_ref_span extra <<<"$allocation"
  test -n "$user_ref_slot"; test -n "$user_ref_base"; test -n "$user_ref_span"
  test -z "${extra:-}"
  user_ref_end=$((user_ref_base + user_ref_span))
  lease_token="${RUN_ID}-${user_ref_slot}"
  [[ "$lease_token" =~ ^[A-Za-z0-9._-]+$ ]]
  "${SSH[@]}" "$TRADER_HOST" bash -s -- \
    "$RUN_DIR" "$RUNTIME_ROOT" "$lease_token" <<'REMOTE'
set -Eeuo pipefail
run_dir="$1"; runtime_root="$2"; new_token="$3"
session_dir="$run_dir/dpdk-session"
mkdir -p "$session_dir"
if test -s "$session_dir/lease-start.receipt"; then
  old_unit="$(sed -n 's/^lease_unit=//p' "$session_dir/lease-start.receipt")"
  old_token="$(sed -n 's/^lease_token=//p' "$session_dir/lease-start.receipt")"
  [[ "$old_unit" =~ ^flle-x2522-lease-[0-9a-f]{20}$ ]]
  test -n "$old_token"
  test ! -e "$session_dir/lease.token"
  test "$(<"$session_dir/lease.token.consumed")" = "$old_token"
  grep -Fxq 'state=CONSUMED' "$session_dir/ownership.state"
  grep -Fxq "lease_token=$old_token" "$session_dir/ownership.state"
  if test -s "$session_dir/lease-recovery.receipt"; then
    grep -Fxq 'recovery=PASS' "$session_dir/lease-recovery.receipt"
    grep -Fxq "lease_token=$old_token" \
      "$session_dir/lease-recovery.receipt"
  else
    grep -Fxq 'restore_state=PASS' "$session_dir/gate-exit.receipt"
    grep -Fxq 'ownership_state=CONSUMED' \
      "$session_dir/gate-exit.receipt"
    grep -Fxq "lease_token=$old_token" "$session_dir/gate-exit.receipt"
  fi
  test "$(systemctl show -p ActiveState --value "$old_unit.timer")" = inactive
  test "$(systemctl show -p ActiveState --value "$old_unit.service")" = inactive
fi
test ! -e "$session_dir/lease.token"
test "$(basename "$(readlink /sys/bus/pci/devices/0000:03:00.0/driver)")" = sfc
mapfile -t ipv4 < <(ip -4 -o addr show dev ens64np1 scope global)
test "${#ipv4[@]}" -eq 1
test "$(awk '{print $4}' <<<"${ipv4[0]}")" = 20.1.1.2/24
test "$(cat /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages)" = 0
for process in /proc/[0-9]*; do
  test "$(readlink -f "$process/exe" 2>/dev/null || true)" != \
    "$runtime_root/bin/flle-trader-dpdk"
  test -r "$process/cmdline" || continue
  command="$(tr '\0' ' ' <"$process/cmdline")" || continue
  case "$command" in
    *"$runtime_root/bin/x2522-dpdk-trader-remote.sh"*"$session_dir"*)
      echo "previous DPDK ownership actor is still alive: ${process##*/}" >&2
      exit 1;;
  esac
done
rm -f -- "$run_dir/dpdk.stop" "$run_dir/trader-dpdk-gate.pid" \
  "$session_dir/gate-start.receipt" "$session_dir/gate-exit.receipt" \
  "$session_dir/trader-exit.receipt" "$session_dir/lease-recovery.receipt" \
  "$session_dir/lease-start.receipt" "$session_dir/lease.token.consumed" \
  "$session_dir/ownership.state" "$session_dir/ownership.baseline" \
  "$session_dir/gate.identity" "$session_dir/trader.identity" \
  "$session_dir/hugetlbfs.mount.baseline" \
  "$session_dir/hugetlbfs-files.baseline" \
  "$session_dir/hugetlbfs-files.final" \
  "$session_dir/hugetlbfs-files.recovery-final"
printf 'wrapper=%s\nsession_dir=%s\nstop_file=%s\nlease_token=%s\n' \
  "$runtime_root/bin/x2522-dpdk-trader-remote.sh" "$session_dir" \
  "$run_dir/dpdk.stop" "$new_token" >"$run_dir/dpdk-launch.intent"
REMOTE
  start_dpdk_prime
  "${SSH[@]}" "$TRADER_HOST" "set -eu; cd '$RUN_DIR'; nohup env FLLE_DPDK_GATE_PID_FILE='$RUN_DIR/trader-dpdk-gate.pid' FLLE_DPDK_LEASE_TOKEN='$lease_token' FLLE_DPDK_DEADMAN=1800 FLLE_DPDK_USER_REF_SLOT='$user_ref_slot' FLLE_DPDK_USER_REF_BASE='$user_ref_base' FLLE_DPDK_USER_REF_SPAN='$user_ref_span' taskset -c 0 '$RUNTIME_ROOT/bin/x2522-dpdk-trader-remote.sh' '$RUNTIME_ROOT/etc/f-stack-x2522.ini' '$RUNTIME_ROOT/bin/flle-trader-dpdk' '$RUN_DIR/dpdk-session' '$RUN_DIR/dpdk.stop' >trader-dpdk-gate.log 2>&1 </dev/null & launcher=\$!; for _ in \$(seq 1 80); do if test -s trader-dpdk-gate.pid && test -s dpdk-session/gate-start.receipt && test -s dpdk-session/lease-start.receipt; then test \"\$(<trader-dpdk-gate.pid)\" = \"\$launcher\"; kill -0 \"\$launcher\"; grep -Fxq 'lease_token=$lease_token' dpdk-session/gate-start.receipt; grep -Fxq 'recovery_executor=systemd_timer_independent_of_wrapper' dpdk-session/lease-start.receipt; exit 0; fi; kill -0 \"\$launcher\" || exit 1; sleep 0.05; done; kill -INT \"\$launcher\" 2>/dev/null || true; echo 'DPDK gate did not publish identity and lease receipts' >&2; exit 1"
  # F-Stack cold start includes EAL, VFIO, PMD and FreeBSD-stack bootstrap;
  # keep its readiness budget separate from the already-warm SFC clients.
  dpdk_ready="$(wait_state 48125 '"order_transport":"DPDK_FSTACK"' 400)"
  [[ "$dpdk_ready" == *"\"user_ref_base\":$user_ref_base"* ]]
  [[ "$dpdk_ready" == *"\"user_ref_span\":$user_ref_span"* ]]
  [[ "$dpdk_ready" == *"\"user_ref_end_exclusive\":$user_ref_end"* ]]
  [[ "$dpdk_ready" == *"\"user_ref_next\":$user_ref_base"* ]]
  attest_dpdk_receipt LAUNCH
  stop_dpdk_prime
  trap - ERR
}

configure_exchange_rss() {
  if "${SSH[@]}" "$EXCHANGE_HOST" "test -s '$RUN_DIR/exchange-rss.receipt'"; then
    if verify_exchange_rss; then return; fi
    # A previous stop/rollback keeps its receipt. Validate and restore only
    # settings owned by this RUN, then archive them before a fresh application.
    restore_exchange_rss || return 1
    "${SSH[@]}" "$EXCHANGE_HOST" bash -s -- "$RUN_DIR" <<'REMOTE'
set -Eeuo pipefail
run_dir="$1"
archive="$(mktemp -d "$run_dir/exchange-rss-history.XXXXXXXX")"
cp -p -- "$run_dir"/exchange-rss{.receipt,-baseline.txt,-applied.txt,-restored.txt} "$archive/"
(cd "$archive" && sha256sum exchange-rss* >SHA256SUMS)
rm -- "$run_dir"/exchange-rss{.receipt,-baseline.txt,-applied.txt,-restored.txt}
printf 'X2522_EXCHANGE_RSS_REAPPLY previous_receipt=%s\n' "$archive"
REMOTE
  fi
  "${SSH[@]}" "$EXCHANGE_HOST" bash -s -- "$RUN_DIR" <<'REMOTE'
set -Eeuo pipefail
run_dir="$1"; iface=ens64np0; bdf=0000:03:00.0
baseline="$run_dir/exchange-rss-baseline.txt"
applied="$run_dir/exchange-rss-applied.txt"
receipt="$run_dir/exchange-rss.receipt"
baseline_tmp="$baseline.tmp.$BASHPID"
applied_tmp="$applied.tmp.$BASHPID"
receipt_tmp="$receipt.tmp.$BASHPID"
rss_changed=0
irq_changed=0
irqbalance_paused=0
irq_affinity_baseline=""
cleanup() {
  rc=$?
  if test "$rss_changed" -eq 1; then
    ethtool -X "$iface" equal 4 >/dev/null 2>&1 || true
  fi
  if test "$irq_changed" -eq 1 && test -n "$irq_affinity_baseline"; then
    printf '%s\n' "$irq_affinity_baseline" \
      >"/proc/irq/$irq/smp_affinity_list" 2>/dev/null || true
  fi
  if test "$irqbalance_paused" -eq 1; then
    systemctl start irqbalance >/dev/null 2>&1 || true
  fi
  rm -f -- "$baseline_tmp" "$applied_tmp" "$receipt_tmp"
  exit "$rc"
}
trap cleanup ERR
test ! -e "$baseline"; test ! -e "$applied"; test ! -e "$receipt"
test "$(basename "$(readlink "/sys/bus/pci/devices/$bdf/driver")")" = sfc
grep -Fxq 'receive-hashing: on' < <(ethtool -k "$iface")
ethtool -x "$iface" >"$baseline_tmp"
read -r baseline_entries baseline_bad < <(
  awk '
    /^[[:space:]]*[0-9]+:/ {
      for (field = 2; field <= NF; ++field) {
        expected = count % 4
        if ($field != expected) ++bad
        ++count
      }
    }
    END { print count + 0, bad + 0 }
  ' "$baseline_tmp"
)
test "$baseline_entries" -eq 128; test "$baseline_bad" -eq 0
mapfile -t irq_matches < <(
  awk '$NF == "ens64np0-1" { gsub(":", "", $1); print $1 }' /proc/interrupts
)
test "${#irq_matches[@]}" -eq 1
irq="${irq_matches[0]}"; case "$irq" in ''|*[!0-9]*) exit 1;; esac
irq_affinity_baseline="$(cat "/proc/irq/$irq/smp_affinity_list")"
irq_effective_baseline="$(cat "/proc/irq/$irq/effective_affinity_list")"
case "$irq_affinity_baseline" in ''|*[!0-9,-]*) exit 1;; esac
case "$irq_effective_baseline" in ''|*[!0-9,-]*) exit 1;; esac
irqbalance_baseline="$(systemctl is-active irqbalance 2>/dev/null || true)"
case "$irqbalance_baseline" in active|inactive) ;; *) exit 1;; esac
if test "$irqbalance_baseline" = active; then
  systemctl stop irqbalance
  irqbalance_paused=1
fi
for _ in $(seq 1 40); do
  test "$(systemctl is-active irqbalance 2>/dev/null || true)" = inactive && break
  sleep 0.1
done
test "$(systemctl is-active irqbalance 2>/dev/null || true)" = inactive
printf '2\n' >"/proc/irq/$irq/smp_affinity_list"
irq_changed=1
test "$(cat "/proc/irq/$irq/smp_affinity_list")" = 2
test "$(cat "/proc/irq/$irq/effective_affinity_list")" = 2
ethtool -X "$iface" weight 0 1 0 0
rss_changed=1
ethtool -x "$iface" >"$applied_tmp"
read -r applied_entries applied_bad < <(
  awk '
    /^[[:space:]]*[0-9]+:/ {
      for (field = 2; field <= NF; ++field) {
        if ($field != 1) ++bad
        ++count
      }
    }
    END { print count + 0, bad + 0 }
  ' "$applied_tmp"
)
test "$applied_entries" -eq 128; test "$applied_bad" -eq 0
baseline_sha256="$(sha256sum "$baseline_tmp" | awk '{print $1}')"
applied_sha256="$(sha256sum "$applied_tmp" | awk '{print $1}')"
{
  echo 'interface=ens64np0'
  echo 'bdf=0000:03:00.0'
  echo 'driver=sfc'
  echo 'rss_entries=128'
  echo 'rss_queue=1'
  echo "irq=$irq"
  echo "irq_affinity_baseline=$irq_affinity_baseline"
  echo "irq_effective_baseline=$irq_effective_baseline"
  echo "irqbalance_baseline=$irqbalance_baseline"
  echo 'irq_affinity_applied=2'
  echo 'irqbalance_during_run=inactive'
  echo 'effective_cpu=2'
  echo 'exchange_cpu=2'
  echo 'verification=X2522_RSS_ALL_BUCKETS_TO_EXCHANGE_CPU_QUEUE'
  echo "baseline_sha256=$baseline_sha256"
  echo "applied_sha256=$applied_sha256"
} >"$receipt_tmp"
mv -- "$baseline_tmp" "$baseline"
mv -- "$applied_tmp" "$applied"
mv -- "$receipt_tmp" "$receipt"
rss_changed=0
irq_changed=0
irqbalance_paused=0
trap - ERR
cat "$receipt"
REMOTE
}

verify_exchange_rss() {
  "${SSH[@]}" "$EXCHANGE_HOST" bash -s -- "$RUN_DIR" <<'REMOTE'
set -Eeuo pipefail
run_dir="$1"; iface=ens64np0
receipt="$run_dir/exchange-rss.receipt"
applied="$run_dir/exchange-rss-applied.txt"
test -s "$receipt"; test -s "$applied"
expected_sha="$(sed -n 's/^applied_sha256=//p' "$receipt")"
irq="$(sed -n 's/^irq=//p' "$receipt")"
grep -Eq '^[0-9a-f]{64}$' <<<"$expected_sha"
case "$irq" in ''|*[!0-9]*) exit 1;; esac
test "$(sha256sum "$applied" | awk '{print $1}')" = "$expected_sha"
current="$(ethtool -x "$iface")"
current_sha="$(printf '%s\n' "$current" | sha256sum | awk '{print $1}')"
requested_cpu="$(cat "/proc/irq/$irq/smp_affinity_list")"
effective_cpu="$(cat "/proc/irq/$irq/effective_affinity_list")"
irqbalance_state="$(systemctl is-active irqbalance 2>/dev/null || true)"
read -r entries bad < <(
  printf '%s\n' "$current" | awk '
    /^[[:space:]]*[0-9]+:/ {
      for (field = 2; field <= NF; ++field) {
        if ($field != 1) ++bad
        ++count
      }
    }
    END { print count + 0, bad + 0 }
  '
)
test "$current_sha" = "$expected_sha"
test "$entries" -eq 128; test "$bad" -eq 0
test "$requested_cpu" = 2
test "$effective_cpu" = 2
test "$irqbalance_state" = inactive
printf 'X2522_EXCHANGE_RSS_VERIFIED entries=128 queue=1 irq=%s requested_cpu=2 effective_cpu=2 irqbalance=paused\n' "$irq"
REMOTE
}

restore_exchange_rss() {
  "${SSH[@]}" "$EXCHANGE_HOST" bash -s -- "$RUN_DIR" <<'REMOTE'
set -Eeuo pipefail
run_dir="$1"; iface=ens64np0
baseline="$run_dir/exchange-rss-baseline.txt"
applied="$run_dir/exchange-rss-applied.txt"
receipt="$run_dir/exchange-rss.receipt"
restored="$run_dir/exchange-rss-restored.txt"
if test ! -s "$receipt"; then
  echo 'X2522_EXCHANGE_RSS_RESTORE ownership=ABSENT action=NONE'
  exit 0
fi
test -s "$baseline"; test -s "$applied"
baseline_sha256="$(sed -n 's/^baseline_sha256=//p' "$receipt")"
applied_sha256="$(sed -n 's/^applied_sha256=//p' "$receipt")"
irq="$(sed -n 's/^irq=//p' "$receipt")"
irq_affinity_baseline="$(sed -n 's/^irq_affinity_baseline=//p' "$receipt")"
irq_effective_baseline="$(sed -n 's/^irq_effective_baseline=//p' "$receipt")"
irqbalance_baseline="$(sed -n 's/^irqbalance_baseline=//p' "$receipt")"
grep -Eq '^[0-9a-f]{64}$' <<<"$baseline_sha256"
grep -Eq '^[0-9a-f]{64}$' <<<"$applied_sha256"
test "$(sha256sum "$baseline" | awk '{print $1}')" = "$baseline_sha256"
test "$(sha256sum "$applied" | awk '{print $1}')" = "$applied_sha256"
current="$restored.current.$BASHPID"
cleanup(){ rm -f -- "$current"; }
trap cleanup EXIT
ethtool -x "$iface" >"$current"
if test -n "$irq_affinity_baseline"; then
  case "$irq" in ''|*[!0-9]*) exit 1;; esac
  case "$irq_affinity_baseline" in ''|*[!0-9,-]*) exit 1;; esac
  case "$irq_effective_baseline" in ''|*[!0-9,-]*) exit 1;; esac
  case "$irqbalance_baseline" in active|inactive) ;; *) exit 1;; esac
  irqbalance_current="$(systemctl is-active irqbalance 2>/dev/null || true)"
  requested_current="$(cat "/proc/irq/$irq/smp_affinity_list")"
  effective_current="$(cat "/proc/irq/$irq/effective_affinity_list")"
  if cmp -s "$current" "$baseline" && \
      test "$irqbalance_current" = "$irqbalance_baseline"; then
    if test "$irqbalance_baseline" = active || \
        { test "$requested_current" = "$irq_affinity_baseline" && \
          test "$effective_current" = "$irq_effective_baseline"; }; then
      cp -- "$current" "$restored"
      test "$(sha256sum "$restored" | awk '{print $1}')" = "$baseline_sha256"
      printf 'X2522_EXCHANGE_IRQ_RESTORED irq=%s affinity_before_policy=%s irqbalance=%s already=1\n' \
        "$irq" "$irq_affinity_baseline" "$irqbalance_baseline"
      echo "X2522_EXCHANGE_RSS_RESTORED entries=128 pattern=0,1,2,3 sha256=$baseline_sha256 already=1"
      exit 0
    fi
  fi
  test "$irqbalance_current" = inactive
  if ! { test "$requested_current" = 2 && test "$effective_current" = 2; } && \
      ! { test "$requested_current" = "$irq_affinity_baseline" && \
          test "$effective_current" = "$irq_effective_baseline"; }; then
    echo 'X2522 Exchange IRQ changed outside the owned course transition' >&2
    exit 1
  fi
fi
if ! cmp -s "$current" "$baseline"; then
  cmp -s "$current" "$applied" || {
    echo 'X2522 Exchange RSS changed outside the owned course transition' >&2
    exit 1
  }
  ethtool -X "$iface" equal 4
  ethtool -x "$iface" >"$current"
  cmp -s "$current" "$baseline"
fi
cp -- "$current" "$restored"
test "$(sha256sum "$restored" | awk '{print $1}')" = "$baseline_sha256"
if test -n "$irq_affinity_baseline"; then
  if test "$(cat "/proc/irq/$irq/smp_affinity_list")" != \
      "$irq_affinity_baseline"; then
    printf '%s\n' "$irq_affinity_baseline" >"/proc/irq/$irq/smp_affinity_list"
  fi
  test "$(cat "/proc/irq/$irq/smp_affinity_list")" = "$irq_affinity_baseline"
  test "$(cat "/proc/irq/$irq/effective_affinity_list")" = "$irq_effective_baseline"
  if test "$irqbalance_baseline" = active; then
    systemctl start irqbalance
    for _ in $(seq 1 40); do
      test "$(systemctl is-active irqbalance 2>/dev/null || true)" = active && break
      sleep 0.1
    done
    test "$(systemctl is-active irqbalance 2>/dev/null || true)" = active
  fi
  printf 'X2522_EXCHANGE_IRQ_RESTORED irq=%s affinity_before_policy=%s irqbalance=%s\n' \
    "$irq" "$irq_affinity_baseline" "$irqbalance_baseline"
fi
echo "X2522_EXCHANGE_RSS_RESTORED entries=128 pattern=0,1,2,3 sha256=$baseline_sha256"
REMOTE
}

select_exchange_runtime() {
  EXCHANGE_EXECUTABLE="$RUNTIME_ROOT/bin/flle-exchange"
  EXCHANGE_START_MODE=UNICAST
  if "${SSH[@]}" "$EXCHANGE_HOST" "test -f '$RUN_DIR/deployed.sha256'"; then
    EXCHANGE_EXECUTABLE="$RUN_DIR/flle-exchange"
    EXCHANGE_START_MODE=MULTICAST_A
    "${SSH[@]}" "$EXCHANGE_HOST" "cd '$RUN_DIR' && sha256sum -c deployed.sha256 >/dev/null" || return 1
  fi
}

start_exchange() {
  select_exchange_runtime
  if ! platform_process_running "$EXCHANGE_HOST" exchange "$EXCHANGE_EXECUTABLE" 2>/dev/null; then
  start_remote_process "$EXCHANGE_HOST" exchange \
    "taskset -c 2 '$EXCHANGE_EXECUTABLE' --telemetry-host '$TELEMETRY_HOST' --replay-file '$RUN_DIR/AAPL_NVDA.itch' --book-checkpoint '$RUN_DIR/opening-book.checkpoint' --market-date 2026-06-12 --market-mode '$EXCHANGE_START_MODE' --replay-speed 1"
  fi
  wait_remote_listener "$EXCHANGE_HOST" exchange /flle-exchange 43120
  wait_remote_listener "$EXCHANGE_HOST" exchange /flle-exchange 48120
  verify_exchange_runtime
}

verify_exchange_runtime() {
  select_exchange_runtime
  platform_process_running "$EXCHANGE_HOST" exchange "$EXCHANGE_EXECUTABLE"
  "${SSH[@]}" "$EXCHANGE_HOST" bash -s -- \
    "$RUN_DIR" "$RUNTIME_ROOT" "$TELEMETRY_HOST" "$EXCHANGE_EXECUTABLE" "$EXCHANGE_START_MODE" <<'REMOTE'
set -Eeuo pipefail
run_dir="$1"; runtime_root="$2"; telemetry_host="$3"
expected_exe="$4"; start_mode="$5"
mapfile -t pid_lines <"$run_dir/exchange.pid"
test "${#pid_lines[@]}" -eq 1
pid="${pid_lines[0]}"; case "$pid" in ''|*[!0-9]*) exit 1;; esac
mapfile -d '' -t observed_argv <"/proc/$pid/cmdline"
expected_argv=(
  "$expected_exe"
  --telemetry-host "$telemetry_host"
  --replay-file "$run_dir/AAPL_NVDA.itch"
  --book-checkpoint "$run_dir/opening-book.checkpoint"
  --market-date 2026-06-12
  --market-mode "$start_mode"
  --replay-speed 1
)
test "${#observed_argv[@]}" -eq "${#expected_argv[@]}"
for index in "${!expected_argv[@]}"; do
  test "${observed_argv[$index]}" = "${expected_argv[$index]}"
done
exe="$(readlink -f "/proc/$pid/exe")"
test "$exe" = "$expected_exe"
exe_sha="$(sha256sum "$exe" | awk '{print $1}')"
if test "$start_mode" = MULTICAST_A; then
  test "$exe_sha" = "$(awk '$2=="flle-exchange" {print $1}' "$run_dir/deployed.sha256")"
else
  test "$exe_sha" = "$(awk '$2=="bin/flle-exchange" {print $1}' "$runtime_root/MANIFEST.sha256")"
fi
checkpoint_sha="$(sha256sum "$run_dir/opening-book.checkpoint" | awk '{print $1}')"
itch_sha="$(sha256sum "$run_dir/AAPL_NVDA.itch" | awk '{print $1}')"
grep -Fxq "opening_book_sha256=$checkpoint_sha" "$run_dir/data-plane-input.receipt"
grep -Fxq "itch_sha256=$itch_sha" "$run_dir/data-plane-input.receipt"
printf 'EXCHANGE_RUNTIME_RECEIPT pid=%s exe_sha256=%s checkpoint_sha256=%s itch_sha256=%s\n' \
  "$pid" "$exe_sha" "$checkpoint_sha" "$itch_sha"
REMOTE
  if test "$EXCHANGE_START_MODE" = MULTICAST_A; then platform_verify_exchange_network; fi
}

verify_controller_identity() {
  if [[ "$CONTROL_LOCAL" != 1 ]]; then
    "${SSH[@]}" "$TRADER_HOST" bash "$CONTROL_SCRIPT" controller-check "$RUN_ID"
    return
  fi
  local pid command listeners
  systemctl is-active --quiet "$CONTROLLER_UNIT" || return 1
  pid="$(systemctl show -p MainPID --value "$CONTROLLER_UNIT" 2>/dev/null)" \
    || return 1
  case "$pid" in ''|0|*[!0-9]*) return 1;; esac
  test -r "/proc/$pid/cmdline" || return 1
  command="$(tr '\0' ' ' <"/proc/$pid/cmdline")" || return 1
  case "$command" in
    *"$APP_DIR/flle_trading/transport_controller.py"*"--control-script $SCRIPT_DIR/transport_labctl.sh"*"--run-id $RUN_ID"*) ;;
    *) return 1;;
  esac
  listeners="$(ss -ltnpH '( sport = :48606 )' 2>/dev/null)" || return 1
  case "$listeners" in *"pid=$pid,"*) return 0;; *) return 1;; esac
}

verify_gateway_identity() {
  "${SSH[@]}" "$OBSERVER_HOST" bash -s -- "$RUN_DIR" <<'REMOTE'
set -Eeuo pipefail
run_dir="$1"; pidfile="$run_dir/gateway.pid"; identity="$run_dir/gateway.identity"
test -s "$pidfile" && test -s "$identity"
IFS= read -r pid <"$pidfile"
read -r pid_field start_field boot_field extra <"$identity"
test -z "${extra:-}"; test "$pid_field" = "pid=$pid"
start_ticks="${start_field#start_ticks=}"; boot_id="${boot_field#boot_id=}"
case "$pid" in ''|*[!0-9]*) exit 1;; esac
case "$start_ticks" in ''|*[!0-9]*) exit 1;; esac
test -r "/proc/$pid/cmdline"
command="$(tr '\0' ' ' <"/proc/$pid/cmdline")"
case "$command" in *flle_trading.gateway*) ;; *) exit 1;; esac
case "$command" in *"$run_dir"*) ;; *) exit 1;; esac
test "$(awk '{print $22}' "/proc/$pid/stat")" = "$start_ticks"
test "$(cat /proc/sys/kernel/random/boot_id)" = "$boot_id"
listeners="$(ss -ltnpH '( sport = :8088 )' 2>/dev/null)"
case "$listeners" in *"pid=$pid,"*) ;; *) exit 1;; esac
REMOTE
}

lab_is_quiescent() {
  local unit="${1:-$CONTROLLER_UNIT}"
  "${SSH[@]}" "$TRADER_HOST" "! systemctl is-active --quiet '$unit' && test -z \"\$(ss -ltnpH '( sport = :48606 )')\"" || return 1
  ! systemctl is-active --quiet "$unit" || return 1
  test -z "$(ss -ltnpH '( sport = :48606 )' 2>/dev/null || true)" || return 1
  "${SSH[@]}" "$EXCHANGE_HOST" bash -s <<'REMOTE' || return 1
set -Eeuo pipefail
test "$(basename "$(readlink /sys/bus/pci/devices/0000:03:00.0/driver)")" = sfc
ip -4 -o addr show dev ens64np0 | grep -Fq ' 20.1.1.1/24 '
test "$(cat /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages)" = 0
for port in 43120 48120; do test -z "$(ss -ltnpH "( sport = :$port )" 2>/dev/null || true)"; done
read -r entries bad < <(ethtool -x ens64np0 | awk '/^[[:space:]]*[0-9]+:/ {for(i=2;i<=NF;i++){if($i!=(n%4))b++;n++}} END{print n+0,b+0}')
test "$entries" -eq 128 && test "$bad" -eq 0
systemctl is-active --quiet irqbalance
REMOTE
  "${SSH[@]}" "$TRADER_HOST" bash -s <<'REMOTE' || return 1
set -Eeuo pipefail
test "$(basename "$(readlink /sys/bus/pci/devices/0000:03:00.0/driver)")" = sfc
ip -4 -o addr show dev ens64np1 | grep -Fq ' 20.1.1.2/24 '
test "$(cat /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages)" = 0
for port in 48121 48122 48123 48124 48125; do test -z "$(ss -ltnpH "( sport = :$port )" 2>/dev/null || true)"; done
! mountpoint -q /mnt/huge
REMOTE
  "${SSH[@]}" "$OBSERVER_HOST" \
    "test -z \"\$(ss -ltnpH '( sport = :8088 )' 2>/dev/null || true)\"" || return 1
}

start_controller() {
  if [[ "$CONTROL_LOCAL" != 1 ]]; then
    "${SSH[@]}" "$TRADER_HOST" bash "$CONTROL_SCRIPT" controller-start "$RUN_ID"
    return
  fi
  mkdir -p "$CONTROL_DIR"
  if systemctl is-active --quiet "$CONTROLLER_UNIT"; then
    verify_controller_identity || {
      echo "active controller unit failed PID/cmdline/socket identity" >&2
      return 1
    }
    return 0
  fi
  test -z "$(ss -ltnpH '( sport = :48606 )' 2>/dev/null || true)" || {
    echo "controller port 48606 is already owned by another process" >&2
    return 1
  }
  systemd-run --quiet --collect --unit "$CONTROLLER_UNIT" \
    --property="WorkingDirectory=$REPO_ROOT" \
    /usr/bin/env -u FLLE_TRANSPORT_LOCK_HELD \
      /usr/bin/python3 "$APP_DIR/flle_trading/transport_controller.py" \
      --bind-ip "$CONTROLLER_IP" --allowed-peer 10.1.1.101 \
      --control-script "$SCRIPT_DIR/transport_labctl.sh" --run-id "$RUN_ID" \
      --log-dir "$RUN_DIR/mode-actions"
  for _ in $(seq 1 40); do
    systemctl is-active --quiet "$CONTROLLER_UNIT" || break
    verify_controller_identity && return 0
    sleep 0.25
  done
  journalctl -u "$CONTROLLER_UNIT" -n 30 --no-pager >&2 || true
  return 1
}

start_gateway() {
  if verify_gateway_identity 2>/dev/null; then return; fi
  start_remote_process "$OBSERVER_HOST" gateway \
    "env PYTHONPATH='$RUN_DIR' python3 -m flle_trading.gateway --web-root '$RUN_DIR/web' --transport-lab --data-plane-controller-url 'http://$CONTROLLER_IP:48606'"
  wait_remote_listener "$OBSERVER_HOST" gateway flle_trading.gateway 8088
}

collect_status() {
  if platform_is_software; then platform_software_status; return; fi
  local driver hugepages_2mb data_ip_present mode owner transition
  local socket_state onload_state tcpdirect_state dpdk_state
  local active_receipts name receipt socket_receipt="" onload_receipt=""
  local tcpdirect_receipt="" dpdk_receipt="" exchange_rss_receipt=""
  read -r driver hugepages_2mb data_ip_present < <(
    "${SSH[@]}" "$TRADER_HOST" "driver=\$(basename \"\$(readlink /sys/bus/pci/devices/0000:03:00.0/driver)\"); pages=\$(cat /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages); if ip -4 -o addr show dev ens64np1 2>/dev/null | grep -Fq ' 20.1.1.2/24 '; then ip_present=1; else ip_present=0; fi; printf '%s %s %s\n' \"\$driver\" \"\$pages\" \"\$ip_present\"" \
      2>/dev/null || echo 'UNKNOWN -1 0'
  )
  if [[ "$driver" == vfio-pci ]]; then mode=DPDK; owner=vfio-pci; else mode=SFC; owner="$driver"; fi
  socket_state="$(management_command 48122 STATE 2>/dev/null || true)"
  onload_state="$(management_command 48123 STATE 2>/dev/null || true)"
  tcpdirect_state="$(management_command 48124 STATE 2>/dev/null || true)"
  dpdk_state="$(management_command 48125 STATE 2>/dev/null || true)"
  exchange_rss_receipt="$("${SSH[@]}" "$EXCHANGE_HOST" bash -s -- "$RUN_DIR" <<'REMOTE'
set -u
run_dir="$1"
receipt="$run_dir/exchange-rss.receipt"
applied="$run_dir/exchange-rss-applied.txt"
test -s "$receipt" && test -s "$applied" || { echo ABSENT; exit 0; }
expected_sha="$(sed -n 's/^applied_sha256=//p' "$receipt")"
irq="$(sed -n 's/^irq=//p' "$receipt")"
test -n "$expected_sha" && test -n "$irq" || { echo DRIFT; exit 0; }
applied_sha="$(sha256sum "$applied" 2>/dev/null | awk '{print $1}')"
requested_cpu="$(cat "/proc/irq/$irq/smp_affinity_list" 2>/dev/null || true)"
effective_cpu="$(cat "/proc/irq/$irq/effective_affinity_list" 2>/dev/null || true)"
irqbalance_state="$(systemctl is-active irqbalance 2>/dev/null || true)"
if test "$applied_sha" = "$expected_sha" && test "$requested_cpu" = 2 &&
   test "$effective_cpu" = 2 && test "$irqbalance_state" = inactive; then
  printf 'READY|entries=128|queue=1|irq=%s|requested_cpu=2|effective_cpu=2|irqbalance=paused|verification=X2522_RSS_ALL_BUCKETS_TO_EXCHANGE_CPU_QUEUE\n' "$irq"
else
  printf 'DRIFT|receipt_sha=%s|irq=%s|requested_cpu=%s|effective_cpu=%s|irqbalance=%s\n' \
    "$applied_sha" "$irq" "$requested_cpu" "$effective_cpu" "$irqbalance_state"
fi
REMOTE
)"
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
  command="$(tr '\0' ' ' 2>/dev/null <"/proc/$pid/cmdline" || true)"
  test -n "$command" || return 0
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
  [[ "$exchange_rss_receipt" == READY\|* ]] || transition=DEGRADED
  if [[ "$mode" == SFC ]]; then
    [[ "$owner" == sfc && "$hugepages_2mb" == 128 &&
       "$data_ip_present" == 1 &&
       "$socket_state" == *'"status":"ONLINE"'* &&
       "$socket_state" == *'"order_transport":"POSIX_SOCKET"'* &&
       "$socket_state" == *'"queue_locked":true'* && -n "$socket_receipt" &&
       "$onload_state" == *'"status":"ONLINE"'* &&
       "$onload_state" == *'"order_transport":"OPENONLOAD"'* &&
       "$onload_state" == *'"queue_locked":true'* && -n "$onload_receipt" &&
       "$tcpdirect_state" == *'"status":"ONLINE"'* &&
       "$tcpdirect_state" == *'"order_transport":"TCPDIRECT_ZF"'* &&
       "$tcpdirect_state" == *'"queue_locked":true'* && -n "$tcpdirect_receipt" ]] || transition=DEGRADED
  else
    [[ "$owner" == vfio-pci && "$hugepages_2mb" == 256 &&
       "$data_ip_present" == 0 &&
       "$dpdk_state" == *'"status":"ONLINE"'* &&
       "$dpdk_state" == *'"order_transport":"DPDK_FSTACK"'* &&
       "$dpdk_state" == *'"queue_locked":true'* && -n "$dpdk_receipt" ]] || transition=DEGRADED
  fi
  python3 - "$mode" "$transition" "$owner" "$hugepages_2mb" \
    "$data_ip_present" "$socket_receipt" "$onload_receipt" \
    "$tcpdirect_receipt" "$dpdk_receipt" "$exchange_rss_receipt" <<'PY'
import json, sys
mode, transition, owner, hugepages_raw, ip_raw, socket_raw, onload_raw, tcpdirect_raw, dpdk_raw, exchange_rss_raw = sys.argv[1:]
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
def exchange_rss_receipt(raw):
    parts = raw.split("|")
    if not parts or parts[0] != "READY":
        return {
            "launch_verified": False,
            "verified": False,
            "summary": "X2522 Exchange RSS 未固定或已漂移",
            "state": parts[0] if parts else "ABSENT",
        }
    fields = dict(item.split("=", 1) for item in parts[1:])
    return {
        "launch_verified": True,
        "verified": True,
        "summary": "X2522 128 个 RSS 桶固定到与 Exchange 同核的 RX ring 1",
        "entries": int(fields["entries"]),
        "queue": int(fields["queue"]),
        "irq": int(fields["irq"]),
        "requested_cpu": int(fields["requested_cpu"]),
        "effective_cpu": int(fields["effective_cpu"]),
        "irqbalance": fields["irqbalance"],
        "verification": fields["verification"],
    }
print(json.dumps({
    "mode": mode,
    "experiment_profile": "TRANSPORT",
    "transition": transition,
    "owner": owner,
    "hugepages_2mb": int(hugepages_raw),
    "data_ip_present": ip_raw == "1",
    "hardware_receipts": {
        "socket": receipt(socket_raw, "当前 PID 的 sfc netdev + Kernel TCP"),
        "onload": receipt(onload_raw, "当前 PID 的 Established Onloaded(Valid) + X2522 VI"),
        "tcpdirect": receipt(tcpdirect_raw, "当前 PID 的 ZF stack；CTPIO 由代码合同另验"),
        "dpdk": receipt(dpdk_raw, "当前 PID 的 IOMMU type 1 + net_sfc_efx + ULL firmware"),
        "exchange_rss": exchange_rss_receipt(exchange_rss_raw),
    },
}, separators=(",", ":")))
PY
}

require_mode_ready() {
  local expected_mode="${1:?expected mode is required}" state="${2:?state JSON is required}"
  python3 - "$expected_mode" "$state" <<'PY'
import json
import sys

expected_mode, raw = sys.argv[1:]
state = json.loads(raw)
expected = {
    "SFC": ("sfc", 128, True, ("socket", "onload", "tcpdirect", "exchange_rss")),
    "DPDK": ("vfio-pci", 256, False, ("dpdk", "exchange_rss")),
}
if expected_mode not in expected:
    raise SystemExit(f"unsupported expected mode: {expected_mode}")
owner, pages, ip_present, receipt_names = expected[expected_mode]
if not (
    state.get("mode") == expected_mode
    and state.get("transition") == "READY"
    and state.get("owner") == owner
    and state.get("hugepages_2mb") == pages
    and state.get("data_ip_present") is ip_present
):
    raise SystemExit(f"{expected_mode} terminal hard gates failed: {state}")
receipts = state.get("hardware_receipts")
if not isinstance(receipts, dict) or any(
    not isinstance(receipts.get(name), dict)
    or receipts[name].get("launch_verified") is not True
    for name in receipt_names
):
    raise SystemExit(f"{expected_mode} launch identity receipts failed: {state}")
PY
}

source "$SCRIPT_DIR/platform-baseline.sh"
source "$SCRIPT_DIR/platform-boot.sh"

case "$ACTION" in
  boot) platform_boot_restore ;;
  boot-enable) platform_boot_enable ;;
  controller-start) start_controller ;;
  controller-check) verify_controller_identity ;;
  controller-stop) controller_stop ;;
  feed-profile)
    case "$TARGET" in direct) start_feed_receiver 1;; unicast-only) start_feed_receiver 0;; *) exit 2;; esac
    ;;
  baseline)
    platform_start_software
    ;;
  preflight)
    assert_runtime_blob
    verify_prepared_runtime_on_host "$EXCHANGE_HOST"
    verify_prepared_runtime_on_host "$TRADER_HOST"
    "$BASE_CTL" preflight "$RUN_ID" stage-c
    "${SSH[@]}" "$EXCHANGE_HOST" bash -s <<'REMOTE'
set -Eeuo pipefail
iface=ens64np0
grep -Fxq 'receive-hashing: on' < <(ethtool -k "$iface")
read -r entries baseline_bad measure_bad < <(
  ethtool -x "$iface" | awk '
    /^[[:space:]]*[0-9]+:/ {
      for (field = 2; field <= NF; ++field) {
        if ($field != (count % 4)) ++baseline_bad
        if ($field != 1) ++measure_bad
        ++count
      }
    }
    END { print count + 0, baseline_bad + 0, measure_bad + 0 }
  '
)
test "$entries" -eq 128
mapfile -t irq_matches < <(
  awk '$NF == "ens64np0-1" { gsub(":", "", $1); print $1 }' /proc/interrupts
)
test "${#irq_matches[@]}" -eq 1
irq="${irq_matches[0]}"
requested_cpu="$(cat "/proc/irq/$irq/smp_affinity_list")"
effective_cpu="$(cat "/proc/irq/$irq/effective_affinity_list")"
irqbalance_state="$(systemctl is-active irqbalance 2>/dev/null || true)"
case "$irqbalance_state" in active|inactive) ;; *) exit 1;; esac
if test "$baseline_bad" -eq 0; then
  table=baseline-0-1-2-3
elif test "$measure_bad" -eq 0 && test "$requested_cpu" = 2 && \
     test "$effective_cpu" = 2 && test "$irqbalance_state" = inactive; then
  table=measure-all-1
else
  printf 'exchange_rss_preflight=FAIL entries=%s baseline_bad=%s measure_bad=%s irq=%s requested_cpu=%s effective_cpu=%s irqbalance=%s\n' \
    "$entries" "$baseline_bad" "$measure_bad" "$irq" "$requested_cpu" "$effective_cpu" "$irqbalance_state" >&2
  exit 1
fi
printf 'exchange_rss_preflight=PASS iface=%s entries=128 table=%s queue=1 irq=%s requested_cpu=%s effective_cpu=%s irqbalance=%s exchange_cpu=2\n' \
  "$iface" "$table" "$irq" "$requested_cpu" "$effective_cpu" "$irqbalance_state"
REMOTE
    echo "transport_preflight=PASS runtime_sha256=$RUNTIME_SHA queue=DEQUE_CV"
    ;;
  deploy)
    assert_runtime_blob
    verify_prepared_runtime_on_host "$EXCHANGE_HOST"
    verify_prepared_runtime_on_host "$TRADER_HOST"
    "$BASE_CTL" deploy-data "$RUN_ID"
    install_runtime_on_host "$EXCHANGE_HOST"
    install_runtime_on_host "$TRADER_HOST"
    "${SSH[@]}" "$EXCHANGE_HOST" bash -s -- \
      "$RUN_DIR" "$RUNTIME_ROOT" "$RUNTIME_SHA" <<'REMOTE'
set -Eeuo pipefail
run_dir="$1"; runtime_root="$2"; runtime_sha="$3"
cd "$run_dir"
tmp="opening-book.checkpoint.tmp.$BASHPID"
cleanup(){ rm -f -- "$tmp"; }
trap cleanup EXIT
"$runtime_root/bin/flle-book-checkpoint" \
  AAPL_NVDA.itch "$tmp" 34200000000000 | tee checkpoint.fixed.txt
test -s "$tmp"
mv -- "$tmp" opening-book.checkpoint
exchange_sha="$(sha256sum "$runtime_root/bin/flle-exchange" | awk '{print $1}')"
generator_sha="$(sha256sum "$runtime_root/bin/flle-book-checkpoint" | awk '{print $1}')"
runtime_manifest_sha="$(sha256sum "$runtime_root/MANIFEST.sha256" | awk '{print $1}')"
checkpoint_sha="$(sha256sum opening-book.checkpoint | awk '{print $1}')"
itch_sha="$(sha256sum AAPL_NVDA.itch | awk '{print $1}')"
test "$exchange_sha" = "$(awk '$2=="bin/flle-exchange" {print $1}' "$runtime_root/MANIFEST.sha256")"
test "$generator_sha" = "$(awk '$2=="bin/flle-book-checkpoint" {print $1}' "$runtime_root/MANIFEST.sha256")"
{
  echo "runtime_sha256=$runtime_sha"
  echo "runtime_manifest_sha256=$runtime_manifest_sha"
  echo "exchange_sha256=$exchange_sha"
  echo "checkpoint_generator_sha256=$generator_sha"
  echo "opening_book_sha256=$checkpoint_sha"
  echo "itch_sha256=$itch_sha"
} >data-plane-input.receipt
sha256sum transport-runtime.tgz opening-book.checkpoint AAPL_NVDA.itch \
  data-plane-input.receipt >transport.deployed.sha256
cat data-plane-input.receipt
REMOTE
    "${SCP[@]}" -3 \
      "$EXCHANGE_HOST:$RUN_DIR/opening-book.checkpoint" \
      "$EXCHANGE_HOST:$RUN_DIR/data-plane-input.receipt" \
      "$TRADER_HOST:$RUN_DIR/"
    "${SSH[@]}" "$TRADER_HOST" \
      "set -eu; cd '$RUN_DIR'; sha256sum transport-runtime.tgz opening-book.checkpoint data-plane-input.receipt >transport.deployed.sha256"
    platform_build_native
    bash "$SCRIPT_DIR/prepare-control-host.sh"
    install_control_workspace
    ;;
  start)
    live_run="$(sed -n 's/^RUN_ID=//p' \
      "$REPO_ROOT/Documents/reports/run-state/02-trading-baseline.env" 2>/dev/null || true)"
    case "$live_run" in
      *-02-trading-platform|*-06-four-path-orders)
        if test "$live_run" != "$RUN_ID"; then
          live_unit="flle-transport-controller-${live_run//_/-}"
          if ! lab_is_quiescent "$live_unit"; then
            echo "live four-path RUN $live_run still holds an incomplete lab; reuse it or run ⑥ first" >&2
            exit 1
          fi
        fi
        ;;
    esac
    keep_exchange=0; keep_gateway=0
    select_exchange_runtime
    if platform_process_running "$EXCHANGE_HOST" exchange "$EXCHANGE_EXECUTABLE" 2>/dev/null; then keep_exchange=1; fi
    if verify_gateway_identity 2>/dev/null; then keep_gateway=1; fi
    start_stage=verify_deployed_inputs
    start_rollback() {
      local original_rc=$? recovery_failed=0
      trap - ERR
      set +e
      echo "TRANSPORT_START_FAILED stage=$start_stage rc=$original_rc" >&2
      if test "$keep_gateway" -eq 0; then
        stop_remote_process "$OBSERVER_HOST" gateway flle_trading.gateway 8088 || recovery_failed=1
      fi
      if systemctl is-active --quiet "$CONTROLLER_UNIT"; then
        systemctl stop "$CONTROLLER_UNIT" || recovery_failed=1
      fi
      for _ in $(seq 1 40); do
        systemctl is-active --quiet "$CONTROLLER_UNIT" || break
        sleep 0.1
      done
      systemctl is-active --quiet "$CONTROLLER_UNIT" && recovery_failed=1
      test -z "$(ss -ltnpH '( sport = :48606 )' 2>/dev/null || true)" || recovery_failed=1
      stop_sfc_clients || recovery_failed=1
      stop_dpdk_client || recovery_failed=1
      stop_remote_process "$TRADER_HOST" trader-auto /flle-trader 48121 || recovery_failed=1
      stop_feed_receiver || recovery_failed=1
      wait_hugepages_zero || recovery_failed=1
      if test "$keep_exchange" -eq 0; then
        stop_remote_process "$EXCHANGE_HOST" exchange /flle-exchange 43120 48120 || recovery_failed=1
      fi
      restore_exchange_rss || recovery_failed=1
      "${SSH[@]}" "$TRADER_HOST" "set -eu; test \"\$(basename \"\$(readlink /sys/bus/pci/devices/0000:03:00.0/driver)\")\" = sfc; ip -4 -o addr show dev ens64np1 | grep -Fq ' 20.1.1.2/24 '; test \"\$(cat /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages)\" = 0" || recovery_failed=1
      if [[ "$recovery_failed" -ne 0 ]]; then
        echo "transport start failed (rc=$original_rc) and rollback did not restore every gate" >&2
        exit 125
      fi
      echo "transport start failed (rc=$original_rc); clients stopped, SFC device baseline restored; retained_exchange=$keep_exchange retained_gateway=$keep_gateway" >&2
      exit "$original_rc"
    }
    trap start_rollback ERR
    verify_deployed_inputs
    start_stage=stop_software_clients
    if platform_is_software; then platform_stop_software_clients; fi
    platform_set_profile TRANSPORT
    start_stage=check_listeners
    if ! platform_process_running "$EXCHANGE_HOST" exchange "$EXCHANGE_EXECUTABLE" 2>/dev/null; then
      stop_foreign_course_listener "$EXCHANGE_HOST" 43120 /flle-exchange
    fi
    stop_foreign_course_listener "$TRADER_HOST" 48121 /flle-trader
    stop_foreign_course_listener "$TRADER_HOST" 48122 /flle-trader
    stop_foreign_course_listener "$TRADER_HOST" 48123 /flle-trader
    stop_foreign_course_listener "$TRADER_HOST" 48124 /flle-trader-tcpdirect
    stop_foreign_course_listener "$TRADER_HOST" 48125 /flle-trader-dpdk
    if ! verify_gateway_identity 2>/dev/null; then
      stop_foreign_course_listener "$OBSERVER_HOST" 8088 flle_trading.gateway
    fi
    start_stage=configure_exchange_rss
    configure_exchange_rss
    start_stage=start_exchange
    start_exchange
    start_stage=start_sfc_clients
    "$0" sfc "$RUN_ID" >/dev/null
    start_stage=start_controller
    start_controller
    start_stage=start_gateway
    start_gateway
    start_stage=check_ready
    start_state="$(collect_status)"
    require_mode_ready SFC "$start_state"
    printf '%s\n' "$start_state"
    trap - ERR
    ;;
  sfc)
    case "$TARGET" in ''|order-only) ;; *) echo 'invalid SFC restoration target' >&2; exit 2;; esac
    if platform_is_software; then "$0" start "$RUN_ID"; exit; fi
    verify_exchange_rss >/dev/null
    # TRANSPORT order clients stay order-only. After SFC is READY, restore the
    # shared receiver and book Guardian so the GUI ladder and IGMP membership
    # return. A mid-session join is a feed gap; resync uses the existing
    # Exchange REPLAY|RESTART. Filter labs still switch that same receiver
    # with feed-guardianctl.
    platform_stop_software_clients || { echo 'SFC_ACTION_FAILED stage=stop_feed_consumers' >&2; exit 1; }
    stop_feed_receiver || { echo 'SFC_ACTION_FAILED stage=stop_feed_receiver' >&2; exit 1; }
    current="$(collect_status)"
    if [[ "$current" == *'"mode":"SFC"'* &&
          "$current" == *'"transition":"READY"'* ]] && posix_clients_current; then
      require_mode_ready SFC "$current"
      if [[ "$TARGET" != order-only ]]; then
        restore_book_feed || exit 1
      fi
      printf '%s\n' "$current"
      exit 0
    fi
    stop_sfc_clients || { echo 'SFC_ACTION_FAILED stage=stop_sfc_clients' >&2; exit 1; }
    stop_dpdk_client || { echo 'SFC_ACTION_FAILED stage=stop_dpdk_client' >&2; exit 1; }
    wait_hugepages_zero || { echo 'SFC_ACTION_FAILED stage=wait_hugepages_zero' >&2; exit 1; }
    "${SSH[@]}" "$TRADER_HOST" "set -eu; test \"\$(basename \"\$(readlink /sys/bus/pci/devices/0000:03:00.0/driver)\")\" = sfc; ip -4 -o addr show dev ens64np1 | grep -Fq ' 20.1.1.2/24 '; sysctl -w vm.nr_hugepages=128 >/dev/null; test \"\$(cat /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages)\" = 128"
    start_sfc_clients || { echo 'SFC_ACTION_FAILED stage=start_sfc_clients' >&2; exit 1; }
    verify_exchange_rss >/dev/null
    if ! current="$(collect_status)"; then
      echo 'SFC_STATUS_COLLECTION_FAILED after client start' >&2
      exit 1
    fi
    require_mode_ready SFC "$current" || {
      printf 'SFC_TERMINAL_GATE_FAILED state=%s\n' "$current" >&2
      exit 1
    }
    if [[ "$TARGET" != order-only ]]; then
      restore_book_feed || exit 1
    fi
    printf '%s\n' "$current"
    ;;
  dpdk)
    case "$TARGET" in ''|order-only) ;; *) echo 'invalid DPDK restoration target' >&2; exit 2;; esac
    # SOFTWARE origin still returns to baseline. TRANSPORT/SFC now keeps a
    # receiver for the GUI book, so a running receiver is not SOFTWARE origin.
    # SFC restore itself brings the receiver and book Guardian back.
    dpdk_recovery=sfc
    if platform_is_software; then
      dpdk_recovery=baseline
    fi
    dpdk_stage=prepare_sfc
    dpdk_rollback() {
      local original_rc=$?
      trap - ERR
      # Command substitutions propagate failure; only the owning shell recovers.
      if (( BASH_SUBSHELL > 0 )); then exit "$original_rc"; fi
      set +e
      printf 'DPDK_ACTION_FAILED stage=%s rc=%s\n' "$dpdk_stage" "$original_rc" >&2
      if "$0" "$dpdk_recovery" "$RUN_ID" "$TARGET" >/dev/null; then
        printf 'DPDK_RECOVERY_OK profile=%s\n' "$dpdk_recovery" >&2
        exit "$original_rc"
      fi
      printf 'DPDK_RECOVERY_FAILED profile=%s; inspect RUN logs before retry\n' "$dpdk_recovery" >&2
      exit 125
    }
    trap dpdk_rollback ERR
    if platform_is_software; then "$0" start "$RUN_ID" >/dev/null; fi
    verify_exchange_rss >/dev/null
    current="$(collect_status)"
    if [[ "$current" == *'"mode":"DPDK"'* &&
          "$current" == *'"transition":"READY"'* ]]; then
      require_mode_ready DPDK "$current"
      printf '%s\n' "$current"
      exit 0
    fi
    dpdk_stage=stop_feed_consumers
    platform_stop_software_clients
    dpdk_stage=stop_sfc_clients
    stop_sfc_clients
    dpdk_stage=stop_feed_receiver
    stop_feed_receiver
    dpdk_stage=stop_dpdk_client
    stop_dpdk_client
    dpdk_stage=wait_hugepages_zero
    wait_hugepages_zero
    dpdk_stage=start_dpdk_client
    start_dpdk_client
    dpdk_stage=verify_exchange_rss
    verify_exchange_rss >/dev/null
    dpdk_stage=collect_status
    current="$(collect_status)"
    dpdk_stage=require_mode_ready
    require_mode_ready DPDK "$current"
    printf '%s\n' "$current"
    trap - ERR
    ;;
  reset-paper)
    # Explicit user reset: restart order-only clients without changing NIC mode.
    exec 9>/var/tmp/flle-ch08-10.lock
    flock -n 9 || { echo '过滤实验正在运行，请结束实验后再清空交易。' >&2; exit 75; }
    "${SSH[@]}" "$TRADER_HOST" "set -eu; if ps -eo comm | grep -q '^mold_filter'; then echo 'filter process active' >&2; exit 75; fi; test ! -e /var/tmp/flle-market-filter.cmd; if ip -details link show dev ens64np1 2>/dev/null | grep -q prog/xdp; then echo 'XDP active' >&2; exit 75; fi"
    "${SSH[@]}" root@10.1.1.11 "! pgrep -x simple_switch"
    if platform_is_software; then
      platform_stop_software_clients
      platform_start_software >/dev/null
      state="$(platform_software_status)"
      python3 -c 'import json,sys; x=json.loads(sys.argv[1]); x["software_clients_ready"] or sys.exit("software clients not ready"); x["paper_reset"]=True; print(json.dumps(x,separators=(",",":")))' "$state"
      exit
    fi
    current="$(collect_status)"
    reset_mode="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["mode"])' <<<"$current")"
    require_mode_ready "$reset_mode" "$current"
    if [[ "$reset_mode" == SFC ]]; then
      stop_sfc_clients
      start_sfc_clients
      reset_ports=(48122 48123 48124)
    else
      stop_dpdk_client
      wait_hugepages_zero
      start_dpdk_client
      reset_ports=(48125)
    fi
    for port in "${reset_ports[@]}"; do
      management_command "$port" STATE | python3 -c '
import json,sys
state=json.load(sys.stdin)
positions=state.get("positions")
if not isinstance(positions,dict) or any(positions.get(s)!=0 for s in ("AAPL","NVDA")):
    raise SystemExit("client positions were not cleared")
if state.get("stats",{}).get("orders")!=0:
    raise SystemExit("client orders were not cleared")
'
    done
    current="$(collect_status)"; require_mode_ready "$reset_mode" "$current"
    python3 -c 'import json,sys; s=json.load(sys.stdin); s["paper_reset"]=True; print(json.dumps(s,separators=(",",":")))' <<<"$current"
    ;;
  measure)
    verify_deployed_inputs
    # A platform can be measured again. Keep earlier immutable receipt trees;
    # each formal measurement must start with an empty per-cell namespace.
    formal_receipt_archive="$(date -u +%Y%m%dT%H%M%S.%NZ)-$$"
    for receipt_host in "$EXCHANGE_HOST" "$TRADER_HOST"; do
      "${SSH[@]}" "$receipt_host" bash -s -- "$RUN_DIR" "$formal_receipt_archive" <<'REMOTE'
set -Eeuo pipefail
cd "$1"
for tree in native-receipts native-exchange-receipts native-exchange-staging; do
  if test -e "$tree"; then
    test -d "$tree" && test ! -L "$tree"
    mkdir -p "native-receipts-history/$2"
    test ! -e "native-receipts-history/$2/$tree"
    mv "$tree" "native-receipts-history/$2/$tree"
  fi
done
REMOTE
    done
    stop_remote_process "$OBSERVER_HOST" gateway flle_trading.gateway 8088
    controller_stop
    formal_exchange_session="$(exchange_playing_session)"
    formal_cleanup_armed=1
    formal_emergency_cleanup() {
      local original_rc=$? cleanup_failed=0 recovery_state=""
      trap - EXIT INT TERM HUP
      if [[ "$formal_cleanup_armed" == 1 ]]; then
        set +e
        reconcile_exchange_playing "$formal_exchange_session" || cleanup_failed=1
        recovery_state="$("$0" sfc "$RUN_ID")" || cleanup_failed=1
        if [[ -n "$recovery_state" ]]; then
          require_mode_ready SFC "$recovery_state" || cleanup_failed=1
        else
          cleanup_failed=1
        fi
        if [[ "$cleanup_failed" -ne 0 ]]; then
          echo "formal emergency cleanup did not restore every replay/SFC gate" >&2
          exit 125
        fi
      fi
      exit "$original_rc"
    }
    trap formal_emergency_cleanup EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM
    trap 'exit 129' HUP
    measure_rc=0
    python3 "$SCRIPT_DIR/measure_four_transports.py" --run-id "$RUN_ID" \
      --control-script "$0" \
      --output-root "$REPO_ROOT/Documents/reports/course-runs" || measure_rc=$?
    replay_recovery_failed=0
    reconcile_exchange_playing "$formal_exchange_session" || replay_recovery_failed=1
    recovery_state=""
    if ! recovery_state="$("$0" sfc "$RUN_ID")"; then
      echo "formal run failed (rc=$measure_rc) and SFC recovery failed" >&2
      exit 125
    fi
    require_mode_ready SFC "$recovery_state" || {
      echo "formal run recovery did not pass the SFC hard gates" >&2
      exit 125
    }
    if [[ "$replay_recovery_failed" -ne 0 ]]; then
      echo "formal run failed to restore the Exchange replay; bounded pause lease remains armed" >&2
      exit 125
    fi
    verify_deployed_inputs
    start_controller
    start_gateway
    formal_cleanup_armed=0
    trap - EXIT INT TERM HUP
    if test "$measure_rc" -ne 0; then exit "$measure_rc"; fi
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
      capture_id="$(date -u +%Y%m%dT%H%M%S.%NZ)-$$"
      manifest="$(capture_native_receipt "$TARGET:standalone:$capture_id:evidence")"
      remote_relative="$(python3 -c 'import json,sys,pathlib; print(pathlib.PurePosixPath(json.loads(sys.argv[1])["files"][0]["path"]).parent)' "$manifest")"
      case "$remote_relative" in standalone-native-receipts/standalone-*) ;; *) echo "invalid standalone native receipt path" >&2; exit 1;; esac
      mkdir -p "$EXPORT_DIR/$(dirname -- "$remote_relative")"
      "${SCP[@]}" -r \
        "$TRADER_HOST:$RUN_DIR/$remote_relative" \
        "$EXPORT_DIR/$(dirname -- "$remote_relative")/"
      python3 - "$manifest" "$EXPORT_DIR" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

manifest = json.loads(sys.argv[1])
output = Path(sys.argv[2])
expected_paths = {item["path"] for item in manifest["files"]}
if len(expected_paths) != len(manifest["files"]):
    raise SystemExit("standalone native manifest repeats a file path")
actual_paths = {
    path.relative_to(output).as_posix()
    for path in output.rglob("*")
    if path.is_file()
}
if actual_paths != expected_paths:
    raise SystemExit(
        "standalone native file set mismatch: "
        f"missing={sorted(expected_paths - actual_paths)} "
        f"unexpected={sorted(actual_paths - expected_paths)}"
    )
for item in manifest["files"]:
    target = output / item["path"]
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
sealed_files = sorted(path for path in output.rglob("*") if path.is_file())
sha_path = output / "SHA256SUMS"
sha_path.write_text(
    "".join(
        f"{hashlib.sha256(path.read_bytes()).hexdigest()}  "
        f"{path.relative_to(output).as_posix()}\n"
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
  retire-snapshot-controller)
    platform_retire_snapshot_controller
    ;;
  reuse-state)
    controller_ok=0; gateway_ok=0; quiescent=0
    verify_controller_identity >/dev/null 2>&1 && controller_ok=1
    verify_gateway_identity >/dev/null 2>&1 && gateway_ok=1
    control="$(collect_status 2>/dev/null || true)"
    api="$(curl -fsS --max-time 2 "http://$TELEMETRY_HOST:8088/api/transport-lab" 2>/dev/null || true)"
    lab_is_quiescent >/dev/null 2>&1 && quiescent=1
    python3 "$APP_DIR/flle_trading/transport_reuse.py" \
      "$controller_ok" "$gateway_ok" "$quiescent" "$control" "$api"
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
    if platform_is_software; then
      "$BASE_CTL" verify "$RUN_ID"
      verify_deployed_inputs
      # Restore may inspect a verified old session before explicitly upgrading it.
      # All normal verification and measurement callers require the A/B schema.
      if test "$TARGET" != --allow-legacy-market; then platform_verify_market_network; fi
      state="$(platform_software_status)"
      [[ "$state" == *'"transition":"READY"'* ]]
      printf '%s\n' "$state"
      exit
    fi
    verify_exchange_rss >/dev/null
    verify_exchange_runtime
    state="$(collect_status)"
    mode="$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["mode"])' "$state")"
    require_mode_ready "$mode" "$state"
    verify_deployed_inputs
    printf '%s\n' "$state"
    ;;
  stop)
    platform_boot_disable
    platform_stop_software_clients
    stop_sfc_clients
    stop_dpdk_client
    wait_hugepages_zero
    stop_remote_process "$OBSERVER_HOST" gateway flle_trading.gateway 8088
    stop_remote_process "$EXCHANGE_HOST" exchange /flle-exchange 43120 48120
    stop_feed_receiver
    restore_exchange_rss
    controller_stop
    "${SSH[@]}" "$TRADER_HOST" "set -eu; test \"\$(basename \"\$(readlink /sys/bus/pci/devices/0000:03:00.0/driver)\")\" = sfc; ip -4 -o addr show dev ens64np1 | grep -Fq ' 20.1.1.2/24 '; test \"\$(cat /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages)\" = 0; for port in 48122 48123 48124 48125; do test -z \"\$(ss -ltnpH \"( sport = :\$port )\" 2>/dev/null || true)\"; done; ! mountpoint -q /mnt/huge"
    "${SSH[@]}" "$EXCHANGE_HOST" "set -eu; test \"\$(basename \"\$(readlink /sys/bus/pci/devices/0000:03:00.0/driver)\")\" = sfc; ip -4 -o addr show dev ens64np0 | grep -Fq ' 20.1.1.1/24 '; for port in 43120 48120; do test -z \"\$(ss -ltnpH \"( sport = :\$port )\" 2>/dev/null || true)\"; done; if test -s '$RUN_DIR/exchange-rss.receipt'; then test -s '$RUN_DIR/exchange-rss-baseline.txt'; cmp -s '$RUN_DIR/exchange-rss-baseline.txt' '$RUN_DIR/exchange-rss-restored.txt'; fi; ping -I ens64np0 -c 3 -W 1 20.1.1.2 >/dev/null"
    echo '{"mode":"SFC","transition":"STOPPED","owner":"sfc","hardware_receipts":{}}'
    ;;
  *)
    echo "usage: $0 {preflight|deploy|start|sfc|dpdk|reset-paper|measure|attest|native-receipt|reuse-state|status|verify|stop} RUN_ID [TARGET [LOCAL_EXPORT_DIR]]" >&2
    exit 2
    ;;
esac
