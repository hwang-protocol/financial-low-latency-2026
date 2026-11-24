"""Network and fanout behavior of the single Socket feed owner."""
import os
import json
from pathlib import Path
import select
import socket
import struct
import subprocess
import tempfile
import time
import unittest


class SharedFeedReceiverTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.binary = Path(__file__).resolve().parents[1] / "build/flle-feed-receiver"
        if not cls.binary.exists():
            raise unittest.SkipTest("build/flle-feed-receiver is required")

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="feed-test-")
        self.path = str(Path(self.tmp.name) / "feed.sock")
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.bind(("127.0.0.1", 0))
            self.port = probe.getsockname()[1]
        self.command = [str(self.binary), "--data-ip", "127.0.0.1",
                        "--socket", self.path, "--unicast-port", str(self.port),
                        "--multicast-receiver", "0", "--receive-buffer-bytes", "65536"]
        self.process = subprocess.Popen(self.command, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, text=True)
        if not select.select([self.process.stdout], [], [], 5)[0]:
            self.fail("receiver never became ready")
        self.ready = self.process.stdout.readline()
        self.assertIn("feed_receiver=READY", self.ready)
        self.clients = []

    def tearDown(self):
        for client in self.clients:
            client.close()
        self.process.terminate()
        self.process.communicate(timeout=5)
        self.tmp.cleanup()

    def subscribe(self):
        client = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        client.settimeout(2)
        client.connect(self.path)
        self.clients.append(client)
        return client

    def publish(self, payload):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
            sender.sendto(payload, ("127.0.0.1", self.port))

    def restart_receiver(self, *extra):
        self.assertEqual(self.clients, [])
        self.process.terminate()
        self.process.communicate(timeout=5)
        self.process = subprocess.Popen(self.command + list(extra), stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, text=True)
        self.assertTrue(select.select([self.process.stdout], [], [], 5)[0])
        self.assertIn('feed_receiver=READY', self.process.stdout.readline())

    def stop_and_status(self):
        self.process.terminate()
        stdout, stderr = self.process.communicate(timeout=5)
        self.assertEqual(self.process.returncode, 0, stderr)
        statuses = [json.loads(line.partition('feed_receiver=STATUS ')[2])
                    for line in stdout.splitlines() if line.startswith('feed_receiver=STATUS ')]
        self.assertTrue(statuses)
        return statuses[-1], stderr

    def test_complete_identical_packets_and_receive_time_for_both_clients(self):
        first, second = self.subscribe(), self.subscribe()
        for payload in [b"first-packet", bytes(range(256)) * 200, b"last-packet"]:
            self.publish(payload)
            left, right = first.recv(65552), second.recv(65552)
            self.assertEqual(left, right)
            self.assertEqual(left[:5], b"FLF1\x00")
            self.assertGreater(struct.unpack("!Q", left[8:16])[0], 0)
            self.assertEqual(left[16:], payload)

    def test_effective_buffer_is_reported_and_invalid_sizes_rejected(self):
        fields = dict(item.split("=", 1) for item in self.ready.split())
        self.assertGreaterEqual(int(fields["unicast_rcvbuf"]), 2 * 65536)
        self.assertEqual(fields["multicast_rcvbuf"], "0")
        for value in ['0', '-1', '67108865']:
            result = subprocess.run(self.command[:-1] + [value], capture_output=True, text=True, timeout=5)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('invalid feed receive buffer size', result.stderr)

    def test_no_second_network_owner_and_existing_receiver_survives(self):
        duplicate = subprocess.run(self.command, capture_output=True, text=True, timeout=5)
        self.assertNotEqual(duplicate.returncode, 0)
        self.assertIn("UDP bind failed", duplicate.stderr)
        self.assertTrue(Path(self.path).is_socket())
        client = self.subscribe()
        self.publish(b"still-online")
        self.assertEqual(client.recv(65552)[16:], b"still-online")

    def test_disconnected_consumer_does_not_stop_other_consumer(self):
        first, second = self.subscribe(), self.subscribe()
        first.close()
        self.publish(b"after-disconnect")
        self.assertEqual(second.recv(65552)[16:], b"after-disconnect")

    def test_slow_consumer_cannot_block_fast_consumer(self):
        slow = self.subscribe()
        fast = self.subscribe()
        # Fill the unread client's finite queue, while draining the other one.
        payload = b"x" * 8192
        for i in range(100):
            packet = struct.pack("!I", i) + payload
            self.publish(packet)
            self.assertEqual(fast.recv(65552)[16:], packet)
        # With network input now idle, POLLOUT must still drain the entire queue.
        for i in range(100):
            self.assertEqual(slow.recv(65552)[16:], struct.pack('!I', i) + payload)
        status, _ = self.stop_and_status()
        self.assertEqual(status['received'], 100)
        self.assertEqual(status['delivered'], 200)
        self.assertGreater(status['backpressure_events'], 0)
        self.assertEqual(status['overflow_disconnects'], 0)
        self.assertEqual(status['discarded_queue_packets'], 0)
        self.assertEqual(status['queued_packets'], 0)

    def test_queue_limit_disconnects_only_slow_client_and_is_visible(self):
        self.restart_receiver('--client-queue-packets', '2')
        slow, fast = self.subscribe(), self.subscribe()
        for i in range(100):
            payload = struct.pack('!I', i) + b'x' * 8192
            self.publish(payload)
            self.assertEqual(fast.recv(65552)[16:], payload)
        while slow.recv(65552):
            pass
        self.publish(b'fast-still-online')
        self.assertEqual(fast.recv(65552)[16:], b'fast-still-online')
        status, stderr = self.stop_and_status()
        self.assertEqual(status['overflow_disconnects'], 1)
        self.assertGreater(status['discarded_queue_packets'], 0)
        self.assertLessEqual(status['peak_client_packets'], 2)
        self.assertIn('QUEUE_LIMIT_RESYNC_REQUIRED', stderr)

    def test_queue_byte_limit_is_independent_of_packet_limit(self):
        self.restart_receiver('--client-queue-bytes', '65536')
        self.subscribe()
        fast = self.subscribe()
        for i in range(50):
            payload = struct.pack('!I', i) + b'x' * 16384
            self.publish(payload)
            self.assertEqual(fast.recv(65552)[16:], payload)
        status, _ = self.stop_and_status()
        self.assertEqual(status['overflow_disconnects'], 1)
        self.assertLessEqual(status['peak_client_bytes'], 65536)


if __name__ == "__main__":
    unittest.main()
