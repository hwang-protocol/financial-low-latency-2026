#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-06-dpdk-vfio-l2-audit"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
CLASSROOM="$OUT/raw/classroom.txt"; : >"$CLASSROOM"
KH=(-o BatchMode=yes -o StrictHostKeyChecking=yes)
SRC=Documents/newDoc/assets/06-kernel-bypass
MAC1=00:0f:53:d3:af:20
MAC2=00:0f:53:d3:af:21
STOP="/tmp/$RUN_ID-stop"
SESSION="/tmp/$RUN_ID-session"
SRC_SHA="$(sha256sum "$SRC/08-dpdk-vfio-l2.sh" "$SRC/l2_probe_rtt.c" "$SRC/l2_echo.c" "$SRC/dpdk-bind-measure-restore.sh" | tr '\n' ';')"
printf 'RUN_ID=%s\nUTC_STARTED=%s\nHOSTS=%s\nCPU=%s\nPAYLOAD=%s\nFRAME_BYTES_NO_FCS=%s\nWARMUP=%s\nMEASURED_PER_ROUND=%s\nROUNDS_PER_ARM=%s\nPERCENTILE_METHOD=%s\nSOURCES=%s\n' \
  "$RUN_ID" "$(date -u +%FT%TZ)" '10.1.1.1,10.1.1.2' 2 52 66 1000 10000 3 nearest-rank "$SRC_SHA" >"$OUT/run.env"

restore_gate() {
  ssh "${KH[@]}" root@10.1.1.1 "touch '$STOP'" 2>/dev/null || true
  sleep 2
  ssh "${KH[@]}" root@10.1.1.1 bash -s <<'REMOTE' || true
set +e
BDF=0000:03:00.0; IFACE=ens64np0
pkill -x dpdk-testpmd 2>/dev/null || true
/usr/bin/dpdk-devbind.py --bind=sfc "$BDF" >/dev/null 2>&1 || true
udevadm settle || true
current="$(find "/sys/bus/pci/devices/$BDF/net" -mindepth 1 -maxdepth 1 -printf '%f\n' 2>/dev/null | head -n 1)"
if [[ -n "$current" && "$current" != "$IFACE" ]]; then
  ip link set "$current" down || true; ip link set "$current" name "$IFACE" || true
fi
ip link set "$IFACE" up || true
ip addr replace 20.1.1.1/24 dev "$IFACE" || true
find /dev/hugepages -maxdepth 1 -type f -name 'rtemap_*' -delete 2>/dev/null || true
sysctl -w vm.nr_hugepages=0 >/dev/null || true
REMOTE
}
trap restore_gate EXIT

stage() {
  printf '\n===== %s =====\n' "$1" | tee -a "$CLASSROOM"
}

show_probe() {
  local mode="$1" round="$2" raw="$OUT/raw/${mode}_r${round}.txt"
  awk -v mode="$mode" -v round="$round" '
    {for (i=1;i<=NF;i++) {split($i,a,"="); v[a[1]]=a[2]}}
    END {printf "%-6s r%s  completed=%s lost=%s  p50=%s ns  p99=%s ns  max=%s ns\n",
      toupper(mode),round,v["completed"],v["lost"],v["rtt_p50_ns"],v["rtt_p99_ns"],v["rtt_max_ns"]}' "$raw" | tee -a "$CLASSROOM"
}

# ~~~~~先编 L2 尺子；外层 EXIT 负责交还闸~~~~~
stage '[1/5] 固定合同与编译两端 L2 尺子'
printf 'payload=52 B  frame=66 B(no FCS)  warmup=1000  measured=10000  rounds=3+3  cpu=2\n' | tee -a "$CLASSROOM"
scp "${KH[@]}" "$SRC/l2_probe_rtt.c" "$SRC/l2_echo.c" root@10.1.1.1:/tmp/
ssh "${KH[@]}" root@10.1.1.1 \
  'gcc -O2 -Wall -Wextra -Werror -o /opt/flle/course-bin/l2_probe_rtt /tmp/l2_probe_rtt.c && gcc -O2 -Wall -Wextra -Werror -o /opt/flle/course-bin/l2_echo /tmp/l2_echo.c && sha256sum /opt/flle/course-bin/l2_probe_rtt /opt/flle/course-bin/l2_echo' \
  >"$OUT/raw/build.txt"
scp "${KH[@]}" root@10.1.1.1:/opt/flle/course-bin/l2_probe_rtt root@10.1.1.1:/opt/flle/course-bin/l2_echo /tmp/
scp "${KH[@]}" /tmp/l2_probe_rtt /tmp/l2_echo root@10.1.1.2:/opt/flle/course-bin/

probe_one() {
  local mode="$1" round="$2" remote_raw
  remote_raw="/tmp/${RUN_ID}-${mode}-r${round}.csv"
  ssh "${KH[@]}" root@10.1.1.2 \
    "taskset -c 2 /opt/flle/course-bin/l2_probe_rtt ens64np1 $MAC2 $MAC1 '$remote_raw'" \
    >"$OUT/raw/${mode}_r${round}.txt"
  scp "${KH[@]}" "root@10.1.1.2:$remote_raw" "$OUT/raw/${mode}_r${round}_samples.csv"
  show_probe "$mode" "$round"
}

