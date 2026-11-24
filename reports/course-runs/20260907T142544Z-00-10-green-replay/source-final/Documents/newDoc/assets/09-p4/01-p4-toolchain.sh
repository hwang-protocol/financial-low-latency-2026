#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
source Documents/newDoc/assets/common/flle-remote.sh
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-09-p4-toolchain"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"

ssh -n "${FLLE_SSH_OPTS[@]}" root@10.1.1.101 '
  printf "===== root@10.1.1.101 =====\n"
  printf "$ p4c --version\n"
  p4c --version
  printf "$ simple_switch --version\n"
  simple_switch --version 2>&1
  printf "$ command -v simple_switch_CLI\n"
  command -v simple_switch_CLI
' 2>&1 | tee "$OUT/raw/result.txt"
(cd "$OUT" && sha256sum raw/result.txt run.env >SHA256SUMS)
printf 'evidence=%s\n' "$OUT"
