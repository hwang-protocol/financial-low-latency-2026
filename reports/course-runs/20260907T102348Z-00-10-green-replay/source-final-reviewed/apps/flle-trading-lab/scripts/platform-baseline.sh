#!/usr/bin/env bash
# Sourced by transport_labctl.sh: one deployed platform, two experiment profiles.
platform_is_software() {
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
test -s "$run/$name.pid" && test -s "$run/$name.identity"
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
  "${SCP[@]}" "$OBSERVER_HOST:$RUN_DIR/build/flle-trader" "$TRADER_HOST:$RUN_DIR/flle-trader"
  "${SSH[@]}" "$EXCHANGE_HOST" "set -eu; cd '$RUN_DIR'; ln -sfn 'transport-runtime/flle-ch06-four-path/bin/flle-exchange' flle-exchange; sha256sum flle-exchange AAPL_NVDA.itch AAPL_NVDA.manifest.json opening-book.checkpoint >deployed.sha256"
  "${SSH[@]}" "$TRADER_HOST" "set -eu; cd '$RUN_DIR'; sha256sum flle-trader opening-book.checkpoint >deployed.sha256"
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
  stop_remote_process "$TRADER_HOST" trader-auto /flle-trader 48121
  if platform_is_software; then
    stop_remote_process "$TRADER_HOST" trader-manual /flle-trader 48122
  fi
}
platform_start_software() {
  verify_deployed_inputs
  if platform_is_software; then
    state="$(platform_software_status)"
    if [[ "$state" == *'"transition":"READY"'* ]]; then
      verify_gateway_identity; verify_controller_identity
      printf '%s\n' "$state"; return
    fi
  fi
  # A fresh deployment has no listeners; profile changes release only owned ones.
  platform_stop_software_clients
  stop_sfc_clients
  stop_dpdk_client
  wait_hugepages_zero
  configure_exchange_rss
  platform_set_profile SOFTWARE
  local allocation slot base onload_base tcpdirect_base span extra
  allocation="$(allocate_sfc_user_ref_slot)"
  read -r slot base onload_base tcpdirect_base span extra <<<"$allocation"
  test -z "${extra:-}"
  local auto_base=$((1 + slot * 1000000))
  test "$auto_base" -lt 2000000000
  start_remote_process "$TRADER_HOST" trader-auto \
    "'$RUN_DIR/flle-trader' --role AUTO --management-port 48121 --unicast-port 42121 --user-ref-base $auto_base --user-ref-span 1000000 --clordid-prefix AUTO --telemetry-host '$TELEMETRY_HOST' --book-checkpoint '$RUN_DIR/opening-book.checkpoint'"
  start_remote_process "$TRADER_HOST" trader-manual \
    "'$RUN_DIR/flle-trader' --role MANUAL --management-port 48122 --unicast-port 42122 --user-ref-base $base --user-ref-span $span --clordid-prefix MANU --telemetry-host '$TELEMETRY_HOST' --book-checkpoint '$RUN_DIR/opening-book.checkpoint'"
  wait_remote_listener "$TRADER_HOST" trader-auto /flle-trader 48121
  wait_remote_listener "$TRADER_HOST" trader-manual /flle-trader 48122
  wait_state 48121 '"market_receiver_ready":true' >/dev/null
  wait_state 48122 '"market_receiver_ready":true' >/dev/null
  start_exchange
  "${SSH[@]}" "$TRADER_HOST" "sysctl -w vm.nr_hugepages=128 >/dev/null"
  start_accelerated_clients "$onload_base" "$tcpdirect_base" "$span"
  start_controller
  start_gateway
  state="$(platform_software_status)"
  [[ "$state" == *'"transition":"READY"'* ]]
  printf '%s\n' "$state"
}
