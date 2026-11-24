#!/usr/bin/env python3
"""Offline regression: current deployed UI contract, including broken guards."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('gap_ui', Path(__file__).with_name('assert-feed-gap-ui.py'))
ui = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ui)


class GapContractTests(unittest.TestCase):
    def setUp(self):
        web = ROOT / 'apps/flle-trading-lab/web'
        self.index = (web / 'index.html').read_text()
        self.js = (web / 'terminal.js').read_text()
        self.css = (web / 'terminal.css').read_text()
        self.state = {'feed': {'integrity': 'GAP', 'trading_gate': 'INHIBITED_FEED_GAP'}}

    def check(self):
        return ui.verify(self.index, self.js, self.css, self.state)

    def test_current_ui_with_stale_and_shared_order_guard(self):
        self.assertEqual(self.check()['result'], 'PASS')
        self.js = self.js.replace('gap||stale', 'gap || stale')
        self.assertEqual(self.check()['result'], 'PASS')

    def test_live_gate_must_be_closed(self):
        self.state['feed']['trading_gate'] = 'OPEN'
        with self.assertRaisesRegex(ValueError, 'trading gate'):
            self.check()

    def test_healthy_state_is_not_gap_evidence(self):
        self.state['feed']['integrity'] = 'HEALTHY'
        with self.assertRaisesRegex(ValueError, 'not GAP'):
            self.check()

    def test_removed_button_guards_are_rejected(self):
        original = self.js
        for expression in ('app.submittingOrder||Boolean(reason)',
                           'busy||app.submittingOrder||Boolean(orderUnavailable(state,transport))'):
            with self.subTest(expression=expression):
                self.assertIn(expression, original)
                self.js = original.replace(expression, 'false')
                with self.assertRaisesRegex(ValueError, 'button'):
                    self.check()

    def test_removed_feed_guard_is_rejected(self):
        self.js = self.js.replace('if(feedIntegrity(state)!=="HEALTHY")', 'if(false)')
        with self.assertRaisesRegex(ValueError, 'unhealthy-feed'):
            self.check()

    def test_missing_visual_indicator_is_rejected(self):
        self.css = self.css.replace('body.feed-gap .book-card', 'body .book-card')
        with self.assertRaisesRegex(ValueError, 'CSS'):
            self.check()


if __name__ == '__main__':
    unittest.main()
