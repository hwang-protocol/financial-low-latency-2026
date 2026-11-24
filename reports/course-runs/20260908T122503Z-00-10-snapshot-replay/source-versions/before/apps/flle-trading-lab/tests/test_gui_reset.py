"""The GUI reset must clear authoritative state, not just hide old rows."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from flle_trading.gateway import Gateway, StateStore


class GuiResetTest(unittest.TestCase):
    def gateway(self):
        gateway = Gateway.__new__(Gateway)
        gateway.args = argparse.Namespace(transport_lab=True, exchange_host='exchange',
            exchange_management_port=1, trader_host='trader', trader_management_port=2,
            manual_trader_management_port=3, onload_trader_management_port=4,
            tcpdirect_trader_management_port=5, dpdk_trader_management_port=6,
            data_plane_controller_url='http://controller')
        gateway.store = StateStore(True)
        gateway.action_lock = threading.RLock()
        gateway.resetting = threading.Event()
        return gateway

    def test_full_projection_reset_preserves_connection_cursor_and_configuration(self):
        store = StateStore(True)
        store.sequence = 40
        store.strategy['enabled'] = False
        store.orders.append({'old': True})
        store.fills.append({'old': True})
        store.events.append({'old': True})
        store.chart['AAPL'] = [[1, 2]]
        store.client_positions['trader_manual']['AAPL'] = 200
        store.client_latency['trader_manual']['samples'] = 1942
        store.exchange_ledger.append({'old': True})
        store.health['trader_manual']['status'] = 'ONLINE'
        store.clear_gui_state()
        self.assertEqual(store.sequence, 40)
        self.assertFalse(store.strategy['enabled'])
        self.assertGreater(store.gui_reset_ns, 0)
        for value in (store.orders, store.fills, store.events, store.chart, store.exchange_ledger):
            self.assertFalse(value)
        self.assertEqual(store.client_positions['trader_manual']['AAPL'], 0)
        self.assertEqual(store.client_latency['trader_manual']['samples'], 0)
        self.assertEqual(store.health['trader_manual']['status'], 'WAITING')

    @patch('flle_trading.gateway.controller_request', return_value={})
    @patch('flle_trading.gateway.send_command', return_value={'session': 'old'})
    def test_missing_real_client_receipt_cannot_report_success(self, command, controller):
        gateway = self.gateway()
        gateway.store.orders.append({'old': True})
        with self.assertRaisesRegex(ValueError, '清零确认'):
            gateway.restart_and_clear()
        self.assertTrue(gateway.store.orders)
        self.assertFalse(gateway.resetting.is_set())
        self.assertEqual(command.call_count, 1)

    @patch('flle_trading.gateway.urlopen')
    @patch('flle_trading.gateway.controller_request', return_value={'paper_reset': True, 'mode': 'SFC', 'transition': 'READY', 'owner': 'sfc'})
    def test_reset_waits_for_new_session_and_resets_lanz(self, controller, urlopen):
        gateway = self.gateway()
        urlopen.return_value.__enter__.return_value.read.return_value = b'{"cleared":true}'
        restarted = False
        def command(host, port, message, **kwargs):
            nonlocal restarted
            if message == 'REPLAY|RESTART':
                restarted = True
                return {'ok': True}
            if port == 6:
                raise ConnectionRefusedError()
            return {'session': 'new' if restarted else 'old', 'positions': {'AAPL': 0, 'NVDA': 0}}
        with patch('flle_trading.gateway.send_command', side_effect=command):
            result = gateway.restart_and_clear()
        self.assertTrue(result['cleared_trades'])
        self.assertEqual(result['session'], 'new')
        self.assertEqual(urlopen.call_args.args[0].full_url, 'http://127.0.0.1:8089/api/lanz/reset')
        self.assertFalse(gateway.resetting.is_set())

    def test_lanz_clears_source_counts_and_persisted_history(self):
        path = ROOT / 'tests/lanz_stream_collector.py'
        if not path.is_file():
            path = ROOT.parents[1] / 'Documents/newDoc/assets/07-arista-time/lanz_stream_collector.py'
        spec = importlib.util.spec_from_file_location('lanz_reset_test', path)
        collector = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(collector)
        collector._state['events'].append({'entry_type': 'START'})
        collector._state['counts']['START'] = 99
        collector._state['connected'] = True
        with patch.object(collector, 'persist') as persist:
            self.assertTrue(collector.reset_history()['cleared'])
        persist.assert_called_once()
        self.assertEqual(collector.snapshot()['events'], [])
        self.assertFalse(any(collector.snapshot()['counts'].values()))
        self.assertTrue(collector.snapshot()['connected'])


if __name__ == '__main__':
    unittest.main()
