#!/usr/bin/env bash
# Icarus simulates the AXI-Lite wrapper; no card or PCIe device is opened.
set -Eeuo pipefail
ip -4 -o address show | grep -Fq '10.1.1.101/'
test -s /opt/flle-ch09-dev/current.env || { echo '请先执行2.1；恢复快照后先重做第08章准备。' >&2; exit 1; }
unset CH09_RUN CH09_TEST_DIR CH09_SRC CH09_STATUS
source /opt/flle-ch09-dev/current.env
[[ ${CH09_STATUS:-} == READY ]] || { echo '本轮未就绪；请先完成2.1。' >&2; exit 1; }
[[ "$CH09_TEST_DIR" == "/opt/flle-ch09-dev/$CH09_RUN" ]]
cd "$CH09_TEST_DIR"
rm -f work/registers/test.PASS
sha256sum -c inputs.sha256 > /dev/null
sha256sum -c work/registers/build.sha256
vvp work/registers/axil-test.vvp 2>&1 | tee work/registers/simulation.log
grep -q '^PASS: 110 AXI-Lite register/response checks;' work/registers/simulation.log
touch work/registers/test.PASS
printf 'register_simulation=PASS checks=110 hardware=NOT_RUN\n'
