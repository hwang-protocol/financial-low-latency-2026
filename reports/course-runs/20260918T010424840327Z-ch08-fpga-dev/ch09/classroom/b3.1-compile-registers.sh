#!/usr/bin/env bash
# Build the register testbench and lint the wrapper around the same core.
set -Eeuo pipefail
ip -4 -o address show | grep -Fq '10.1.1.101/'
test -s /opt/flle-ch09-dev/current.env || { echo '请先执行2.1；恢复快照后先重做第08章准备。' >&2; exit 1; }
unset CH09_RUN CH09_TEST_DIR CH09_SRC CH09_STATUS
source /opt/flle-ch09-dev/current.env
[[ ${CH09_STATUS:-} == READY ]] || { echo '本轮未就绪；请先完成2.1。' >&2; exit 1; }
[[ "$CH09_TEST_DIR" == "/opt/flle-ch09-dev/$CH09_RUN" && "$CH09_SRC" == "$CH09_TEST_DIR/src" ]]
cd "$CH09_TEST_DIR"
sha256sum -c inputs.sha256 > /dev/null
mkdir -p work/registers
rm -f work/registers/build.sha256 work/registers/test.PASS
iverilog -g2012 -s test_market_filter_axil -o work/registers/axil-test.vvp \
  "$CH09_SRC/market_filter.sv" "$CH09_SRC/v80/market_filter_axil.sv" \
  "$CH09_SRC/v80/test_market_filter_axil.sv" 2>&1 | tee work/registers/compile.log
verilator --lint-only -Wall -Wno-UNUSED --top-module market_filter_axil \
  "$CH09_SRC/market_filter.sv" "$CH09_SRC/v80/market_filter_axil.sv" \
  2>&1 | tee work/registers/lint.log
sha256sum work/registers/axil-test.vvp > work/registers/build.sha256
printf 'register_compile=PASS lint=PASS tests=NOT_RUN\n'
