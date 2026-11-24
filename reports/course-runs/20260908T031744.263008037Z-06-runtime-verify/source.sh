#!/usr/bin/env bash
# Observe the runtime installed in Chapter 02. No installation or driver reload.
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%S.%NZ)-06-runtime-verify"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
cp "$0" "$OUT/source.sh"
finish(){ rc=$?; trap - EXIT; printf 'EXIT_CODE=%s\n' "$rc" >>"$OUT/run.env"; (cd "$OUT" && sha256sum raw/result.txt run.env source.sh >SHA256SUMS); echo "evidence=$OUT"; exit "$rc"; }
trap finish EXIT
{
for host in 10.1.1.1 10.1.1.2; do
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@"$host" bash -s <<'REMOTE'
set -Eeuo pipefail
printf '\n===== 已部署的 Onload 运行时 =====\n'
hostname
onload --version
loaded_sfc="$(cat /sys/module/sfc/version)"
expected_sfc="$(modinfo -F version sfc)"
printf 'loaded_sfc=%s expected_sfc=%s\n' "$loaded_sfc" "$expected_sfc"
test "$loaded_sfc" = "$expected_sfc"
test -c /dev/onload && test -c /dev/sfc_char
ls -l /dev/onload /dev/sfc_char
test "$(basename "$(readlink /sys/bus/pci/devices/0000:03:00.0/driver)")" = sfc
echo runtime=READY
REMOTE
done
} 2>&1 | tee "$OUT/raw/result.txt"
