#!/usr/bin/env python3
"""Installed beside one RUN's binary on .2; never selects an unrelated process."""
from pathlib import Path
import json
import os
import re
import signal
import subprocess
import sys
import time

BASE = Path(__file__).resolve().parent
CONTROL = Path('/var/tmp/flle-market-filter.cmd')
BINARY = BASE / 'mold_filter_adapter'
IDENTITY = BASE / 'adapter.identity.json'
LOG = BASE / 'adapter.log'


def identity(pid):
    try:
        stat = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        if stat[0] == 'Z':
            return None
        return {'pid': pid, 'start': stat[19],
                'boot': Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                'exe': str(Path(f'/proc/{pid}/exe').resolve(strict=True))}
    except (FileNotFoundError, ProcessLookupError):
        return None


def owned():
    if not IDENTITY.exists():
        return None
    saved = json.loads(IDENTITY.read_text())
    current = identity(saved['pid'])
    if current is None:
        return None
    if current != saved or current['exe'] != str(BINARY):
        raise RuntimeError('adapter identity mismatch; refusing to signal another process')
    return current['pid']


def start():
    if CONTROL.exists() or IDENTITY.exists() or LOG.exists():
        raise RuntimeError('RUN already started or control file occupied')
    with LOG.open('x') as log:
        proc = subprocess.Popen([str(BINARY)], stdin=subprocess.DEVNULL, stdout=log,
                                stderr=subprocess.STDOUT, start_new_session=True,
                                env=dict(os.environ, FLLE_FILTER_MODE='allow', FLLE_REMAINING_DROPS='1'))
    try:
        saved = identity(proc.pid)
        if not saved or saved['exe'] != str(BINARY):
            raise RuntimeError('cannot record adapter identity')
        tmp = IDENTITY.with_suffix('.tmp')
        tmp.write_text(json.dumps(saved)+'\n'); tmp.replace(IDENTITY)
        for _ in range(50):
            if proc.poll() is not None:
                raise RuntimeError('adapter exited during startup')
            if 'adapter_ready mode=allow remaining_drops=0' in LOG.read_text():
                print('adapter_started=1'); return
            time.sleep(0.1)
        raise RuntimeError('adapter readiness timeout')
    except BaseException:
        if proc.poll() is None:
            proc.terminate(); proc.wait(timeout=5)
        raise


def command(value):
    if owned() is None:
        raise RuntimeError('adapter missing')
    # O_EXCL: an unconsumed command must not be silently overwritten.
    with CONTROL.open('x') as stream:
        stream.write(value+'\n')
    for _ in range(30):
        if not CONTROL.exists():
            print('control_consumed='+value); return
        if owned() is None:
            raise RuntimeError('adapter exited before consuming command')
        time.sleep(0.1)
    raise RuntimeError('control command not consumed')


def stop():
    pid = owned()
    if not IDENTITY.exists():
        # Handles interruption between spawn and identity write; match this exact RUN binary.
        matches = [int(p.name) for p in Path('/proc').iterdir()
                   if p.name.isdigit() and (identity(int(p.name)) or {}).get('exe') == str(BINARY)]
        if len(matches) > 1:
            raise RuntimeError('multiple processes for this RUN; manual inspection required')
        pid = matches[0] if matches else None
    if pid:
        expected = identity(pid)
        os.kill(pid, signal.SIGTERM)
        for _ in range(50):
            current = identity(pid)
            if current is None:
                break
            if current != expected:
                raise RuntimeError('PID changed while stopping adapter')
            time.sleep(0.1)
        else:
            raise RuntimeError('adapter did not stop')
    CONTROL.unlink(missing_ok=True)
    print('adapter_stopped=1 control_absent=1')


if __name__ == '__main__':
    if BASE.parent != Path('/var/tmp') or not re.fullmatch(r'\d{8}T\d{6}Z-10-rtl-stages', BASE.name):
        sys.exit('invalid remote RUN directory')
    action = sys.argv[1]
    if action == 'start': start()
    elif action == 'check':
        if owned() is None: sys.exit('adapter missing')
        print('adapter_running=1')
    elif action in {'block', 'allow'}: command(action)
    elif action == 'stop': stop()
    else: sys.exit('unknown remote action')
