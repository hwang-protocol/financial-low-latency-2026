#!/usr/bin/env bash
set -Eeuo pipefail
cd /qyt-fll
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-05-kernel-syscalls"
OUT="reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"

# ~~~~~在 .1 本机跑 52 字节短消息，只数网络系统调用~~~~~
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.1 \
  strace -qq -f -c -e trace=network python3 - \
  < assets/05-kernel-bypass/kernel_socket.py \
  2>&1 | tee "$OUT/raw/result.txt"
(cd "$OUT" && sha256sum raw/result.txt run.env >SHA256SUMS)
echo "evidence=$OUT"
