#!/usr/bin/env python3
"""Four foreground stages; classroom pauses have no deadline, failed actions do."""
from pathlib import Path
import datetime
import fcntl
import hashlib
import json
import os
import re
import signal
import shutil
import subprocess
import sys
import time
import urllib.request

ROOT = Path('/financial-low-latency')
ASSET = ROOT / 'Documents/newDoc/assets/09-verilator'
RUNS = ROOT / 'Documents/reports/course-runs'
POINTER = ROOT / 'Documents/reports/run-state/ch10-rtl-stages.json'
GLOBAL_LOCK = Path('/var/tmp/flle-ch08-10.lock')
LEASE = 1800
WAITING = {'PREPARED', 'GAP_CAPTURED', 'VERIFIED'}
ALLOWED = {'arm': {'PREPARED'}, 'verify': {'GAP_CAPTURED', 'VERIFIED'},
           'restore': {'PREPARING', 'PREPARED', 'ARMING', 'GAP_CAPTURED', 'VERIFYING', 'VERIFIED',
                       'RESTORING', 'RESTORE_REQUIRED', 'INTERRUPTED'}}
RESULT = {'prepare': 'PREPARED', 'arm': 'GAP_CAPTURED', 'verify': 'VERIFIED', 'restore': 'RESTORED'}
TERMINAL = {'RESTORED', 'ROLLED_BACK', 'EXPIRED', 'PRECHECK_FAILED'}
IN_PROGRESS = {'prepare': 'PREPARING', 'arm': 'ARMING', 'verify': 'VERIFYING', 'restore': 'RESTORING'}


def save(path, state):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2)+'\n')
    temp.replace(path)


def run_path(run_id):
    if not re.fullmatch(r'[0-9]{8}T[0-9]{6}Z-10-rtl-stages', run_id):
        raise RuntimeError('invalid run identity')
    return RUNS / run_id


def identity(pid):
    try:
        # Start time is field 22; comm may contain spaces or parentheses.
        fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        return None if fields[0] == 'Z' else fields[19]
    except FileNotFoundError:
        return None


def stage_lock(lock):
    # The guard briefly reads state under this lock; do not fail on that normal poll.
    for attempt in range(40):
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError:
            time.sleep(0.05)
    raise RuntimeError('another stage or recovery is still running; retry after it completes')


def execute(action, state, stage_fd):
    out = run_path(state['run_id'])
    for name in ['stage-session.py', 'stage-actions.sh', 'stage-output.py', 'remote-control.py']:
        source = ASSET / 'live-support' / name
        if source.exists():
            shutil.copyfile(source, out / 'source' / f'{action}-{time.time_ns()}-{name}')
    shutil.copyfile(ASSET.parent / 'common/feed-guardianctl.sh',
                    out / 'source' / f'{action}-{time.time_ns()}-feed-guardianctl.sh')
    env = dict(os.environ, RUN_ID=state['run_id'], OUT=str(run_path(state['run_id'])),
               ORIGINAL_MODE=state['original_mode'], ORIGINAL_PLAYBACK=state['original_playback'])
    attempt = time.time_ns()
    history = out / 'raw' / 'history' / f'{action}-{attempt}'
    history.mkdir(parents=True)
    for receipt in (out / 'raw').iterdir():
        if receipt.is_file() and not receipt.name.endswith('-full.txt') and receipt.name != 'build-and-selftest.txt':
            shutil.copyfile(receipt, history / receipt.name)
    log_path = run_path(state['run_id']) / 'raw' / f'{action}-{attempt}-full.txt'
    with log_path.open('w') as log:
        proc = subprocess.Popen(['bash', str(ASSET / 'live-support/stage-actions.sh'), action],
                                env=env, start_new_session=True, pass_fds=(stage_fd,),
                                stdout=log, stderr=subprocess.STDOUT)
    try:
        code = proc.wait(timeout=420 if action == 'prepare' else 150)
        if code:
            print(f'本步失败，完整日志：{log_path}', file=sys.stderr)
            for line in log_path.read_text(errors='replace').splitlines()[-8:]:
                if not re.search(r'secret|password|ssh-key|username', line, re.I):
                    print(line[:400], file=sys.stderr)
            raise RuntimeError(f'{action} failed ({code})')
    except BaseException:
        # Stop the foreground action and its SSH children before attempting rollback.
        try:
            os.killpg(proc.pid, signal.SIGTERM)
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL); proc.wait()
        except ProcessLookupError:
            pass
        raise


