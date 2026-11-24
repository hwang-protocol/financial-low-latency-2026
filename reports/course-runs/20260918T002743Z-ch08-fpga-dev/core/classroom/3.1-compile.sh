#!/usr/bin/env bash
set -Eeuo pipefail
ip -4 -o address show | grep -q '10.1.1.101/'
source /opt/flle-ch08-dev/current.env
mkdir -p "$FLLE_DEV/work/simulation"
cd "$FLLE_DEV/work/simulation"
rm -f filter.vvp
iverilog -g2012 -s filter_tb -o filter.vvp \
  "$FLLE_CORE/nvda_match.sv" "$FLLE_CORE/drop_once.sv" \
  "$FLLE_CORE/frame_filter.sv" "$FLLE_CORE/control_regs.sv" \
  "$FLLE_CORE/filter_tb.sv" 2>&1 | tee compile.log
sha256sum filter.vvp "$FLLE_CORE/"*.sv > compile.sha256
printf 'simulation_build=PASS artifact=filter.vvp\n'
