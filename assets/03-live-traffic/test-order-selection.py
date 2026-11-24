#!/usr/bin/env python3
"""Select the trade check's completed ID, including a rejected first attempt."""
import contextlib
import importlib.util
import io
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import inspect_order_pcap as inspect

spec = importlib.util.spec_from_file_location('classroom', Path(__file__).with_name('classroom-output.py'))
classroom = importlib.util.module_from_spec(spec)
spec.loader.exec_module(classroom)


class OrderSelectionTest(unittest.TestCase):
    def run_case(self, expected, executed=True, sessions_text=None, first_connection=False):
        def order(ref):
            payload = bytearray(47)
            payload[0] = ord('O')
            struct.pack_into('!I', payload, 1, ref)
            payload[5] = ord('B')
            struct.pack_into('!I', payload, 6, 1)
            payload[10:18] = b'AAPL    '
            struct.pack_into('!Q', payload, 18, 100)
            payload[31:45] = f'MANU{ref:010d}'.encode()
            return bytes(payload)
        def response(kind, ref):
            data = bytearray({'A': 64, 'E': 36, 'J': 29}[kind])
            data[0] = ord(kind)
            struct.pack_into('!I', data, 9, ref)
            if kind == 'A':
                struct.pack_into('!Q', data, 36, 99)
                data[47] = ord('L')
                data[48:62] = f'MANU{ref:010d}'.encode()
            if kind == 'E':
                struct.pack_into('!I', data, 13, 1)
                struct.pack_into('!Q', data, 17, 100)
                struct.pack_into('!Q', data, 26, 101)
            return bytes(data)
        client = [('U', order(1)), ('U', order(2))]
        server = [('S', response('J', 1)), ('S', response('A', 2))]
        if first_connection:
            client.insert(0, ('L', b'login request'))
            server.insert(0, ('A', b'login accepted'))
        if executed:
            server.append(('S', response('E', 2)))
        with tempfile.TemporaryDirectory() as directory:
            sessions = Path(directory) / 'sessions.txt'
            sessions.write_text(sessions_text if sessions_text is not None else
                                'auto_pid=10\nmanual_pid=20\n'
                                '20.1.1.2:51000 20.1.1.1:43120 pid=10\n'
                                '20.1.1.2:51001 20.1.1.1:43120 pid=20\n')
            trade = Path(directory) / 'first-trade.txt'
            trade.write_text(f'order_id={expected} result=ORDER_EXECUTED\n')
            packet = SimpleNamespace(data=b'placeholder')
            ip = SimpleNamespace(source='20.1.1.2', destination='20.1.1.1')
            tcp = SimpleNamespace(source_port=51001, destination_port=43120, sequence=1, payload=b'placeholder')
            output = io.StringIO()
            with patch('sys.argv', ['inspect', 'test.pcap', str(sessions), '--first-trade', str(trade)]), \
                 patch.object(inspect, 'read_pcap', return_value=('test', 1, [packet])), \
                 patch.object(inspect, 'parse_ethernet_ipv4', return_value=ip), \
                 patch.object(inspect, 'parse_tcp', return_value=tcp), \
                 patch.object(inspect, 'reassemble', return_value=b'placeholder'), \
                 patch.object(inspect, 'soup_frames', side_effect=[client, server]), \
                 patch.object(inspect, 'find_enter_frame', return_value=None), \
                 contextlib.redirect_stdout(output):
                inspect.main()
            return output.getvalue()

    def test_rejected_first_attempt_does_not_replace_filled_id(self):
        result = self.run_case(2)
        self.assertIn('OUCH_O user_ref=2', result)
        self.assertIn('OUCH_E user_ref=2', result)
        self.assertNotIn('user_ref=1', result)

    def test_missing_requested_id_is_not_replaced_by_another_order(self):
        with self.assertRaisesRegex(AssertionError, 'client ID 3'):
            self.run_case(3)

    def test_missing_execution_is_reported_for_the_selected_id(self):
        with self.assertRaisesRegex(AssertionError, 'responses for client ID 2'):
            self.run_case(2, executed=False)

    def test_first_manual_connection_can_include_login_without_an_auto_connection(self):
        result = self.run_case(2, first_connection=True, sessions_text=
                               'auto_pid=10\nmanual_pid=20\n'
                               '20.1.1.2:51001 20.1.1.1:43120 pid=20\n')
        self.assertIn('established_sessions=1', result)
        self.assertIn('OUCH_E user_ref=2', result)

    def test_unproven_manual_pid_is_not_inferred_from_an_order_prefix(self):
        with self.assertRaisesRegex(AssertionError, 'collect sessions after submitting'):
            self.run_case(2, sessions_text='auto_pid=10\nmanual_pid=20\n'
                          '20.1.1.2:51001 20.1.1.1:43120 pid=10\n')

    def test_formatted_messages_keep_selected_order_and_exact_prices(self):
        raw = self.run_case(2) + 'Frame 1: request details\n    UserRefNum: 2\n'
        output = io.StringIO()
        with patch('sys.stdin', io.StringIO(raw)), contextlib.redirect_stdout(output):
            classroom.display('annotate', 'order', [])
        displayed = output.getvalue()
        for heading in ('① O · 下单请求｜MANUAL → Exchange',
                        '② A · 受理回报｜Exchange → MANUAL',
                        '③ E · 成交回报｜Exchange → MANUAL'):
            self.assertEqual(displayed.count(heading), 1)
        self.assertEqual(displayed.count('客户端编号 UserRefNum：2\n'), 3)
        self.assertNotIn('UserRefNum：1', displayed)
        self.assertIn('方向 Side：买入', displayed)
        self.assertIn('限价 Price：0.0100', displayed)
        self.assertIn('成交价格 Price：0.0100', displayed)
        self.assertIn('订单引用号 Order Reference Number：99', displayed)
        self.assertIn('成交编号 Match Number：101', displayed)
        self.assertIn('verdict=LIVE_ORDER_FLOW_PASS', displayed)
        self.assertNotIn('Frame 1:', displayed)
        self.assertIn('Frame 1:', raw)

    def test_bad_display_input_keeps_raw_line_and_does_not_invent_a_message(self):
        raw = 'OUCH_O user_ref=2 side=UNKNOWN\n'
        output = io.StringIO()
        with patch('sys.stdin', io.StringIO(raw)), contextlib.redirect_stdout(output):
            classroom.display('annotate', 'order', [])
        self.assertIn('[展示失败]', output.getvalue())
        self.assertIn(raw, output.getvalue())
        self.assertNotIn('① O', output.getvalue())


if __name__ == '__main__':
    unittest.main()
