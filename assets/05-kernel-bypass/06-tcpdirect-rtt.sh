#!/usr/bin/env bash
set -Eeuo pipefail
cd /qyt-fll
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-05-tcpdirect-rtt"
OUT="reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
BIN=/opt/flle/course-bin/tcpdirect-9.0.2/zftcppingpong
BIN_SHA="$(ssh -n -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.1 "sha256sum $BIN" | awk '{print $1}')"
printf 'RUN_ID=%s\nUTC_STARTED=%s\nHOSTS=%s\nCPU=%s\nPAYLOAD=%s\nWARMUP=%s\nMEASURED_PER_ROUND=%s\nROUNDS=%s\nBINARY_SHA256=%s\n' \
  "$RUN_ID" "$(date -u +%FT%TZ)" '10.1.1.1,10.1.1.2' 2 52 1000 10000 3 "$BIN_SHA" >"$OUT/run.env"
restore_pages() {
  ssh -n -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.1 'pkill -x zftcppingpong 2>/dev/null || true; sysctl -w vm.nr_hugepages=0 >/dev/null' || true
  ssh -n -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 'pkill -x zftcppingpong 2>/dev/null || true; sysctl -w vm.nr_hugepages=0 >/dev/null' || true
}
trap restore_pages EXIT
run_one() {
  local round="$1" port="$2"
  ssh -n -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.1 'pkill -x zftcppingpong 2>/dev/null || true'
  ssh -f -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.1 "taskset -c 2 env ZF_ATTR=interface=ens64np0 $BIN -s 52 -i 10000 -r 1000 -p 99 -f pong 20.1.1.1:$port > /tmp/zf_pong_r${round}.txt 2>&1"
  sleep 1
  ssh -n -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 "taskset -c 2 env ZF_ATTR=interface=ens64np1 $BIN -s 52 -i 10000 -r 1000 -p 99 -f -w /tmp/${RUN_ID}-zf-r${round}.ns ping 20.1.1.1:$port" >"$OUT/raw/zf_ping_r${round}.txt"
  scp -o BatchMode=yes -o StrictHostKeyChecking=yes "root@10.1.1.2:/tmp/${RUN_ID}-zf-r${round}.ns" "$OUT/raw/zf_r${round}_samples.ns"
  ssh -n -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.1 "cat /tmp/zf_pong_r${round}.txt" >"$OUT/raw/zf_pong_r${round}.txt"
}
# ~~~~~两端借 128 页，三轮 52 字节 ping/pong；退出还回 0~~~~~
{
  printf '===== hugepages borrow =====\n'
  for host in 10.1.1.1 10.1.1.2; do
    printf '%s  ' "$host"
    ssh -n -o BatchMode=yes -o StrictHostKeyChecking=yes root@"$host" 'p=/sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages; b=$(cat $p); sysctl -w vm.nr_hugepages=128 >/dev/null; printf "%s -> %s\n" "$b" "$(cat $p)"'
  done
  for spec in '1 47021' '2 47022' '3 47023'; do
    set -- $spec
    run_one "$1" "$2"
    printf '===== r%s =====\n' "$1"
    LC_ALL=C sort -n "$OUT/raw/zf_r${1}_samples.ns" | awk '{v[NR]=$1; sum+=$1} END {p50=int((NR*50+99)/100); p99=int((NR*99+99)/100); printf "samples=%d half_p50_ns=%d half_p99_ns=%d full_mean_rtt_ns=%.0f\n", NR,v[p50],v[p99],2*sum/NR}'
  done
  printf '===== hugepages return =====\n'
  for host in 10.1.1.1 10.1.1.2; do
    printf '%s  ' "$host"
    ssh -n -o BatchMode=yes -o StrictHostKeyChecking=yes root@"$host" 'pkill -x zftcppingpong 2>/dev/null || true; p=/sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages; b=$(cat $p); sysctl -w vm.nr_hugepages=0 >/dev/null; printf "%s -> %s\n" "$b" "$(cat $p)"'
  done
} 2>&1 | tee "$OUT/raw/classroom.txt"
trap - EXIT
(cd "$OUT/raw" && wc -l zf_r*_samples.ns | tee sample-counts.txt)
for host in 10.1.1.1 10.1.1.2; do ssh -n -o BatchMode=yes -o StrictHostKeyChecking=yes root@"$host" 'test "$(cat /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages)" = 0'; done
(cd "$OUT" && sha256sum raw/* run.env >SHA256SUMS); echo "evidence=$OUT"
