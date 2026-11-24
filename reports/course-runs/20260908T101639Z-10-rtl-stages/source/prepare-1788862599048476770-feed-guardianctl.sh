#!/usr/bin/env bash
# Activate the already-deployed feed guardian; never build or replace the platform.
set -Eeuo pipefail
cd /financial-low-latency
source Documents/newDoc/assets/common/flle-remote.sh

ACTION="${1:-direct}"
case "$ACTION" in direct) MULTICAST=1;; unicast-only) MULTICAST=0;; *) echo 'usage: feed-guardianctl.sh direct|unicast-only' >&2; exit 2;; esac
FEED_CHECK="${2:-wait-feed}"
case "$FEED_CHECK" in wait-feed|--defer-feed-check) ;; *) echo 'invalid feed check option' >&2; exit 2;; esac
STATE=Documents/reports/run-state/02-trading-baseline.env
test -s "$STATE"
PARENT_RUN_ID="$(sed -n 's/^RUN_ID=//p' "$STATE")"
[[ "$PARENT_RUN_ID" =~ ^[A-Za-z0-9._-]+-(02-trading-platform|06-four-path-orders)$ ]]
RUN_DIR="/var/tmp/flle-trading-lab-$PARENT_RUN_ID"
ADDON="$RUN_DIR"
APP=apps/flle-trading-lab
API=http://10.1.1.101:8088
CTL=apps/flle-trading-lab/scripts/transport_labctl.sh
BINARY_SHA="$(ssh -n "${FLLE_SSH_OPTS[@]}" root@10.1.1.2 "set -eu; cd '$RUN_DIR'; sha256sum -c deployed.sha256 >/dev/null; sha256sum flle-trader" | awk '{print $1}')"
TMP="$(mktemp -d)"
cleanup_local(){ find "$TMP" -mindepth 1 -delete 2>/dev/null || true; rmdir "$TMP" 2>/dev/null || true; }
trap cleanup_local EXIT

status="$(bash "$CTL" status "$PARENT_RUN_ID")"
python3 -c 'import json,sys; x=json.loads(sys.argv[1]); assert (x["mode"],x["transition"],x["owner"]) == ("SFC","READY","sfc")' "$status"

# Network reception belongs to the shared receiver, including the RTL profile.
bash "$CTL" feed-profile "$PARENT_RUN_ID" "$ACTION"

stop_owned() {
  local host="$1" name="$2" expected="$3" port="$4"
  ssh "${FLLE_SSH_OPTS[@]}" "root@$host" bash -s -- "$RUN_DIR" "$name" "$expected" "$port" <<'REMOTE'
set -Eeuo pipefail
run_dir="$1"; name="$2"; expected="$3"; port="$4"
pidfile="$run_dir/$name.pid"; identity="$run_dir/$name.identity"
listener="$(ss -ltnpH "( sport = :$port )" 2>/dev/null || true)"
if test ! -s "$pidfile"; then
  test -z "$listener" || { echo "unowned listener on $port" >&2; exit 1; }
  exit 0
fi
IFS= read -r pid <"$pidfile"
read -r pid_field start_field boot_field extra <"$identity"
test -z "${extra:-}"; test "$pid_field" = "pid=$pid"
case "$pid" in ''|*[!0-9]*) exit 1;; esac
test -r "/proc/$pid/cmdline" || { rm -f -- "$pidfile" "$identity"; test -z "$listener"; exit; }
command="$(tr '\0' ' ' <"/proc/$pid/cmdline")"
case "$command" in *"$run_dir"*) ;; *) echo "refusing mismatched $name run pid=$pid" >&2; exit 1;; esac
case "$command" in *"$expected"*) ;; *) echo "refusing mismatched $name command pid=$pid" >&2; exit 1;; esac
test "$(awk '{print $22}' "/proc/$pid/stat")" = "${start_field#start_ticks=}"
test "$(cat /proc/sys/kernel/random/boot_id)" = "${boot_field#boot_id=}"
kill -INT "$pid"
for _ in $(seq 1 40); do kill -0 "$pid" 2>/dev/null || break; sleep 0.25; done
if kill -0 "$pid" 2>/dev/null; then
  test "$(awk '{print $22}' "/proc/$pid/stat")" = "${start_field#start_ticks=}"
  kill -KILL "$pid"
