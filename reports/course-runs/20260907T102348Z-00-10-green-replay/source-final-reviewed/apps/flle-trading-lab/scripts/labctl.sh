#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-}"
RUN_ID="${2:-}"
PREFLIGHT_SCOPE="${3:-full}"

case "$RUN_ID" in
  ""|*[!A-Za-z0-9._-]*)
    echo "usage: $0 {preflight|deploy|deploy-data|start|status|verify|stop} RUN_ID [full|stage-c]" >&2
    exit 2
    ;;
esac

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd -- "$APP_DIR/../.." && pwd)"
EXCHANGE_HOST="${FLLE_EXCHANGE_HOST:-root@10.1.1.1}"
TRADER_HOST="${FLLE_TRADER_HOST:-root@10.1.1.2}"
OBSERVER_HOST="${FLLE_OBSERVER_HOST:-root@10.1.1.101}"
TELEMETRY_HOST="${FLLE_TELEMETRY_HOST:-10.1.1.101}"
RUN_DIR="/var/tmp/flle-trading-lab-$RUN_ID"
REPLAY_SOURCE="${FLLE_REPLAY_SOURCE:-$REPO_ROOT/artifacts/blobs/nasdaq/S061226-v50/AAPL_NVDA.itch}"
REPLAY_MANIFEST="${FLLE_REPLAY_MANIFEST:-$REPO_ROOT/artifacts/blobs/nasdaq/S061226-v50/AAPL_NVDA.manifest.json}"
REPLAY_SHA256="82e1d74f961803e0646e1f09329f080d72f21f581540344ed8da605a7641ef2b"
MANIFEST_SHA256="3a45c11b22e483412a67ca8ac6881ddcc9d256f2fdb92be8be42af38473bc2d1"

assert_local_assets() {
  test -s "$REPLAY_SOURCE"
  test -s "$REPLAY_MANIFEST"
  test "$(sha256sum "$REPLAY_SOURCE" | awk '{print $1}')" = "$REPLAY_SHA256"
  test "$(sha256sum "$REPLAY_MANIFEST" | awk '{print $1}')" = "$MANIFEST_SHA256"
  python3 - "$REPLAY_SOURCE" "$REPLAY_MANIFEST" <<'PY'
import json, os, sys
replay, manifest_path = sys.argv[1:]
with open(manifest_path, encoding="utf-8") as stream:
    manifest = json.load(stream)
assert manifest["truncated_input"] is False
assert manifest["output_bytes"] == os.path.getsize(replay) == 561727241
assert manifest["output_sha256"] == "82e1d74f961803e0646e1f09329f080d72f21f581540344ed8da605a7641ef2b"
assert manifest["symbols"] == ["AAPL", "NVDA"]
PY
}

remote_preflight() {
  ssh "$EXCHANGE_HOST" "set -eu; iface=\$(ip -4 -o addr show | awk '\$4 == \"20.1.1.1/24\" {print \$2}'); [ -n \"\$iface\" ]; [ \"\$(printf '%s\n' \"\$iface\" | wc -l)\" -eq 1 ]; ethtool \"\$iface\" | grep -Fq 'Link detected: yes'; echo \"exchange_data=PASS interface=\$iface address=20.1.1.1/24 link=yes\""
  ssh "$TRADER_HOST" "set -eu; iface=\$(ip -4 -o addr show | awk '\$4 == \"20.1.1.2/24\" {print \$2}'); [ -n \"\$iface\" ]; [ \"\$(printf '%s\n' \"\$iface\" | wc -l)\" -eq 1 ]; ethtool \"\$iface\" | grep -Fq 'Link detected: yes'; echo \"trader_data=PASS interface=\$iface address=20.1.1.2/24 link=yes\""
  remote_builder_preflight
}

remote_builder_preflight() {
  ssh "$OBSERVER_HOST" "set -eu; command -v g++-11 make python3 >/dev/null; echo 'builder_tools=PASS host=10.1.1.101 compiler=g++-11'"
}

remote_start() {
  local host="$1" name="$2" command="$3"
  ssh "$host" "set -eu; cd '$RUN_DIR'; if [ -s '$name.pid' ] && kill -0 \$(cat '$name.pid') 2>/dev/null; then echo '$name already running'; exit 1; fi; nohup $command </dev/null >'$name.log' 2>&1 & echo \$! >'$name.pid'"
}

