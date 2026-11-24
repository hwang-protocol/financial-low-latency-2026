#!/usr/bin/env bash
# Compile the network adapter and the separate RTL regression; do not run them.
set -Eeuo pipefail
ip -4 -o address show | grep -Fq '10.1.1.101/'
test -s /opt/flle-ch09-dev/current.env || { echo '请先执行2.1；恢复快照后先重做第08章准备。' >&2; exit 1; }
unset CH09_RUN CH09_TEST_DIR CH09_SRC CH09_STATUS
source /opt/flle-ch09-dev/current.env
[[ ${CH09_STATUS:-} == READY ]] || { echo '本轮未就绪；请先完成2.1。' >&2; exit 1; }
[[ "$CH09_TEST_DIR" == "/opt/flle-ch09-dev/$CH09_RUN" && "$CH09_SRC" == "$CH09_TEST_DIR/src" ]]
cd "$CH09_TEST_DIR"
sha256sum -c inputs.sha256 > /dev/null
rm -f work/core-build.sha256 work/selftest.PASS work/regression.PASS
verilator --cc --exe --build --Wall -Wno-fatal \
  --top-module market_filter --Mdir "$CH09_TEST_DIR/obj_core" \
  -o mold_filter_adapter "$CH09_SRC/market_filter.sv" \
  "$CH09_SRC/mold_filter_adapter.cpp" 2>&1 | tee work/adapter-build.log
verilator --cc --exe --build --Wall -Wno-fatal \
  --top-module market_filter --Mdir "$CH09_TEST_DIR/obj_regression" \
  -o market_filter_tb "$CH09_SRC/market_filter.sv" \
  "$CH09_SRC/market_filter_tb.cpp" 2>&1 | tee work/regression-build.log
sha256sum obj_core/mold_filter_adapter obj_regression/market_filter_tb > work/core-build.sha256
printf 'core_compile=PASS tests=NOT_RUN\n'
