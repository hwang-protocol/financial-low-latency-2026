#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-00-page-fault-shape"
OUT="Documents/reports/course-runs/$RUN_ID"
mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"

printf '===== root@10.1.1.101 · page touch demo =====\n'
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.101 \
  python3 - <<'PY' 2>&1 | tee "$OUT/raw/result.txt"
import mmap
import os
import resource

page = os.sysconf("SC_PAGE_SIZE")
size = page * 128
buf = mmap.mmap(-1, size,
                flags=mmap.MAP_PRIVATE | mmap.MAP_ANONYMOUS,
                prot=mmap.PROT_READ | mmap.PROT_WRITE)
before = resource.getrusage(resource.RUSAGE_SELF).ru_minflt

for offset in range(0, size, page):
    buf[offset] = 1

after = resource.getrusage(resource.RUSAGE_SELF).ru_minflt
print("page_size=%d" % page)
print("touched_pages=%d" % (size // page))
print("minor_fault_delta=%d" % (after - before))
buf.close()
PY

(cd "$OUT" && sha256sum raw/result.txt run.env >SHA256SUMS); printf 'evidence=%s\n' "$OUT"
