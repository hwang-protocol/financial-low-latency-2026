import datetime
import json
from pathlib import Path
import socket
import subprocess
import time
from urllib.request import Request, urlopen

ROOT = Path('/financial-low-latency')
API = 'http://10.1.1.101:8088'


def stamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def api(path, body=None):
    request = Request(API + path, data=None if body is None else json.dumps(body).encode(),
                      headers={'Content-Type': 'application/json'})
    with urlopen(request, timeout=45) as reply:
        result = json.load(reply)
    if result.get('error'):
        raise RuntimeError(result['error'])
    return result


def direct(host, port):
    with socket.create_connection((host, port), timeout=5) as connection:
        connection.sendall(b'STATE\n')
        connection.shutdown(socket.SHUT_WR)
        with connection.makefile('rb') as stream:
            return json.loads(stream.readline())


run_id = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-02-full-source-soak'
out = ROOT / 'Documents/reports/course-runs' / run_id
(out / 'raw').mkdir(parents=True)
summary = dict(run_id=run_id, started=stamp(), speed=20, status='RUNNING', samples=0,
               limits='Accelerated complete source replay, not 6.5 hours at normal speed.')
(ROOT / 'Documents/reports/run-state/02-full-source-soak.json').write_text(json.dumps(summary, indent=2) + '\n')


def save(name, value):
    (out / 'raw' / name).write_text(json.dumps(value, indent=2) + '\n')


def host_snapshot(label):
    command = r'''python3 - <<'PY'
import json, pathlib, subprocess
lines=pathlib.Path('/proc/net/snmp').read_text().splitlines()
udp=[line.split()[1:] for line in lines if line.startswith('Udp:')]
processes=[]
for item in pathlib.Path('/proc').iterdir():
    if not item.name.isdigit(): continue
    try:
        cmd=(item/'cmdline').read_bytes().replace(b'\0',b' ').decode()
        if not cmd.startswith('/var/tmp/flle-trading-lab-') or 'flle-' not in cmd: continue
        status=(item/'status').read_text()
        processes.append(dict(pid=int(item.name), command=cmd,
             memory=[line for line in status.splitlines() if line.startswith(('VmRSS:', 'VmSize:'))]))
    except (OSError,UnicodeError): pass
print(json.dumps(dict(udp=dict(zip(udp[0],map(int,udp[1]))), processes=processes,
    sockets=subprocess.check_output(['ss','-u','-a','-n','-m','-p'],text=True)),indent=2))
PY'''
    result = subprocess.run(['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
                             '-o', 'ConnectTimeout=5', 'root@10.1.1.2', command],
                            capture_output=True, text=True, timeout=20)
    (out / 'raw' / (label + '-host.txt')).write_text(result.stdout + result.stderr)
    result.check_returncode()
    return json.loads(result.stdout)


before = direct('10.1.1.1', 48120)
save('before-exchange.json', before)
original_speed, original_mode = before['replay_speed'], before['market_mode']
start = time.monotonic()
try:
    baseline = host_snapshot('before')
    save('set-unicast.json', api('/api/market', {'market_mode': 'UNICAST'}))
    save('set-speed.json', api('/api/replay', {'action': 'SPEED', 'speed': 20}))
    reset = api('/api/replay', {'action': 'RESTART', 'clear_trades': True})
    save('reset.json', reset)
    session = reset['session']
    summary['session'] = session
    print('SOAK_STARTED', run_id, 'session=' + session, flush=True)
    previous_log = 0
    with (out / 'raw/samples.jsonl').open('w') as log:
        while time.monotonic() - start < 2400:
            exchange = direct('10.1.1.1', 48120)
            auto = direct('10.1.1.2', 48121)
            manual = direct('10.1.1.2', 48122)
            sample = dict(utc=stamp(), seconds=time.monotonic()-start,
                          exchange=exchange, auto=auto, manual=manual)
            log.write(json.dumps(sample) + '\n'); log.flush()
            summary['samples'] += 1
            for name, state in [('auto', auto), ('manual', manual)]:
                if state['session'] != session or state['integrity'] != 'HEALTHY' or state['pending']:
                    raise AssertionError((name, {key: state.get(key) for key in
                        ['session', 'integrity', 'pending', 'next_expected', 'resync_reason']}))
                if state.get('gaps', 0) or state.get('bad_packets', 0):
                    raise AssertionError((name, 'nonzero gap/bad packet counter'))
            if sample['seconds'] - previous_log >= 30:
                previous_log = sample['seconds']
                gateway = api('/api/state')
                save('gateway-%04d.json' % int(previous_log), gateway)
                receiver = gateway.get('feed_receiver', {})
                if receiver.get('overflow_disconnects') or receiver.get('discarded_queue_packets'):
                    raise AssertionError(('receiver', receiver))
                print('SOAK', round(sample['seconds']), 'seconds', exchange['source_clock'],
                      'seq=' + str(exchange['market_sequence']),
                      'pending=' + str(auto['pending']) + '/' + str(manual['pending']),
                      'queue_peak=' + str(receiver.get('peak_client_packets')), flush=True)
                host_snapshot('sample-%04d' % int(previous_log))
            if exchange['session'] != session:
                raise AssertionError('Replay rolled before COMPLETE was recorded')
            if exchange['replay_status'] == 'COMPLETE':
                expected = exchange['market_sequence']
                for name, state in [('auto', auto), ('manual', manual)]:
                    if state['last_delivered'] != expected or state['next_expected'] != expected + 1:
                        raise AssertionError((name, 'final sequence mismatch', expected, state['last_delivered']))
                save('complete.json', sample)
                summary.update(status='PASS', messages=expected,
                    source_first=exchange['first_source_clock'], source_last=exchange['last_source_clock'],
                    seconds=sample['seconds'], old_gap_sequence_covered=expected >= 7641279)
                break
            time.sleep(1)
        else:
            raise TimeoutError('Complete source replay exceeded 2400 seconds')
    after = host_snapshot('after')
    summary['udp_error_delta'] = {key: after['udp'][key] - baseline['udp'][key]
                                 for key in ['InErrors', 'RcvbufErrors']}
    if any(summary['udp_error_delta'].values()):
        raise AssertionError(summary['udp_error_delta'])
    save('after-gateway.json', api('/api/state'))
except BaseException as error:
    summary.update(status='FAIL', error=repr(error))
    raise
finally:
    try:
        save('restore-speed.json', api('/api/replay', {'action': 'SPEED', 'speed': original_speed}))
        save('restore-mode.json', api('/api/market', {'market_mode': original_mode}))
        restored = direct('10.1.1.1', 48120)
        if restored['replay_speed'] != original_speed or restored['market_mode'] != original_mode:
            raise AssertionError('Restore readback mismatch')
        summary['restored'] = True
    except BaseException as error:
        summary.update(status='FAIL', restore_error=repr(error))
    summary['finished'] = stamp()
    (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    (ROOT / 'Documents/reports/run-state/02-full-source-soak.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2), flush=True)

if summary['status'] != 'PASS':
    raise SystemExit(1)
