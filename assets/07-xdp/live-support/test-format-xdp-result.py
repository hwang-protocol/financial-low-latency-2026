#!/usr/bin/env python3
"""Field-projection tests; fixtures are not new device measurements."""
import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('formatter', Path(__file__).with_name('format-xdp-result.py'))
fmt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fmt)


class FormatTests(unittest.TestCase):
    def test_gap_shows_distinct_delivered_missing_and_pending_sequences(self):
        source = {'session': 'fixture', 'market_mode': 'MULTICAST_A', 'trader_auto': 'ONLINE',
                  'feed': {'integrity': 'GAP', 'trading_gate': 'INHIBITED_FEED_GAP',
                           'last_delivered': 642, 'next_expected': 643, 'first_pending': 644,
                           'gap_size': 1, 'pending': 7}}
        text = fmt.render_feed(json.dumps(source))
        self.assertIn('已交付 642 → 期望 643 → 最早待处理 644', text)
        self.assertIn('1 条；等待补齐后处理的消息 7 条', text)
        self.assertIn('暂停下单（INHIBITED_FEED_GAP）', text)
        self.assertNotIn('{', text)
        self.assertEqual(len(text.splitlines()), 8)

    def test_healthy_state_and_modes_are_not_invented(self):
        for mode, label in [('MULTICAST_A', '组播 A'), ('MULTICAST_B', '组播 B'), ('DUAL', 'A/B 双路')]:
            source = {'session': 'fixture', 'market_mode': mode, 'trader_auto': 'ONLINE',
                      'feed': {'integrity': 'HEALTHY', 'trading_gate': 'OPEN', 'next_expected': 321}}
            text = fmt.render_feed(json.dumps(source))
            self.assertIn(label, text)
            self.assertIn('321', text)
            self.assertIn('正常（HEALTHY）', text)
            self.assertNotIn('缺失消息', text)

    def test_missing_fields_and_invalid_json_fail(self):
        for source in ('{', '{}', '{"feed":{}}'):
            with self.assertRaises((ValueError, KeyError)):
                fmt.render_feed(source)

    def test_drop_proof_retains_actual_values(self):
        text = fmt.render_proof('xdp_drop_packets=1 sequence=643 locate=8095\n')
        self.assertIn('1 包', text)
        self.assertEqual(text.count('643'), 2)
        self.assertIn('8095', text)
        with self.assertRaises(ValueError):
            fmt.render_proof('result=PASS')

    def test_interface_excerpt_keeps_original_selected_lines(self):
        source = '3: ens64np1: <UP> mtu 1500 xdp qdisc mq\n    link/ether 00:00:00:00:00:00 noisy fields\n    prog/xdp id 34 tag abc jited \n'
        self.assertEqual(fmt.render_link(source),
                         '3: ens64np1: <UP> mtu 1500 xdp qdisc mq\n    prog/xdp id 34 tag abc jited\n')


if __name__ == '__main__':
    unittest.main()
