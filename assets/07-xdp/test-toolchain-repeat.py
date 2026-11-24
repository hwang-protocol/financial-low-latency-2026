#!/usr/bin/env python3
"""Preparation-card repeat/failure regression; installer/SSH/tools are fixtures."""
from pathlib import Path
import os
import shlex
import subprocess
import tempfile
import unittest

ASSET = Path(__file__).resolve().parent
COMMON = ASSET.parent / 'common/flle-remote.sh'
ROOT = ASSET.parents[1]


class RepeatPrep(unittest.TestCase):
    def run_case(self, case, expected):
        with tempfile.TemporaryDirectory(prefix='flle-prep-test-') as tmp:
            home = Path(tmp)
            installer = home/'assets/common/install-offline-packages.py'
            installer.parent.mkdir(parents=True)
            installer.write_text('''import os, pathlib, sys
assert sys.argv[1:] == ['10.1.1.2', 'xdp']
with pathlib.Path(os.environ['INSTALL_LOG']).open('a') as log:
    log.write('10.1.1.2 xdp\\n')
case = os.environ['CASE']
if case == 'ssh-fail': sys.exit(255)
if case == 'apt-fail': sys.exit(100)
print('offline installer fixture: '+case)
''')
            binpath = home / 'bin'; binpath.mkdir()
            fixtures = {
                'ssh': 'if [[ $CASE == ssh-fail ]]; then echo "fixture SSH failure" >&2; exit 255; fi\nexec bash -s',
                'uname': 'echo fixture-kernel',
                'dpkg-query': '[[ $CASE != install && $CASE != apt-fail ]] || exit 1\nprintf "install ok installed"',
                'apt-get': 'echo "$*" >>"$APT_LOG"\n[[ $CASE != apt-fail ]] || { echo "fixture APT failure" >&2; exit 100; }',
                'clang': 'printf "Ubuntu clang fixture\\nTarget: fixture\\n"\nseq 1 20000',
                'llvm-objdump': 'exit 0',
                'bpftool': '[[ $CASE != tool-fail ]] || { echo "fixture bpftool failure" >&2; exit 7; }\necho "bpftool fixture"',
                'ip': 'echo "ip fixture"',
            }
            for name, body in fixtures.items():
                file = binpath / name
                file.write_text('#!/usr/bin/env bash\n'+body+'\n'); file.chmod(0o755)
            source = (ASSET / '00-xdp-toolchain-prep.sh').read_text()
            source = source.replace('cd /qyt-fll', 'cd '+shlex.quote(tmp))
            source = source.replace('source assets/common/flle-remote.sh',
                                    'source '+shlex.quote(str(COMMON)))
            card = home / 'card.sh'; card.write_text(source)
            command = 'source '+shlex.quote(str(COMMON))+'\n'
            command += 'before_flags=$-; before_traps="$(trap -p)"\n'
            command += 'source '+shlex.quote(str(card))+'\nrc=$?\n'
            if expected == 0:
                command += 'source '+shlex.quote(str(card))+'\nrc=$?\n'
            command += '[[ $before_flags == "$-" && $before_traps == "$(trap -p)" ]] || exit 99\nexit "$rc"'
            # Loading the library intentionally sets errexit; switch it off in
            # the caller so the failure test can inspect the subshell's status.
            command = command.replace('before_flags=$-', 'set +e; before_flags=$-')
            env = dict(os.environ, PATH=str(binpath)+':'+os.environ['PATH'],
                       CASE=case, APT_LOG=str(home/'apt.log'), INSTALL_LOG=str(home/'install.log'))
            result = subprocess.run(['bash','-c',command], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, expected, result.stdout+result.stderr)
            receipts = list((home/'reports/course-runs').iterdir())
            self.assertEqual(len(receipts), 2 if expected == 0 else 1)
            for run in receipts:
                self.assertRegex(run.name, r'^\d{8}T\d{6}Z-07-xdp-toolchain-prep-[A-Za-z0-9]+$')
                self.assertIn(f'EXIT_CODE={expected}\n', (run/'run.env').read_text())
                subprocess.run(['sha256sum','-c','--quiet','SHA256SUMS'], cwd=run, check=True)
            self.assertEqual((home/'install.log').read_text().splitlines(),
                             ['10.1.1.2 xdp'] * (2 if expected == 0 else 1))
            self.assertFalse((home/'apt.log').exists(), 'card must delegate installation to the offline installer')
            if expected: self.assertIn('失败', result.stdout+result.stderr)

    def test_ready_repeat(self): self.run_case('ready', 0)
    def test_install_repeat(self): self.run_case('install', 0)
    def test_ssh_failure(self): self.run_case('ssh-fail', 255)
    def test_apt_failure(self): self.run_case('apt-fail', 100)
    def test_tool_failure(self): self.run_case('tool-fail', 7)

    def test_old_library_then_new_library(self):
        old = subprocess.check_output(['git','show','HEAD:assets/common/flle-remote.sh'],cwd=ROOT,text=True)
        with tempfile.NamedTemporaryFile(mode='w',suffix='.sh') as temp:
            temp.write(old); temp.flush()
            script = f'source {shlex.quote(temp.name)}; before="$(declare -p FLLE_SSH_OPTS)"; source {shlex.quote(str(COMMON))}; source {shlex.quote(str(COMMON))}; [[ "$before" == "$(declare -p FLLE_SSH_OPTS)" ]]'
            subprocess.run(['bash','-c',script],check=True)


if __name__ == '__main__':
    unittest.main()
