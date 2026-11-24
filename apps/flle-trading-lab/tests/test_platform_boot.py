"""Exercise the production boot orchestration without rebooting or using SSH."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
BOOT = (SCRIPTS / 'platform-boot.sh').read_text()


class PlatformBootTest(unittest.TestCase):
    def fixture(self, root):
        return (BOOT.replace('/var/lib/flle', str(root / 'state'))
                .replace('/usr/local/libexec', str(root / 'libexec'))
                .replace('/etc/systemd/system', str(root / 'units')))

    def run_shell(self, source, root, **env):
        return subprocess.run(['bash', '-Eeuo', 'pipefail', '-c', source,
                               str(root / 'ctl')], capture_output=True, text=True,
                              env=dict(os.environ, ROOT=str(root), **env), timeout=10)

    def test_install_enable_and_retire_only_matching_run(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'units').mkdir()
            (root / 'experiment-profile').write_text('TRANSPORT\n')
            prefix = self.fixture(root) + '''
CONTROL_LOCAL=1; CONTROL_DIR="$ROOT"; RUN_ID=fixture-02-trading-platform
systemctl(){ printf '%s\\n' "$*" >>"$ROOT/calls"; }
'''
            result = self.run_shell(prefix + '\nplatform_boot_enable\n', root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((root / 'state/active-platform').read_text(), 'fixture-02-trading-platform\n')
            unit = (root / 'units/flle-platform-boot.service').read_text()
            self.assertIn('Restart=on-failure', unit)
            self.assertIn('RemainAfterExit=yes', unit)
            self.assertIn('WantedBy=multi-user.target', unit)
            self.assertIn('StartLimitIntervalSec=0', unit)
            self.assertNotIn('start flle', (root / 'calls').read_text())
            for run, removes in [('other-02-trading-platform', False), ('fixture-02-trading-platform', True)]:
                result = self.run_shell(prefix + f'\nRUN_ID={run}\nplatform_boot_disable\n', root)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual((root / 'state/active-platform').exists(), not removes)

    def test_boot_profiles_readiness_and_retry(self):
        for profile, ready, peer, final in [
            ('TRANSPORT', '1', '1', '1'), ('SOFTWARE', '1', '1', '1'),
            ('TRANSPORT', '0', '0', '1'), ('TRANSPORT', '0', '1', '1'),
            ('SOFTWARE', '0', '1', '1'), ('TRANSPORT', '0', '1', '0'),
            ('BROKEN', '0', '1', '1'),
        ]:
            with self.subTest(profile=profile, ready=ready, peer=peer, final=final), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                (root / 'state').mkdir()
                (root / 'state/active-platform').write_text('fixture-02-trading-platform\n')
                (root / 'experiment-profile').write_text(profile + '\n')
                ctl = root / 'ctl'
                ctl.write_text('#!/bin/bash\necho "$1" >>"$ROOT/calls"\n')
                ctl.chmod(0o755)
                script = self.fixture(root) + '''
CONTROL_LOCAL=1; RUN_ID=fixture-02-trading-platform
CONTROL_DIR="$ROOT"; RUN_DIR="$ROOT"; SCRIPT_DIR="$ROOT"
EXCHANGE_HOST=exchange; OBSERVER_HOST=observer; SSH=(remote)
remote(){ test "$PEER" = 1; }
ip(){ echo ' 20.1.1.2/24 '; }
verify_controller_identity(){ :; }
verify_gateway_identity(){ :; }
python3(){
  if [[ "$*" == *'--timeout 30'* ]]; then test "$FINAL" = 1
  else test "$READY" = 1; fi
}
platform_start_software(){ echo baseline >>"$ROOT/calls"; }
restart_exchange_replay(){ echo replay >>"$ROOT/calls"; }
platform_boot_restore
'''
                result = self.run_shell(script, root, READY=ready, PEER=peer, FINAL=final)
                expected_ok = profile != 'BROKEN' and peer == '1' and (ready == '1' or final == '1')
                self.assertEqual(result.returncode == 0, expected_ok, result.stderr)
                calls = (root / 'calls').read_text().splitlines() if (root / 'calls').exists() else []
                expected = [] if ready == '1' or peer == '0' or profile == 'BROKEN' else (
                    ['baseline', 'replay'] if profile == 'SOFTWARE' else ['start'])
                self.assertEqual(calls, expected)
                if not expected_ok:
                    self.assertNotIn('platform_boot=READY', result.stdout)


if __name__ == '__main__':
    unittest.main()
