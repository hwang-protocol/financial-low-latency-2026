#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-07-phc-readonly"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"

for host in 10.1.1.1 10.1.1.2; do
  ssh -n -o BatchMode=yes -o StrictHostKeyChecking=yes root@"$host" '
    name=$(hostname)
    printf "%s / verify\n===== 查主机名 =====\n[哪台] 对: vm-2522-01 或 vm-2522-02  证: 没看错机\n$ hostname\n%s\n" "$name" "$name"
    printf "===== 查同步进程 =====\n[进程] 对: none  证: 当前没有 ptp4l / phc2sys / ts2phc / sfptpd 管理 PHC\n$ pgrep -ax ptp4l; pgrep -ax phc2sys; pgrep -ax ts2phc; pgrep -ax sfptpd\n"
    syncers=$(for p in ptp4l phc2sys ts2phc sfptpd; do pgrep -ax "$p" || :; done)
    [ -z "$syncers" ] || { printf "%s\n" "$syncers"; exit 1; }
    printf "none\n"
    printf "===== 查PHC节点 =====\n[/dev/ptp0] 对: 以 c 开头的字符设备  证: 这只硬件钟能打开\n$ ls -l /dev/ptp0\n"
    ls -l /dev/ptp0
    printf "===== 查PHC读数 =====\n[phc_ctl] 对: 打出 clock time is 和小数秒  证: PHC 可读；两次读数不能相减\n$ phc_ctl /dev/ptp0 get\n"
    phc_ctl /dev/ptp0 get
  '
done 2>&1 | tee "$OUT/raw/result.txt"
(cd "$OUT" && sha256sum raw/result.txt run.env >SHA256SUMS)
echo "evidence=$OUT"
