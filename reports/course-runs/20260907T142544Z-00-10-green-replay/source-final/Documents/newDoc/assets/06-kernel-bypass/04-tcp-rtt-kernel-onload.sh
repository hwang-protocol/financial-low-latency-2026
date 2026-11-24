#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-06-tcp-rtt-kernel-onload"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
SRC=Documents/newDoc/assets/06-kernel-bypass/tcp_rtt.c
SRC_SHA="$(sha256sum "$SRC" | awk '{print $1}')"
printf 'RUN_ID=%s\nUTC_STARTED=%s\nHOSTS=%s\nCPU=%s\nPAYLOAD=%s\nWARMUP=%s\nMEASURED_PER_ROUND=%s\nROUNDS_PER_ARM=%s\nPERCENTILE_METHOD=%s\nSOURCE_SHA256=%s\n' \
  "$RUN_ID" "$(date -u +%FT%TZ)" '10.1.1.1,10.1.1.2' 2 52 1000 10000 3 nearest-rank "$SRC_SHA" >"$OUT/run.env"
# ~~~~~同一份 tcp_rtt，先编到两端~~~~~
scp -o BatchMode=yes -o StrictHostKeyChecking=yes "$SRC" root@10.1.1.1:/tmp/tcp_rtt.c
ssh -n -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.1 \
  'gcc -O2 -Wall -Wextra -Werror -o /opt/flle/course-bin/tcp_rtt /tmp/tcp_rtt.c && sha256sum /opt/flle/course-bin/tcp_rtt' >"$OUT/raw/compile.txt"
scp -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.1:/opt/flle/course-bin/tcp_rtt /tmp/tcp_rtt
scp -o BatchMode=yes -o StrictHostKeyChecking=yes /tmp/tcp_rtt root@10.1.1.2:/opt/flle/course-bin/tcp_rtt
run_one() {
  local mode="$1" round="$2" port="$3" launcher='' tag
  tag="${mode}_r${round}"
  [[ "$mode" == onload ]] && launcher=onload
  ssh -n -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.1 'pkill -x tcp_rtt 2>/dev/null || true'
  ssh -f -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.1 \
    "taskset -c 2 $launcher /opt/flle/course-bin/tcp_rtt server $port > /tmp/${tag}_server.txt 2>&1"
  sleep 1
  ssh -n -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
    "taskset -c 2 $launcher /opt/flle/course-bin/tcp_rtt client 20.1.1.1 $port /tmp/${RUN_ID}-${tag}.csv" \
    >"$OUT/raw/${tag}_client.txt"
  scp -o BatchMode=yes -o StrictHostKeyChecking=yes \
    "root@10.1.1.2:/tmp/${RUN_ID}-${tag}.csv" "$OUT/raw/${tag}_samples.csv"
  ssh -n -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.1 \
    "cat /tmp/${tag}_server.txt" >"$OUT/raw/${tag}_server.txt"
  ssh -n -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.1 'pkill -x tcp_rtt 2>/dev/null || true'
}

# ~~~~~交错三轮：K→O，O→K，K→O；按轮次隔开对照表~~~~~
run_one kernel 1 47001; run_one onload 1 47011
run_one onload 2 47012; run_one kernel 2 47002
run_one kernel 3 47003; run_one onload 3 47013
{
  printf '%-8s %-3s %10s %4s %8s %8s\n' path rnd completed lost p50_ns p99_ns
  prev=; for tag in kernel_r1 onload_r1 onload_r2 kernel_r2 kernel_r3 onload_r3; do
    rnd=${tag##*_r}; [[ "$rnd" != "$prev" ]] && printf '%s\n' "----- r${rnd} -----"
    awk -v t="$tag" '{for(i=1;i<=NF;i++){n=split($i,a,"=");if(n==2)k[a[1]]=a[2]}}
      END{split(t,p,/_r/);printf "%-8s r%-2s %10s %4s %8s %8s\n",p[1],p[2],k["completed"],k["lost"],k["rtt_p50_ns"],k["rtt_p99_ns"]}' \
      "$OUT/raw/${tag}_client.txt"
    prev=$rnd
  done
} | tee "$OUT/raw/classroom.txt"
(cd "$OUT/raw" && wc -l *_samples.csv >sample-counts.txt)
(cd "$OUT" && sha256sum raw/* run.env >SHA256SUMS); echo "evidence=$OUT"
