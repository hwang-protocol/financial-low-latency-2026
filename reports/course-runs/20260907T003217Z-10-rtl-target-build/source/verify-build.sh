#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
source Documents/newDoc/assets/common/flle-remote.sh
source Documents/reports/run-state/10-rtl-target-build.env
OUT="/financial-low-latency/Documents/reports/course-runs/$RUN_ID"
REMOTE="/var/tmp/$RUN_ID"
ASSET=/financial-low-latency/Documents/newDoc/assets/10-verilator
remote2(){ ssh -n "${FLLE_SSH_OPTS[@]}" root@10.1.1.2 "$@"; }
exec 9>/var/tmp/flle-ch08-10.lock
flock -n 9
cleanup(){
  rc=$?
  trap - EXIT
  set +e
  remote2 "find '$REMOTE' -mindepth 1 -delete && rmdir '$REMOTE' && test ! -e '$REMOTE'" >"$OUT/raw/cleanup.txt" 2>&1
  clean_rc=$?
  printf 'EXIT_CODE=%s\nCLEANUP_EXIT_CODE=%s\n' "$rc" "$clean_rc" >>"$OUT/run.env"
  cp "$OUT/run.env" Documents/reports/run-state/10-rtl-target-build.env
  (cd "$OUT" && find raw artifacts source -type f -print0 | sort -z | xargs -0 sha256sum; sha256sum "$OUT/run.env") >"$OUT/SHA256SUMS"
  printf 'evidence=%s exit=%s cleanup=%s\n' "$OUT" "$rc" "$clean_rc"
  if [ "$rc" -eq 0 ] && [ "$clean_rc" -ne 0 ]; then rc=$clean_rc; fi
  exit "$rc"
}
trap cleanup EXIT
remote2 "hostname; uname -m; dpkg-query -W verilator g++ make; verilator --version; g++ --version; make --version" >"$OUT/raw/toolchain.txt"
remote2 "mkdir '$REMOTE'"
scp -q "${FLLE_SSH_OPTS[@]}" "$ASSET/market_filter.sv" "$ASSET/mold_filter_adapter.cpp" root@10.1.1.2:"$REMOTE/"
printf '%s\n' '' 'vm-2522-02 / build' '===== 查RTL 构建与六项自测 =====' '[Verilator] 对: 构建成功 / 六个case均为1  证: 先验证周期逻辑，再把模型接到真实行情' '$ verilator --cc --exe --build ...；obj_dir/mold_filter_adapter --selftest'
remote2 "set -Eeuo pipefail; cd '$REMOTE'; verilator --cc --exe --build --Wall -Wno-fatal --top-module market_filter -o mold_filter_adapter market_filter.sv mold_filter_adapter.cpp; test -x obj_dir/mold_filter_adapter; obj_dir/mold_filter_adapter --selftest" 2>&1 | tee "$OUT/raw/build-and-selftest.txt" | python3 "$ASSET/live-support/classroom-output.py" selftest
grep -Fq 'rtl_selftest=PASS' "$OUT/raw/build-and-selftest.txt"
scp -q "${FLLE_SSH_OPTS[@]}" root@10.1.1.2:"$REMOTE/obj_dir/mold_filter_adapter" "$OUT/artifacts/"
remote2 "cp '$REMOTE/obj_dir/mold_filter_adapter' '$REMOTE/mold_filter_adapter'"
remote2 "cmp '$REMOTE/obj_dir/mold_filter_adapter' '$REMOTE/mold_filter_adapter'; '$REMOTE/mold_filter_adapter' --selftest; sha256sum '$REMOTE/mold_filter_adapter'" | tee "$OUT/raw/target-selftest.txt"
