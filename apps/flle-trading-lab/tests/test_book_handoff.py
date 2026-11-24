import copy
import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('book_handoff', ROOT / 'scripts/verify-book-handoff.py')
HANDOFF = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HANDOFF)


def state(sequence):
    return dict(data_plane_mode='SFC', data_plane_transition='READY', data_plane_owner='sfc',
                replay={'status': 'PLAYING'}, strategy={'enabled': False}, session='S1',
                server_ns=10_000_000_000,
                health={'trader_auto': dict(status='ONLINE', last_event_ns=9_000_000_000)},
                feed=dict(integrity='HEALTHY', trading_gate='OPEN', session='S1', next_expected=sequence),
                feed_receiver=dict(status='ONLINE', last_event_ns=9_000_000_000, clients=1, received=sequence),
                trader_books={symbol: dict(session='S1', market_sequence=sequence - 1,
                    integrity='HEALTHY', trading_gate='OPEN', bids=[[100, 1]] * 5, asks=[[101, 1]] * 5)
                    for symbol in ('AAPL', 'NVDA')})


class BookHandoffTest(unittest.TestCase):
    def test_progress_does_not_require_a_price_change(self):
        self.assertEqual(HANDOFF.verify_progress(state(10), state(20))['result'], 'LIVE_BOOK_READY')

    def test_software_boot_keeps_strategy_and_requires_manual_trader(self):
        before, after = state(10), state(20)
        for sample in (before, after):
            sample['experiment_profile'] = 'SOFTWARE'
            sample['strategy']['enabled'] = True
            sample['health']['trader_manual'] = dict(status='ONLINE')
        self.assertEqual(HANDOFF.verify_progress(before, after, 'SOFTWARE')['result'], 'LIVE_BOOK_READY')
        after['health']['trader_manual']['status'] = 'STALE'
        with self.assertRaisesRegex(ValueError, 'manual trader'):
            HANDOFF.verify_progress(before, after, 'SOFTWARE')

    def test_frozen_healthy_ladder_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'did not advance'):
            HANDOFF.verify_progress(state(10), state(10))

    def test_healthy_feed_with_one_frozen_symbol_is_rejected(self):
        after = state(20)
        after['trader_books']['NVDA']['market_sequence'] = 9
        with self.assertRaisesRegex(ValueError, 'did not advance'):
            HANDOFF.verify_progress(state(10), after)

    def test_incomplete_handoffs_are_rejected(self):
        mutations = [
            ('replay', 'status', 'PAUSED'), ('strategy', 'enabled', True),
            ('feed', 'integrity', 'GAP'), ('feed', 'session', 'OLD'),
            ('feed_receiver', 'status', 'STOPPED'), ('feed_receiver', 'last_event_ns', 1),
            ('feed_receiver', 'clients', 0),
        ]
        for section, key, value in mutations:
            with self.subTest(section=section, key=key):
                after = state(20)
                after[section][key] = value
                with self.assertRaises(ValueError):
                    HANDOFF.verify_progress(state(10), after)

    def test_old_or_missing_book_is_rejected(self):
        for key, value in (('session', 'OLD'), ('bids', []), ('trading_gate', 'CLOSED')):
            with self.subTest(key=key):
                after = state(20)
                after['trader_books']['AAPL'][key] = value
                with self.assertRaises(ValueError):
                    HANDOFF.verify_progress(state(10), after)

    def test_session_rollover_is_retried_not_counted_as_progress(self):
        after = copy.deepcopy(state(20))
        after['session'] = after['feed']['session'] = 'S2'
        for book in after['trader_books'].values():
            book['session'] = 'S2'
        with self.assertRaisesRegex(ValueError, 'session changed'):
            HANDOFF.verify_progress(state(10), after)


if __name__ == '__main__':
    unittest.main()
