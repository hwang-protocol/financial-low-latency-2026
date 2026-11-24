#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-05-irq-cpu-map"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"

ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.1 \
  bash -s <<'REMOTE' 2>&1 | tee "$OUT/raw/result.txt"
set -Eeuo pipefail
printf '$ cat /proc/interrupts\n'
cat /proc/interrupts
while IFS= read -r line; do
  case "$line" in
    *ens64np0-[0-9])
      irq="${line%%:*}"; irq="${irq//[[:space:]]/}"
      printf '\n$ cat /proc/irq/%s/effective_affinity_list\n' "$irq"
      cat "/proc/irq/$irq/effective_affinity_list"
      ;;
  esac
done </proc/interrupts
REMOTE
(cd "$OUT" && sha256sum raw/result.txt run.env >SHA256SUMS)
echo "evidence=$OUT"
