#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
source Documents/newDoc/assets/common/flle-remote.sh
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-09-p4-symbol-boundary"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw" "$OUT/artifacts"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
SOURCE="Documents/newDoc/assets/09-p4/symbol_exact.p4"
REMOTE="/tmp/$RUN_ID"
cleanup(){ ssh -n "${FLLE_SSH_OPTS[@]}" root@10.1.1.101 "find '$REMOTE' -type f -delete 2>/dev/null; rmdir '$REMOTE' 2>/dev/null || true"; }
trap cleanup EXIT

printf '===== root@10.1.1.101 =====\n$ mkdir %s\n' "$REMOTE" | tee "$OUT/raw/compile.txt"
ssh -n "${FLLE_SSH_OPTS[@]}" root@10.1.1.101 "mkdir '$REMOTE'" 2>&1 | tee -a "$OUT/raw/compile.txt"
printf '===== jump-host =====\n$ scp symbol_exact.p4 root@10.1.1.101:%s/\n' "$REMOTE" | tee -a "$OUT/raw/compile.txt"
scp -q "${FLLE_SSH_OPTS[@]}" "$SOURCE" root@10.1.1.101:"$REMOTE/symbol_exact.p4"
printf '===== root@10.1.1.101 =====\n$ p4c-bm2-ss --p4v 16 --p4runtime-files %s/symbol.p4info.txt -o %s/symbol.json %s/symbol_exact.p4\n$ ls -lh %s/symbol.json %s/symbol.p4info.txt\n$ sed -n 1,60p %s/symbol.p4info.txt\n' \
  "$REMOTE" "$REMOTE" "$REMOTE" "$REMOTE" "$REMOTE" "$REMOTE" | tee -a "$OUT/raw/compile.txt"
ssh -n "${FLLE_SSH_OPTS[@]}" root@10.1.1.101 "
  p4c-bm2-ss --p4v 16 --p4runtime-files '$REMOTE/symbol.p4info.txt' \
    -o '$REMOTE/symbol.json' '$REMOTE/symbol_exact.p4'
  ls -lh '$REMOTE'/symbol.{json,p4info.txt}
  sed -n '1,60p' '$REMOTE/symbol.p4info.txt'
" 2>&1 | tee -a "$OUT/raw/compile.txt"
scp -q "${FLLE_SSH_OPTS[@]}" root@10.1.1.101:"$REMOTE/symbol.json" "$OUT/artifacts/"
scp -q "${FLLE_SSH_OPTS[@]}" root@10.1.1.101:"$REMOTE/symbol.p4info.txt" "$OUT/artifacts/"
(cd "$OUT" && sha256sum raw/* artifacts/* run.env >SHA256SUMS)
printf 'evidence=%s\n' "$OUT"
