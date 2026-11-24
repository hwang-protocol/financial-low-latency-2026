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
    support = root/'Documents/newDoc/assets/09-p4/live-support'
    support.mkdir(parents=True)
    (root/'Documents/reports/course-runs').mkdir(parents=True)
    code = (HERE/'stage-session.py').read_text().replace("ROOT = Path('/financial-low-latency')", f'ROOT = Path({str(root)!r})')
    code = code.replace("GLOBAL_LOCK = Path('/var/tmp/flle-ch08-10.lock')", f'GLOBAL_LOCK = Path({str(root/"global.lock")!r})')
    module_path = support/'stage-session.py'; module_path.write_text(code)
    (support/'stage-actions.sh').write_text('''#!/usr/bin/env bash
set -Eeuo pipefail
printf '%s\\n' "$1" >>"$OUT/actions.log"
if test "$1" = configure; then touch "$OUT/armed"; fi
if test "${FLLE_STAGE_TEST_FAIL:-}" = "$1"; then exit 17; fi
''')
    spec = importlib.util.spec_from_file_location('stages', module_path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    module.display = lambda *args: None  # Output uses separate receipt tests, never fake evidence.
    return module


def create(module):
    with patch.object(module.urllib.request, 'urlopen', return_value=io.BytesIO(b'{"market_mode":"UNICAST"}')):
        module.foreground('configure')
    run_id = json.loads(module.POINTER.read_text())['run_id']
    out = module.run_path(run_id)
    return out, lambda: json.loads((out/'session.json').read_text())


for scenario in ['four-stages', 'failed-drop', 'long-pause', 'interrupted-action', 'missing-guard']:
    with tempfile.TemporaryDirectory(prefix='flle-p4-stages-test-') as tmp:
        module = load_isolated(Path(tmp))
        out, state = create(module)
        try:
            assert (out/'actions.log').read_text() == 'configure\n', 'configure ran a future stage'
            assert state()['phase'] == 'CONFIGURED'
            if scenario == 'four-stages':
                legacy = state(); legacy.pop('guard_boot'); module.save(out/'session.json', legacy)
            try:
                module.foreground('drop')
            except RuntimeError:
                pass
            else:
                raise AssertionError('drop accepted without inspection')
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
                    module.foreground('inspect')
                    release.join()
                assert 'guard_boot' in state(), 'legacy state was not accepted/backfilled'
            else:
                module.foreground('inspect')
            assert (out/'actions.log').read_text() == 'configure\ninspect\n', 'inspect ran DROP'
            if scenario == 'missing-guard':
                os.kill(state()['guard_pid'], signal.SIGTERM)
                wait_until(lambda: module.identity(state()['guard_pid']) is None)
                try:
                    module.foreground('drop')
                except RuntimeError:
                    pass
                else:
                    raise AssertionError('DROP accepted without guard')
                module.foreground('restore')
                assert state()['phase'] == 'RESTORED'
                assert (out/'actions.log').read_text() == 'configure\ninspect\nrestore\n'
            elif scenario == 'long-pause':
                # Simulate an arbitrarily old legacy lease; quiet classroom states remain open.
                data = state(); data['expires'] = 0; module.save(out/'session.json', data)
                time.sleep(5.5)
                assert state()['phase'] == 'OBSERVED'
                assert (out/'actions.log').read_text() == 'configure\ninspect\n'
                module.foreground('drop')
                module.foreground('restore')
                assert state()['phase'] == 'RESTORED'
            elif scenario == 'interrupted-action':
                data = state(); data['phase'] = 'DROPPING'; data['expires'] = 0
                module.save(out/'session.json', data)
                wait_until(lambda: state()['phase'] == 'EXPIRED')
                assert (out/'actions.log').read_text() == 'configure\ninspect\ncleanup\n'
            elif scenario == 'failed-drop':
                with patch.dict(os.environ, {'FLLE_STAGE_TEST_FAIL': 'drop'}):
                    try:
                        module.foreground('drop')
                    except RuntimeError:
                        pass
                    else:
                        raise AssertionError('failed drop returned success')
                assert state()['phase'] == 'ROLLED_BACK'
                assert (out/'actions.log').read_text().endswith('drop\ncleanup\n')
            else:
                module.foreground('drop')
                assert state()['phase'] == 'DROPPED'
                assert (out/'actions.log').read_text() == 'configure\ninspect\ndrop\n'
                try:
                    module.foreground('drop')
                except RuntimeError:
                    pass
                else:
                    raise AssertionError('duplicate DROP accepted')
                module.foreground('restore')
                assert state()['phase'] == 'RESTORED'
                assert (out/'actions.log').read_text() == 'configure\ninspect\ndrop\nrestore\n'
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

source = (HERE/'stage-actions.sh').read_text()
assert source.index("'register_write IngressImpl.remaining_drops 0 1'") < source.index('( sleep 5;')
cleanup = source[source.index('cleanup(){'):source.index('restore(){')]
assert cleanup.index('p4-trading-restore-endpoints.plan') < cleanup.index('kill ') < cleanup.index('p4-trading-restore-final.plan')
print('PASS four independent stages; no automatic advance; shared lock between cards; wrong-order/duplicate rejection; failure rollback; unlimited classroom pauses and interrupted-action guard cleanup; isolated mocks only')

# Synthetic parser fixtures: assert bounded, data-derived output and reject a bad Feed.
spec = importlib.util.spec_from_file_location('stage_output', HERE/'stage-output.py')
formatter = importlib.util.module_from_spec(spec); spec.loader.exec_module(formatter)
with tempfile.TemporaryDirectory(prefix='flle-output-test-') as tmp:
    root = Path(tmp); raw = root/'raw'; raw.mkdir()
    (raw/'eos-inspect.txt').write_text('100 LEFT active Et1, Et11\n200 RIGHT active Et2, Et12\nusername SECRET_SENTINEL\n')
    (raw/'cli-inspect.txt').write_text('''Obtaining JSON from switch...
* ipv4.src : EXACT 14010101
* ipv4.dst : EXACT ef140114
* itch_type.value : EXACT 41
* itch_add.locate : EXACT 1f9f
* itch_add.stock : EXACT 4e56444120202020
Action entry: IngressImpl.select_policy -
RuntimeCmd: RuntimeCmd: IngressImpl.remaining_drops[0]= 0
RuntimeCmd: IngressImpl.policy_drop_packets[0]= (0 bytes, 0 packets)
''')
    data = {'session':'fixture', 'feed':{'integrity':'HEALTHY', 'next_expected':12345}}
    (raw/'feed-inspect.json').write_text(json.dumps(data))
    (raw/'state-inspect.json').write_text(json.dumps({'replay':{'status':'PAUSED'}}))
    rendered = formatter.render('inspect', root)
    assert 'next_expected=12345' in rendered and 'PAUSED' in rendered
    assert 'SECRET_SENTINEL' not in rendered and 'Obtaining JSON' not in rendered and 'RuntimeCmd:' not in rendered
    assert len(rendered.splitlines()) <= 24
    data['feed']['integrity'] = 'GAP'
    (raw/'feed-inspect.json').write_text(json.dumps(data))
    try:
        formatter.render('inspect', root)
    except ValueError:
        pass
    else:
        raise AssertionError('formatter claimed HEALTHY for a failed receipt')
print('PASS bounded output derives real fields, omits unselected logs and rejects unhealthy inspection')
