#!/usr/bin/env bash
set -Eeuo pipefail
ip -4 -o address show | grep -q '10.1.1.111/'
FLLE_REPO=/financial-low-latency
source "$FLLE_REPO/Documents/reports/run-state/ch08-fpga-dev.env"
ssh root@10.1.1.101 bash -s -- "$FLLE_DEV" <<'REMOTE'
set -euo pipefail
cd "$1"
test -s work/simulation/simulation.log
test -s work/management.log
test -s work/core-synthesis/frame-filter-netlist.json
test -s work/core-synthesis/control-regs-netlist.json
tar -czf results.tgz work
sha256sum results.tgz > results.sha256
REMOTE
scp "root@10.1.1.101:$FLLE_DEV/results.tgz" \
  "root@10.1.1.101:$FLLE_DEV/results.sha256" "$RESULT_DIR/"
(cd "$RESULT_DIR" && sha256sum -c results.sha256)
printf 'STATUS=COLLECTED\n' >> "$FLLE_REPO/Documents/reports/run-state/ch08-fpga-dev.env"
printf 'results_saved=%s\n' "$RESULT_DIR"
