#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
command -v tcpdump >/dev/null || { echo 'ERROR: tcpdump is required'; exit 127; }
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-07-ptp-tc-pcap-ab"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
BASE="Documents/newDoc/assets/07-arista-time/ptp-baseline-client-20260721.pcap"
TC="Documents/newDoc/assets/07-arista-time/ptp-tc-client-20260721.pcap"
FILTER='udp[8] & 0x0f = 8 or udp[8] & 0x0f = 9'
tcpdump -t -nn -r "$BASE" "$FILTER" 2>/dev/null >"$OUT/raw/baseline-decoded.txt"
tcpdump -t -nn -r "$TC" "$FILTER" 2>/dev/null >"$OUT/raw/tc-decoded.txt"

counts() {
  awk '/follow up msg/{f++;if(/sub NS correction : 0,/)fz++} /delay resp msg/{d++;if(/sub NS correction : 0,/)dz++} END{print f+0,fz+0,d+0,dz+0}' "$1"
}
read -r BF BZ BD BDZ <<<"$(counts "$OUT/raw/baseline-decoded.txt")"
read -r TF TZ TD TDZ <<<"$(counts "$OUT/raw/tc-decoded.txt")"
TNF=$((TF - TZ)); TND=$((TD - TDZ))
read -r TMIN TMAX <<<"$(awk -F'sub NS correction : ' 'NF>1{split($2,a,",");v=a[1]+0;if(n++==0||v<min)min=v;if(v>max)max=v} END{print min,max}' "$OUT/raw/tc-decoded.txt")"

{
  printf '$ sha256sum -c PTP-AB-SHA256SUMS\n'
  sha256sum -c Documents/newDoc/assets/07-arista-time/PTP-AB-SHA256SUMS
  printf '\n===== TC OFF · baseline samples =====\n'
  grep -m1 'follow up msg' "$OUT/raw/baseline-decoded.txt"
  grep -m1 'delay resp msg' "$OUT/raw/baseline-decoded.txt"
  printf '\n===== TC ON · E2E Transparent Clock samples =====\n'
  grep -m1 'follow up msg' "$OUT/raw/tc-decoded.txt"
  grep -m1 'delay resp msg' "$OUT/raw/tc-decoded.txt"
  printf '\nfull_scan baseline follow_up_zero=%s/%s delay_resp_zero=%s/%s\n' "$BZ" "$BF" "$BDZ" "$BD"
  printf 'full_scan tc follow_up_nonzero=%s/%s delay_resp_nonzero=%s/%s correction_subns_range=%s..%s\n' "$TNF" "$TF" "$TND" "$TD" "$TMIN" "$TMAX"
  if [[ "$BF" -gt 0 && "$BD" -gt 0 && "$BZ" -eq "$BF" && "$BDZ" -eq "$BD" && "$TF" -gt 0 && "$TD" -gt 0 && "$TZ" -eq 0 && "$TDZ" -eq 0 ]]; then
    printf 'effect=PASS baseline_all_zero=yes tc_all_nonzero=yes\n'
  else
    printf 'effect=FAIL baseline_all_zero=no_or_tc_all_nonzero=no\n'
    exit 1
  fi
} 2>&1 | tee "$OUT/raw/result.txt"
(cd "$OUT" && sha256sum raw/*.txt run.env >SHA256SUMS)
echo "evidence=$OUT"
