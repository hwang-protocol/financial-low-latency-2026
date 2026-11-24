"""Network and fanout behavior of the single Socket feed owner."""
import os
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
                        "--multicast-receiver", "0"]
        self.process = subprocess.Popen(self.command, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, text=True)
        if not select.select([self.process.stdout], [], [], 5)[0]:
            self.fail("receiver never became ready")
        self.assertIn("feed_receiver=READY", self.process.stdout.readline())
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

    def test_complete_identical_packets_and_receive_time_for_both_clients(self):
        first, second = self.subscribe(), self.subscribe()
        for payload in [b"first-packet", bytes(range(256)) * 200, b"last-packet"]:
            self.publish(payload)
            left, right = first.recv(65552), second.recv(65552)
            self.assertEqual(left, right)
            self.assertEqual(left[:5], b"FLF1\x00")
            self.assertGreater(struct.unpack("!Q", left[8:16])[0], 0)
            self.assertEqual(left[16:], payload)

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
        self.subscribe()
        fast = self.subscribe()
        # Fill the unread client's finite queue, while draining the other one.
        payload = b"x" * 8192
        for i in range(100):
            packet = struct.pack("!I", i) + payload
            self.publish(packet)
            self.assertEqual(fast.recv(65552)[16:], packet)
        self.process.terminate()
        stdout, stderr = self.process.communicate(timeout=5)
        self.assertEqual(self.process.returncode, 0, stderr)
        self.assertRegex(stdout, r"slow_consumer_drops=[1-9][0-9]*")


if __name__ == "__main__":
    unittest.main()
