#!/usr/bin/env python3
"""Run real foreground scripts with local API/SSH fixtures; never touch devices."""
import copy
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]

DRIVER = r'''
import json, os, pathlib, sys
root = pathlib.Path(os.environ['XDP_TEST_ROOT'])
path = root/'fixture.json'
s = json.loads(path.read_text())
kind, *args = sys.argv[1:]
def save(): path.write_text(json.dumps(s))
def log(event):
    with (root/'events.log').open('a') as f: f.write(event+'\n')
if kind == 'curl':
    if '-d' in args:
        data = json.loads(args[args.index('-d')+1])
        if 'market_mode' in data:
            s['market_mode'] = data['market_mode']; log('market:'+s['market_mode'])
        else:
            action = data['action']; log('replay:'+action)
            if action == 'RESTART':
                s['session'] = str(int(s['session'])+1)
                s['feed'].update(session=s['session'], integrity='HEALTHY', trading_gate='OPEN', next_expected=100, pending=0)
                s['replay']['status'] = 'PLAYING'
            elif action == 'PAUSE': s['replay']['status'] = 'PAUSED'
            else: raise SystemExit('unexpected API mutation')
        save(); print('{"ok":true}')
    else:
        if os.environ.get('XDP_FAIL_GET'): raise SystemExit(76)
        if os.environ.get('XDP_BAD_JSON'): print('{bad JSON'); raise SystemExit(0)
        print(json.dumps(s))
elif kind == 'ssh':
    command = args[-1]
    if 'xdp-session.py attach' in command:
        log('attach'); s['attached'] = True; save(); print('{"program_id":123}')
    elif 'xdp-session.py' in command and ' detach' in command:
        log('detach')
        if os.environ.get('XDP_FAIL_DETACH'): raise SystemExit(71)
        s['attached'] = False; save(); print('owned_xdp=detached')
    elif 'set-xdp-policy.py block' in command:
        log('drop'); s['feed'].update(integrity='GAP', trading_gate='INHIBITED_FEED_GAP', next_expected=756, pending=2,
                                    last_delivered=755, first_pending=757, gap_size=1)
        save(); print('policy_id=7 mode=block remaining=1 ttl_seconds=5.0')
    elif 'set-xdp-policy.py allow' in command:
        log('allow'); print('policy_id=7 mode=allow remaining=0 ttl_seconds=0')
    elif ' dump counters' in command:
        if os.environ.get('XDP_FAIL_AUDIT'): raise SystemExit(72)
        print(json.dumps([{'formatted':{'key':6, 'values':[{'value':1}]}}]))
    elif ' dump drop_audit' in command:
        print(json.dumps([{'formatted':{'value':{'drops':1,'first_drop_sequence':756,'first_drop_locate':8095}}}]))
    elif 'cat ' in command and 'attachment.json' in command:
        print('{"program_id":123,"interface":"ens64np1","ifindex":154}')
    elif 'python3 -c' in command and 'attachment.json' in command: print('123')
    elif 'bpftool -j prog show' in command: print('{"id":123}')
    elif 'mkdir ' in command:
        if s['attached']: raise SystemExit(73)
    elif 'grep -q prog/xdp' in command:
        log('filter-check')
        if s['attached'] or os.environ.get('XDP_FOREIGN_FILTER'): raise SystemExit(74)
    elif command == 'ip -details link show dev ens64np1':
        if s['attached']: print('154: ens64np1: <UP> mtu 1500 xdp qdisc mq\n    prog/xdp id 123 tag test jited')
        else: print('154: ens64np1: <UP> mtu 1500 qdisc mq')
    else: raise SystemExit('unexpected SSH: '+command)
elif kind == 'scp':
    if 'root@' in args[-2]:
        pathlib.Path(args[-1], 'flle_xdp_mold_itch.o').write_bytes(b'local-test-object')
elif kind == 'ctl':
    action = args[0]
    if action == 'controller-check':
        if os.environ.get('XDP_BAD_PLATFORM'): raise SystemExit(77)
        raise SystemExit(0)
    log('ctl:'+action)
    if os.environ.get('XDP_FAIL_START') and action == 'baseline': raise SystemExit(75)
    if action not in ('stop', 'baseline', 'verify'): raise SystemExit('unexpected ctl action')
    print('{"mode":"SFC","transition":"READY","owner":"sfc"}')
elif kind == 'handoff':
    if s['attached'] or os.environ.get('XDP_FOREIGN_FILTER'): raise SystemExit(74)
    print('trading_profile=SFC/READY/sfc; receiver=no-XDP/no-filter')
else: raise SystemExit('unexpected tool: '+kind)
'''

