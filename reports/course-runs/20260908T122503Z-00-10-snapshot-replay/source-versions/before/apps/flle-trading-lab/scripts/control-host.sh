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
    bash -c "$*" 8>&-
  else
    command ssh -o BatchMode=yes -o StrictHostKeyChecking=yes \
      -o ConnectTimeout=8 "$host" "$@"
  fi
}
SSH=(control_host_command)

# Closing fd 8 in local child shells keeps daemon processes from retaining
# the parent operation lock after the operation returns.
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
    baseline|start|sfc|dpdk|reset-paper|status|verify|feed-profile|controller-start|controller-check|controller-stop)
      exec ssh -o BatchMode=yes -o StrictHostKeyChecking=yes "$TRADER_HOST" \
        bash "$CONTROL_SCRIPT" "$ACTION" "$RUN_ID" "$TARGET" "$EXPORT_DIR"
      ;;
  esac
fi

install_control_workspace() {
  local remote_app="$CONTROL_WORKSPACE/apps/flle-trading-lab"
  "${SSH[@]}" "$TRADER_HOST" "mkdir -p '$remote_app/scripts' '$remote_app/flle_trading'"
  "${SCP[@]}" "$APP_DIR"/scripts/*.sh "$APP_DIR"/scripts/*.py "$TRADER_HOST:$remote_app/scripts/"
  "${SCP[@]}" "$APP_DIR"/flle_trading/*.py "$TRADER_HOST:$remote_app/flle_trading/"
  "${SSH[@]}" "$TRADER_HOST" "cd '$CONTROL_WORKSPACE'; find apps -type f -print0 | sort -z | xargs -0 sha256sum >MANIFEST.sha256"
}

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

start_feed_receiver() {
  local multicast="${1:-1}"
  if platform_process_running "$TRADER_HOST" feed-receiver "$RUN_DIR/flle-feed-receiver"; then
    if "${SSH[@]}" "$TRADER_HOST" "grep -Fxq '$multicast' '$RUN_DIR/feed-multicast.profile'"; then return; fi
    stop_feed_receiver
  fi
  start_remote_process "$TRADER_HOST" feed-receiver \
    "'$RUN_DIR/flle-feed-receiver' --socket '$RUN_DIR/feed.sock' --multicast-receiver $multicast"
  "${SSH[@]}" "$TRADER_HOST" "set -eu; for _ in \$(seq 1 40); do if test -S '$RUN_DIR/feed.sock'; then printf '%s\\n' '$multicast' >'$RUN_DIR/feed-multicast.profile'; exit 0; fi; sleep 0.1; done; cat '$RUN_DIR/feed-receiver.log' >&2; exit 1"
}

stop_feed_receiver() {
  stop_remote_process "$TRADER_HOST" feed-receiver /flle-feed-receiver || return 1
  "${SSH[@]}" "$TRADER_HOST" "test ! -S '$RUN_DIR/feed.sock'"
}
