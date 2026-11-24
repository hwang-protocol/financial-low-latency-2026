"""Pinned additive client contract; the original v13 runtime remains immutable."""
import hashlib
from pathlib import Path

NAME = 'flle-posix-qos-v1'
ARCHIVE_SHA = '307ed39428770766453095cf04dd4b2432b2e765c6c233f4a0f86ebd117eb05e'
BINARY_SHA = 'e7c5be8e70c0e61cede54c9b7ba8406c1640464b5863d93e2a1297e8523343f1'
MANIFEST_SHA = '2ba8228fd630680263227585213021f3caacc31b5b726437366e1ddfead446f7'
SUFFIX = '/posix-runtime/' + NAME + '/bin/flle-trader'

def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def verify_root(root):
    root = Path(root)
    if digest(root / 'MANIFEST.sha256') != MANIFEST_SHA:
        raise ValueError('POSIX QoS manifest digest mismatch')
    for line in (root / 'MANIFEST.sha256').read_text().splitlines():
        expected, name = line.split()
        p = root / name
        if not p.resolve().is_relative_to(root.resolve()) or digest(p) != expected:
            raise ValueError(f'POSIX QoS file mismatch: {name}')
    if digest(root / 'bin/flle-trader') != BINARY_SHA:
        raise ValueError('POSIX QoS executable digest mismatch')
    return root

def runtime_root(run):
    run = Path(run)
    marker = run / 'posix-qos.enabled'
    if not marker.exists(): return run / 'transport-runtime/flle-ch05-four-path'
    if marker.read_text().strip() != 'POSIX_QOS_V1':
        raise ValueError('unknown POSIX QoS selection')
    return verify_root(run / 'posix-runtime' / NAME)
