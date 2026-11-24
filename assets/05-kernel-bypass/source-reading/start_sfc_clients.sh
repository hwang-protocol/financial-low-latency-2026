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
