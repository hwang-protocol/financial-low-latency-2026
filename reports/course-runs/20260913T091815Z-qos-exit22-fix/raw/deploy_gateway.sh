#!/usr/bin/env bash
set -Eeuo pipefail
source Documents/reports/run-state/06-qos-exit22-fix.env
REMOTE_RUN_DIR="/var/tmp/flle-trading-lab-$PARENT_RUN_ID"
scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes "root@10.1.1.101:$REMOTE_RUN_DIR/flle_trading/gateway.py" "$OUT/raw/gateway-before.py"
scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes "root@10.1.1.101:$REMOTE_RUN_DIR/source.sha256" "$OUT/raw/source-before.sha256"
scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes apps/flle-trading-lab/flle_trading/gateway.py "root@10.1.1.101:$REMOTE_RUN_DIR/flle_trading/gateway.py.qos-fix"
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.101 bash -s -- "$REMOTE_RUN_DIR" <<'REMOTE' >"$OUT/raw/gateway-deploy.txt" 2>&1
set -Eeuo pipefail
run_dir="$1"
cd "$run_dir"
sha256sum -c source.sha256 >/dev/null
read -r pid_field start_field boot_field <gateway.identity
pid="${pid_field#pid=}"
test "$(cat gateway.pid)" = "$pid"
test "$(awk '{print $22}' /proc/$pid/stat)" = "${start_field#start_ticks=}"
test "$(cat /proc/sys/kernel/random/boot_id)" = "${boot_field#boot_id=}"
tr '\0' ' ' </proc/$pid/cmdline | grep -F -- "--web-root $run_dir/web"
cp -p flle_trading/gateway.py flle_trading/gateway.py.before-qos-fix
mv flle_trading/gateway.py.qos-fix flle_trading/gateway.py
python3 - <<'PY'
from pathlib import Path
import hashlib
p=Path('source.sha256');lines=p.read_text().splitlines();count=0
for i,line in enumerate(lines):
 digest,name=line.split(maxsplit=1)
 if name.lstrip('./')=='flle_trading/gateway.py':
  lines[i]=hashlib.sha256(Path(name).read_bytes()).hexdigest()+'  '+name;count+=1
assert count==1
p.write_text('\n'.join(lines)+'\n')
compile(Path('flle_trading/gateway.py').read_text(),'gateway.py','exec')
PY
kill -TERM "$pid"
for _ in $(seq 1 50); do test ! -e "/proc/$pid" && break; sleep 0.1; done
test ! -e "/proc/$pid"
nohup env PYTHONPATH="$run_dir" python3 -m flle_trading.gateway --web-root "$run_dir/web" --transport-lab --data-plane-controller-url http://10.1.1.2:48606 </dev/null >gateway.log 2>&1 &
new_pid=$!
printf '%s\n' "$new_pid" >gateway.pid
printf 'pid=%s start_ticks=%s boot_id=%s\n' "$new_pid" "$(awk '{print $22}' /proc/$new_pid/stat)" "$(cat /proc/sys/kernel/random/boot_id)" >gateway.identity
sha256sum -c source.sha256 >/dev/null
cat gateway.identity
sha256sum flle_trading/gateway.py
REMOTE
curl -fsS --retry 8 --retry-connrefused --retry-delay 1 http://10.1.1.101:8088/api/state >"$OUT/raw/state-after-restart.json"
