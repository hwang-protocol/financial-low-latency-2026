#!/usr/bin/env bash
# These five CLI guard tests reject arguments before any sysfs/MMIO access.
set -Eeuo pipefail
ip -4 -o address show | grep -Fq '10.1.1.101/'
test -s /opt/flle-ch09-dev/current.env || { echo '请先执行2.1；恢复快照后先重做第08章准备。' >&2; exit 1; }
unset CH09_RUN CH09_TEST_DIR CH09_SRC CH09_STATUS
source /opt/flle-ch09-dev/current.env
[[ ${CH09_STATUS:-} == READY ]] || { echo '本轮未就绪；请先完成2.1。' >&2; exit 1; }
[[ "$CH09_TEST_DIR" == "/opt/flle-ch09-dev/$CH09_RUN" && "$CH09_SRC" == "$CH09_TEST_DIR/src" ]]
cd "$CH09_TEST_DIR"
rm -f work/host-tool/guards.PASS
sha256sum -c inputs.sha256 > /dev/null
sha256sum -c work/host-tool/build.sha256
python3 "$CH09_SRC/v80/test_mmio_guards.py" "$CH09_TEST_DIR/work/host-tool/flle-v80-mmio" \
  2>&1 | tee work/host-tool/guards.log
grep -q '^Ran 5 tests in ' work/host-tool/guards.log
grep -Fxq OK work/host-tool/guards.log
touch work/host-tool/guards.PASS
printf 'host_tool_guards=PASS tests=5 hardware=NOT_RUN\n'
