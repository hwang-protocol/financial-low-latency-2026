#!/usr/bin/env bash
set -euo pipefail
asset_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
build_dir="$(mktemp -d)"
trap 'rm -rf -- "$build_dir"' EXIT
compiler="${IVERILOG:-iverilog}"
runner="${VVP:-vvp}"
extra=()
if [[ -n ${IVERILOG_IVL_DIR:-} ]]; then
    extra=(-B "$IVERILOG_IVL_DIR")
fi
"$compiler" "${extra[@]}" -g2012 -s filter_tb -o "$build_dir/filter.vvp" \
    "$asset_dir/nvda_match.sv" "$asset_dir/drop_once.sv" \
    "$asset_dir/frame_filter.sv" "$asset_dir/control_regs.sv" "$asset_dir/filter_tb.sv"
"$runner" "$build_dir/filter.vvp"
