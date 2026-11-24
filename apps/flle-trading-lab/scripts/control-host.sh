#!/usr/bin/env bash
# Sourced by transport_labctl.sh. Runtime control belongs to the Trader host.
CONTROL_LOCAL=0
if ip -4 -o addr show | awk '{print $4}' | grep -Fxq '10.1.1.2/24'; then
  CONTROL_LOCAL=1
fi
CONTROL_WORKSPACE="$RUN_DIR/control"
CONTROL_SCRIPT="$CONTROL_WORKSPACE/apps/flle-trading-lab/scripts/transport_labctl.sh"

# On .2, execute local operations directly; preserve ssh's command-string and
# stdin semantics for the existing audited bash -s helpers. Other hosts keep SSH.
control_host_command() {
  local host="$1"; shift
  if [[ "$CONTROL_LOCAL" == 1 && "${host#*@}" == 10.1.1.2 ]]; then
    bash -c "$*" 8>&- 9>&-
  else
    command ssh -o BatchMode=yes -o StrictHostKeyChecking=yes \
      -o ConnectTimeout=8 "$host" "$@"
  fi
}
SSH=(control_host_command)

install_control_workspace() {
  local remote_app="$CONTROL_WORKSPACE/apps/flle-trading-lab"
  "${SSH[@]}" "$TRADER_HOST" "mkdir -p '$remote_app/scripts' '$remote_app/flle_trading'"
  "${SCP[@]}" "$APP_DIR"/scripts/*.sh "$APP_DIR"/scripts/*.py "$TRADER_HOST:$remote_app/scripts/"
  "${SCP[@]}" "$APP_DIR"/flle_trading/*.py "$TRADER_HOST:$remote_app/flle_trading/"
  "${SSH[@]}" "$TRADER_HOST" "cd '$CONTROL_WORKSPACE'; find apps -type f -print0 | sort -z | xargs -0 sha256sum >MANIFEST.sha256"
}

# Local daemons must retain neither the ownership lock (8) nor the filter/reset
# lock (9). The parent still holds both until its operation has returned.
if [[ "$CONTROL_LOCAL" == 1 ]]; then
  RUNTIME_BLOB="$RUN_DIR/transport-runtime.tgz"
else
  # No runtime operation is performed by an HTTP service on the jump host.
  case "$ACTION" in
    stop|reuse-state|retire-snapshot-controller)
      if "${SSH[@]}" "$TRADER_HOST" "test -f '$CONTROL_SCRIPT'"; then
        exec ssh -o BatchMode=yes -o StrictHostKeyChecking=yes "$TRADER_HOST" \
          bash "$CONTROL_SCRIPT" "$ACTION" "$RUN_ID" "$TARGET" "$EXPORT_DIR"
      fi
      # Snapshot/partial-deploy recovery can inspect and release owned remote
      # state before the per-run workspace exists; it never starts a local HTTP service.
      ;;
    baseline|start|sfc|dpdk|reset-paper|status|verify|feed-profile|controller-start|controller-check|controller-stop|boot|boot-enable)
      case "$ACTION" in
        start|sfc|feed-profile|boot-enable)
          # Jump-host edits only take effect after the per-RUN copy on .2 is refreshed.
          install_control_workspace
          ;;
      esac
      exec ssh -o BatchMode=yes -o StrictHostKeyChecking=yes "$TRADER_HOST" \
        bash "$CONTROL_SCRIPT" "$ACTION" "$RUN_ID" "$TARGET" "$EXPORT_DIR"
      ;;
  esac
fi

controller_stop() {
  if [[ "$CONTROL_LOCAL" != 1 ]]; then
    if "${SSH[@]}" "$TRADER_HOST" "test -f '$CONTROL_SCRIPT'"; then
      "${SSH[@]}" "$TRADER_HOST" bash "$CONTROL_SCRIPT" controller-stop "$RUN_ID"
    else
      "${SSH[@]}" "$TRADER_HOST" "! systemctl is-active --quiet '$CONTROLLER_UNIT' && test -z \"\$(ss -ltnpH '( sport = :48606 )')\""
    fi
    return
  fi
  if systemctl is-active --quiet "$CONTROLLER_UNIT"; then
    verify_controller_identity || return 1
    systemctl stop "$CONTROLLER_UNIT"
  fi
  ! systemctl is-active --quiet "$CONTROLLER_UNIT" || return 1
  test -z "$(ss -ltnpH '( sport = :48606 )')"
}

verify_feed_receiver() {
  "${SSH[@]}" "$TRADER_HOST" "python3 '$CONTROL_WORKSPACE/apps/flle-trading-lab/scripts/verify-feed-receiver.py' '$RUN_DIR' '${1:-1}'"
}

start_feed_receiver() {
  local multicast="${1:-1}"
  if platform_process_running "$TRADER_HOST" feed-receiver "$RUN_DIR/flle-feed-receiver"; then
    if "${SSH[@]}" "$TRADER_HOST" "grep -Fxq '$multicast' '$RUN_DIR/feed-multicast.profile'"; then
      if platform_is_software; then verify_feed_receiver "$multicast" || return 1; fi
      return
    fi
    stop_feed_receiver
  fi
  start_remote_process "$TRADER_HOST" feed-receiver \
    "'$RUN_DIR/flle-feed-receiver' --socket '$RUN_DIR/feed.sock' --multicast-receiver $multicast --telemetry-host '$TELEMETRY_HOST'"
  "${SSH[@]}" "$TRADER_HOST" "set -eu; for _ in \$(seq 1 40); do if test -S '$RUN_DIR/feed.sock' && grep -q '^feed_receiver=READY ' '$RUN_DIR/feed-receiver.log'; then printf '%s\\n' '$multicast' >'$RUN_DIR/feed-multicast.profile'; exit 0; fi; sleep 0.1; done; cat '$RUN_DIR/feed-receiver.log' >&2; exit 1"
  if platform_is_software; then verify_feed_receiver "$multicast" || return 1; fi
}

stop_feed_receiver() {
  stop_remote_process "$TRADER_HOST" feed-receiver /flle-feed-receiver || return 1
  # A shutdown or crash leaves the pathname after the kernel socket is gone.
  # Never unlink a socket still owned by any process, including an unknown one.
  "${SSH[@]}" "$TRADER_HOST" python3 - "$RUN_DIR/feed.sock" <<'PY'
from pathlib import Path
import stat
import sys

path = Path(sys.argv[1])
try:
    before = path.lstat()
except FileNotFoundError:
    raise SystemExit(0)
if not stat.S_ISSOCK(before.st_mode):
    raise SystemExit('refusing unexpected feed socket path: ' + str(path))
for line in Path('/proc/net/unix').read_text().splitlines()[1:]:
    fields = line.split(maxsplit=7)
    if len(fields) == 8 and fields[7] == str(path):
        raise SystemExit('feed socket is still owned: ' + str(path))
after = path.lstat()
if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
    raise SystemExit('feed socket changed during cleanup')
path.unlink()
print('FEED_SOCKET_STALE_REMOVED ' + str(path))
PY
}

start_feed_book_guardian() {
  # TRANSPORT order clients do not apply the GUI book. Reuse the Chapter 07
  # Guardian: AUTO + feed.sock, strategy off, so the ladder updates without
  # automatic orders.
  if platform_process_running "$TRADER_HOST" trader-auto "$RUN_DIR/flle-trader"; then
    if "${SSH[@]}" "$TRADER_HOST" bash -s -- "$RUN_DIR" <<'REMOTE'
set -eu
run_dir="$1"
pid="$(cat "$run_dir/trader-auto.pid")"
command="$(tr '\0' ' ' <"/proc/$pid/cmdline")"
case "$command" in
  *"--feed-socket $run_dir/feed.sock"*"--strategy-enabled 0"*) exit 0;;
esac
exit 1
REMOTE
    then
      return 0
    fi
    stop_remote_process "$TRADER_HOST" trader-auto /flle-trader 48121 || return 1
  fi
  start_remote_process "$TRADER_HOST" trader-auto \
    "taskset -c 2,3 '$RUN_DIR/flle-trader' --role AUTO --feed-socket '$RUN_DIR/feed.sock' --strategy-enabled 0 --data-ip 20.1.1.2 --exchange-data-ip 20.1.1.1 --management-ip 10.1.1.2 --telemetry-host '$TELEMETRY_HOST' --book-checkpoint '$RUN_DIR/opening-book.checkpoint' --management-port 48121 --user-ref-base 1 --user-ref-span 2000000000 --clordid-prefix AUTO --order-transport-label POSIX_SOCKET --order-queue DEQUE_CV --order-cpu 2 --management-cpu 3"
  wait_remote_listener "$TRADER_HOST" trader-auto /flle-trader 48121
}

book_feed_healthy() {
  # Guardian STATE, not the GUI snapshot: mid-session join is a gap even when
  # Exchange is still PLAYING and the last frozen ladder looks HEALTHY.
  local state later
  state="$(management_command 48121 STATE 2>/dev/null || true)"
  sleep 0.25
  later="$(management_command 48121 STATE 2>/dev/null || true)"
  python3 -c 'import json,sys
state=json.loads(sys.argv[1])
strategy=state.get("strategy") if isinstance(state.get("strategy"), dict) else {}
if state.get("integrity") != "HEALTHY" or state.get("trading_gate") != "OPEN":
    raise SystemExit(1)
if strategy.get("enabled") is not False:
    raise SystemExit(1)
if int(state.get("next_expected") or 0) <= 0:
    raise SystemExit(1)
if not state.get("session"):
    raise SystemExit(1)
later=json.loads(sys.argv[2])
if later.get("session") != state["session"] or later.get("integrity") != "HEALTHY" or later.get("trading_gate") != "OPEN":
    raise SystemExit(1)
if later.get("strategy", {}).get("enabled") is not False:
    raise SystemExit(1)
if int(later.get("next_expected") or 0) <= int(state["next_expected"]):
    raise SystemExit(1)
' "$state" "$later"
}

restart_exchange_replay() {
  python3 - "$EXCHANGE_HOST" <<'PY'
import json
import socket
import sys

host = sys.argv[1].split("@", 1)[-1]
with socket.create_connection((host, 48120), timeout=3) as connection:
    connection.sendall(b"REPLAY|RESTART\n")
    payload = bytearray()
    while not payload.endswith(b"\n"):
        chunk = connection.recv(65536)
        if not chunk:
            break
        payload.extend(chunk)
state = json.loads(payload.decode("ascii"))
if state.get("ok") is not True:
    raise SystemExit(state)
print(state.get("session") or state.get("replay_status") or "RESTARTED")
PY
}

resync_book_feed() {
  local _
  for _ in $(seq 1 32); do
    book_feed_healthy && return 0
    sleep 0.25
  done
  restart_exchange_replay >/dev/null || return 1
  for _ in $(seq 1 100); do
    book_feed_healthy && return 0
    sleep 0.25
  done
  echo 'book Guardian did not become HEALTHY/OPEN after replay restart' >&2
  return 1
}

restore_book_feed() {
  start_feed_receiver 1 || { echo 'SFC_ACTION_FAILED stage=start_feed_receiver' >&2; return 1; }
  start_feed_book_guardian || { echo 'SFC_ACTION_FAILED stage=start_feed_book_guardian' >&2; return 1; }
  resync_book_feed || { echo 'SFC_ACTION_FAILED stage=resync_book_feed' >&2; return 1; }
}
