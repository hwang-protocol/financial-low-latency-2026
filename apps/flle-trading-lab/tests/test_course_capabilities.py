"""Run the real prep scripts through local SSH/SCP fixtures, never use lab VMs."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CHECKOUT = (ROOT/'apps/flle-trading-lab').resolve() == Path(__file__).resolve().parents[1]
SCRIPTS = Path('apps/flle-trading-lab/scripts')
RUN = '20000101T000000Z-02-trading-platform'


@unittest.skipUnless(CHECKOUT, 'management-checkout test requires its cached deployment artifacts')
class Capabilities(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='flle-capabilities-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.run = self.root/'runs'/('flle-trading-lab-'+RUN)
        self.run.mkdir(parents=True)
        (self.root/'locks').mkdir()
        (self.root/'driver').symlink_to('/sys/bus/pci/drivers/sfc')
        self.bindir = self.root/'bin'
        self.bindir.mkdir()
        shutil.copytree(ROOT/'apps/flle-trading-lab/flle_trading', self.root/'apps/flle-trading-lab/flle_trading', ignore=shutil.ignore_patterns('__pycache__'))
        target = self.root/SCRIPTS
        target.mkdir(parents=True)
        for name in ('prepare-posix-qos.sh', 'prepare-lanz-reader.sh', 'prepare-course-capabilities.sh', 'posix-qos-package.py'):
            data = (ROOT/SCRIPTS/name).read_text().replace('/var/tmp/', str(self.root/'runs')+'/').replace('/run/lock/', str(self.root/'locks')+'/').replace('/sys/bus/pci/devices/0000:03:00.0/driver', str(self.root/'driver')).replace('/opt/flle/', str(self.root/'opt')+'/')
            (target/name).write_text(data)
        # Only controller lifecycle is mocked; staging, checksums, tar, package
        # validation, marker selection and rollback all execute their real code.
        self.old = self.run/'control/apps/flle-trading-lab/scripts'
        self.old.mkdir(parents=True)
        controller = """#!/bin/bash
printf '%s:%s\n' VERSION "$1" >>"$CALLS"
case "$1" in
 controller-stop) rm -f "$ACTIVE";;
 controller-start) if test "${FAIL_NEW_START:-0}" = 1 && test VERSION = new; then exit 37; fi; touch "$ACTIVE";;
esac
"""
        (self.old/'transport_labctl.sh').write_text(controller.replace('VERSION','old'))
        (target/'transport_labctl.sh').write_text(controller.replace('VERSION','new'))
        artifact = self.root/'artifacts/blobs'
        artifact.parent.mkdir()
        artifact.symlink_to(ROOT/'artifacts/blobs', target_is_directory=True)
        for name, body in {
            'ssh': """#!/usr/bin/env python3
import os,sys
args=sys.argv[1:]
while args[0]=='-o': args=args[2:]
args=args[1:]
os.execvp('bash',['bash','-c',' '.join(args)])
""",
            'scp': """#!/usr/bin/env python3
import shutil,sys
args=sys.argv[1:]
while args[0].startswith('-'):
    args=args[2:] if args[0]=='-o' else args[1:]
dest=args[-1].split(':',1)[-1]
for src in args[:-1]: shutil.copy(src,dest)
""",
            'systemctl': '#!/bin/bash\ntest "$1" = is-active && test -e "$ACTIVE"\n',
        }.items():
            script = self.bindir/name
            script.write_text(body)
            script.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.bindir)+':'+os.environ['PATH'], CALLS=str(self.root/'calls'), ACTIVE=str(self.root/'active'))
        self.profile = self.root/'runs'/('flle-transport-controller-'+RUN)/'experiment-profile'
        self.profile.parent.mkdir()
        self.profile.write_text('SOFTWARE\n')
        (self.run/'flle-trader').write_text('ordinary client unchanged')
        (self.run/'opening-book.checkpoint').write_text('keep book')

    def execute(self, script, *args, fail=False):
        return subprocess.run(['bash', str(self.root/SCRIPTS/script), *args], env=dict(self.env, FAIL_NEW_START=str(int(fail))), capture_output=True, text=True, timeout=30)

    def test_snapshot_topup_then_readonly_reuse(self):
        (self.root/'active').touch()
        result = self.execute('prepare-course-capabilities.sh', RUN)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertIn('course_capabilities=PREPARED', result.stdout)
        self.assertEqual((self.root/'calls').read_text(), 'old:controller-stop\nnew:controller-start\n')
        self.assertEqual(self.profile.read_text(), 'SOFTWARE\n')
        self.assertEqual((self.run/'flle-trader').read_text(), 'ordinary client unchanged')
        self.assertEqual((self.run/'opening-book.checkpoint').read_text(), 'keep book')
        for script, args in [('prepare-posix-qos.sh',(RUN,'--check')), ('prepare-lanz-reader.sh',('--check',)), ('prepare-course-capabilities.sh',(RUN,))]:
            checked = self.execute(script, *args)
            self.assertEqual(checked.returncode, 0, checked.stdout+checked.stderr)
        self.assertEqual((self.root/'calls').read_text().count('controller-stop'), 1)
        self.assertTrue((self.root/'active').exists())

    def test_readonly_missing_and_running_legacy_comparison_refuse(self):
        for script, args in [('prepare-posix-qos.sh',(RUN,'--check')), ('prepare-lanz-reader.sh',('--check',))]:
            self.assertEqual(self.execute(script, *args).returncode, 2)
        self.assertFalse((self.root/'calls').exists())
        self.profile.write_text('TRANSPORT\n')
        result = self.execute('prepare-posix-qos.sh', RUN)
        self.assertEqual(result.returncode, 2, result.stdout+result.stderr)
        self.assertFalse((self.root/'calls').exists())
        self.assertFalse((self.run/'posix-qos.enabled').exists())

    def test_failed_controller_restart_rolls_back_selection_and_workspace(self):
        (self.root/'active').touch()
        result = self.execute('prepare-posix-qos.sh', RUN, fail=True)
        self.assertEqual(result.returncode, 37, result.stdout+result.stderr)
        self.assertFalse((self.run/'posix-qos.enabled').exists())
        self.assertTrue((self.root/'active').exists())
        self.assertIn('old:controller-start', (self.root/'calls').read_text())
        self.assertIn('old', (self.old/'transport_labctl.sh').read_text())
        self.assertEqual((self.run/'flle-trader').read_text(), 'ordinary client unchanged')


if __name__ == '__main__':
    unittest.main()
