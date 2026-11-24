#!/usr/bin/env bash
# FLLE trading lab on two AWS EC2 instances (adapted from scripts/labctl.sh).
#
# Course lab            -> AWS
#   .1  Exchange        -> flle-ex1  (private 172.31.10.43)
#   .2  AUTO/MANUAL     -> flle-tr2  (private 172.31.12.156)
#   .101 Gateway / web  -> flle-tr2  (same host as the traders)
#   20.1.1.x data net + 10.1.1.x mgmt net -> one ENA interface, one private IP
#   Market feed: UNICAST (AWS VPC has no native multicast)
#
# Run from Git Bash on Windows (uses ~/.ssh/config aliases flle-ex1 / flle-tr2).
# Usage: aws/flle-aws.sh {start|stop|status|tunnel|logs} [replay_speed]
set -euo pipefail

EX_SSH=flle-ex1
TR_SSH=flle-tr2
EX_IP=172.31.10.43
TR_IP=172.31.12.156
APP=/home/ubuntu/flle/app/build
RUN=/home/ubuntu/flle/run
SPEED="${2:-1}"

r() { ssh -o BatchMode=yes -o LogLevel=ERROR "$1" "$2"; }

start_proc() {  # host name expected-substring command...
  local host="$1" name="$2" cmd="$3"
  r "$host" "set -eu; cd '$RUN'; if [ -s '$name.pid' ] && kill -0 \$(cat '$name.pid') 2>/dev/null; then echo '$name already running'; exit 0; fi; nohup $cmd </dev/null >'$name.log' 2>&1 & echo \$! >'$name.pid'; echo '$name started pid='\$!"
}

wait_port() {  # host name port
  local host="$1" name="$2" port="$3"
  r "$host" "for _ in \$(seq 1 40); do pid=\$(cat '$RUN/$name.pid' 2>/dev/null || true); [ -n \"\$pid\" ] && kill -0 \$pid 2>/dev/null || { echo '$name exited:'; tail -n 20 '$RUN/$name.log'; exit 1; }; ss -ltnpH '( sport = :$port )' | grep -q \"pid=\$pid,\" && { echo '$name listening :$port'; exit 0; }; sleep 0.25; done; echo '$name not listening on :$port'; tail -n 20 '$RUN/$name.log'; exit 1"
}

wait_receiver() {  # name port role
  local name="$1" port="$2" role="$3"
  r "$TR_SSH" "for _ in \$(seq 1 40); do state=\$(exec 3<>/dev/tcp/$TR_IP/$port && printf 'STATE\\n' >&3 && IFS= read -r s <&3 && echo \"\$s\") || true; case \"\$state\" in *'\"role\":\"$role\"'*'\"market_receiver_ready\":true'*) echo '$name market_receiver=READY'; exit 0;; esac; sleep 0.25; done; echo '$name market receiver not ready'; exit 1"
}

stop_proc() {  # host name
  r "$1" "cd '$RUN' 2>/dev/null || exit 0; [ -s '$2.pid' ] || exit 0; pid=\$(cat '$2.pid'); if kill \$pid 2>/dev/null; then for _ in 1 2 3 4 5 6 7 8 9 10; do kill -0 \$pid 2>/dev/null || break; sleep 0.5; done; kill -0 \$pid 2>/dev/null && kill -KILL \$pid; echo '$2 stopped'; fi; rm -f '$2.pid'"
}

status_proc() {
  r "$1" "pid=\$(cat '$RUN/$2.pid' 2>/dev/null || true); if [ -n \"\$pid\" ] && kill -0 \$pid 2>/dev/null; then echo '$2=ONLINE pid='\$pid; else echo '$2=OFFLINE'; fi"
}

case "${1:-}" in
  start)
    start_proc "$TR_SSH" feed-receiver "$APP/flle-feed-receiver --socket $RUN/feed.sock --data-ip $TR_IP --multicast-receiver 0 --telemetry-host $TR_IP"
    start_proc "$TR_SSH" trader-auto "$APP/flle-trader --role AUTO --data-ip $TR_IP --management-ip $TR_IP --exchange-data-ip $EX_IP --management-port 48121 --feed-socket $RUN/feed.sock --user-ref-base 1 --user-ref-span 2000000000 --clordid-prefix AUTO --telemetry-host $TR_IP --book-checkpoint $RUN/opening-book.checkpoint"
    wait_port "$TR_SSH" trader-auto 48121
    wait_receiver trader-auto 48121 AUTO
    start_proc "$TR_SSH" trader-manual "$APP/flle-trader --role MANUAL --data-ip $TR_IP --management-ip $TR_IP --exchange-data-ip $EX_IP --management-port 48122 --feed-socket $RUN/feed.sock --user-ref-base 2100000000 --user-ref-span 2000000000 --clordid-prefix MANU --telemetry-host $TR_IP --book-checkpoint $RUN/opening-book.checkpoint"
    wait_port "$TR_SSH" trader-manual 48122
    wait_receiver trader-manual 48122 MANUAL
    start_proc "$EX_SSH" exchange "$APP/flle-exchange --data-ip $EX_IP --trader-data-ip $TR_IP --management-ip $EX_IP --telemetry-host $TR_IP --market-mode UNICAST --replay-file $RUN/AAPL_NVDA.itch --book-checkpoint $RUN/opening-book.checkpoint --market-date 2026-06-12 --replay-speed $SPEED"
    wait_port "$EX_SSH" exchange 43120
    wait_port "$EX_SSH" exchange 48120
    start_proc "$TR_SSH" gateway "env PYTHONPATH=/home/ubuntu/flle/app python3 -m flle_trading.gateway --bind-ip $TR_IP --exchange-host $EX_IP --trader-host $TR_IP --web-root /home/ubuntu/flle/app/web"
    wait_port "$TR_SSH" gateway 8088
    echo "READY. Open the web UI with:  aws/flle-aws.sh tunnel   then browse http://localhost:8088/"
    ;;
  stop)
    stop_proc "$TR_SSH" gateway
    stop_proc "$EX_SSH" exchange
    stop_proc "$TR_SSH" trader-manual
    stop_proc "$TR_SSH" trader-auto
    stop_proc "$TR_SSH" feed-receiver
    ;;
  status)
    status_proc "$EX_SSH" exchange
    status_proc "$TR_SSH" feed-receiver
    status_proc "$TR_SSH" trader-auto
    status_proc "$TR_SSH" trader-manual
    status_proc "$TR_SSH" gateway
    r "$TR_SSH" "curl -s --max-time 5 http://$TR_IP:8088/api/health" ; echo
    ;;
  tunnel)
    echo "Forwarding http://localhost:8088 -> $TR_IP:8088 (Ctrl+C to close)"
    exec ssh -N -L 8088:$TR_IP:8088 "$TR_SSH"
    ;;
  logs)
    r "$EX_SSH" "tail -n 15 $RUN/exchange.log"
    for n in feed-receiver trader-auto trader-manual gateway; do echo "== $n"; r "$TR_SSH" "tail -n 15 $RUN/$n.log"; done
    ;;
  *)
    echo "usage: $0 {start|stop|status|tunnel|logs} [replay_speed]" >&2; exit 2 ;;
esac
