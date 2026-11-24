#!/usr/bin/env bash
set -Eeuo pipefail
cd /qyt-fll
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-07-linuxptp-tooling-prep"
OUT="reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"

for host in 10.1.1.1 10.1.1.2; do
  python3 assets/common/install-offline-packages.py "$host" ptp
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@"$host" bash -s <<'REMOTE'
set -Eeuo pipefail
printf '%s / verify\n' "$(hostname)"
printf '===== 查主机名 =====\n[哪台] 对: vm-2522-01 或 vm-2522-02  证: 没看错机\n$ hostname\n%s\n' "$(hostname)"
printf '===== 查phc_ctl =====\n[phc_ctl] 对: /usr/sbin/phc_ctl  证: 能读 PHC\n$ command -v phc_ctl\n%s\n' "$(command -v phc_ctl)"
printf '===== 查ptp4l =====\n[ptp4l] 对: /usr/sbin/ptp4l  证: 后面 PTP 实验有客户端\n$ command -v ptp4l\n%s\n' "$(command -v ptp4l)"
printf '===== 查ptp4l版本 =====\n[版本] 对: 打出一行版本号  证: linuxptp 已经能跑\n$ ptp4l -v\n%s\n' "$(ptp4l -v)"
REMOTE
done 2>&1 | tee "$OUT/raw/result.txt"
(cd "$OUT" && sha256sum raw/result.txt run.env >SHA256SUMS)
echo "evidence=$OUT"
