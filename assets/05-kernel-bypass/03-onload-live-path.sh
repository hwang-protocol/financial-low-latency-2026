#!/usr/bin/env bash
(
set -Eeuo pipefail
cd /qyt-fll
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-05-onload-live-path"
OUT="reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
S=/var/tmp/onload_path_server.py
C=/var/tmp/onload_path_client.py
# ~~~~~两端 onload 建连接；lots 全文入库，终端只筛课堂行~~~~~
scp -o BatchMode=yes -o StrictHostKeyChecking=yes assets/05-kernel-bypass/onload_server.py root@10.1.1.1:"$S"
scp -o BatchMode=yes -o StrictHostKeyChecking=yes assets/05-kernel-bypass/onload_client.py root@10.1.1.2:"$C"
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.1 "set -Eeuo pipefail; onload python3 $S 46211 & p=\$!; sleep 2; onload_stackdump lots; wait \$p" >"$OUT/raw/server.txt" 2>&1 &
sp=$!
sleep 1
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 "set -Eeuo pipefail; onload python3 $C 46211 & p=\$!; sleep 2; onload_stackdump lots; wait \$p" >"$OUT/raw/client.txt" 2>&1 &
wait $!
wait "$sp"
pick='^TCP .*ESTABLISHED|Onloaded\(Valid\)|server_bytes=|client_bytes=|client_reply=|LD_PRELOAD='
{
  printf '%s\n' "===== 活连接 Onloaded(Valid) =====" "----- server -----"
  grep -E "$pick" "$OUT/raw/server.txt" || true
  printf '%s\n' "" "----- client -----"
  grep -E "$pick" "$OUT/raw/client.txt" || true
  # ~~~~~同一份 client：先普通 python3，再 onload；整行交给 .2~~~~~
  printf '%s\n' "" "===== 同一份程序两种启动 =====" "----- kernel -----"
  ssh -f -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.1 "python3 $S 46301 >/tmp/kb46301.txt 2>&1"
  ssh -f -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.1 "python3 $S 46302 >/tmp/kb46302.txt 2>&1"
  sleep 1
  ssh -n -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 "strace -qq -f -c -e trace=network python3 $C 46301"
  printf '%s\n' "" "----- onload -----"
  ssh -n -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 "strace -qq -f -c -e trace=network onload python3 $C 46302"
} 2>&1 | tee "$OUT/raw/result.txt"
ssh -n -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.1 "rm -f $S /tmp/kb46301.txt /tmp/kb46302.txt"
ssh -n -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 "rm -f $C"
(cd "$OUT" && sha256sum raw/*.txt run.env >SHA256SUMS)
echo "evidence=$OUT"
)
