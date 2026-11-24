#!/usr/bin/env bash
# Sourced by transport_labctl.sh: one deployed platform, two experiment profiles.
platform_is_software() {
  if [[ "$CONTROL_LOCAL" != 1 ]]; then
    "${SSH[@]}" "$TRADER_HOST" "grep -Fxq SOFTWARE '$CONTROL_DIR/experiment-profile'"
    return
  fi
  test -f "$CONTROL_DIR/experiment-profile" &&
    grep -Fxq SOFTWARE "$CONTROL_DIR/experiment-profile"
}
platform_set_profile() {
  case "$1" in SOFTWARE|TRANSPORT) ;; *) return 2;; esac
  mkdir -p "$CONTROL_DIR"
  printf '%s\n' "$1" >"$CONTROL_DIR/experiment-profile.tmp.$BASHPID"
  mv -- "$CONTROL_DIR/experiment-profile.tmp.$BASHPID" "$CONTROL_DIR/experiment-profile"
}
platform_process_running() {
  local host="$1" name="$2" expected="$3"
  "${SSH[@]}" "$host" bash -s -- "$RUN_DIR" "$name" "$expected" <<'REMOTE'
set -Eeuo pipefail
run="$1"; name="$2"; expected="$3"
test -s "$run/$name.pid" && test -s "$run/$name.identity" || exit 1
IFS= read -r pid <"$run/$name.pid"
read -r p s b extra <"$run/$name.identity"
test -z "${extra:-}" && test "$p" = "pid=$pid"
case "$pid" in ''|*[!0-9]*) exit 1;; esac
test -r "/proc/$pid/cmdline"
test "$(awk '{print $22}' "/proc/$pid/stat")" = "${s#start_ticks=}"
test "$(cat /proc/sys/kernel/random/boot_id)" = "${b#boot_id=}"
test "$(readlink -f "/proc/$pid/exe")" = "$expected"
REMOTE
}
platform_build_native() {
  # All software/Feed capabilities are built now, never during a later filter lab.
  "${SSH[@]}" "$OBSERVER_HOST" "set -eu; cd '$RUN_DIR'; make clean test tools"
  "${SCP[@]}" -3 "$OBSERVER_HOST:$RUN_DIR/build/flle-trader" "$OBSERVER_HOST:$RUN_DIR/build/flle-feed-receiver" "$TRADER_HOST:$RUN_DIR/"
  # The software course uses the freshly built A/B Exchange. Keep the frozen
  # transport package intact for the separately scheduled Chapter 05 migration.
  "${SCP[@]}" -3 "$OBSERVER_HOST:$RUN_DIR/build/flle-exchange" "$EXCHANGE_HOST:$RUN_DIR/flle-exchange.native"
  "${SSH[@]}" "$EXCHANGE_HOST" "set -eu; cd '$RUN_DIR'; mv -T flle-exchange.native flle-exchange; sha256sum flle-exchange AAPL_NVDA.itch AAPL_NVDA.manifest.json opening-book.checkpoint >deployed.sha256"
  "${SSH[@]}" "$TRADER_HOST" "set -eu; cd '$RUN_DIR'; sha256sum flle-trader flle-feed-receiver opening-book.checkpoint >deployed.sha256"
}
platform_verify_market_network() {
  verify_feed_receiver 1 || return
  platform_verify_exchange_network
}
platform_verify_exchange_network() {
  platform_process_running "$EXCHANGE_HOST" exchange "$RUN_DIR/flle-exchange" || return
  "${SSH[@]}" "$EXCHANGE_HOST" "cd '$RUN_DIR' && sha256sum -c deployed.sha256 >/dev/null" || return
  python3 - "$EXCHANGE_HOST" <<'PY'
import json, socket, sys
with socket.create_connection((sys.argv[1].split('@')[-1], 48120), timeout=3) as connection:
    connection.sendall(b'STATE\n')
    s = json.loads(connection.makefile('rb').readline(1048576))
expected = dict(market_schema="udp-multicast-ab-v1",
               market_group_a="233.74.125.32", market_port_a=31032,
               market_group_b="233.74.125.33", market_port_b=31033)
if any(s.get(key) != value for key, value in expected.items()):
    raise SystemExit("A/B platform upgrade required: Exchange endpoints do not match the course")
print("market_network=UDP_MULTICAST_AB A=233.74.125.32:31032 B=233.74.125.33:31033")
PY
}
platform_start_exchange() {
  if ! platform_process_running "$EXCHANGE_HOST" exchange "$RUN_DIR/flle-exchange"; then
    start_remote_process "$EXCHANGE_HOST" exchange \
      "taskset -c 2 '$RUN_DIR/flle-exchange' --telemetry-host '$TELEMETRY_HOST' --replay-file '$RUN_DIR/AAPL_NVDA.itch' --book-checkpoint '$RUN_DIR/opening-book.checkpoint' --market-date 2026-06-12 --market-mode MULTICAST_A --replay-speed 1"
  fi
  wait_remote_listener "$EXCHANGE_HOST" exchange /flle-exchange 43120
  wait_remote_listener "$EXCHANGE_HOST" exchange /flle-exchange 48120
  platform_verify_market_network
}
platform_software_status() {
  local auto manual onload tcpdirect physical
  auto="$(management_command 48121 STATE 2>/dev/null || true)"
  manual="$(management_command 48122 STATE 2>/dev/null || true)"
  onload="$(management_command 48123 STATE 2>/dev/null || true)"
  tcpdirect="$(management_command 48124 STATE 2>/dev/null || true)"
  physical="$("${SSH[@]}" "$TRADER_HOST" "printf '%s %s ' \"\$(basename \"\$(readlink /sys/bus/pci/devices/0000:03:00.0/driver)\")\" \"\$(cat /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages)\"; ip -4 -o addr show dev ens64np1 | grep -Fq ' 20.1.1.2/24 ' && echo 1 || echo 0")"
  python3 - "$auto" "$manual" "$physical" "$onload" "$tcpdirect" <<'PY'
