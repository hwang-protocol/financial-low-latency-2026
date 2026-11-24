#!/usr/bin/env python3
"""Local repeat/failure regression; SSH/APT/tools are fixtures, never real devices."""
from pathlib import Path
import os
import shlex
import subprocess
import tempfile
import unittest

ASSET = Path(__file__).resolve().parent
COMMON = ASSET.parent / 'common/flle-remote.sh'
ROOT = ASSET.parents[3]


class RepeatPrep(unittest.TestCase):
    def run_case(self, case, expected):
        with tempfile.TemporaryDirectory(prefix='flle-prep-test-') as tmp:
            home = Path(tmp)
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
            source = source.replace('cd /financial-low-latency', 'cd '+shlex.quote(tmp))
            source = source.replace('source Documents/newDoc/assets/common/flle-remote.sh',
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
                       CASE=case, APT_LOG=str(home/'apt.log'))
            result = subprocess.run(['bash','-c',command], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, expected, result.stdout+result.stderr)
            receipts = list((home/'Documents/reports/course-runs').iterdir())
            self.assertEqual(len(receipts), 2 if expected == 0 else 1)
            for run in receipts:
                self.assertIn(f'EXIT_CODE={expected}\n', (run/'run.env').read_text())
                subprocess.run(['sha256sum','-c','--quiet','SHA256SUMS'], cwd=run, check=True)
            if case == 'ready': self.assertFalse((home/'apt.log').exists())
            if case == 'install': self.assertIn('DPkg::Lock::Timeout=120', (home/'apt.log').read_text())
            if expected: self.assertIn('失败', result.stdout+result.stderr)

    def test_ready_repeat(self): self.run_case('ready', 0)
    def test_install_repeat(self): self.run_case('install', 0)
    def test_ssh_failure(self): self.run_case('ssh-fail', 255)
    def test_apt_failure(self): self.run_case('apt-fail', 100)
    def test_tool_failure(self): self.run_case('tool-fail', 7)

    def test_old_library_then_new_library(self):
        old = subprocess.check_output(['git','show','HEAD:Documents/newDoc/assets/common/flle-remote.sh'],cwd=ROOT,text=True)
        with tempfile.NamedTemporaryFile(mode='w',suffix='.sh') as temp:
            temp.write(old); temp.flush()
            script = f'source {shlex.quote(temp.name)}; before="$(declare -p FLLE_SSH_OPTS)"; source {shlex.quote(str(COMMON))}; source {shlex.quote(str(COMMON))}; [[ "$before" == "$(declare -p FLLE_SSH_OPTS)" ]]'
            subprocess.run(['bash','-c',script],check=True)


if __name__ == '__main__':
    unittest.main()
