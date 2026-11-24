import datetime
import json
from pathlib import Path
import subprocess
import time
from urllib.request import Request, urlopen


root = Path('/financial-low-latency')
run_id = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-02-reset-lock-check'
out = root / 'Documents/reports/course-runs' / run_id
(out / 'raw').mkdir(parents=True)
summary = dict(run_id=run_id, status='RUNNING', resets=[])


def api(path, body=None):
    request = Request('http://10.1.1.101:8088' + path,
                      data=None if body is None else json.dumps(body).encode(),
                      headers={'Content-Type': 'application/json'})
    with urlopen(request, timeout=60) as reply:
        return json.load(reply)


command = r'''python3 - <<'PY'
import json, pathlib, subprocess
owners = []
for process in pathlib.Path('/proc').iterdir():
    if not process.name.isdigit(): continue
    try:
        cmd = (process / 'cmdline').read_bytes().replace(b'\0', b' ').decode()
        if not cmd.startswith('/var/tmp/flle-trading-lab-'): continue
        for fd in (process / 'fd').iterdir():
            try: target = str(fd.readlink())
            except OSError: continue
            if target == '/var/tmp/flle-ch08-10.lock':
                owners.append(dict(pid=int(process.name), fd=fd.name, command=cmd))
    except (OSError, UnicodeError): pass
lock = subprocess.run(['flock', '-n', '/var/tmp/flle-ch08-10.lock', 'true'])
print(json.dumps(dict(owners=owners, lock_probe_rc=lock.returncode)))
assert not owners and lock.returncode == 0
PY'''
try:
    for number in [1, 2]:
        before = api('/api/state')
        (out / 'raw' / f'before-{number}.json').write_text(json.dumps(before) + '\n')
        result = api('/api/replay', {'action': 'RESTART', 'clear_trades': True})
        (out / 'raw' / f'reset-{number}.json').write_text(json.dumps(result, indent=2) + '\n')
        assert result.get('ok') and result.get('session'), result
        probe = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                                'root@10.1.1.2', command], capture_output=True, text=True, timeout=20)
        (out / 'raw' / f'lock-{number}.txt').write_text(probe.stdout + probe.stderr)
        probe.check_returncode()
        summary['resets'].append(dict(number=number, session=result['session'], lock=json.loads(probe.stdout)))
        print('RESET', number, 'session=' + result['session'], 'LOCK_FREE no inherited descriptors', flush=True)
        time.sleep(2)
    assert summary['resets'][0]['session'] != summary['resets'][1]['session']
    summary['status'] = 'PASS'
except BaseException as error:
    summary.update(status='FAIL', error=repr(error))
    raise
finally:
    (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    (root / 'Documents/reports/run-state/02-reset-lock-check.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2), flush=True)
