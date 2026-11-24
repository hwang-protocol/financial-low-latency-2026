import datetime
import json
from pathlib import Path
import socket
import subprocess
from urllib.request import urlopen

root = Path('/financial-low-latency')
out = root / 'Documents/reports/course-runs/20260910T080208Z-02-fanout-fix/raw'
run = '20260910T085337Z-02-trading-platform'


def direct(host, port):
    with socket.create_connection((host, port), timeout=5) as connection:
        connection.sendall(b'STATE\n')
        connection.shutdown(socket.SHUT_WR)
        with connection.makefile('rb') as stream:
            return json.loads(stream.readline())


result = dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), run=run)
with urlopen('http://10.1.1.101:8088/api/state', timeout=10) as reply:
    gateway = json.load(reply)
(out / 'final-gateway.json').write_text(json.dumps(gateway, indent=2) + '\n')
result['exchange'] = direct('10.1.1.1', 48120)
assert result['exchange']['replay_speed'] == 1 and result['exchange']['market_mode'] == 'UNICAST'
for name, port in [('auto', 48121), ('manual', 48122)]:
    client = result[name] = direct('10.1.1.2', port)
    assert client['integrity'] == 'HEALTHY' and client['trading_gate'] == 'OPEN'
    assert client['pending'] == client['gaps'] == client['bad_packets'] == 0
    assert not client['resync_required']
result['receiver'] = gateway['feed_receiver']
assert result['receiver']['overflow_disconnects'] == result['receiver']['discarded_queue_packets'] == 0
assert result['receiver']['clients'] == 2
verify = subprocess.run(['bash', 'apps/flle-trading-lab/scripts/transport_labctl.sh', 'verify', run],
                        cwd=root, capture_output=True, text=True, timeout=90)
(out / 'final-platform-verify.txt').write_text(verify.stdout + verify.stderr)
verify.check_returncode()
command = r'''python3 - <<'PY'
import json, pathlib, subprocess, hashlib
lines=pathlib.Path('/proc/net/snmp').read_text().splitlines()
udp=[line.split()[1:] for line in lines if line.startswith('Udp:')]
owners=[]
for process in pathlib.Path('/proc').iterdir():
    if not process.name.isdigit(): continue
    try:
        cmd=(process/'cmdline').read_bytes().replace(b'\0',b' ').decode()
        if not cmd.startswith('/var/tmp/flle-trading-lab-'): continue
        held=[]
        for fd in (process/'fd').iterdir():
            try: target=str(fd.readlink())
            except OSError: continue
            if target=='/var/tmp/flle-ch08-10.lock': held.append(fd.name)
        owners.append(dict(pid=int(process.name),command=cmd,lock_fds=held,
                           binary_sha256=hashlib.sha256((process/'exe').read_bytes()).hexdigest()))
    except (OSError,UnicodeError): pass
lock=subprocess.run(['flock','-n','/var/tmp/flle-ch08-10.lock','true'])
result=dict(processes=owners,lock_probe_rc=lock.returncode,
            udp=dict(zip(udp[0],map(int,udp[1]))),
            sockets=subprocess.check_output(['ss','-u','-a','-n','-m','-p'],text=True),
            membership=subprocess.check_output(['ip','maddr','show','dev','ens64np1'],text=True),
            driver=str(pathlib.Path('/sys/bus/pci/devices/0000:03:00.0/driver').resolve()))
print(json.dumps(result,indent=2))
assert lock.returncode==0 and not any(item['lock_fds'] for item in owners)
assert result['udp']['InErrors']==result['udp']['RcvbufErrors']==0
assert result['driver']=='/sys/bus/pci/drivers/sfc'
PY'''
probe = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                        'root@10.1.1.2', command], capture_output=True, text=True, timeout=25)
(out / 'final-trader-host.txt').write_text(probe.stdout + probe.stderr)
probe.check_returncode()
result['trader_host'] = json.loads(probe.stdout)
result['verify_exit_code'] = verify.returncode
igmp = subprocess.run(['python3', 'Documents/newDoc/assets/02-trading-baseline/inspect-igmp.py',
                       str(out / 'final-switch.txt'), '--members'], cwd=root, capture_output=True, text=True)
(out / 'final-igmp-inspection.txt').write_text(igmp.stdout + igmp.stderr)
igmp.check_returncode()
result['igmp_exit_code'] = igmp.returncode
result['status'] = 'PASS'
(out / 'final-readonly.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps({key: result[key] for key in ['utc', 'run', 'status', 'verify_exit_code']}, indent=2))
for name in ['auto', 'manual']:
    print(name, {key: result[name][key] for key in ['session', 'integrity', 'next_expected', 'pending', 'gaps', 'trading_gate']})
print('receiver', result['receiver'])