import json,sys
try:
    auto,manual=(json.loads(x) for x in sys.argv[1:3])
except (ValueError,TypeError):
    auto=manual={}
owner,pages,ip=sys.argv[3].split()
try:
    onload,tcpdirect=(json.loads(x) for x in sys.argv[4:6])
except (ValueError,TypeError):
    onload=tcpdirect={}
ready=(owner=='sfc' and pages=='128' and ip=='1' and auto.get('role')=='AUTO'
       and manual.get('role')=='MANUAL'
       and auto.get('market_receiver_ready') is True
       and manual.get('market_receiver_ready') is True
       and manual.get('software_latency',{}).get('queue_locked') is False
       and onload.get('order_transport')=='OPENONLOAD' and onload.get('status')=='ONLINE'
       and tcpdirect.get('order_transport')=='TCPDIRECT_ZF' and tcpdirect.get('status')=='ONLINE')
print(json.dumps({'mode':'SFC','experiment_profile':'SOFTWARE',
    'transition':'READY' if ready else 'DEGRADED','owner':owner,
    'hugepages_2mb':int(pages),'data_ip_present':ip=='1',
    'software_clients_ready':ready,'hardware_receipts':{}},separators=(',',':')))
PY
}
platform_stop_software_clients() {
  stop_remote_process "$TRADER_HOST" trader-auto /flle-trader 48121 || return 1
  if platform_is_software; then
    stop_remote_process "$TRADER_HOST" trader-manual /flle-trader 48122
  fi
}
platform_start_software() {
  verify_deployed_inputs
  if platform_is_software; then
    state="$(platform_software_status)"
    if [[ "$state" == *'"transition":"READY"'* ]]; then
      start_feed_receiver 1
      platform_start_exchange
      start_controller
      start_gateway
      printf '%s\n' "$state"; return
    fi
  fi
  # A fresh deployment has no listeners; profile changes release only owned ones.
  platform_stop_software_clients
  stop_feed_receiver
  stop_sfc_clients
  stop_dpdk_client
  wait_hugepages_zero
  configure_exchange_rss
  platform_set_profile SOFTWARE
  start_feed_receiver 1
  local allocation slot base onload_base tcpdirect_base span extra
  allocation="$(allocate_sfc_user_ref_slot)"
  read -r slot base onload_base tcpdirect_base span extra <<<"$allocation"
  test -z "${extra:-}"
  local auto_base=$((1 + slot * 1000000))
  test "$auto_base" -lt 2000000000
  start_remote_process "$TRADER_HOST" trader-auto \
    "'$RUN_DIR/flle-trader' --role AUTO --management-port 48121 --feed-socket $RUN_DIR/feed.sock --user-ref-base $auto_base --user-ref-span 1000000 --clordid-prefix AUTO --telemetry-host '$TELEMETRY_HOST' --book-checkpoint '$RUN_DIR/opening-book.checkpoint'"
  start_remote_process "$TRADER_HOST" trader-manual \
    "'$RUN_DIR/flle-trader' --role MANUAL --management-port 48122 --feed-socket $RUN_DIR/feed.sock --user-ref-base $base --user-ref-span $span --clordid-prefix MANU --telemetry-host '$TELEMETRY_HOST' --book-checkpoint '$RUN_DIR/opening-book.checkpoint'"
  wait_remote_listener "$TRADER_HOST" trader-auto /flle-trader 48121
  wait_remote_listener "$TRADER_HOST" trader-manual /flle-trader 48122
  wait_state 48121 '"market_receiver_ready":true' >/dev/null
  wait_state 48122 '"market_receiver_ready":true' >/dev/null
  platform_start_exchange
  "${SSH[@]}" "$TRADER_HOST" "sysctl -w vm.nr_hugepages=128 >/dev/null"
  start_accelerated_clients "$onload_base" "$tcpdirect_base" "$span"
  start_controller
  start_gateway
  state="$(platform_software_status)"
  [[ "$state" == *'"transition":"READY"'* ]]
  printf '%s\n' "$state"
}

platform_retire_snapshot_controller() {
  # Four guests may be restored while the persistent management host survives.
  # A partial/unknown remote deployment is never treated as an empty snapshot.
  local host
  for host in "$EXCHANGE_HOST" "$TRADER_HOST" "$OBSERVER_HOST"; do
    "${SSH[@]}" "$host" bash -s <<'REMOTE'
set -Eeuo pipefail
if compgen -G '/var/tmp/flle-trading-lab-*' >/dev/null; then
  echo 'snapshot retirement refused: a remote platform directory still exists' >&2; exit 1
fi
for port in 43120 48120 48121 48122 48123 48124 48125 8088; do
  test -z "$(ss -ltnpH "( sport = :$port )")" || {
    echo "snapshot retirement refused: remote listener on $port" >&2; exit 1;
  }
done
! ps -eo comm= | grep -Eq '^flle-(exchange|trader)'
REMOTE
  done
  if systemctl is-active --quiet "$CONTROLLER_UNIT"; then
    verify_controller_identity || { echo 'snapshot retirement refused: controller identity mismatch' >&2; return 1; }
    systemctl stop "$CONTROLLER_UNIT"
  fi
  ! systemctl is-active --quiet "$CONTROLLER_UNIT"
  test -z "$(ss -ltnpH '( sport = :48606 )')"
  lab_is_quiescent
  printf 'snapshot_retirement=PASS previous_run=%s remote_platforms=ABSENT controller=STOPPED\n' "$RUN_ID"
}
