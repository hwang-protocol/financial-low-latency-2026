#!/usr/bin/env python3
"""Regression: ephemeral UDP source ports and empty capture diagnostics."""
import importlib.util
import socket
import struct
import tempfile
import unittest
from pathlib import Path

path = Path(__file__).parent / 'live-support/stamped-span/analyze_stamped_span.py'
spec = importlib.util.spec_from_file_location('stamped_span', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class InputsTest(unittest.TestCase):
    def test_ab_endpoints_and_source_filter(self):
        for group, port in [('233.74.125.32', 31032), ('233.74.125.33', 31033)]:
            packet = {'proto': 17, 'src': '20.1.1.1', 'dst': group,
                      'l4': struct.pack('!HHHH', 51001, port, 14, 0) + b'market',
                      'ipid': 1, 'frame': bytes(60)}
            self.assertTrue(module.is_market_udp(packet, False, 51001))
            self.assertFalse(module.is_market_udp(packet, False, 51002))
            packet['src'] = '20.1.1.99'
            self.assertFalse(module.is_market_udp(packet, False, 51001))
            packet['src'] = '20.1.1.1'
            packet['dst'] = '233.74.125.33' if port == 31032 else '233.74.125.32'
            self.assertFalse(module.is_market_udp(packet, False, 51001))

    def test_dual_same_payloads_pair_per_route(self):
        # Synthetic nanosecond pcaps, not hardware or latency evidence.
        def frame(src, dst, proto, payload, ipid=0):
            return (bytes(12) + b'\x08\x00' +
                    struct.pack('!BBHHHBBH4s4s', 0x45, 0, 20+len(payload), ipid,
                                0, 1, proto, 0, socket.inet_aton(src), socket.inet_aton(dst)) + payload)
        def pcap(path, rows):
            data = bytearray(struct.pack('<IHHIIII', 0xa1b23c4d, 2, 4, 0, 0, 262144, 1))
            for timestamp, packet in sorted(rows):
                data += struct.pack('<IIII', timestamp//10**9, timestamp%10**9, len(packet), len(packet))
                data += packet
            path.write_bytes(data)
        copies, live = [], []
        for second in range(100, 104):
            payload = struct.pack('!QQQ', second*350_000_000, second*10**9, 0)
            copies.append((second*10**9, frame('20.1.1.254', '21.1.1.11', 253, payload)))
        for index in range(600):
            tick = 101*700_000_000 + (index+1)*700_000
            ingress = 101*10**9 + (index+1)*1_000_000
            payload = b'SESSION001'+struct.pack('!Q', index)+bytes(30)
            for group, port in [('233.74.125.32', 31032), ('233.74.125.33', 31033)]:
                packet = frame('20.1.1.1', group, 17,
                               struct.pack('!HHHH', 51001, port, len(payload)+8, 0)+payload, index)
                live.append((ingress+7000, packet))
                copies.append((ingress+10000, packet+struct.pack('!I', tick % (1<<32))))
        with tempfile.TemporaryDirectory() as tmp:
            copy, rx = Path(tmp)/'copy.pcap', Path(tmp)/'live.pcap'
            pcap(copy, copies); pcap(rx, live)
            result = module.analyze(copy, rx, 51001)
        self.assertTrue(result['pass'], result['gates'])
        self.assertEqual(result['paired'], 1200)
        self.assertEqual(result['ambiguous'], 0)
        self.assertEqual(result['delay_ns']['p50'], 7000)

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
