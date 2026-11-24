"""Real local UDP multicast checks; no lab devices or trading orders."""
import json
from pathlib import Path
import select
import socket
import struct
import subprocess
import tempfile
import time
import unittest


class ABMulticastTest(unittest.TestCase):
    def setUp(self):
        self.build = Path(__file__).resolve().parents[1] / 'build'
        for name in ('flle-exchange', 'flle-feed-receiver'):
            if not (self.build / name).exists():
                self.skipTest('build native programs first')
        self.tmp = tempfile.TemporaryDirectory(prefix='ab-multicast-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.sockets = []
        self.processes = []
        self.addCleanup(self.close)

    def close(self):
        for p in self.processes:
            p.terminate()
            p.communicate(timeout=5)
        for s in self.sockets:
            s.close()

    def udp(self, group=None):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sockets.append(s)
        s.bind(('', 0))
        if group:
            s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP,
                         socket.inet_aton(group) + socket.inet_aton('127.0.0.1'))
        s.settimeout(2)
        return s

    def port(self):
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            return s.getsockname()[1]

    def launch(self, binary, args):
        p = subprocess.Popen([str(self.build / binary)] + args,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.processes.append(p)
        return p

    def test_exchange_modes_send_identical_ab_and_no_unicast(self):
        a, b, u = self.udp('233.74.125.32'), self.udp('233.74.125.33'), self.udp()
        checkpoint = self.root / 'book'
        checkpoint.write_bytes(b'FLLEB01\0' + struct.pack('!Q', 0))
        replay = self.root / 'feed'
        # Twenty seconds of paced ITCH System Events, one per 10 ms.
        replay.write_bytes(b''.join(struct.pack('!H', 12) + b'S' + bytes(4) +
            (34200000000000 + i * 10000000).to_bytes(6, 'big') + b'O' for i in range(2000)))
        management = self.port()
        p = self.launch('flle-exchange', ['--data-ip', '127.0.0.1',
            '--trader-data-ip', '127.0.0.1', '--management-ip', '127.0.0.1',
            '--management-port', str(management), '--order-port', str(self.port()),
            '--telemetry-host', '127.0.0.1', '--telemetry-port', str(self.udp().getsockname()[1]),
            '--multicast-port', str(a.getsockname()[1]), '--multicast-port-b', str(b.getsockname()[1]),
            '--unicast-port', str(u.getsockname()[1]), '--replay-file', str(replay),
            '--book-checkpoint', str(checkpoint)])
        def command(value):
            with socket.create_connection(('127.0.0.1', management), timeout=2) as c:
                c.sendall(value.encode() + b'\n')
                return json.loads(c.makefile('rb').readline())
        deadline = time.monotonic() + 5
        while True:
            try:
                initial = command('STATE'); break
            except ConnectionRefusedError:
                if p.poll() is not None or time.monotonic() > deadline:
                    self.fail('Exchange did not start')
                time.sleep(.01)
        self.assertEqual(initial['market_schema'], 'udp-multicast-ab-v1')
        self.assertEqual(initial['market_group_b'], '233.74.125.33')
        sessions, last = set(), 0
        for mode, active in [('MULTICAST_A', [a]), ('MULTICAST_B', [b]), ('DUAL', [a, b])]:
            command('REPLAY|PAUSE')
            time.sleep(.03)
            for s in (a, b, u):
                while select.select([s], [], [], 0)[0]: s.recv(65536)
            command('MARKET|' + mode)
            command('REPLAY|RESUME')
            packets = [s.recv(65536) for s in active]
            if mode == 'DUAL': self.assertEqual(packets[0], packets[1])
            sessions.add(packets[0][:10])
            sequence = struct.unpack('!Q', packets[0][10:18])[0]
            self.assertGreater(sequence, last)
            last = sequence
            inactive = [s for s in (a, b, u) if s not in active]
            self.assertEqual(select.select(inactive, [], [], .05)[0], [])
        self.assertEqual(len(sessions), 1)

    def test_receiver_joins_both_groups_and_preserves_local_abi(self):
        # Reserve distinct receive ports, then release before the receiver binds.
        ports = []
        for _ in range(3):
            s = self.udp(); ports.append(s.getsockname()[1]); s.close()
        path = str(self.root / 'feed.sock')
        p = self.launch('flle-feed-receiver', ['--data-ip', '127.0.0.1', '--multicast-source', '127.0.0.1', '--socket', path,
            '--unicast-port', str(ports[0]), '--multicast-port', str(ports[1]),
            '--multicast-port-b', str(ports[2]), '--telemetry-host', '127.0.0.1'])
        self.assertTrue(select.select([p.stdout], [], [], 5)[0])
        self.assertIn('feed_receiver=READY', p.stdout.readline())
        client = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
        self.sockets.append(client); client.settimeout(2); client.connect(path)
        sender = self.udp()
        sender.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton('127.0.0.1'))
        for ip, port, marker in [('127.0.0.1', ports[0], 0),
                ('233.74.125.32', ports[1], 1), ('233.74.125.33', ports[2], 1)]:
            sender.sendto(b'identical-mold-payload', (ip, port))
            packet = client.recv(65536)
            self.assertEqual(packet[:5], b'FLF1' + bytes([marker]))
            self.assertEqual(packet[16:], b'identical-mold-payload')
        # A datagram with a different source must never reach local subscribers.
        rogue = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sockets.append(rogue); rogue.bind(('127.0.0.2', 0))
        rogue.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton('127.0.0.1'))
        for group, port in [('233.74.125.32', ports[1]), ('233.74.125.33', ports[2])]:
            rogue.sendto(b'foreign-session-payload', (group, port))
        self.assertEqual(select.select([client], [], [], .2)[0], [])
        p.terminate(); out, err = p.communicate(timeout=5)
        self.processes.remove(p)
        self.assertEqual(p.returncode, 0, err)
        status = json.loads([s.split('STATUS ', 1)[1] for s in out.splitlines() if 'STATUS ' in s][-1])
        for key in ('unicast_received', 'multicast_a_received', 'multicast_b_received'):
            self.assertEqual(status[key], 1)


if __name__ == '__main__':
    unittest.main()
