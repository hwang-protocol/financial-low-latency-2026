#!/usr/bin/env python3
"""Regression: ephemeral UDP source ports and empty capture diagnostics."""
import importlib.util
import unittest
from pathlib import Path

path = Path(__file__).parent / 'live-support/stamped-span/analyze_stamped_span.py'
spec = importlib.util.spec_from_file_location('stamped_span', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class InputsTest(unittest.TestCase):
    def test_current_source_port_is_required(self):
        for port in (34605, 38622, 51001):
            packet = {'proto': 17, 'src': '20.1.1.1', 'dst': '20.1.1.2',
                      'l4': port.to_bytes(2, 'big') + (42121).to_bytes(2, 'big') + bytes(4) + b'market',
                      'ipid': 1, 'frame': bytes(60)}
            self.assertTrue(module.is_market_udp(packet, False, port))
            self.assertFalse(module.is_market_udp(packet, False, port + 1))
            packet['dst'] = '20.1.1.99'
            self.assertFalse(module.is_market_udp(packet, False, port))

    def test_no_samples_stays_failed_and_renders(self):
        result = {'pass': False, 'paired': 0, 'live_interior': 0, 'live_market': 0,
                  'copy_market': 4, 'window_seconds': 6, 'copy_only': 4,
                  'miss_live': 0, 'keyframes': 4, 'keyframe_last_sync': [0]*4,
                  'delay_ns': {'min': None, 'p50': None, 'p99': None, 'max': None, 'negatives': 0},
                  'freq': None, 'asic_hz_median': 350000000,
                  'copy_frame_len': [], 'live_frame_len': [], 'gates': {'pair_complete': False}}
        text = module.render_summary(result)
        self.assertIn('result=FAIL', text)
        self.assertIn('n/a/n/a/n/a/n/a', text)
        self.assertFalse(result['pass'])

if __name__ == '__main__':
    unittest.main()