remote_assert_stopped() {
  local host="$1" name="$2" expected="$3"
  ssh "$host" "set -eu; [ -s '$RUN_DIR/$name.pid' ] || exit 0; pid=\$(cat '$RUN_DIR/$name.pid'); [ -r \"/proc/\$pid/cmdline\" ] || exit 0; command=\$(tr '\\0' ' ' < \"/proc/\$pid/cmdline\"); case \"\$command\" in *'$expected'*) echo '$name is running; stop this RUN before deploy' >&2; exit 1;; esac"
}

remote_wait_listen() {
  local host="$1" name="$2" expected="$3" port="$4"
  ssh "$host" "set -eu; cd '$RUN_DIR'; for _ in \$(seq 1 40); do pid=\$(cat '$name.pid' 2>/dev/null || true); if [ -z \"\$pid\" ] || [ ! -r \"/proc/\$pid/cmdline\" ]; then tail -n 20 '$name.log' >&2 || true; exit 1; fi; command=\$(tr '\\0' ' ' < \"/proc/\$pid/cmdline\"); case \"\$command\" in *'$expected'*) ;; *) echo '$name pid no longer matches' >&2; exit 1;; esac; listeners=\$(ss -ltnpH '( sport = :$port )' || true); case \"\$listeners\" in *\"pid=\$pid,\"*) echo '$name ready port=$port pid='\"\$pid\"; exit 0;; esac; sleep 0.25; done; tail -n 20 '$name.log' >&2 || true; echo '$name did not listen on $port' >&2; exit 1"
}

remote_wait_trader_receiver() {
  local name="$1" port="$2" role="$3"
  ssh "$TRADER_HOST" "set -eu; for _ in \$(seq 1 40); do exec 3<>/dev/tcp/10.1.1.2/$port; printf 'STATE\\n' >&3; IFS= read -r state <&3; exec 3>&-; case \"\$state\" in *'\"role\":\"$role\"'*'\"market_receiver_ready\":true'*) echo '$name market_receiver=READY role=$role'; exit 0;; esac; sleep 0.25; done; echo '$name market receiver not ready' >&2; exit 1"
}

remote_stop() {
  local host="$1" name="$2" expected="$3"
  ssh "$host" "set -eu; [ -d '$RUN_DIR' ] || exit 0; cd '$RUN_DIR'; [ -s '$name.pid' ] || exit 0; pid=\$(cat '$name.pid'); [ -r \"/proc/\$pid/cmdline\" ] || { rm -f '$name.pid'; exit 0; }; command=\$(tr '\\0' ' ' < \"/proc/\$pid/cmdline\"); case \"\$command\" in *'$expected'*) kill \"\$pid\";; *) echo 'refusing mismatched pid' >&2; exit 1;; esac; for _ in 1 2 3 4 5 6 7 8 9 10; do kill -0 \"\$pid\" 2>/dev/null || break; sleep 0.5; done; kill -0 \"\$pid\" 2>/dev/null && kill -KILL \"\$pid\" || true; rm -f '$name.pid'"
}

remote_status() {
  local host="$1" name="$2" expected="$3"
  ssh "$host" "set -eu; cd '$RUN_DIR'; pid=\$(cat '$name.pid' 2>/dev/null || true); if [ -z \"\$pid\" ] || [ ! -r \"/proc/\$pid/cmdline\" ]; then echo '$name=OFFLINE'; exit 0; fi; command=\$(tr '\\0' ' ' < \"/proc/\$pid/cmdline\"); case \"\$command\" in *'$expected'*) echo '$name=ONLINE pid='\"\$pid\";; *) echo '$name=OFFLINE pid_mismatch='\"\$pid\";; esac"
}

