#!/usr/bin/env bash
# Run on .111. Each collection gets a new directory; earlier results are retained.
set -Eeuo pipefail
umask 077
ip -4 -o address show | grep -Fq '10.1.1.111/'
CH09_REPO=/qyt-fll
mkdir -p "$CH09_REPO/reports/run-state"
CH09_ENV="$(mktemp)"
trap 'rm -f "$CH09_ENV"' EXIT
scp root@10.1.1.101:/opt/flle-ch09-dev/current.env "$CH09_ENV"
unset CH09_RUN CH09_TEST_DIR CH09_SRC CH09_STATUS
source "$CH09_ENV"
[[ ${CH09_STATUS:-} == READY ]] || { echo '本轮未就绪；请先完成2.1。' >&2; exit 1; }
[[ "$CH09_RUN" =~ ^[0-9]{8}T[0-9]{6}Z-ch09-fpga-dev$ ]]
[[ "$CH09_TEST_DIR" == "/opt/flle-ch09-dev/$CH09_RUN" && "$CH09_SRC" == "$CH09_TEST_DIR/src" ]]
cp "$CH09_ENV" "$CH09_REPO/reports/run-state/ch09-fpga-dev.env"
CH09_COLLECTION="collection-$(date -u +%Y%m%dT%H%M%S.%NZ)"
CH09_RESULT="$CH09_REPO/reports/course-runs/$CH09_RUN/$CH09_COLLECTION"
CH09_REMOTE="/opt/flle-ch09-dev/$CH09_RUN-$CH09_COLLECTION"
mkdir -p "$CH09_RESULT"
cp "$CH09_ENV" "$CH09_RESULT/dev.env"
ssh root@10.1.1.101 bash -s -- "$CH09_TEST_DIR" "$CH09_REMOTE" <<'REMOTE'
set -Eeuo pipefail
ip -4 -o address show | grep -Fq '10.1.1.101/'
cd "$1"
sha256sum -c inputs.sha256 > /dev/null
sha256sum -c work/core-build.sha256
test -f work/selftest.PASS && test -f work/regression.PASS
grep -Fxq 'rtl_selftest=PASS allow=1 target_drop=1 second_pass=1 locate_mismatch_pass=1 stock_mismatch_pass=1 type_f_pass=1' work/adapter-selftest.log
grep -Fxq 'RTL_OFFLINE_REGRESSION=PASS cases=14 network=NOT_USED hardware=NOT_RUN' work/regression.log
mkdir -- "$2"
tar -czf "$2/results.tgz" -C /opt/flle-ch09-dev -- "${1##*/}"
cd "$2"
sha256sum results.tgz > results.sha256
REMOTE
scp "root@10.1.1.101:$CH09_REMOTE/results.tgz" \
  "root@10.1.1.101:$CH09_REMOTE/results.sha256" "$CH09_RESULT/"
(cd "$CH09_RESULT" && sha256sum -c results.sha256)
printf 'RESULT_DIR=%q\nSTATUS=COLLECTED\n' "$CH09_RESULT" \
  >> "$CH09_REPO/reports/run-state/ch09-fpga-dev.env"
printf 'results_saved=%s\nsource_run=%s\n' "$CH09_RESULT" "$CH09_RUN"
