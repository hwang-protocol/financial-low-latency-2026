#!/usr/bin/env bash
# Compile the host utility only; compilation never accesses PCIe hardware.
set -Eeuo pipefail
ip -4 -o address show | grep -Fq '10.1.1.101/'
test -s /opt/flle-ch09-dev/current.env || { echo '请先执行2.1；恢复快照后先重做第08章准备。' >&2; exit 1; }
unset CH09_RUN CH09_TEST_DIR CH09_SRC CH09_STATUS
source /opt/flle-ch09-dev/current.env
[[ ${CH09_STATUS:-} == READY ]] || { echo '本轮未就绪；请先完成2.1。' >&2; exit 1; }
[[ "$CH09_TEST_DIR" == "/opt/flle-ch09-dev/$CH09_RUN" && "$CH09_SRC" == "$CH09_TEST_DIR/src" ]]
cd "$CH09_TEST_DIR"
sha256sum -c inputs.sha256 > /dev/null
mkdir -p work/host-tool
rm -f work/host-tool/build.sha256 work/host-tool/guards.PASS
gcc -std=c11 -Wall -Wextra -Werror -O2 "$CH09_SRC/v80/filter_mmio.c" \
  -o work/host-tool/flle-v80-mmio 2>&1 | tee work/host-tool/compile.log
sha256sum work/host-tool/flle-v80-mmio > work/host-tool/build.sha256
printf 'host_tool_compile=PASS hardware=NOT_RUN\n'
