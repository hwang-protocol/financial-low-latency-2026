#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
AUDIT_RUN=$(date -u +%Y%m%dT%H%M%S.%NZ)-05-output-format
AUDIT_OUT=Documents/reports/course-runs/$AUDIT_RUN
mkdir -p "$AUDIT_OUT"
printf '%s\n' "$AUDIT_OUT" >/tmp/flle-ch05-output-validation-out
printf 'AUDIT_RUN=%s\nAUDIT_OUT=%s\nSTATUS=RUNNING\n' "$AUDIT_RUN" "$AUDIT_OUT" > Documents/reports/run-state/05-output-format.env
cp /tmp/flle-ch05-output-validation.sh "$AUDIT_OUT/validation.sh"
trap 'rc=$?; printf "STATUS=FINISHED\nEXIT_CODE=%s\n" "$rc" >> Documents/reports/run-state/05-output-format.env; exit "$rc"' EXIT
for name in 04-socket-real-order 05-onload-real-order 06-tcpdirect-real-order 07-dpdk-real-order 08-four-path-compare 09-four-path-handoff; do
 printf '%s START %s\n' "$(date -u +%FT%TZ)" "$name" >>"$AUDIT_OUT/stages.txt"
 bash "Documents/newDoc/assets/05-kernel-bypass/$name.sh" >"$AUDIT_OUT/$name.txt" 2>&1
 printf '%s PASS %s\n' "$(date -u +%FT%TZ)" "$name" >>"$AUDIT_OUT/stages.txt"
done
(cd "$AUDIT_OUT" && sha256sum *.txt validation.sh >SHA256SUMS)
