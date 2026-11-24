#!/usr/bin/env python3
"""Reject invalid A/B captures using synthetic packets, without a network."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from ab_pcap_fixture import build, packet, write_pcap

HERE = Path(__file__).resolve().parent
A, B = ('233.74.125.32', 31032), ('233.74.125.33', 31033)


class TransportPcaps(unittest.TestCase):
    def check_capture(self, replacement=None, *, expected=0, extra=()):
        with tempfile.TemporaryDirectory() as td:
            raw = Path(td)
            build(raw)
            if replacement:
                name, packets = replacement
                write_pcap(raw / (name + '.pcap'), packets)
            command = [sys.executable, str(HERE/'inspect_transport_pcaps.py')]
            command += [str(raw/(name+'.pcap')) for name in ('MULTICAST_A', 'MULTICAST_B', 'DUAL')]
            command += ['--duplicates-before', '10', '--duplicates-after', '70',
                        '--membership-users', '1', '--membership-users-b', '1', '--pending', '0', '--gaps', '0']
            result = subprocess.run(command + list(extra), capture_output=True, text=True)
            self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
            self.assertEqual('verdict=THREE_TRANSPORT_MODES_PASS' in result.stdout, expected == 0)

    def test_two_multicast_copies_pass(self):
        self.check_capture()

    def test_old_unicast_plus_multicast_is_rejected(self):
        self.check_capture(('DUAL', [packet(*A, 241), packet('20.1.1.2', 42121, 241)]), expected=1)

    def test_conflicting_copies_are_rejected(self):
        self.check_capture(('DUAL', [packet(*A, 241), packet(*B, 241, message=b'changed')]), expected=1)

    def test_unrelated_sequences_are_not_redundant_copies(self):
        self.check_capture(('DUAL', [packet(*A, 241), packet(*B, 900)]), expected=1)

    def test_changed_session_is_rejected(self):
        self.check_capture(('MULTICAST_B', [packet(*B, 121, session=b'NEWSESSION')]), expected=1)

    def test_wrong_single_path_is_rejected(self):
        self.check_capture(('MULTICAST_A', [packet(*B, 121)]), expected=1)

    def test_missing_membership_or_delivery_gap_is_rejected(self):
        for extra in (('--membership-users-b', '0'), ('--pending', '1'), ('--gaps', '1'),
                      ('--duplicates-after', '10')):
            with self.subTest(extra=extra):
                self.check_capture(expected=1, extra=extra)


if __name__ == '__main__':
    unittest.main()
