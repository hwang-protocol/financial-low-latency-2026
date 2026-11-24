#!/usr/bin/env python3
"""Check the live receiver image and its own READY record before A/B reuse."""
import hashlib
from pathlib import Path
import sys


def verify(run, multicast='1', proc=Path('/proc')):
    run = Path(run).resolve()
    pid = int((run / 'feed-receiver.pid').read_text())
    identity = dict(token.split('=', 1) for token in (run / 'feed-receiver.identity').read_text().split())
    process = proc / str(pid)
    def current():
        return dict(pid=str(pid), start_ticks=(process / 'stat').read_text().rsplit(')', 1)[1].split()[19],
                    boot_id=(proc / 'sys/kernel/random/boot_id').read_text().strip())
    if identity != current():
        raise ValueError('receiver process identity changed')
    image = run / 'flle-feed-receiver'
    if (process / 'exe').resolve() != image:
        raise ValueError('receiver is running a replaced or unexpected executable')
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    if digest(process / 'exe') != digest(image):
        raise ValueError('receiver process and deployed executable differ')
    lines = (run / 'feed-receiver.log').read_text().splitlines()
    ready = next((line for line in reversed(lines) if line.startswith('feed_receiver=READY ')), '')
    fields = dict(token.split('=', 1) for token in ready.split() if '=' in token)
    expected = dict(pid=str(pid), market_schema='udp-multicast-ab-v1', multicast_source='20.1.1.1',
                    multicast=('233.74.125.32' if multicast == '1' else 'DISABLED') + ':31032',
                    multicast_b=('233.74.125.33' if multicast == '1' else 'DISABLED') + ':31033')
    if any(fields.get(key) != value for key, value in expected.items()):
        raise ValueError('receiver READY lacks matching A/B endpoints, source filter or PID')
    ipc = Path(fields.get('ipc', ''))
    if not ipc.is_absolute() or ipc.resolve() != run / 'feed.sock':
        raise ValueError('receiver READY refers to a different IPC socket')
    if identity != current():
        raise ValueError('receiver process changed during verification')
    return fields


if __name__ == '__main__':
    try:
        verify(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else '1')
    except (OSError, ValueError, IndexError) as error:
        raise SystemExit(f'A/B receiver verification failed: {error}; deploy the current platform before continuing')
    print('feed_receiver=VERIFIED market_schema=udp-multicast-ab-v1 multicast_source=20.1.1.1')
