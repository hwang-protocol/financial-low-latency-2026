import json
import pathlib
import select
import socket
import struct
import subprocess
import tempfile
import time

out = pathlib.Path('/financial-low-latency/Documents/reports/course-runs/20260910T074430Z-02-feed-gap-diagnosis/raw')
binary = out / 'flle-feed-receiver'
results = []
for pause_slow in [False, True]:
    with tempfile.TemporaryDirectory(prefix='flle-ipc-gap-') as directory:
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
                client.settimeout(2)
                client.connect(path)
                clients.append(client)
            slow, fast = clients
            slow_seen, fast_seen = [], []
            start = time.monotonic()
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sender:
                for seq in range(1, 801):
                    payload = struct.pack('!10sQHH', b'GAPREPRO01', seq, 1, 36) + b'A' + bytes(35)
                    sender.sendto(payload, ('127.0.0.1', port))
                    fast_seen.append(struct.unpack_from('!Q', fast.recv(65552), 26)[0])
                    if not pause_slow:
                        slow_seen.append(struct.unpack_from('!Q', slow.recv(65552), 26)[0])
            pause_ms = (time.monotonic() - start) * 1000
            if pause_slow:
                while select.select([slow], [], [], 0.05)[0]:
                    slow_seen.append(struct.unpack_from('!Q', slow.recv(65552), 26)[0])
            inode = pathlib.Path(f'/proc/{process.pid}/fd/3').readlink().name.split('[')[1].rstrip(']')
            udp_lines = pathlib.Path('/proc/net/udp').read_text().splitlines()
            socket_line = next(line for line in udp_lines[1:] if line.split()[9] == inode)
            udp_drops = int(socket_line.split()[-1])
            process.terminate()
            stdout, stderr = process.communicate(timeout=5)
            assert process.returncode == 0, stderr
            counters = dict(part.split('=', 1) for part in stdout.split())
            missing = sorted(set(range(1, 801)) - set(slow_seen))
            assert fast_seen == list(range(1, 801))
            assert udp_drops == 0
            assert int(counters['slow_consumer_drops']) == len(missing)
            assert bool(missing) == pause_slow
            results.append(dict(pause_slow=pause_slow, send_window_ms=pause_ms,
                                fast_received=len(fast_seen), slow_received=len(slow_seen),
                                slow_missing=len(missing), first_missing=missing[0] if missing else None,
                                udp_drops=udp_drops, raw_udp=socket_line,
                                ready=ready, stopped=stdout.strip()))
        finally:
            for client in clients:
                client.close()
            if process.poll() is None:
                process.terminate()
                process.communicate(timeout=5)
(out / 'local-fanout-reproduction.json').write_text(json.dumps(results, indent=2) + '\n')
print(json.dumps(results, indent=2))
