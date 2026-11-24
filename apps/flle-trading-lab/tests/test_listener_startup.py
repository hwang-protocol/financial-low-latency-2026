"""Exercise the real shell waiter across exec and process-identity failures."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SOURCE = (Path(__file__).resolve().parents[1] / 'scripts/transport_labctl.sh').read_text()
WAITER = 'wait_remote_listener() {' + SOURCE.split('wait_remote_listener() {', 1)[1].split('\nstop_foreign_course_listener()', 1)[0]


class ListenerStartupTest(unittest.TestCase):
    def run_waiter(self, *, delayed=False, wrong_command=False, wrong_owner=False,
                   wrong_identity=False, extra_identity_field=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            launch = root / 'launch.py'
            launch.write_text("import os,time\ntime.sleep(0.1)\nos.execv('/bin/sleep', ['listener-fixture', '30'])\n")
            command = [sys.executable, str(launch)] if delayed else ['/bin/sleep', '30']
            process = subprocess.Popen(command)
            try:
                pid = process.pid
                start = Path(f'/proc/{pid}/stat').read_text().split()[21]
                boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
                (root / 'fixture.pid').write_text(f'{pid}\n')
                (root / 'fixture.identity').write_text(
                    f'pid={pid} start_ticks={int(start) + int(wrong_identity)} boot_id={boot}'
                    + (' unexpected=1' if extra_identity_field else '') + '\n')
                expected = 'never-this-command' if wrong_command else ('listener-fixture' if delayed else '/bin/sleep')
                script = '''
set -Eeuo pipefail
remote() { shift; if test "$#" = 1; then bash -c "$1"; else "$@"; fi; }
ss() { printf 'LISTEN users:(("fixture",pid=%s,fd=3))\\n' "$LISTENER_PID"; }
sleep() { /bin/sleep 0.02; }
export -f ss sleep
SSH=(remote)
''' + WAITER + '\nwait_remote_listener local fixture "$EXPECTED" 48123\n'
                return subprocess.run(['bash', '-c', script], env=dict(os.environ,
                    RUN_DIR=directory, EXPECTED=expected,
                    LISTENER_PID=str(pid + int(wrong_owner))),
                    text=True, capture_output=True, timeout=10)
            finally:
                process.terminate()
                process.wait(timeout=5)

    def test_delayed_exec_becomes_ready_with_same_pid(self):
        result = self.run_waiter(delayed=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_wrong_command_never_becomes_ready(self):
        self.assertNotEqual(self.run_waiter(wrong_command=True).returncode, 0)

    def test_another_process_listener_is_not_ready(self):
        self.assertNotEqual(self.run_waiter(wrong_owner=True).returncode, 0)

    def test_reused_pid_start_time_is_rejected(self):
        self.assertNotEqual(self.run_waiter(wrong_identity=True).returncode, 0)

    def test_extra_identity_field_is_rejected(self):
        self.assertNotEqual(self.run_waiter(extra_identity_field=True).returncode, 0)
