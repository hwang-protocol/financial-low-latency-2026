#!/usr/bin/env python3
"""Check active classroom links without requiring parked tool ports to be up."""
from pathlib import Path
import re
import sys


def check(text: str) -> None:
    ports = {}
    for line in text.splitlines():
        m = re.match(r'^Et(1|2|11|12)\s+(connected|notconnect|disabled|errdisabled)\s+(\S+)\s+', line)
        if m:
            ports[int(m[1])] = (m[2], m[3])
    if set(ports) != {1, 2, 11, 12}:
        raise ValueError('missing course interface status')
    for port, (status, vlan) in ports.items():
        if vlan != '20':
            raise ValueError(f'Et{port}: expected VLAN20, got {vlan}')
        if status == 'notconnect' and port in (11, 12):
            continue
        if status != 'connected':
            raise ValueError(f'Et{port}: required link is {status}')
        if not re.search(r'^Et'+str(port)+r'\s+designated\s+forwarding\b', text, re.M):
            raise ValueError(f'Et{port}: connected link is not forwarding')


if __name__ == '__main__':
    try:
        check(Path(sys.argv[1]).read_text())
    except ValueError as exc:
        print(f'forwarding=WAIT {exc}', file=sys.stderr)
        raise SystemExit(1)
    print('forwarding=READY Et1/Et2 up; every connected course port forwards; parked tool ports may be down')
