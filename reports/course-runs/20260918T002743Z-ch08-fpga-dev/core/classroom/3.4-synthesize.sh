#!/usr/bin/env bash
set -Eeuo pipefail
ip -4 -o address show | grep -q '10.1.1.101/'
source /opt/flle-ch08-dev/current.env
mkdir -p "$FLLE_DEV/work/core-synthesis"
cp "$FLLE_CORE/"*.sv "$FLLE_DEV/work/core-synthesis/"
cd "$FLLE_DEV/work/core-synthesis"
rm -f frame-filter-netlist.json frame-filter-netlist.sha256
"$FLLE_DEV/venv/bin/yowasp-yosys" -Q -T -p '
  read_verilog -sv nvda_match.sv drop_once.sv frame_filter.sv;
  synth -top frame_filter -noabc;
  check -assert;
  stat;
  write_json frame-filter-netlist.json
' > frame-filter-synthesis.log 2>&1
grep 'Found and reported' frame-filter-synthesis.log
sha256sum frame-filter-netlist.json > frame-filter-netlist.sha256
printf 'filter_synthesis=PASS target_mapping=NOT_RUN pdi=NOT_BUILT\n'
