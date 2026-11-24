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
{
# 先在 .2 启动抓包，过滤 .1 → .2 的 ICMP echo request
printf '\n10.1.1.2 / capture · ens64np1\n===== 启动接收端抓包 =====\n[抓包范围] 看: 只记录 20.1.1.1 → 20.1.1.2 的 ICMP 请求，抓到三条后结束\n'
printf '$ timeout 8 tcpdump -ni ens64np1 -c 3 -w %s/probe.pcap %s\n' "$REMOTE" "'$BPF'"
ssh -n "${SSH[@]}" root@10.1.1.2 "mkdir -m 700 '$REMOTE'"
ssh -n "${SSH[@]}" root@10.1.1.2 \
  "timeout 8 tcpdump -ni ens64np1 -c 3 -w '$REMOTE/probe.pcap' '$BPF'" \
  >"$OUT/raw/capture.txt" 2>&1 &
CAPTURE_PID=$!
sleep 1
# 再从 .1 数据口发出三条 ping
printf '\n10.1.1.1 / probe · ens64np0\n===== 发送三条 ping =====\n[探针] 对: 3 transmitted、3 received、0%% packet loss  证: 三条请求都有回应\n$ ping -I ens64np0 -c 3 -W 1 20.1.1.2\n' \
  | tee "$OUT/raw/sender.txt"
ssh -n "${SSH[@]}" root@10.1.1.1 \
  'ping -I ens64np0 -c 3 -W 1 20.1.1.2' 2>&1 | tee -a "$OUT/raw/sender.txt"
if wait "$CAPTURE_PID"; then
  printf '\n10.1.1.2 / verify · ens64np1\n===== 查抓包统计 =====\n[抓包结果] 对: 3 packets captured、0 packets dropped by kernel  证: 捕获三条请求，抓包未报告内核丢包\n'
  cat "$OUT/raw/capture.txt"
else
  rc=$?; cat "$OUT/raw/capture.txt"; exit "$rc"
fi
scp "${SSH[@]}" "root@10.1.1.2:$REMOTE/probe.pcap" "$OUT/raw/probe.pcap"
printf '\n===== 读取三条请求 =====\n[报文] 对: 20.1.1.1 > 20.1.1.2、echo request、seq 1/2/3  证: 到达数据口的方向、类型与序号符合预期\n$ tcpdump -nn -r %s/probe.pcap\n' "$REMOTE"
if ssh -n "${SSH[@]}" root@10.1.1.2 \
  "tcpdump -nn -r '$REMOTE/probe.pcap'" >"$OUT/raw/receiver.txt" 2>&1; then :; else
  rc=$?; cat "$OUT/raw/receiver.txt"; exit "$rc"
fi
cat "$OUT/raw/receiver.txt"
} 2>&1 | tee "$OUT/classroom.txt"
(cd "$OUT" && sha256sum raw/* run.env classroom.txt >SHA256SUMS); printf 'evidence=%s\n' "$OUT"