SITE = r'''
import io, json, os, pathlib, urllib.request
def fixture_urlopen(url, *args, **kwargs):
    if url != 'http://10.1.1.101:8088/api/state':
        raise RuntimeError('tests prohibit unexpected network access: '+str(url))
    return io.BytesIO((pathlib.Path(os.environ['XDP_TEST_ROOT'])/'fixture.json').read_bytes())
urllib.request.urlopen = fixture_urlopen
'''


class ForegroundTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='flle-xdp-drop-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        asset = self.root/'assets/07-xdp'
        shutil.copytree(HERE.parent, asset, ignore=shutil.ignore_patterns('__pycache__'))
        common = self.root/'assets/common'
        common.mkdir()
        (common/'flle-remote.sh').write_text('FLLE_SSH_OPTS=()\n')
        for name in ('check-filter-handoff.sh', 'feed-guardianctl.sh'):
            (common/name).write_text('exit 0\n')
        (common/'check-filter-handoff.sh').write_text(
            f'exec python3 "{self.root}/driver.py" handoff\n')
        shutil.copyfile(ROOT/'assets/common/wait-feed-state.py', common/'wait-feed-state.py')
        self.support = asset/'live-support'
        self.drop = asset/'05-xdp-inline-live.sh'
        self.restart = asset/'06-restart-trading-service.sh'
        for p in (self.drop, self.restart, self.support/'run-xdp-receiver-live.sh', self.support/'xdp-run-state.sh'):
            content = p.read_text().replace('/qyt-fll', str(self.root))
            content = content.replace('/var/tmp/flle-ch08-10.lock', str(self.root/'filter.lock'))
            content = content.replace('/var/tmp/flle-market-filter.lock', str(self.root/'new-filter.lock'))
            content = content.replace('/run/lock/flle-platform-deploy.lock', str(self.root/'deploy.lock'))
            p.write_text(content)
        self.check = self.root/'check-recovery.sh'
        self.check.write_text(
            'set -Eeuo pipefail\n'
            f'source "{self.support}/xdp-run-state.sh"\n'
            'load_state\ncheck_recovery_ready\n')
        state_dir = self.root/'reports/run-state'
        state_dir.mkdir(parents=True)
        self.platform = state_dir/'02-trading-baseline.env'
        self.platform.write_text('RUN_ID=test-02-trading-platform\n')
        self.pointer = state_dir/'07-xdp-drop.env'
        self.fixture = self.root/'fixture.json'
        self.fixture.write_text(json.dumps({'session':'1', 'market_mode':'UNICAST', 'attached':False,
            'replay':{'status':'PLAYING'}, 'health':{'trader_auto':{'status':'ONLINE'}},
            'feed':{'session':'1', 'integrity':'HEALTHY', 'trading_gate':'OPEN', 'next_expected':100, 'pending':0,
                    'last_delivered':99, 'first_pending':0, 'gap_size':0}}))
        (self.root/'driver.py').write_text(DRIVER)
        (self.root/'sitecustomize.py').write_text(SITE)
        bindir = self.root/'bin'; bindir.mkdir()
        for command in ('ssh', 'scp', 'curl'):
            p = bindir/command
            p.write_text(f'#!/bin/bash\nexec python3 "{self.root}/driver.py" {command} "$@"\n')
            p.chmod(0o755)
        ctl = self.root/'apps/flle-trading-lab/scripts/transport_labctl.sh'
        ctl.parent.mkdir(parents=True)
        ctl.write_text(f'#!/bin/bash\nexec python3 "{self.root}/driver.py" ctl "$@"\n')
        self.env = dict(os.environ, PATH=str(bindir)+':'+os.environ['PATH'],
                        PYTHONPATH=str(self.root), XDP_TEST_ROOT=str(self.root))

    def run_script(self, script, success=True, **env):
        result = subprocess.run(['bash', str(script)], env=dict(self.env, **env),
                                text=True, capture_output=True, timeout=30)
        if success:
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout+result.stderr)
        return result

    def events(self):
        p = self.root/'events.log'
        return p.read_text().splitlines() if p.exists() else []

    def assert_no_recovery_after_drop(self):
        events = self.events()
        tail = events[events.index('drop')+1:]
        self.assertNotIn('replay:RESTART', tail)
        self.assertNotIn('allow', tail)
        self.assertFalse(any(e.startswith(('ctl:', 'market:')) for e in tail), tail)

    def assert_lock_blocks_entrypoints(self, name):
        with (self.root/name).open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            for script in (self.drop, self.restart):
                with self.subTest(script=script.name):
                    result = self.run_script(script, success=False)
                    self.assertIn('正在运行', result.stdout+result.stderr)
            self.assertEqual(self.events(), [])
            self.assertFalse(self.pointer.exists())

    def test_new_lock_blocks_drop_and_restart(self):
        self.assert_lock_blocks_entrypoints('new-filter.lock')

    def test_legacy_lock_blocks_drop_and_restart(self):
        self.assert_lock_blocks_entrypoints('filter.lock')

    def test_new_owner_also_blocks_legacy_contenders(self):
        command = 'set -Eeuo pipefail\n'
        command += f'source "{self.support}/xdp-run-state.sh"\n'
        command += 'acquire_filter_lock\nprintf "locked\\n"\nread -r release\n'
        proc = subprocess.Popen(['bash', '-c', command], env=self.env,
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(proc.stdout.readline(), 'locked\n')
            for name in ('new-filter.lock', 'filter.lock'):
                with (self.root/name).open('a') as lock:
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            proc.communicate('release\n', timeout=5)
            self.assertEqual(proc.returncode, 0)
            for name in ('new-filter.lock', 'filter.lock'):
                with (self.root/name).open('a') as lock:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate()

    def test_drop_holds_gap_until_manual_restart(self):
        result = self.run_script(self.drop)
        self.assertIn('result=GAP_HELD', result.stdout)
        self.assert_no_recovery_after_drop()
        held = json.loads(self.fixture.read_text())
        self.assertEqual(held['feed']['integrity'], 'GAP')
        self.assertEqual(held['replay']['status'], 'PAUSED')
        self.assertFalse(held['attached'])
        self.assertIn('PHASE=GAP_HELD', self.pointer.read_text())
        result = self.run_script(self.restart)
        self.assertIn('result=RESTARTED', result.stdout)
        self.assertEqual([e for e in self.events() if e.startswith('ctl:')], ['ctl:stop','ctl:baseline','ctl:verify'])
        self.assertEqual(json.loads(self.fixture.read_text())['market_mode'], 'UNICAST')
        self.assertIn('PHASE=COMPLETE', self.pointer.read_text())
        events = self.events()
        self.run_script(self.restart)
        self.assertEqual(self.events(), events, 'completed restart must not restart again')

    def test_failed_audit_keeps_gap(self):
        self.run_script(self.drop, success=False, XDP_FAIL_AUDIT='1')
        self.assert_no_recovery_after_drop()
        self.assertIn('PHASE=NEEDS_MANUAL_RESTART', self.pointer.read_text())
        self.assertEqual(json.loads(self.fixture.read_text())['feed']['integrity'], 'GAP')
        self.run_script(self.restart)

    def test_duplicate_drop_cannot_clear_or_overwrite_scene(self):
        self.run_script(self.drop)
        events, pointer = self.events(), self.pointer.read_text()
        result = self.run_script(self.drop, success=False)
        self.assertIn('重新开始并清空交易', result.stderr)
        self.assertEqual(self.events(), events)
        self.assertEqual(self.pointer.read_text(), pointer)

    def browser_reset(self):
        state = json.loads(self.fixture.read_text())
        state['session'] = str(int(state['session'])+1)
        state['feed'].update(session=state['session'], integrity='HEALTHY',
                             trading_gate='OPEN', pending=0, next_expected=100)
        state['replay']['status'] = 'PLAYING'
        self.fixture.write_text(json.dumps(state))

    def test_three_drop_cycles_with_browser_recovery(self):
        runs = []
        for cycle in range(3):
            result = self.run_script(self.drop)
            self.assertIn('result=GAP_HELD', result.stdout)
            self.assertIn('重新开始并清空交易', result.stdout)
            self.assertNotIn('06-restart-trading-service.sh', result.stdout)
            if cycle:
                self.assertIn('已确认新行情会话 HEALTHY / OPEN', result.stdout)
                self.assertIn('PHASE=COMPLETE', (runs[-1]/'state.env').read_text())
                self.assertEqual(len(list(runs[-1].glob('recovery-observed-*/state.json'))), 1)
            run_id = self.pointer.read_text().splitlines()[0].split('=', 1)[1]
            runs.append(self.root/'reports/course-runs'/run_id)
            events, pointer = self.events(), self.pointer.read_text()
            # Re-running during GAP must not hide the scene, even on later cycles.
            self.run_script(self.drop, success=False)
            self.assertEqual(self.events(), events)
            self.assertEqual(self.pointer.read_text(), pointer)
            self.browser_reset()
            self.run_script(self.check)
            self.assertEqual(self.events(), events, 'readiness check must not change services')
            self.assertEqual(self.pointer.read_text(), pointer, 'readiness check must not write state')
        self.assertEqual(len(set(runs)), 3)
        for run in runs:
            check = subprocess.run(['sha256sum', '-c', 'SHA256SUMS'], cwd=run,
                                   capture_output=True, text=True)
            self.assertEqual(check.returncode, 0, check.stdout+check.stderr)
        self.assertFalse(any(e.startswith('ctl:') for e in self.events()))
        actions = [e for e in self.events() if e in ('drop', 'replay:RESTART')]
        self.assertEqual(actions, ['replay:RESTART', 'drop'] * 3)
        self.assertEqual(self.events().count('drop'), 3)

    def test_incomplete_browser_recovery_keeps_previous_run(self):
        self.run_script(self.drop)
        old_session = json.loads(self.fixture.read_text())['session']
        self.browser_reset()
        healthy = json.loads(self.fixture.read_text())
        pointer, events = self.pointer.read_text(), self.events()
        variants = [
            {'session':old_session, 'feed':dict(healthy['feed'], session=old_session)},
            {'feed':dict(healthy['feed'], integrity='GAP')},
            {'feed':dict(healthy['feed'], trading_gate='INHIBITED_FEED_GAP')},
            {'feed':dict(healthy['feed'], session='different')},
            {'feed':dict(healthy['feed'], pending=1)},
            {'feed':dict(healthy['feed'], next_expected=1)},
            {'feed':dict(healthy['feed'], resync_required=True)},
            {'feed':{}},
        ]
        for changed in variants:
            with self.subTest(changed=changed):
                self.fixture.write_text(json.dumps(dict(healthy, **changed)))
                self.run_script(self.drop, success=False)
                self.assertEqual(self.pointer.read_text(), pointer)
                self.assertEqual(self.events(), events)

    def test_recovery_query_failure_preserves_previous_run(self):
        self.run_script(self.drop)
        self.browser_reset()
        pointer, events = self.pointer.read_text(), self.events()
        for failure in ('XDP_FAIL_GET', 'XDP_BAD_JSON'):
            with self.subTest(failure=failure):
                result = self.run_script(self.drop, success=False, **{failure:'1'})
                self.assertNotIn('重新开始并清空交易', result.stderr)
                self.assertEqual(self.pointer.read_text(), pointer)
                self.assertEqual(self.events(), events)

    def test_replaced_platform_archives_pointer_without_recovering_old_run(self):
        self.run_script(self.drop)
        self.browser_reset()
        pointer, events = self.pointer.read_text(), self.events()
        old_run = self.root/'reports/course-runs'/pointer.splitlines()[0].split('=', 1)[1]
        old_state = (old_run/'state.env').read_bytes()
        self.platform.write_text('RUN_ID=another-02-trading-platform\n')
        result = self.run_script(self.drop)
        self.assertIn('已归档', result.stdout)
        self.assertIn('PARENT_RUN_ID=another-02-trading-platform', self.pointer.read_text())
        archived = list(old_run.glob('platform-replaced-*/previous-state.env'))
        self.assertEqual(len(archived), 1)
        self.assertEqual(archived[0].read_text(), pointer)
        self.assertEqual((old_run/'state.env').read_bytes(), old_state)
        for directory in (old_run, archived[0].parent):
            check = subprocess.run(['sha256sum', '-c', 'SHA256SUMS'], cwd=directory,
                                   capture_output=True, text=True)
            self.assertEqual(check.returncode, 0, check.stdout+check.stderr)
        self.assertEqual(self.events()[len(events):], ['attach', 'allow', 'market:MULTICAST_A',
                                                     'replay:RESTART', 'drop', 'replay:PAUSE', 'detach'])

    def test_replaced_platform_must_be_healthy_and_unfiltered(self):
        self.run_script(self.drop)
        self.browser_reset()
        pointer, events = self.pointer.read_text(), self.events()
        self.platform.write_text('RUN_ID=another-02-trading-platform\n')
        for failure in ('XDP_BAD_PLATFORM', 'XDP_FOREIGN_FILTER', 'XDP_FAIL_GET', 'XDP_BAD_JSON'):
            with self.subTest(failure=failure):
                self.run_script(self.drop, success=False, **{failure:'1'})
                self.assertEqual(self.pointer.read_text(), pointer)
                self.assertEqual(self.events(), events)
        state = json.loads(self.fixture.read_text())
        state['feed']['integrity'] = 'GAP'
        self.fixture.write_text(json.dumps(state))
        self.run_script(self.drop, success=False)
        self.assertEqual(self.pointer.read_text(), pointer)
        self.assertEqual(self.events(), events)

    def test_ab_modes_use_a_for_drop_and_restore_exact_original_mode(self):
        for mode in ('MULTICAST_A', 'MULTICAST_B', 'DUAL'):
            with self.subTest(mode=mode):
                state = json.loads(self.fixture.read_text())
                state['market_mode'] = mode
                self.fixture.write_text(json.dumps(state))
                self.run_script(self.drop)
                self.assertIn('ORIGINAL_MODE='+mode, self.pointer.read_text())
                self.assertEqual(json.loads(self.fixture.read_text())['market_mode'], 'MULTICAST_A')
                self.run_script(self.restart)
                self.assertEqual(json.loads(self.fixture.read_text())['market_mode'], mode)

    def test_invalid_mode_has_diagnostic_and_no_mutation(self):
        state = json.loads(self.fixture.read_text())
        state['market_mode'] = 'UNKNOWN'
        self.fixture.write_text(json.dumps(state))
        result = self.run_script(self.drop, success=False)
        self.assertIn('无法识别行情模式', result.stderr)
        self.assertEqual(self.events(), [])
        self.assertFalse(self.pointer.exists())

    def test_browser_recovery_refuses_foreign_filter(self):
        self.run_script(self.drop)
        self.browser_reset()
        pointer, events = self.pointer.read_text(), self.events()
        self.run_script(self.drop, success=False, XDP_FOREIGN_FILTER='1')
        self.assertEqual(self.pointer.read_text(), pointer)
        self.assertEqual(self.events(), events)

    def test_missing_held_evidence_cannot_clear_run(self):
        self.run_script(self.drop)
        self.browser_reset()
        run_id = self.pointer.read_text().splitlines()[0].split('=', 1)[1]
        held = self.root/'reports/course-runs'/run_id/'raw/state-held.json'
        pointer, events = self.pointer.read_text(), self.events()
        for content in (None, '', '{bad JSON', '{}'):
            with self.subTest(content=content):
                if content is None:
                    held.unlink()
                else:
                    held.write_text(content)
                result = self.run_script(self.drop, success=False)
                self.assertIn('旧缺口取证文件', result.stderr)
                self.assertIn(str(held), result.stderr)
                self.assertNotIn('重新开始并清空交易', result.stderr)
                self.assertEqual(self.pointer.read_text(), pointer)
                self.assertEqual(self.events(), events)

    def test_missing_run_directory_or_identity_has_specific_message(self):
        self.run_script(self.drop)
        self.browser_reset()
        run_id = self.pointer.read_text().splitlines()[0].split('=', 1)[1]
        out = self.root/'reports/course-runs'/run_id
        pointer, events = self.pointer.read_text(), self.events()
        for name, message in [('raw', '缺少原实验取证目录'), ('run.env', '缺少原实验身份文件')]:
            path = out/name
            hidden = out/(name+'.hidden')
            path.rename(hidden)
            try:
                for script in (self.drop, self.restart):
                    with self.subTest(name=name, script=script.name):
                        result = self.run_script(script, success=False)
                        self.assertIn(message, result.stderr)
                        self.assertIn(str(path), result.stderr)
                        self.assertNotIn('重新开始并清空交易', result.stderr)
                        self.assertEqual(self.pointer.read_text(), pointer)
                        self.assertEqual(self.events(), events)
            finally:
                hidden.rename(path)

    def test_failed_detach_cannot_claim_success_or_recover(self):
        self.run_script(self.drop, success=False, XDP_FAIL_DETACH='1')
        self.assert_no_recovery_after_drop()
        self.assertIn('PHASE=NEEDS_MANUAL_RESTART', self.pointer.read_text())

    def test_changed_platform_refuses_restart(self):
        self.run_script(self.drop)
        events = self.events()
        self.platform.write_text('RUN_ID=another-02-trading-platform\n')
        self.run_script(self.restart, success=False)
        self.assertEqual(self.events(), events)

    def test_foreign_filter_prevents_service_stop(self):
        self.run_script(self.drop)
        self.run_script(self.restart, success=False, XDP_FOREIGN_FILTER='1')
        self.assertNotIn('ctl:stop', self.events())

    def test_restart_failure_can_be_retried(self):
        self.run_script(self.drop)
        self.run_script(self.restart, success=False, XDP_FAIL_START='1')
        self.assertIn('PHASE=RESTART_FAILED', self.pointer.read_text())
        self.run_script(self.restart)
        self.assertIn('PHASE=COMPLETE', self.pointer.read_text())

    def test_missing_state_refuses_restart(self):
        self.run_script(self.restart, success=False)
        self.assertEqual(self.events(), [])

    def test_existing_gap_is_not_cleared_by_preparation(self):
        state = json.loads(self.fixture.read_text())
        state['feed']['integrity'] = 'GAP'
        self.fixture.write_text(json.dumps(state))
        self.run_script(self.drop, success=False)
        self.assertEqual(self.events(), [])
        self.assertFalse(self.pointer.exists())


class HeldStateTests(unittest.TestCase):
    def test_only_same_session_gap_and_paused_is_held(self):
        spec = importlib.util.spec_from_file_location('held', HERE/'wait-held-state.py')
        held = importlib.util.module_from_spec(spec); spec.loader.exec_module(held)
        observed = {'session':'a', 'feed':{'session':'a', 'next_expected':756}}
        state = copy.deepcopy(observed)
        state['feed'].update(integrity='GAP', trading_gate='INHIBITED_FEED_GAP')
        state['replay'] = {'status':'PAUSED'}
        self.assertTrue(held.is_held(state, observed))
        for group, key, value in [('replay','status','PLAYING'), ('feed','session','b'),
                                  ('feed','next_expected',757), ('feed','integrity','HEALTHY'),
                                  ('feed','trading_gate','OPEN')]:
            changed = copy.deepcopy(state); changed[group][key] = value
            self.assertFalse(held.is_held(changed, observed), (group,key,value))
        state['session'] = 'b'
        self.assertFalse(held.is_held(state, observed))


if __name__ == '__main__':
    unittest.main()
