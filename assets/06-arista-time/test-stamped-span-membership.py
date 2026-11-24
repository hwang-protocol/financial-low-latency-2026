#!/usr/bin/env python3
"""Local loopback: real tcpdump keeps, then releases, inherited memberships."""
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest

HELPER = Path(__file__).parent/'live-support/stamped-span/capture_market.py'


class CaptureMembership(unittest.TestCase):
    @unittest.skipUnless(os.geteuid() == 0 and Path('/usr/bin/tcpdump').exists(),
                         'requires local tcpdump capture permission')
    def test_exec_capture_releases_groups_on_exit(self):
        def loopback_filters():
            return [line for line in Path('/proc/net/mcfilter').read_text().upper().splitlines()
                    if ' LO ' in line and any(group in line for group in ('E94A7D20', 'E94A7D21'))]
        baseline = loopback_filters()
        with tempfile.TemporaryDirectory() as tmp, socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
            sender.bind(('127.0.0.1', 0))
            sender.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton('127.0.0.1'))
            port = sender.getsockname()[1]
            root = Path(tmp)
            code = '''
import importlib.util,os,sys
spec=importlib.util.spec_from_file_location('capture',sys.argv[1])
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.SOURCE='127.0.0.1'
s=m.join_market('127.0.0.1')
open(sys.argv[2]+'/fd','w').write(str(s.fileno()))
os.execv('/usr/bin/tcpdump',['tcpdump','-i','lo','-nn','-c','1','-w',sys.argv[2]+'/capture.pcap',
                           'udp and src port '+sys.argv[3]])
'''
            with (root/'log').open('w') as log:
                child = subprocess.Popen([sys.executable, '-c', code, str(HELPER), tmp, str(port)],
                                         stdout=log, stderr=log)
                try:
                    for _ in range(100):
                        if child.poll() is not None:
                            self.fail((root/'log').read_text())
                        if 'listening on' in (root/'log').read_text():
                            break
                        time.sleep(.02)
                    self.assertIn('listening on', (root/'log').read_text())
                    fd = (root/'fd').read_text()
                    self.assertTrue(os.readlink(f'/proc/{child.pid}/fd/{fd}').startswith('socket:['))
                    filters = Path('/proc/net/mcfilter').read_text().upper()
                    # 233.74.125.32/.33 and source 127.0.0.1, as kernel hex.
                    self.assertIn('E94A7D20', filters)
                    self.assertIn('E94A7D21', filters)
                    sender.sendto(b'local capture fixture', ('233.74.125.32', port))
                    self.assertEqual(child.wait(timeout=5), 0)
                    self.assertGreater((root/'capture.pcap').stat().st_size, 24)
                finally:
                    if child.poll() is None:
                        child.terminate()
                        try:
                            child.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            child.kill(); child.wait()
            self.assertFalse(Path(f'/proc/{child.pid}').exists())
            self.assertEqual(loopback_filters(), baseline)


if __name__ == '__main__':
    unittest.main()