fi
for _ in $(seq 1 40); do kill -0 "$pid" 2>/dev/null || break; sleep 0.1; done
! kill -0 "$pid" 2>/dev/null
test -z "$(ss -ltnpH "( sport = :$port )" 2>/dev/null || true)"
rm -f -- "$pidfile" "$identity"
REMOTE
}

# GUI and feed-integrity support were installed in Chapter 02.
ssh -n "${FLLE_SSH_OPTS[@]}" root@10.1.1.101 "cd '$RUN_DIR' && sha256sum -c source.sha256 >/dev/null"
curl -fsS "$API/api/state" | python3 -c 'import json,sys; assert "integrity" in (json.load(sys.stdin).get("feed") or {})'

guardian_ok="$(ssh "${FLLE_SSH_OPTS[@]}" root@10.1.1.2 bash -s -- "$RUN_DIR" "$ADDON" "$MULTICAST" <<'REMOTE'
set -Eeuo pipefail
run_dir="$1"; addon="$2"; multicast="$3"; ok=0
if test -s "$run_dir/trader-auto.pid"; then
  IFS= read -r pid <"$run_dir/trader-auto.pid"
  if test -r "/proc/$pid/cmdline"; then
    command="$(tr '\0' ' ' <"/proc/$pid/cmdline")"
    case "$command" in *"$addon/flle-trader"*"--feed-socket $run_dir/feed.sock"*"--strategy-enabled 0"*) ok=1;; esac
  fi
fi
printf '%s\n' "$ok"
REMOTE
)"
if test "$guardian_ok" != 1; then
  stop_owned 10.1.1.2 trader-auto /flle-trader 48121
  ssh "${FLLE_SSH_OPTS[@]}" root@10.1.1.2 bash -s -- "$RUN_DIR" "$ADDON" "$MULTICAST" <<'REMOTE'
set -Eeuo pipefail
run_dir="$1"; addon="$2"; multicast="$3"; cd "$run_dir"
nohup taskset -c 2,3 "$addon/flle-trader" \
  --role AUTO --feed-socket "$run_dir/feed.sock" --strategy-enabled 0 \
  --data-ip 20.1.1.2 --exchange-data-ip 20.1.1.1 \
  --management-ip 10.1.1.2 --telemetry-host 10.1.1.101 \
  --book-checkpoint "$run_dir/opening-book.checkpoint" \
  --management-port 48121 \
  --user-ref-base 1 \
  --user-ref-span 2000000000 --clordid-prefix AUTO \
  --order-transport-label POSIX_SOCKET --order-queue DEQUE_CV \
  --order-cpu 2 --management-cpu 3 \
  </dev/null >trader-auto.log 2>&1 &
pid=$!; start="$(awk '{print $22}' "/proc/$pid/stat")"; boot="$(cat /proc/sys/kernel/random/boot_id)"
printf '%s\n' "$pid" >trader-auto.pid
printf 'pid=%s start_ticks=%s boot_id=%s\n' "$pid" "$start" "$boot" >trader-auto.identity
for _ in $(seq 1 80); do
  case "$(ss -ltnpH '( sport = :48121 )' 2>/dev/null || true)" in *"pid=$pid,"*) exit 0;; esac
  sleep 0.25
done
tail -n 30 trader-auto.log >&2; exit 1
REMOTE
fi

if test "$FEED_CHECK" = wait-feed; then
  python3 Documents/newDoc/assets/common/wait-feed-state.py "$API/api/state" HEALTHY --timeout 25 >"$TMP/feed-state.json" || {
    printf 'guardian feed check failed; last observed state:\n' >&2
    cat "$TMP/feed-state.json" >&2
    exit 1
  }
fi
ready=0
for _ in $(seq 1 40); do
  state="$(curl -fsS "$API/api/state")"
  if python3 -c 'import json,sys; x=json.loads(sys.argv[1]); assert x["strategy"]["enabled"] is False; assert x["health"]["trader_auto"]["status"] == "ONLINE"' "$state" 2>/dev/null; then
    ready=1; break
  fi
  sleep 0.25
done
test "$ready" -eq 1
if test "$FEED_CHECK" = --defer-feed-check; then
  printf 'guardian=PROCESS_READY feed_check=DEFERRED profile=%s parent_run=%s binary_sha256=%s\n' "$ACTION" "$PARENT_RUN_ID" "$BINARY_SHA"
else
  printf 'guardian=READY profile=%s parent_run=%s binary_sha256=%s\n' "$ACTION" "$PARENT_RUN_ID" "$BINARY_SHA"
fi
