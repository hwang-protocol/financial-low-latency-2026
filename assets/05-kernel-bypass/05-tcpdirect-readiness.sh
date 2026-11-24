#!/usr/bin/env bash
set -Eeuo pipefail
cd /qyt-fll
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-05-tcpdirect-readiness"
OUT="reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"

# ~~~~~两端只读：程序指纹、大页、/dev/onload~~~~~
for host in 10.1.1.1 10.1.1.2; do
  printf '\n===== root@%s =====\n' "$host"
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@"$host" bash -s <<'REMOTE'
    binary=/opt/flle/course-bin/tcpdirect-9.0.2/zftcppingpong
    printf '$ hostname\n'; hostname
    printf '$ ls -l %s\n' "$binary"; ls -l "$binary"
    printf '$ sha256sum %s\n' "$binary"; sha256sum "$binary"
    printf '$ file %s\n' "$binary"; file "$binary"
    printf '$ cat /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages\n'
    cat /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages
    printf '$ ls -l /dev/onload\n'; ls -l /dev/onload
REMOTE
done 2>&1 | tee "$OUT/raw/result.txt"
(cd "$OUT" && sha256sum raw/result.txt run.env >SHA256SUMS)
echo "evidence=$OUT"