def display(action, state):
    out = run_path(state['run_id'])
    rendered = subprocess.check_output([sys.executable, str(ASSET / 'live-support/stage-output.py'),
                                        action, str(out)], text=True)
    (out / 'raw' / f'{action}-display.txt').write_text(rendered)
    print(rendered, end='', flush=True)


def manifest(state):
    out = run_path(state['run_id'])
    files = sorted(p for folder in ['raw', 'artifacts', 'source']
                   for p in (out/folder).rglob('*') if p.is_file())
    if (out/'run.env').exists():
        files.append(out/'run.env')
    files.append(out/'session.json')
    (out/'SHA256SUMS').write_text(''.join(
        f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(out)}\n' for p in files))


def rollback(state, path, stage_fd, success):
    if not (path.parent / 'armed').exists():
        state['phase'] = 'PRECHECK_FAILED'
    else:
        try:
            execute('cleanup', state, stage_fd)
            state['phase'] = success
            state['network_restored'] = True
            if state.get('trade_verification_failed'):
                state['phase'] = 'RESTORE_REQUIRED'
                state['error'] = 'network recovered; review saved order receipts/position before further orders'
        except Exception as exc:
            state['phase'] = 'RESTORE_REQUIRED'
            state['error'] = str(exc)
    save(path, state)
    manifest(state)


def guard(run_id):
    out = run_path(run_id); path = out / 'session.json'
    # Inherited fd holds GLOBAL_LOCK between foreground scripts. No experiment stages here.
    while True:
        with (out / 'stage.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            state = json.loads(path.read_text())
            if state['phase'] in TERMINAL:
                return
            needs_review = state.get('trade_verification_failed') and state.get('network_restored')
            expired = state['phase'] not in WAITING and time.time() >= state['expires']
            if not needs_review and (expired or state['phase'] == 'RESTORE_REQUIRED'):
                rollback(state, path, lock.fileno(), 'EXPIRED')
                if state['phase'] in TERMINAL:
                    return
        time.sleep(5)


def start_guard(state, global_fd):
    out = run_path(state['run_id'])
    shutil.copyfile(Path(__file__).resolve(), out / 'source' / 'guard-stage-session.py')
    with (out / 'guard.log').open('ab') as log:
        proc = subprocess.Popen([sys.executable, str(out / 'source' / 'guard-stage-session.py'), 'guard', state['run_id']],
                                stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                start_new_session=True, pass_fds=(global_fd,))
    state['guard_pid'] = proc.pid
    state['guard_start'] = identity(proc.pid)
    state['guard_boot'] = Path('/proc/sys/kernel/random/boot_id').read_text().strip()


def foreground(action):
    global_lock = None
    if action == 'prepare':
        global_lock = GLOBAL_LOCK.open('a')
        fcntl.flock(global_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if POINTER.exists():
            previous = run_path(json.loads(POINTER.read_text())['run_id']) / 'session.json'
            if json.loads(previous.read_text())['phase'] not in TERMINAL:
                raise RuntimeError('previous session unfinished; run restore first')
        run_id = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-10-rtl-stages'
        out = run_path(run_id); out.mkdir()
        for folder in ['raw', 'artifacts', 'source']:
            (out / folder).mkdir()
        with urllib.request.urlopen('http://10.1.1.101:8088/api/state', timeout=5) as response:
            initial = json.load(response)
            mode = initial['market_mode']
        if mode not in {'UNICAST', 'MULTICAST', 'MULTICAST_A', 'MULTICAST_B', 'DUAL'} or initial['replay']['status'] not in {'PLAYING', 'PAUSED'}:
            raise RuntimeError('unsupported original market mode')
        state = {'run_id': run_id, 'original_mode': mode, 'phase': 'PREPARING',
                 'original_playback': initial['replay']['status'],
                 'expires': time.time()+LEASE}
    else:
        run_id = json.loads(POINTER.read_text())['run_id']
        out = run_path(run_id)
    path = out / 'session.json'
    with (out / 'stage.lock').open('a') as lock:
        stage_lock(lock)
        if action == 'prepare':
            save(path, state)
            start_guard(state, global_lock.fileno())
            save(path, state)
            POINTER.parent.mkdir(parents=True, exist_ok=True)
            save(POINTER, {'run_id': run_id})
        else:
            state = json.loads(path.read_text())
            if state.get('trade_verification_failed') and action != 'restore':
                raise RuntimeError('恢复订单验证失败；请核对回执和持仓。恢复入口仅允许再次恢复网络，不重复下单。')
            if action == 'restore' and state['phase'] in TERMINAL:
                print('本次现场已结束：'+state['phase']+'；不会重复发令或下单。')
                return
            if state['phase'] not in ALLOWED[action]:
                raise RuntimeError(f"{action} cannot run after {state['phase']}; no commands executed")
            boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
            guard_ok = (state.get('guard_start') and identity(state['guard_pid']) == state['guard_start']
                        and state.get('guard_boot') == boot)
            if guard_ok:
                args = Path(f"/proc/{state['guard_pid']}/cmdline").read_bytes().split(b'\0')
                guard_ok = args[-3:-1] == [b'guard', run_id.encode()] and str(out / 'source' / 'guard-stage-session.py').encode() in args
                if guard_ok:
                    state['guard_boot'] = boot
            if not guard_ok:
                if action != 'restore':
                    raise RuntimeError('session guard missing; run the restore script')
                # Recovery may reclaim an abandoned session only when no other lab owns the lock.
                global_lock = GLOBAL_LOCK.open('a')
                fcntl.flock(global_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                start_guard(state, global_lock.fileno())
            if state['phase'] not in WAITING and time.time() >= state['expires'] and action != 'restore':
                raise RuntimeError('session expired; run restore or wait for guard')
        state['phase'] = IN_PROGRESS[action]
        state['expires'] = time.time()+LEASE
        save(path, state)
        label = {'prepare': '运行①：构建与正常放行', 'arm': '运行②：发令', 'verify': '运行③：核对结果', 'restore': '运行④：恢复'}[action]
        print(f'正在执行{label}；完成后显示本步回执，完整日志：{out}/raw。', flush=True)
        try:
            execute('cleanup' if state.get('trade_verification_failed') else action, state, lock.fileno())
        except BaseException as exc:
            state['last_exit_code'] = 1
            state['error'] = str(exc)
            if action == 'restore' and (out / 'order-check-started').exists():
                state['trade_verification_failed'] = True
            rollback(state, path, lock.fileno(), 'ROLLED_BACK')
            raise
        if state.get('trade_verification_failed'):
            state.update(phase='RESTORE_REQUIRED', network_restored=True, last_exit_code=1)
            save(path, state); manifest(state)
            raise RuntimeError('网络已恢复；订单验证仍需核对，未重复发送订单。')
        state['phase'] = RESULT[action]
        state['last_exit_code'] = 0
        if 'error' in state:
            state['previous_error'] = state.pop('error')
        state['expires'] = time.time()+LEASE
        save(path, state)
        # Display is derived from real receipts; a formatting failure never reruns device actions.
        try:
            display(action, state)
        except Exception as exc:
            print(f'本步动作已完成，显示摘要失败：{exc}；原始回执：{out}', file=sys.stderr)
        manifest(state)
    if global_lock is not None:
        global_lock.close()


def interrupted(signum, frame):
    raise KeyboardInterrupt(f'signal {signum}')


if __name__ == '__main__':
    try:
        action = sys.argv[1]
        if action == 'guard':
            guard(sys.argv[2])
        elif action in RESULT:
            signal.signal(signal.SIGTERM, interrupted)
            foreground(action)
        else:
            raise RuntimeError('expected prepare, arm, verify or restore')
    except (Exception, KeyboardInterrupt) as exc:
        print(f'RTL stage stopped: {exc}', file=sys.stderr)
        sys.exit(1)