# ~~~~~Kernel L2 三轮~~~~~
stage '[2/5] Kernel 回弹 — .1 保持 sfc，AF_PACKET echo'
ssh "${KH[@]}" root@10.1.1.1 'pkill -x l2_echo 2>/dev/null || true'
ssh -f "${KH[@]}" root@10.1.1.1 'taskset -c 2 /opt/flle/course-bin/l2_echo ens64np0'
sleep 1
probe_one kernel 1; probe_one kernel 2; probe_one kernel 3
ssh "${KH[@]}" root@10.1.1.1 'pkill -x l2_echo 2>/dev/null || true'

# ~~~~~绑一次 VFIO，再量 DPDK 三轮，然后交还~~~~~
stage '[3/5] 交闸 — .1 从 sfc 改绑 vfio-pci，启动 testpmd'
scp "${KH[@]}" "$SRC/dpdk-bind-measure-restore.sh" "root@10.1.1.1:/tmp/$RUN_ID-gate.sh"
ssh "${KH[@]}" root@10.1.1.1 "mkdir -p '$SESSION'; rm -f '$STOP'; chmod +x '/tmp/$RUN_ID-gate.sh'"
ssh -f "${KH[@]}" root@10.1.1.1 \
  "STOP_FILE='$STOP' SESSION_DIR='$SESSION' bash '/tmp/$RUN_ID-gate.sh'"
ready=0
for _ in $(seq 1 40); do
  ssh "${KH[@]}" root@10.1.1.1 "grep -q TESTPMD_READY '$SESSION/session.log' 2>/dev/null" && { ready=1; break; }
  sleep 1
done
test "$ready" -eq 1
ssh "${KH[@]}" root@10.1.1.1 \
  "grep -m1 '^driver=sfc group=' '$SESSION/session.log'; grep -m1 'Using IOMMU type 1' '$SESSION/testpmd.log'; grep -m1 'Set macswap packet forwarding mode' '$SESSION/testpmd.log'; grep -m1 '^TESTPMD_READY$' '$SESSION/session.log'" \
  | tee -a "$CLASSROOM"

stage '[4/5] DPDK 回弹 — .2 尺子不变，.1 使用 testpmd macswap'
probe_one dpdk 1; probe_one dpdk 2; probe_one dpdk 3
ssh "${KH[@]}" root@10.1.1.1 "touch '$STOP'"
restored=0
for _ in $(seq 1 40); do
  ssh "${KH[@]}" root@10.1.1.1 "grep -q RESTORE_DONE '$SESSION/restore.receipt' 2>/dev/null" && { restored=1; break; }
  sleep 1
done
test "$restored" -eq 1
scp "${KH[@]}" "root@10.1.1.1:$SESSION/testpmd.log" "$OUT/raw/testpmd.log"
scp "${KH[@]}" "root@10.1.1.1:$SESSION/session.log" "$OUT/raw/gate-session.log"
scp "${KH[@]}" "root@10.1.1.1:$SESSION/restore.receipt" "$OUT/raw/gate-restore.txt"
ssh "${KH[@]}" root@10.1.1.1 "cat '$SESSION/session.log'; tail -n 100 '$SESSION/testpmd.log'; cat '$SESSION/restore.receipt'" \
  >"$OUT/raw/session.txt"
grep -E '^  (RX|TX)-packets:.*(dropped|total)' "$OUT/raw/testpmd.log" | tail -n 2 | sed 's/^  //' | tee -a "$CLASSROOM"

restore_gate
trap - EXIT
ssh "${KH[@]}" root@10.1.1.1 'test "$(basename "$(readlink /sys/bus/pci/devices/0000:03:00.0/driver)")" = sfc; test "$(cat /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages)" = 0; ip -4 -o addr show dev ens64np0 | grep -Fq " 20.1.1.1/24 "; ping -I ens64np0 -c 3 -W 1 20.1.1.2' \
  >"$OUT/raw/restore_ping.txt"
ssh "${KH[@]}" root@10.1.1.2 'test "$(basename "$(readlink /sys/bus/pci/devices/0000:03:00.0/driver)")" = sfc; test "$(cat /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages)" = 0; ip -4 -o addr show dev ens64np1 | grep -Fq " 20.1.1.2/24 "'
stage '[5/5] 交还验收 — X2522 回到 sfc，网口、地址和大页复原'
grep -E '^(driver=|netdev=|[0-9]+: ens64np0 |hugepages=|RESTORE_DONE$)' "$OUT/raw/gate-restore.txt" | tee -a "$CLASSROOM"
grep -E '^3 packets transmitted|^rtt min/' "$OUT/raw/restore_ping.txt" | tee -a "$CLASSROOM"
(cd "$OUT/raw" && wc -l *_samples.csv >sample-counts.txt)
printf 'evidence=%s\n' "$OUT" | tee -a "$CLASSROOM"
cp "$CLASSROOM" "$OUT/raw/result.txt"
(cd "$OUT" && sha256sum raw/* run.env >SHA256SUMS)
