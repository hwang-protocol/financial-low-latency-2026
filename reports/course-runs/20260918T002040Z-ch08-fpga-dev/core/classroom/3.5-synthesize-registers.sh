#!/usr/bin/env bash
set -Eeuo pipefail
ip -4 -o address show | grep -q '10.1.1.101/'
source /opt/flle-ch08-dev/current.env
cd "$FLLE_DEV/work/core-synthesis"
"$FLLE_DEV/venv/bin/yowasp-yosys" -Q -T -p '
  read_verilog -sv control_regs.sv;
  synth -top control_regs -noabc;
  check -assert;
  stat;
  write_json control-regs-netlist.json
' > control-regs-synthesis.log 2>&1
grep 'Found and reported' control-regs-synthesis.log
sha256sum control-regs-netlist.json > control-regs-netlist.sha256
printf 'register_synthesis=PASS target_mapping=NOT_RUN pdi=NOT_BUILT\n'
