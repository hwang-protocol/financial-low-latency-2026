#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
source Documents/newDoc/assets/common/flle-remote.sh
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-09-p4-compile"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw" "$OUT/artifacts"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
SRC="Documents/newDoc/assets/09-p4/minimal_exact.p4"
REMOTE="/tmp/${RUN_ID}"
cleanup(){ ssh -n "${FLLE_SSH_OPTS[@]}" root@10.1.1.101 "find '$REMOTE' -type f -delete 2>/dev/null; rmdir '$REMOTE' 2>/dev/null || true"; }
trap cleanup EXIT

printf '===== root@10.1.1.101 =====\n$ mkdir %s\n' "$REMOTE" | tee "$OUT/raw/compile.txt"
ssh -n "${FLLE_SSH_OPTS[@]}" root@10.1.1.101 "mkdir '$REMOTE'" 2>&1 | tee -a "$OUT/raw/compile.txt"
printf '===== jump-host =====\n$ scp minimal_exact.p4 root@10.1.1.101:%s/\n' "$REMOTE" | tee -a "$OUT/raw/compile.txt"
scp -q "${FLLE_SSH_OPTS[@]}" "$SRC" root@10.1.1.101:"$REMOTE/minimal_exact.p4"
printf '===== root@10.1.1.101 =====\n$ p4c-bm2-ss --p4v 16 --p4runtime-files %s/minimal.p4info.txt -o %s/minimal.json %s/minimal_exact.p4\n$ ls -lh %s/minimal.json %s/minimal.p4info.txt\n$ sha256sum %s/minimal.*\n' \
  "$REMOTE" "$REMOTE" "$REMOTE" "$REMOTE" "$REMOTE" "$REMOTE" | tee -a "$OUT/raw/compile.txt"
ssh -n "${FLLE_SSH_OPTS[@]}" root@10.1.1.101 "
  p4c-bm2-ss --p4v 16 --p4runtime-files '$REMOTE/minimal.p4info.txt' \
    -o '$REMOTE/minimal.json' '$REMOTE/minimal_exact.p4'
  ls -lh '$REMOTE/minimal.json' '$REMOTE/minimal.p4info.txt'
  sha256sum '$REMOTE'/minimal.*
" 2>&1 | tee -a "$OUT/raw/compile.txt"
scp -q "${FLLE_SSH_OPTS[@]}" root@10.1.1.101:"$REMOTE/minimal.json" "$OUT/artifacts/"
scp -q "${FLLE_SSH_OPTS[@]}" root@10.1.1.101:"$REMOTE/minimal.p4info.txt" "$OUT/artifacts/"
printf '===== jump-host =====\n$ sed -n 1,45p minimal.p4info.txt\n' | tee "$OUT/raw/p4info.txt"
sed -n '1,45p' "$OUT/artifacts/minimal.p4info.txt" 2>&1 | tee -a "$OUT/raw/p4info.txt"
(cd "$OUT" && sha256sum raw/* artifacts/* run.env >SHA256SUMS)
printf 'evidence=%s\n' "$OUT"
