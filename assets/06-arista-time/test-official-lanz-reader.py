#!/usr/bin/env python3
"""Exercise the compiled official SDK through the existing JSON/HTTP adapter."""
import json
import os
import runpy
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
import time
import unittest
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
COLLECTOR = Path(__file__).with_name('lanz_stream_collector.py')
READER = ROOT / 'artifacts/blobs/arista/lanz-reader-v1/flle-lanz-reader-linux-amd64'
# Synthetic official-schema CongestionRecord, never presented as switch evidence.
START = bytes.fromhex('1b 12 19 08 c0 c4 07 12 09 45 74 68 65 72 6e 65 74 32 18 00 20 02 28 40 30 01 38 01')
END = START.replace(bytes.fromhex('30 01 38 01'), bytes.fromhex('30 03 38 01'))


class OfficialReaderTest(unittest.TestCase):
    def test_collector_moved_to_run_uses_prepared_executable(self):
        # /run holds the Python adapter and state, but is mounted noexec on .101.
        with tempfile.TemporaryDirectory() as tmp:
            moved = Path(tmp) / 'run/flle-lanz-stream/lanz_stream_collector.py'
            moved.parent.mkdir(parents=True)
            moved.write_bytes(COLLECTOR.read_bytes())
            module = runpy.run_path(str(moved), run_name='test_collector')
            self.assertEqual(module['READER_PATH'],
                             '/opt/flle/lanz-reader-v1/flle-lanz-reader')

    def test_sdk_to_web_and_shutdown(self):
        with tempfile.TemporaryDirectory() as tmp, socket.socket() as switch:
            switch.bind(('127.0.0.1', 0))
            switch.listen()
            switch.settimeout(5)
            closed = threading.Event()

            def send_records():
                with switch.accept()[0] as conn:
                    conn.sendall(START + END)
                    conn.settimeout(10)
                    while conn.recv(1):
                        pass
                closed.set()

            worker = threading.Thread(target=send_records, daemon=True)
            worker.start()
            with socket.socket() as reservation:
                reservation.bind(('127.0.0.1', 0))
                http_port = reservation.getsockname()[1]
            code = '''
import runpy, sys
m=runpy.run_path(sys.argv[1], run_name='test_collector')
g=m['serve'].__globals__
g.update(LISTEN_HOST='127.0.0.1', LISTEN_PORT=int(sys.argv[2]),
         SWITCH_HOST='127.0.0.1', SWITCH_PORT=int(sys.argv[3]),
         READER_PATH=sys.argv[4], STATE_PATH=sys.argv[5])
m['serve']()
'''
            process = subprocess.Popen(['python3', '-c', code, str(COLLECTOR), str(http_port),
                str(switch.getsockname()[1]), str(READER), tmp+'/state.json'],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            url = f'http://127.0.0.1:{http_port}/api/lanz'
            children = []
            try:
                state = {}
                for _ in range(100):
                    try:
                        with urlopen(url, timeout=1) as response:
                            state = json.load(response)
                        if state['counts']['END'] == 1:
                            break
                    except OSError:
                        pass
                    time.sleep(.05)
                self.assertTrue(state.get('connected'), state)
                self.assertEqual(state['decoder'], 'arista-goarista-lanz')
                self.assertEqual([e['entry_type'] for e in state['events']], ['START', 'END'])
                self.assertEqual(state['events'][0]['queue_size'], 64)
                self.assertEqual(state['events'][0]['timestamp_raw'], 123456)
                self.assertEqual(state['events'][0]['timestamp_us'], 1234560)
                self.assertEqual(state['counts_by_queue']['Ethernet2/TC1']['END'], 1)
                self.assertEqual(state['events'][0]['intf_name'], 'Ethernet2')
                for child_file in Path(f'/proc/{process.pid}/task').glob('*/children'):
                    children.extend(int(pid) for pid in child_file.read_text().split())
                self.assertEqual(len(children), 1)
                with urlopen(Request(url+'/reset', data=b'{}'), timeout=2) as response:
                    self.assertTrue(json.load(response)['cleared'])
                with urlopen(url, timeout=2) as response:
                    cleared = json.load(response)
                self.assertTrue(cleared['connected'])
                self.assertEqual(cleared['events'], [])
                self.assertEqual(cleared['counts_by_queue'], {})
                self.assertEqual(sum(cleared['counts'].values()), 0)
            finally:
                process.terminate()
                stdout, stderr = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 0, stdout+stderr)
            self.assertTrue(closed.wait(2), 'official client left a connection open')
            worker.join(timeout=1)
            for pid in children:
                with self.assertRaises(ProcessLookupError):
                    os.kill(pid, 0)


if __name__ == '__main__':
    unittest.main()
