import json
from pathlib import Path
import select
import socket
import struct
import subprocess
import tempfile
import time

root = Path('/financial-low-latency')
out = root / 'Documents/reports/course-runs/20260910T080208Z-02-fanout-fix/raw'
binary = root / 'apps/flle-trading-lab/build/flle-feed-receiver'
with tempfile.TemporaryDirectory(prefix='flle-bounded-burst-') as directory:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        probe.bind(('127.0.0.1', 0))
        port = probe.getsockname()[1]
    path = directory + '/feed.sock'
    process = subprocess.Popen([str(binary), '--data-ip', '127.0.0.1', '--socket', path,
                                '--unicast-port', str(port), '--multicast-receiver', '0',
                                '--receive-buffer-bytes', '65536'],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    clients = []
    try:
        assert select.select([process.stdout], [], [], 3)[0]
        ready = process.stdout.readline().strip()
        assert 'feed_receiver=READY' in ready
        for _ in range(2):
            client = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
            client.settimeout(5)
            client.connect(path)
            clients.append(client)
        slow, fast = clients
        started = time.monotonic()
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
            for sequence in range(1, 10001):
                packet = struct.pack('!10sQHH', b'STRESS0001', sequence, 1, 36) + b'A' + bytes(35)
                sender.sendto(packet, ('127.0.0.1', port))
                assert fast.recv(65552)[16:] == packet
        time.sleep(1)
        held = time.monotonic() - started
        for sequence in range(1, 10001):
            packet = struct.pack('!10sQHH', b'STRESS0001', sequence, 1, 36) + b'A' + bytes(35)
            assert slow.recv(65552)[16:] == packet
        line = next(line for line in Path('/proc/net/udp').read_text().splitlines()[1:]
                    if line.split()[1] == f'0100007F:{port:04X}')
        drops = int(line.split()[-1])
        assert drops == 0
        process.terminate()
        stdout, stderr = process.communicate(timeout=5)
        assert process.returncode == 0, stderr
        status = json.loads([line.split(' ', 1)[1] for line in stdout.splitlines()
                             if line.startswith('feed_receiver=STATUS ')][-1])
        assert status['received'] == 10000 and status['delivered'] == 20000
        assert status['peak_client_packets'] > 1131 and status['queued_packets'] == 0
        assert status['overflow_disconnects'] == status['discarded_queue_packets'] == 0
        result = dict(status='PASS', scope='Local isolated child; no live VM pause or configuration change',
                      fast_messages=10000, slow_messages=10000, byte_identical_and_ordered=True,
                      slow_no_read_seconds=held, udp_drops=drops, receiver=status)
        (out / 'local-10000-packet-burst.json').write_text(json.dumps(result, indent=2) + '\n')
        (out / 'local-10000-packet-burst.txt').write_text(ready + '\n' + stdout + stderr)
        print(json.dumps(result, indent=2))
    finally:
        for client in clients:
            client.close()
        if process.poll() is None:
            process.terminate()
            process.communicate(timeout=5)