deploy_control_and_data() {
  assert_local_assets
  remote_preflight
  remote_assert_stopped "$EXCHANGE_HOST" exchange /flle-exchange
  remote_assert_stopped "$TRADER_HOST" trader /flle-trader
  remote_assert_stopped "$TRADER_HOST" trader-auto /flle-trader
  remote_assert_stopped "$TRADER_HOST" trader-manual /flle-trader
  remote_assert_stopped "$OBSERVER_HOST" gateway flle_trading.gateway
  ssh "$OBSERVER_HOST" "mkdir -p '$RUN_DIR/src' '$RUN_DIR/flle_trading' '$RUN_DIR/scripts' '$RUN_DIR/tests' '$RUN_DIR/web'"
  scp "$APP_DIR/Makefile" "$OBSERVER_HOST:$RUN_DIR/Makefile"
  scp "$APP_DIR"/src/*.cpp "$APP_DIR"/src/*.hpp "$OBSERVER_HOST:$RUN_DIR/src/"
  scp "$APP_DIR"/scripts/*.py "$APP_DIR"/scripts/*.sh \
    "$OBSERVER_HOST:$RUN_DIR/scripts/"
  scp "$APP_DIR"/tests/*.py "$OBSERVER_HOST:$RUN_DIR/tests/"
  # The reset regression also exercises the course LANZ collector. Include its
  # actual source in the isolated build inputs; source.sha256 covers this copy.
  scp "$REPO_ROOT/Documents/newDoc/assets/07-arista-time/lanz_stream_collector.py" \
    "$OBSERVER_HOST:$RUN_DIR/tests/lanz_stream_collector.py"
  scp "$APP_DIR"/flle_trading/*.py "$OBSERVER_HOST:$RUN_DIR/flle_trading/"
  scp "$APP_DIR"/web/* "$OBSERVER_HOST:$RUN_DIR/web/"
  ssh "$OBSERVER_HOST" "set -eu; cd '$RUN_DIR'; find Makefile src scripts tests flle_trading web -type f -print0 | sort -z | xargs -0 sha256sum > source.sha256"
  ssh "$EXCHANGE_HOST" "mkdir -p '$RUN_DIR'"
  ssh "$TRADER_HOST" "mkdir -p '$RUN_DIR'"
  scp "$REPLAY_SOURCE" "$EXCHANGE_HOST:$RUN_DIR/AAPL_NVDA.itch"
  scp "$REPLAY_MANIFEST" "$EXCHANGE_HOST:$RUN_DIR/AAPL_NVDA.manifest.json"
}

case "$ACTION" in
  preflight)
    assert_local_assets
    echo "control_assets=PASS replay_bytes=561727241 symbols=AAPL,NVDA"
    case "$PREFLIGHT_SCOPE" in
      full) remote_preflight ;;
      stage-c) remote_builder_preflight ;;
      *) echo "unknown preflight scope: $PREFLIGHT_SCOPE" >&2; exit 2 ;;
    esac
    ;;
  deploy)
    deploy_control_and_data
    ssh "$OBSERVER_HOST" "set -eu; cd '$RUN_DIR'; make clean test tools"
    scp "$OBSERVER_HOST:$RUN_DIR/build/flle-exchange" "$EXCHANGE_HOST:$RUN_DIR/flle-exchange"
    scp "$OBSERVER_HOST:$RUN_DIR/build/flle-book-checkpoint" "$EXCHANGE_HOST:$RUN_DIR/flle-book-checkpoint"
    scp "$OBSERVER_HOST:$RUN_DIR/build/flle-trader" "$TRADER_HOST:$RUN_DIR/flle-trader"
    ssh "$EXCHANGE_HOST" "set -eu; cd '$RUN_DIR'; ./flle-book-checkpoint AAPL_NVDA.itch opening-book.checkpoint 34200000000000 | tee checkpoint.txt; test -s opening-book.checkpoint; sha256sum flle-exchange AAPL_NVDA.itch AAPL_NVDA.manifest.json opening-book.checkpoint > deployed.sha256"
    scp -3 "$EXCHANGE_HOST:$RUN_DIR/opening-book.checkpoint" "$TRADER_HOST:$RUN_DIR/opening-book.checkpoint"
    ssh "$TRADER_HOST" "cd '$RUN_DIR'; sha256sum flle-trader opening-book.checkpoint > deployed.sha256"
    ;;
  deploy-data)
    deploy_control_and_data
    ;;
  start)
    started_exchange=false
    started_trader_auto=false
    started_trader_manual=false
    started_gateway=false
    rollback_start() {
      local rc="${1:-1}"
      set +e
      $started_gateway && remote_stop "$OBSERVER_HOST" gateway flle_trading.gateway
      $started_exchange && remote_stop "$EXCHANGE_HOST" exchange /flle-exchange
      $started_trader_manual && remote_stop "$TRADER_HOST" trader-manual /flle-trader
      $started_trader_auto && remote_stop "$TRADER_HOST" trader-auto /flle-trader
      exit "$rc"
    }
    trap rollback_start ERR
    remote_start "$TRADER_HOST" trader-auto "./flle-trader --role AUTO --management-port 48121 --unicast-port 42121 --user-ref-base 1 --user-ref-span 2000000000 --clordid-prefix AUTO --telemetry-host '$TELEMETRY_HOST' --book-checkpoint '$RUN_DIR/opening-book.checkpoint'" || rollback_start $?
    started_trader_auto=true
    remote_wait_listen "$TRADER_HOST" trader-auto /flle-trader 48121 || rollback_start $?
    remote_wait_trader_receiver trader-auto 48121 AUTO || rollback_start $?
    remote_start "$TRADER_HOST" trader-manual "./flle-trader --role MANUAL --management-port 48122 --unicast-port 42122 --user-ref-base 2100000000 --user-ref-span 2000000000 --clordid-prefix MANU --telemetry-host '$TELEMETRY_HOST' --book-checkpoint '$RUN_DIR/opening-book.checkpoint'" || rollback_start $?
    started_trader_manual=true
    remote_wait_listen "$TRADER_HOST" trader-manual /flle-trader 48122 || rollback_start $?
    remote_wait_trader_receiver trader-manual 48122 MANUAL || rollback_start $?
    remote_start "$EXCHANGE_HOST" exchange "./flle-exchange --telemetry-host '$TELEMETRY_HOST' --replay-file '$RUN_DIR/AAPL_NVDA.itch' --book-checkpoint '$RUN_DIR/opening-book.checkpoint' --market-date '2026-06-12' --replay-speed 1" || rollback_start $?
    started_exchange=true
    remote_wait_listen "$EXCHANGE_HOST" exchange /flle-exchange 43120 || rollback_start $?
    remote_wait_listen "$EXCHANGE_HOST" exchange /flle-exchange 48120 || rollback_start $?
    remote_start "$OBSERVER_HOST" gateway "env PYTHONPATH='$RUN_DIR' python3 -m flle_trading.gateway --web-root '$RUN_DIR/web'" || rollback_start $?
    started_gateway=true
    remote_wait_listen "$OBSERVER_HOST" gateway flle_trading.gateway 8088 || rollback_start $?
    trap - ERR
    ;;
  status)
    remote_status "$EXCHANGE_HOST" exchange /flle-exchange
    remote_status "$TRADER_HOST" trader-auto /flle-trader
    remote_status "$TRADER_HOST" trader-manual /flle-trader
    remote_status "$OBSERVER_HOST" gateway flle_trading.gateway
    curl --fail --silent --show-error "http://10.1.1.101:8088/api/health"
    echo
    ;;
  verify)
    remote_status "$EXCHANGE_HOST" exchange /flle-exchange
    remote_status "$TRADER_HOST" trader-auto /flle-trader
    remote_status "$TRADER_HOST" trader-manual /flle-trader
    remote_status "$OBSERVER_HOST" gateway flle_trading.gateway
    ssh "$EXCHANGE_HOST" "set -eu; cd '$RUN_DIR'; sha256sum -c deployed.sha256 >/dev/null"
    ssh "$TRADER_HOST" "set -eu; cd '$RUN_DIR'; sha256sum -c deployed.sha256 >/dev/null"
    ssh "$OBSERVER_HOST" "set -eu; cd '$RUN_DIR'; sha256sum -c source.sha256 >/dev/null"
    curl --fail --silent --show-error "http://10.1.1.101:8088/api/health" | python3 -c 'import json,sys; value=json.load(sys.stdin); replay=value["replay"]; assert all(value["health"][name]["status"] == "ONLINE" for name in ("exchange", "trader_auto", "trader_manual", "gateway")); assert replay["market_date"] == "2026-06-12"; assert replay["window"] == "REGULAR_SESSION"; assert replay["first_source_clock"] == "09:30:00.000000000"; assert replay["last_source_clock"] == "16:00:00.000000000"; assert 0 <= float(replay["progress"]) <= 1; assert "skipped_ns" not in replay'
    echo "deployed_sha256=PASS exchange,trader_auto,trader_manual,source,replay,manifest,opening_book_checkpoint"
    echo "restore_verdict=TRADING_LAB_READY"
    ;;
  stop)
    remote_stop "$TRADER_HOST" trader-manual /flle-trader
    remote_stop "$TRADER_HOST" trader-auto /flle-trader
    remote_stop "$TRADER_HOST" trader /flle-trader
    remote_stop "$EXCHANGE_HOST" exchange /flle-exchange
    remote_stop "$OBSERVER_HOST" gateway flle_trading.gateway
    ;;
  *)
    echo "usage: $0 {preflight|deploy|deploy-data|start|status|verify|stop} RUN_ID" >&2
    exit 2
    ;;
esac
