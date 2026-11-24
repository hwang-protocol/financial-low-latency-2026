#!/usr/bin/env python3
"""Exercise real stage processes/guard with fake actions in an isolated /tmp root."""
from pathlib import Path
from unittest.mock import patch
import importlib.util
import io
import json
import os
import signal
import tempfile
import threading
import time

HERE = Path(__file__).resolve().parent


def wait_until(predicate):
    deadline = time.monotonic()+8
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.05)
    raise AssertionError('guard did not finish')


def load_isolated(root):
    support = root/'Documents/newDoc/assets/10-verilator/live-support'
    support.mkdir(parents=True)
    common = support.parent.parent / 'common'
    common.mkdir()
    (common/'feed-guardianctl.sh').write_text('# isolated fixture\n')
    (root/'Documents/reports/course-runs').mkdir(parents=True)
    code = (HERE/'stage-session.py').read_text().replace("ROOT = Path('/financial-low-latency')", f'ROOT = Path({str(root)!r})')
    code = code.replace("GLOBAL_LOCK = Path('/var/tmp/flle-ch08-10.lock')", f'GLOBAL_LOCK = Path({str(root/"global.lock")!r})')
    module_path = support/'stage-session.py'; module_path.write_text(code)
    (support/'stage-actions.sh').write_text('''#!/usr/bin/env bash
set -Eeuo pipefail
printf '%s\\n' "$1" >>"$OUT/actions.log"
if test "$1" = prepare; then touch "$OUT/armed"; fi
if test "${FLLE_STAGE_TEST_FAIL:-}" = "$1"; then exit 17; fi
''')
    spec = importlib.util.spec_from_file_location('stages', module_path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    module.display = lambda *args: None  # Output uses separate receipt tests, never fake evidence.
    return module


def create(module):
    with patch.object(module.urllib.request, 'urlopen', return_value=io.BytesIO(b'{"market_mode":"UNICAST","replay":{"status":"PLAYING"}}')):
        module.foreground('prepare')
    run_id = json.loads(module.POINTER.read_text())['run_id']
    out = module.run_path(run_id)
    return out, lambda: json.loads((out/'session.json').read_text())


for scenario in ['four-stages', 'failed-verify', 'expired', 'long-pause', 'missing-guard']:
    with tempfile.TemporaryDirectory(prefix='flle-rtl-stages-test-') as tmp:
        module = load_isolated(Path(tmp))
        out, state = create(module)
        try:
            assert (out/'actions.log').read_text() == 'prepare\n', 'prepare ran a future stage'
            assert state()['phase'] == 'PREPARED'
            try:
                module.foreground('verify')
            except RuntimeError:
                pass
            else:
                raise AssertionError('verify accepted before arm')
            # Guard must keep the shared lock after the configure process ends.
            with module.GLOBAL_LOCK.open('a') as lock:
                try:
                    module.fcntl.flock(lock, module.fcntl.LOCK_EX | module.fcntl.LOCK_NB)
                except BlockingIOError:
                    pass
                else:
                    raise AssertionError('shared lock lost between cards')
            if scenario == 'four-stages':
                with (out/'stage.lock').open('a') as poll_lock:
                    module.fcntl.flock(poll_lock, module.fcntl.LOCK_EX)
                    release = threading.Timer(0.15, lambda: module.fcntl.flock(poll_lock, module.fcntl.LOCK_UN))
                    release.start()
                    module.foreground('arm')
                    release.join()
                assert 'guard_boot' in state()
            else:
                module.foreground('arm')
            assert (out/'actions.log').read_text() == 'prepare\narm\n', 'arm advanced to verification'
            if scenario == 'missing-guard':
                os.kill(state()['guard_pid'], signal.SIGTERM)
                wait_until(lambda: module.identity(state()['guard_pid']) is None)
                try:
                    module.foreground('verify')
                except RuntimeError:
                    pass
                else:
                    raise AssertionError('DROP accepted without guard')
                module.foreground('restore')
                assert state()['phase'] == 'RESTORED'
                assert (out/'actions.log').read_text() == 'prepare\narm\nrestore\n'
            elif scenario == 'expired':
                data = state(); data.update(expires=0, phase='VERIFYING'); module.save(out/'session.json', data)
                wait_until(lambda: state()['phase'] == 'EXPIRED')
                assert (out/'actions.log').read_text() == 'prepare\narm\ncleanup\n'
            elif scenario == 'long-pause':
                data = state(); data['expires'] = 0; module.save(out/'session.json', data)
                time.sleep(5.5)  # Let the real guard poll after the old deadline.
                assert state()['phase'] == 'GAP_CAPTURED', 'teacher pause triggered cleanup'
                module.foreground('verify')
                data = state(); data['expires'] = 0; module.save(out/'session.json', data)
                module.foreground('verify')
                module.foreground('restore')
                assert (out/'actions.log').read_text() == 'prepare\narm\nverify\nverify\nrestore\n'
            elif scenario == 'failed-verify':
                with patch.dict(os.environ, {'FLLE_STAGE_TEST_FAIL': 'verify'}):
                    try:
                        module.foreground('verify')
                    except RuntimeError:
                        pass
                    else:
                        raise AssertionError('failed verify returned success')
                assert state()['phase'] == 'ROLLED_BACK'
                assert (out/'actions.log').read_text().endswith('verify\ncleanup\n')
            else:
                module.foreground('verify')
                assert state()['phase'] == 'VERIFIED'
                assert (out/'actions.log').read_text() == 'prepare\narm\nverify\n'
                try:
                    module.foreground('arm')
                except RuntimeError:
                    pass
                else:
                    raise AssertionError('duplicate arm accepted')
                module.foreground('verify')
                assert (out/'actions.log').read_text() == 'prepare\narm\nverify\nverify\n'
                module.foreground('restore')
                module.foreground('restore')
                assert state()['phase'] == 'RESTORED'
                assert (out/'actions.log').read_text() == 'prepare\narm\nverify\nverify\nrestore\n'
        finally:
            data = state(); data['phase'] = 'RESTORED'; module.save(out/'session.json', data)
            def released():
                with module.GLOBAL_LOCK.open('a') as lock:
                    try:
                        module.fcntl.flock(lock, module.fcntl.LOCK_EX | module.fcntl.LOCK_NB)
                        return True
                    except BlockingIOError:
                        return False
            wait_until(released)

print('PASS: independent stages; shared lock; order/duplicate gates; failure rollback; expiry; missing-guard recovery (isolated mocks)')

# These are synthetic fixtures, not course-run evidence.
spec = importlib.util.spec_from_file_location('stage_output', HERE/'stage-output.py')
formatter = importlib.util.module_from_spec(spec); spec.loader.exec_module(formatter)
with tempfile.TemporaryDirectory(prefix='flle-rtl-output-fixture-') as tmp:
    out=Path(tmp); raw=out/'raw'; raw.mkdir()
    feed={'session':'fixture', 'integrity':'HEALTHY', 'next_expected':100, 'gap_size':0, 'path':'UNICAST', 'trading_gate':'OPEN'}
    compact={'session':'fixture','market_mode':'MULTICAST','trader_auto':'ONLINE','feed':feed}
    full={'session':'fixture','market_mode':'MULTICAST','replay':{'status':'PAUSED'},
          'health':{'trader_auto':{'status':'ONLINE'}},'feed':feed}
    def write(name, data): (raw/(name+'.json')).write_text(json.dumps(data))
    write('feed-baseline',compact); write('state-prepared',full)
    initial='adapter_ready mode=allow remaining_drops=0\n'
    (raw/'adapter-prepared.log').write_text(initial)
    (raw/'build-and-selftest.txt').write_text('rtl_selftest=PASS allow=1 target_drop=1 second_pass=1 locate_mismatch_pass=1 stock_mismatch_pass=1 type_f_pass=1\n')
    assert '本次策略丢包数：0' in formatter.render('prepare',out)
    feed.update(integrity='GAP', next_expected=579, gap_size=1, trading_gate='INHIBITED_FEED_GAP')
    write('feed-gap',compact); write('feed-verify',compact); write('state-armed',full); write('state-verify',full)
    dropped=initial+'adapter_arm remaining_drops=1 ttl_ms=5000\nrtl_drop sequence=579 remaining=0 drop_count=1\n'
    for name in ['adapter-armed','adapter-verify']: (raw/(name+'.log')).write_text(dropped)
    (raw/'block-command.txt').write_text('control_consumed=block\n')
    write('order-gate',{'http_status':400,'error':'FEED_NOT_HEALTHY'}); write('gui-gap-contract',{'result':'PASS'})
    assert '现场已保留' in formatter.render('arm',out)
    assert 'sequence=579' in formatter.render('verify',out)
    for mutation in ['wrong-sequence','duplicate-drop','different-session','running-replay']:
        write('state-verify',full); write('feed-verify',compact); (raw/'adapter-verify.log').write_text(dropped)
        if mutation=='wrong-sequence':
            bad=json.loads(json.dumps(compact)); bad['feed']['next_expected']=580; write('feed-verify',bad)
        elif mutation=='duplicate-drop': (raw/'adapter-verify.log').write_text(dropped+'rtl_drop sequence=580 remaining=0 drop_count=2\n')
        elif mutation=='different-session':
            bad=json.loads(json.dumps(full)); bad['session']='other'; bad['feed']['session']='other'; write('state-verify',bad)
        else:
            bad=json.loads(json.dumps(full)); bad['replay']['status']='PLAYING'; write('state-verify',bad)
        try: formatter.render('verify',out)
        except ValueError: pass
        else: raise AssertionError('accepted '+mutation)
    feed.update(session='restored-fixture', integrity='HEALTHY', gap_size=0, trading_gate='OPEN')
    full.update(session='restored-fixture', market_mode='UNICAST', replay={'status':'PLAYING'})
    write('state-restored',full)
    (out/'session.json').write_text(json.dumps({'original_mode':'UNICAST','original_playback':'PLAYING'}))
    (raw/'adapter-stop.txt').write_text('adapter_stopped=1 control_absent=1\n')
    orders={'result':'PASS','feed':dict(feed),'orders':[{'result':'ORDER_EXECUTED'},{'result':'ORDER_EXECUTED'}], 'position_AAPL':[10,10]}
    write('post-restore-orders',orders)
    assert '10 → 10' in formatter.render('restore',out)
    orders['position_AAPL']=[10,11]; write('post-restore-orders',orders)
    try: formatter.render('restore',out)
    except ValueError: pass
    else: raise AssertionError('unbalanced position accepted as restored')
print('PASS: receipt validation rejects wrong sequence, extra DROP, changed session and unpaused replay')

# Signal only a child process we created; a forged identity must be rejected.
import subprocess
spec=importlib.util.spec_from_file_location('remote_control', HERE/'remote-control.py')
remote=importlib.util.module_from_spec(spec); spec.loader.exec_module(remote)
with tempfile.TemporaryDirectory(prefix='flle-rtl-identity-fixture-') as tmp:
    remote.IDENTITY=Path(tmp)/'identity.json'; remote.CONTROL=Path(tmp)/'control'
    proc=subprocess.Popen(['sleep','60'])
    try:
        saved=remote.identity(proc.pid); remote.BINARY=Path(saved['exe'])
        forged=dict(saved,start='incorrect'); remote.IDENTITY.write_text(json.dumps(forged))
        try: remote.stop()
        except RuntimeError: pass
        else: raise AssertionError('forged PID identity accepted')
        assert proc.poll() is None
        remote.IDENTITY.write_text(json.dumps(saved))
        remote.CONTROL.write_text('allow\n')
        try: remote.command('block')
        except FileExistsError: pass
        else: raise AssertionError('unconsumed control was overwritten')
        assert remote.CONTROL.read_text()=='allow\n'
        remote.CONTROL.unlink()
        def consume():
            assert remote.CONTROL.read_text()=='block\n'
            remote.CONTROL.unlink()
        consumer=threading.Timer(0.05,consume); consumer.start()
        remote.command('block'); consumer.join()
        remote.stop(); proc.wait(timeout=2)
    finally:
        if proc.poll() is None: proc.kill(); proc.wait()
print('PASS: remote identity mismatch cannot stop the process; matched child stops correctly')

with tempfile.TemporaryDirectory(prefix='flle-rtl-recovery-fixture-') as tmp:
    module=load_isolated(Path(tmp)); out, state=create(module)
    try:
        (out/'order-check-started').touch()  # Simulate failure after recovery orders began.
        with patch.dict(os.environ, {'FLLE_STAGE_TEST_FAIL':'restore'}):
            try: module.foreground('restore')
            except RuntimeError: pass
            else: raise AssertionError('failed recovery accepted')
        assert state()['phase']=='RESTORE_REQUIRED' and state()['network_restored']
        try: module.foreground('restore')
        except RuntimeError: pass
        else: raise AssertionError('failed trade verification was hidden')
        calls=(out/'actions.log').read_text().splitlines()
        assert calls.count('restore')==1 and calls.count('cleanup')==2, calls
    finally:
        data=state(); data['phase']='RESTORED'; module.save(out/'session.json',data)
        wait_until(lambda: module.identity(data['guard_pid']) is None)
print('PASS: failed order verification only permits network cleanup; repeated orders blocked')
