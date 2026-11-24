"""Exercise the real local command adapter and its ownership-lock lifetime."""
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/control-host.sh'

class LocalControlTest(unittest.TestCase):
    def test_local_daemon_does_not_retain_device_lock(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw)
            ip=root/'ip'; ip.write_text('#!/bin/sh\necho "2: ens33 inet 10.1.1.2/24 scope global ens33"\n');ip.chmod(0o755)
            env=dict(os.environ,PATH=str(root)+':'+os.environ['PATH'],RUN_DIR=str(root),ACTION='test',TRADER_HOST='root@10.1.1.2')
            command='''source "$1"
exec 8>"$RUN_DIR/lock"
flock -n 8
control_host_command root@10.1.1.2 'sleep 15 >/dev/null 2>&1 & echo $! >"$RUN_DIR/daemon.pid"'
'''
            subprocess.run(['bash','-eu','-c',command,'test',str(SCRIPT)],env=env,check=True)
            pid=int((root/'daemon.pid').read_text())
            try:
                os.kill(pid,0)
                self.assertEqual(subprocess.run(['flock','-n',str(root/'lock'),'true']).returncode,0)
            finally:
                os.kill(pid,signal.SIGTERM)

    def test_local_command_preserves_stdin_and_failure(self):
        with tempfile.TemporaryDirectory() as raw:
            p=Path(raw)/'ip';p.write_text('#!/bin/sh\necho "2: ens33 inet 10.1.1.2/24 scope global ens33"\n');p.chmod(0o755)
            env=dict(os.environ,PATH=raw+':'+os.environ['PATH'],RUN_DIR=raw,ACTION='test')
            r=subprocess.run(['bash','-c','source "$1"; control_host_command root@10.1.1.2 "cat; exit 17"','test',str(SCRIPT)],input='message\n',text=True,capture_output=True,env=env)
            self.assertEqual((r.returncode,r.stdout),(17,'message\n'))
