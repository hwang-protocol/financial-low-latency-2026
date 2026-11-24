#!/usr/bin/env python3
"""Exercise preparation reuse, failure evidence and first-trade readiness offline."""
import copy
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / 'assets'
spec = importlib.util.spec_from_file_location('first_trade', ROOT / 'apps/flle-trading-lab/tests/first_trade.py')
trade = importlib.util.module_from_spec(spec)
spec.loader.exec_module(trade)


class PreparationContracts(unittest.TestCase):
    def test_initramfs_reuse_and_failure_retry(self):
        source = (ASSETS / '02-trading-baseline/00a-runtime-prep.sh').read_text()
        snippet = source[source.index('mkdir -p /etc/systemd/network'):source.index('expected_sfc=')]
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bindir = root / 'bin'
            bindir.mkdir()
            for name, content in {
                'uname': 'echo test-kernel',
                'modinfo': 'echo "$FIXTURE_MODULES/$2"',
                'update-initramfs': 'echo update >>"$FIXTURE_CALLS"; test "${FAIL_UPDATE:-0}" = 0',
            }.items():
                p = bindir / name
                p.write_text('#!/bin/bash\n' + content + '\n')
                p.chmod(0o755)
            modules = root / 'modules'
            modules.mkdir()
            for name in ('sfc', 'onload'):
                (modules / name).write_text('version-one')
            env = dict(os.environ, PATH=str(bindir)+':'+os.environ['PATH'],
                       FIXTURE_MODULES=str(modules), FIXTURE_CALLS=str(root/'calls'))
            snippet = snippet.replace('/etc/systemd/network', str(root/'network')).replace('/var/lib/flle', str(root/'state'))
            def run(fail=False):
                return subprocess.run(['bash', '-Eeuo', 'pipefail', '-c', 'iface=ens64np0\n'+snippet],
                                      env=dict(env, FAIL_UPDATE=str(int(fail))), capture_output=True, text=True)
            self.assertEqual(run().returncode, 0)
            link = root/'network/10-flle-data.link'
            mtime = link.stat().st_mtime_ns
            self.assertEqual(run().returncode, 0)
            self.assertEqual(link.stat().st_mtime_ns, mtime)
            self.assertEqual((root/'calls').read_text().count('update'), 1)
            (modules/'sfc').write_text('version-two')
            self.assertNotEqual(run(fail=True).returncode, 0)
            self.assertEqual(run().returncode, 0)
            self.assertEqual((root/'calls').read_text().count('update'), 3)

    def test_readonly_cards_preserve_failed_receipts(self):
        for name in ('01c-verify-runtime.sh', '02c-verify-iommu.sh'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                bindir = root/'bin'
                bindir.mkdir()
                ssh = bindir/'ssh'
                ssh.write_text('#!/bin/bash\necho "fixture: SSH unavailable" >&2\nexit 23\n')
                ssh.chmod(0o755)
                p = root/name
                p.write_text((ASSETS/'05-kernel-bypass'/name).read_text().replace('cd /qyt-fll', 'cd '+td))
                run = subprocess.run(['bash', str(p)], env=dict(os.environ, PATH=str(bindir)+':'+os.environ['PATH']), capture_output=True, text=True)
                self.assertEqual(run.returncode, 23)
                self.assertIn('evidence=', run.stdout)
                out = next((root/'reports/course-runs').iterdir())
                self.assertIn('EXIT_CODE=23', (out/'run.env').read_text())
                self.assertIn('SSH unavailable', (out/'raw/result.txt').read_text())
                subprocess.run(['sha256sum', '--quiet', '-c', 'SHA256SUMS'], cwd=out, check=True)

    def test_first_trade_profiles_and_health_gate(self):
        state = dict(experiment_profile='SOFTWARE', data_plane_mode='SFC', data_plane_transition='READY',
                     feed=dict(integrity='HEALTHY'), replay=dict(status='PLAYING'),
                     trader_books=dict(AAPL=dict(asks=[[100, 1]], bids=[[99, 1]])),
                     health={n: dict(status='ONLINE') for n in ('exchange','trader_auto','trader_manual','gateway')})
        self.assertTrue(trade.ready_for_manual_trade(state))
        state['health']['trader_auto']['status'] = 'OFFLINE'
        self.assertFalse(trade.ready_for_manual_trade(state))
        state['experiment_profile'] = 'TRANSPORT'
        state['instruments'] = state.pop('trader_books')
        self.assertEqual(trade.manual_trade_book(state), state['instruments']['AAPL'])
        self.assertTrue(trade.ready_for_manual_trade(state))
        for field, bad in [('data_plane_mode','DPDK'), ('data_plane_transition','SWITCHING'), ('experiment_profile','UNKNOWN')]:
            changed = copy.deepcopy(state)
            changed[field] = bad
            self.assertFalse(trade.ready_for_manual_trade(changed))
        for field, key, value in [('feed','integrity','GAP'), ('replay','status','PAUSED')]:
            changed = copy.deepcopy(state)
            changed[field][key] = value
            self.assertFalse(trade.ready_for_manual_trade(changed))
        state['instruments']['AAPL']['asks'] = []
        self.assertFalse(trade.ready_for_manual_trade(state))


if __name__ == '__main__':
    unittest.main()
