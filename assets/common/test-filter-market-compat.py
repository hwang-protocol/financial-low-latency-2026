#!/usr/bin/env python3
"""Offline regressions for A/B entry, A-only filtering and exact-mode recovery."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ASSETS = Path(__file__).resolve().parent.parent
MODES = ('MULTICAST_A', 'MULTICAST_B', 'DUAL', 'MULTICAST', 'UNICAST')


def module(chapter, name):
    path = ASSETS/chapter/'live-support'/name
    spec = importlib.util.spec_from_file_location(chapter+'_'+name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


class MarketCompatibility(unittest.TestCase):
    def test_shell_stage_entry_accepts_all_supported_original_modes(self):
        # An unknown action stops before any device operation, after real argument checks.
        for chapter, suffix in [('09-verilator', '10-rtl-stages')]:
            for mode in (*MODES, 'INVALID'):
                with self.subTest(chapter=chapter, mode=mode):
                    run = '20000101T000000Z-'+suffix
                    env = dict(os.environ, RUN_ID=run,
                               OUT='/qyt-fll/reports/course-runs/'+run,
                               ORIGINAL_MODE=mode, ORIGINAL_PLAYBACK='PLAYING')
                    result = subprocess.run(['bash', str(ASSETS/chapter/'live-support/stage-actions.sh'),
                                             'offline-invalid-action'], env=env, capture_output=True, timeout=5)
                    self.assertEqual(result.returncode, 2 if mode in MODES else 1)

    def test_rtl_pre_arm_context_rejects_b_or_dual(self):
        formatter = module('09-verilator', 'stage-output.py')
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp); (out/'raw').mkdir()
            for mode in MODES:
                with self.subTest(mode=mode):
                    state = {'market_mode': mode, 'replay': {'status': 'PAUSED'},
                             'session': 'fixture', 'health': {'trader_auto': {'status': 'ONLINE'}},
                             'feed': {'session': 'fixture', 'integrity': 'HEALTHY', 'path': 'UNICAST'}}
                    (out/'raw/state-before-arm.json').write_text(json.dumps(state))
                    if mode in ('MULTICAST_A', 'MULTICAST'):
                        formatter.context(out, 'state-before-arm', 'HEALTHY')
                    else:
                        with self.assertRaises(ValueError):
                            formatter.context(out, 'state-before-arm', 'HEALTHY')



if __name__ == '__main__':
    unittest.main()
