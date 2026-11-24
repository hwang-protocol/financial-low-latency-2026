#!/usr/bin/env bash
# --selftest exits before the adapter opens its network receive path.
set -Eeuo pipefail
ip -4 -o address show | grep -Fq '10.1.1.101/'
test -s /opt/flle-ch09-dev/current.env || { echo '请先执行2.1；恢复快照后先重做第08章准备。' >&2; exit 1; }
unset CH09_RUN CH09_TEST_DIR CH09_SRC CH09_STATUS
source /opt/flle-ch09-dev/current.env
[[ ${CH09_STATUS:-} == READY ]] || { echo '本轮未就绪；请先完成2.1。' >&2; exit 1; }
[[ "$CH09_TEST_DIR" == "/opt/flle-ch09-dev/$CH09_RUN" ]]
cd "$CH09_TEST_DIR"
rm -f work/selftest.PASS
sha256sum -c inputs.sha256 > /dev/null
sha256sum -c work/core-build.sha256
obj_core/mold_filter_adapter --selftest 2>&1 | tee work/adapter-selftest.log
grep -Fxq 'rtl_selftest=PASS allow=1 target_drop=1 second_pass=1 locate_mismatch_pass=1 stock_mismatch_pass=1 type_f_pass=1' work/adapter-selftest.log
touch work/selftest.PASS
printf 'adapter_selftest=PASS cases=6 network=NOT_USED hardware=NOT_RUN\n'
