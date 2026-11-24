#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency

RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-01-packet-proof"
OUT="Documents/reports/course-runs/${RUN_ID}"
REMOTE="/var/tmp/$RUN_ID"
mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
SSH=(-o BatchMode=yes -o StrictHostKeyChecking=yes)
BPF='icmp[icmptype] = icmp-echo and src 20.1.1.1 and dst 20.1.1.2'

cleanup() {
  ssh -n "${SSH[@]}" root@10.1.1.2 "rm -rf -- '$REMOTE'" >/dev/null 2>&1 || true
}
trap cleanup EXIT

# 先在 .2 启动抓包，过滤 .1 → .2 的 ICMP echo request
ssh -n "${SSH[@]}" root@10.1.1.2 "mkdir -m 700 '$REMOTE'"
ssh -n "${SSH[@]}" root@10.1.1.2 \
  "timeout 8 tcpdump -ni ens64np1 -c 3 -w '$REMOTE/probe.pcap' '$BPF'" \
  >"$OUT/raw/capture.txt" 2>&1 &
CAPTURE_PID=$!
sleep 1

# 再从 .1 数据口发出三条 ping
printf '===== root@10.1.1.1 · ping sender =====\n$ ping -I ens64np0 -c 3 -W 1 20.1.1.2\n' \
  | tee "$OUT/raw/sender.txt"
ssh -n "${SSH[@]}" root@10.1.1.1 \
  'ping -I ens64np0 -c 3 -W 1 20.1.1.2' 2>&1 | tee -a "$OUT/raw/sender.txt"

wait "$CAPTURE_PID"
printf '\n===== root@10.1.1.2 · tcpdump receiver =====\n'
printf '$ timeout 8 tcpdump -ni ens64np1 -c 3 -w %s/probe.pcap %s\n' "$REMOTE" "'$BPF'"
cat "$OUT/raw/capture.txt"

scp "${SSH[@]}" "root@10.1.1.2:$REMOTE/probe.pcap" "$OUT/raw/probe.pcap"
ssh -n "${SSH[@]}" root@10.1.1.2 \
  "tcpdump -nn -r '$REMOTE/probe.pcap'" >"$OUT/raw/receiver.txt" 2>&1
printf '\n$ tcpdump -nn -r %s/probe.pcap\n' "$REMOTE"
cat "$OUT/raw/receiver.txt"
(cd "$OUT" && sha256sum raw/* run.env >SHA256SUMS); printf 'evidence=%s\n' "$OUT"
