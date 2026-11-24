import datetime
import hashlib
import json
import pathlib
import subprocess
import urllib.request

root = pathlib.Path('/financial-low-latency')
run_id = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-02-feed-gap-diagnosis'
out = root / 'Documents/reports/course-runs' / run_id
(out / 'raw').mkdir(parents=True)
base = '20260910T043800Z-02-trading-platform'
remote_dir = '/var/tmp/flle-trading-lab-' + base
(out / 'run.env').write_text(f'RUN_ID={run_id}\nBASE_RUN_ID={base}\nMODE=READ_ONLY_DIAGNOSIS\n')
(root / 'Documents/reports/run-state/02-feed-gap-diagnosis.env').write_text(f'RUN_ID={run_id}\nBASE_RUN_ID={base}\nMODE=READ_ONLY_DIAGNOSIS\n')
for endpoint in ['state', 'events']:
    with urllib.request.urlopen('http://10.1.1.101:8088/api/' + endpoint, timeout=15) as response:
        data = response.read()
    (out / 'raw' / (endpoint + '.json')).write_bytes(data)
    value = json.loads(data)
    if endpoint == 'state':
        print('STATE_KEYS', list(value))
        for key, item in value.items():
            if key not in ['orders', 'order_history', 'trades', 'events', 'book', 'books', 'latency', 'reaction_latency']:
                encoded = json.dumps(item, ensure_ascii=False)
                print(key, encoded[:18000])
commands = {
    'trader-host': ('10.1.1.2', f'''date -u
uptime
ss -uapnm
ss -xapnm
cat /proc/net/snmp
cat /proc/net/softnet_stat
ps -eo pid,ppid,comm,pcpu,pmem,rss,etimes,args --sort=-rss
for file in {remote_dir}/*.pid {remote_dir}/*.log {remote_dir}/*.identity; do
  printf '\\nFILE=%s\\n' "$file"
  cat "$file"
done
sha256sum {remote_dir}/flle-feed-receiver {remote_dir}/flle-trader
ethtool -S ens64np1
journalctl -k --since '2026-09-10 12:30:00' --no-pager
'''),
    'exchange-host': ('10.1.1.1', f'''date -u
uptime
ss -uapnm
cat /proc/net/snmp
ps -eo pid,comm,pcpu,pmem,rss,etimes,args --sort=-rss
ls -lah {remote_dir}
ethtool -S ens64np0
'''),
}
for label, (host, command) in commands.items():
    result = subprocess.run(['ssh', '-T', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=5', 'root@' + host, 'bash', '-s'], input=command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
    (out / 'raw' / (label + '.txt')).write_text(result.stdout)
    print(label, 'rc=', result.returncode, 'bytes=', len(result.stdout))
lines = []
for path in sorted(out.rglob('*')):
    if path.is_file():
        lines.append(hashlib.sha256(path.read_bytes()).hexdigest() + '  ' + str(path.relative_to(out)))
(out / 'SHA256SUMS').write_text('\n'.join(lines) + '\n')
print('OUT=' + str(out))
