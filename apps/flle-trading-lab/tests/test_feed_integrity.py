"""Exercise bounded gaps and reconnect safety through a real Trader process."""
import json
from pathlib import Path
import select
import socket
import struct
import subprocess
import tempfile
import time
import unittest


class FeedIntegrityTest(unittest.TestCase):
    def setUp(self):
        binary = Path(__file__).resolve().parents[1] / 'build/flle-trader'
        if not binary.is_file():
            self.skipTest('build/flle-trader is required')
        self.tmp = tempfile.TemporaryDirectory(prefix='feed-integrity-')
        self.addCleanup(self.tmp.cleanup)
        self.path = str(Path(self.tmp.name) / 'feed.sock')
        checkpoint = Path(self.tmp.name) / 'book.checkpoint'
        checkpoint.write_bytes(b'FLLEB01\0' + struct.pack('!Q', 0))
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        self.addCleanup(self.server.close)
        self.server.settimeout(3)
        self.server.bind(self.path)
        self.server.listen(2)
        self.telemetry = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.addCleanup(self.telemetry.close)
        self.telemetry.bind(('127.0.0.1', 0))
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 0))
            self.port = probe.getsockname()[1]
        self.process = subprocess.Popen([str(binary), '--role', 'MANUAL',
            '--management-ip', '127.0.0.1', '--management-port', str(self.port),
            '--exchange-data-ip', '127.0.0.1', '--order-port', str(self.port),
            '--feed-socket', self.path, '--book-checkpoint', str(checkpoint),
            '--telemetry-host', '127.0.0.1', '--telemetry-port', str(self.telemetry.getsockname()[1])],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(self.stop_process)
        self.input, _ = self.server.accept()
        self.addCleanup(lambda: self.input.close())
        self.input.settimeout(3)
        # Feed and management listeners start on independent threads.
        self.wait_state(lambda value: True, starting=True)

    def stop_process(self):
        if self.process.poll() is None:
            self.process.terminate()
        self.process.communicate(timeout=5)

    def publish(self, sequence, count=1, session=b'TEST000001'):
        message = b'S' + bytes(10) + b'O'
        mold = struct.pack('!10sQH', session, sequence, count)
        mold += (struct.pack('!H', len(message)) + message) * count
        envelope = b'FLF1' + bytes(4) + struct.pack('!Q', time.monotonic_ns())
        self.input.sendall(envelope + mold)

    def state(self):
        with socket.create_connection(('127.0.0.1', self.port), timeout=2) as connection:
            connection.sendall(b'STATE\n')
            connection.shutdown(socket.SHUT_WR)
            return json.loads(connection.makefile('rb').readline())

    def wait_state(self, predicate, starting=False):
        deadline = time.monotonic() + 5
        state = None
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                stdout, stderr = self.process.communicate()
                self.fail(f'Trader exited with {self.process.returncode}: {stdout}\n{stderr}')
            try:
                state = self.state()
            except ConnectionRefusedError:
                if not starting:
                    raise
                time.sleep(0.01)
                continue
            if predicate(state):
                return state
            time.sleep(0.01)
        self.fail(f'state did not converge: {state}')

    def test_permanent_gap_is_bounded_and_new_session_restores_consistency(self):
        self.publish(1)
        for sequence in range(3, 100003, 1000):
            self.publish(sequence, 1000)
        state = self.wait_state(lambda value: value['highest_received'] == 100002)
        self.assertEqual(state['next_expected'], 2)
        self.assertEqual(state['stats']['delivered'], 1)
        self.assertEqual(state['pending'], 32768)
        self.assertEqual(state['pending_bytes'], 32768 * 12)
        self.assertTrue(state['resync_required'])
        self.assertEqual(state['gaps'], 1)
        self.assertEqual(state['gap_messages'], 100000)
        events = []
        while select.select([self.telemetry], [], [], 0)[0]:
            events.append(json.loads(self.telemetry.recv(65536)))
        self.assertLessEqual(sum(event['kind'] == 'feed_gap' for event in events), 5)
        self.publish(2)
        self.assertEqual(self.state()['next_expected'], 2)
        self.publish(1, session=b'TEST000002')
        recovered = self.wait_state(lambda value: value['session'] == 'TEST000002')
        self.assertEqual(recovered['integrity'], 'HEALTHY')
        self.assertEqual(recovered['next_expected'], 2)
        self.assertEqual(recovered['stats']['delivered'], 1)
        self.assertFalse(recovered['resync_required'])
        self.assertEqual(recovered['pending'], 0)

    def test_disconnect_cannot_reopen_gate_on_same_session(self):
        self.publish(1)
        self.wait_state(lambda value: value['next_expected'] == 2)
        self.input.close()
        self.input, _ = self.server.accept()
        self.input.settimeout(3)
        self.publish(2)
        state = self.wait_state(lambda value: value['highest_received'] == 2)
        self.assertEqual(state['next_expected'], 2)
        self.assertTrue(state['resync_required'])
        self.assertEqual(state['resync_reason'], 'RECEIVER_DISCONNECTED')
        self.assertEqual(state['trading_gate'], 'INHIBITED_FEED_GAP')
        self.publish(1, session=b'TEST000002')
        self.wait_state(lambda value: value['integrity'] == 'HEALTHY')

    def test_late_start_does_not_claim_a_complete_book(self):
        self.publish(100)
        state = self.wait_state(lambda value: value['highest_received'] == 100)
        self.assertEqual(state['next_expected'], 1)
        self.assertEqual(state['stats']['delivered'], 0)
        self.assertEqual(state['integrity'], 'GAP')

    def test_redundant_copies_deliver_once_and_fill_out_of_order_gap(self):
        # A/B retain the same local multicast tag and Mold Session/sequence.
        self.publish(1)
        self.publish(1)
        self.publish(3)
        self.publish(2)
        self.publish(2)
        self.publish(3)
        state = self.wait_state(lambda value: value['stats']['received'] == 6)
        self.assertEqual(state['stats']['delivered'], 3)
        self.assertEqual(state['next_expected'], 4)
        self.assertEqual(state['pending'], 0)
        self.assertEqual(state['integrity'], 'HEALTHY')


if __name__ == '__main__':
    unittest.main()
