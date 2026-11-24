#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-09-p4-linklocal"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
SOURCE="Documents/newDoc/assets/09-p4/evidence"

cp "$SOURCE/linklocal-tcpdump.txt" "$OUT/raw/tcpdump.txt"
cp "$SOURCE/linklocal-eos-stp.txt" "$OUT/raw/eos-stp.txt"
{
  printf '===== 2026-08-20 现场原生证据：tcpdump =====\n'
  printf '%s\n' \
    "captured_by=tcpdump -nn -r bpdu-current-port1-inbound.pcap 'ether dst 01:80:c2:00:00:00'" \
    "captured_by=tcpdump -nn -r bpdu-current-port1-outbound.pcap 'ether dst 01:80:c2:00:00:00'" \
    "captured_by=tcpdump -nn -r bpdu-current-port2-inbound.pcap 'ether dst 01:80:c2:00:00:00'" \
    "captured_by=tcpdump -nn -r bpdu-current-port2-outbound.pcap 'ether dst 01:80:c2:00:00:00'"
  cat "$OUT/raw/tcpdump.txt"
  printf '===== 2026-08-20 现场原生证据：Arista EOS =====\n'
  printf 'captured_by=show spanning-tree vlan 3101,3102\n'
  cat "$OUT/raw/eos-stp.txt"
} 2>&1 | tee "$OUT/raw/transcript.txt"
(cd "$OUT" && sha256sum raw/*.txt run.env >SHA256SUMS)
printf 'evidence=%s\n' "$OUT"
