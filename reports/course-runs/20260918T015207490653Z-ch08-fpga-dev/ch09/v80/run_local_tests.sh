#!/usr/bin/env bash
set -euo pipefail
asset_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
core_file="${CH09_CORE_FILE:-$asset_dir/../market_filter.sv}"
out_dir="${1:-$(mktemp -d /tmp/flle-v80-axil.XXXXXX)}"
mkdir -p "$out_dir"
iverilog -g2012 -s test_market_filter_axil -o "$out_dir/axil-test.vvp" \
    "$core_file" "$asset_dir/market_filter_axil.sv" "$asset_dir/test_market_filter_axil.sv" \
    > "$out_dir/iverilog.stdout" 2> "$out_dir/iverilog.stderr"
vvp "$out_dir/axil-test.vvp" | tee "$out_dir/simulation.txt"
# Ignored AXI protection bits and intentionally unparsed ITCH fields are expected.
verilator --lint-only -Wall -Wno-UNUSED --top-module market_filter_axil \
    "$core_file" "$asset_dir/market_filter_axil.sv" \
    > "$out_dir/verilator.stdout" 2> "$out_dir/verilator.stderr"
gcc -std=c11 -Wall -Wextra -Werror -O2 "$asset_dir/filter_mmio.c" -o "$out_dir/flle-v80-mmio"
python3 "$asset_dir/test_mmio_guards.py" "$out_dir/flle-v80-mmio" > "$out_dir/mmio-guards.txt" 2>&1
printf 'PASS: RTL simulation, Verilator lint, C build, and MMIO CLI guards. Logs: %s\n' "$out_dir"
printf 'NOT RUN: Vivado, AMC image build, card programming, PCIe MMIO, or Ethernet traffic.\n'
