#!/usr/bin/env bash
# Build and test locally. No SSH, replay API, multicast, or live process control.
set -Eeuo pipefail
ASSET_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if (( $# > 1 )); then
  echo 'usage: bash offline-selftest.sh [new-output-directory]' >&2
  exit 2
fi
for tool in verilator g++ make; do
  command -v "$tool" >/dev/null || {
    printf 'missing local build tool: %s\n' "$tool" >&2
    exit 1
  }
done
if (( $# == 1 )); then
  # Refuse an existing directory so previous evidence is never overwritten.
  mkdir -m 700 -- "$1"
  BUILD_DIR="$(cd -- "$1" && pwd)"
else
  BUILD_DIR="$(mktemp -d "${TMPDIR:-/tmp}/flle-ch09-offline.XXXXXX")"
fi
printf 'offline_output=%s\n' "$BUILD_DIR"
cp -- "$ASSET_DIR/market_filter.sv" "$ASSET_DIR/mold_filter_adapter.cpp" \
  "$ASSET_DIR/market_filter_tb.cpp" "$ASSET_DIR/offline-selftest.sh" "$BUILD_DIR/"
cd -- "$BUILD_DIR"
{
  verilator --version
  g++ --version
  make --version
} > tools.txt 2>&1

# --selftest returns before the adapter's network mode opens any socket.
verilator --cc --exe --build --Wall -Wno-fatal \
  --top-module market_filter -o mold_filter_adapter \
  market_filter.sv mold_filter_adapter.cpp 2>&1 | tee adapter-build.log
obj_dir/mold_filter_adapter --selftest 2>&1 | tee adapter-selftest.log

# This separate testbench exercises configuration collisions and reset priority.
verilator --cc --exe --build --Wall -Wno-fatal --Mdir obj_regression \
  --top-module market_filter -o market_filter_tb \
  market_filter.sv market_filter_tb.cpp 2>&1 | tee regression-build.log
obj_regression/market_filter_tb 2>&1 | tee regression.log
sha256sum market_filter.sv mold_filter_adapter.cpp market_filter_tb.cpp \
  offline-selftest.sh tools.txt adapter-build.log adapter-selftest.log \
  regression-build.log regression.log > SHA256SUMS
printf 'offline_result=PASS network=NOT_USED hardware=NOT_RUN output=%s\n' "$BUILD_DIR"
