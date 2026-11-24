#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
source Documents/newDoc/assets/common/flle-remote.sh
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-10-verilator-toolchain"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
SRC="Documents/newDoc/assets/10-verilator"
REMOTE="/tmp/$RUN_ID"
cleanup(){ ssh -n "${FLLE_SSH_OPTS[@]}" root@10.1.1.101 "find '$REMOTE' -type f -delete 2>/dev/null; find '$REMOTE' -depth -type d -empty -delete 2>/dev/null || true"; }
trap cleanup EXIT

printf '===== root@10.1.1.101 =====\n$ mkdir %s\n' "$REMOTE" | tee "$OUT/raw/result.txt"
ssh -n "${FLLE_SSH_OPTS[@]}" root@10.1.1.101 "mkdir '$REMOTE'" 2>&1 | tee -a "$OUT/raw/result.txt"
printf '===== jump-host =====\n$ scp toolchain_smoke.sv toolchain_smoke.cpp root@10.1.1.101:%s/\n' "$REMOTE" | tee -a "$OUT/raw/result.txt"
scp -q "${FLLE_SSH_OPTS[@]}" "$SRC/toolchain_smoke.sv" "$SRC/toolchain_smoke.cpp" \
  root@10.1.1.101:"$REMOTE/"
printf '===== root@10.1.1.101 =====\n$ verilator --version\n$ verilator --cc --exe --build --top-module toolchain_smoke toolchain_smoke.sv toolchain_smoke.cpp\n$ ./obj_dir/Vtoolchain_smoke\n' | tee -a "$OUT/raw/result.txt"
ssh -n "${FLLE_SSH_OPTS[@]}" root@10.1.1.101 "
  set -Eeuo pipefail
  cd '$REMOTE'
  verilator --version
  verilator --cc --exe --build --top-module toolchain_smoke \
    toolchain_smoke.sv toolchain_smoke.cpp
  ./obj_dir/Vtoolchain_smoke
" 2>&1 | tee -a "$OUT/raw/result.txt"
(cd "$OUT" && sha256sum raw/result.txt run.env >SHA256SUMS)
printf 'evidence=%s\n' "$OUT"
