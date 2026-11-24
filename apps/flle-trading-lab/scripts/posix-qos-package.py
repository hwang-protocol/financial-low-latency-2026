#!/usr/bin/env python3
"""Local package verification; never deploy or change a running process."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from flle_trading.posix_qos import ARCHIVE_SHA, digest, runtime_root, verify_root

if __name__ == '__main__':
    try:
        action, path = sys.argv[1:]
        if action == 'runtime-root': print(runtime_root(path))
        elif action == 'verify-root': print(verify_root(path))
        elif action == 'verify-archive':
            if digest(path) != ARCHIVE_SHA: raise ValueError('POSIX QoS archive digest mismatch')
            print('posix_qos_archive=PASS default_dscp=0')
        else: raise ValueError('unknown action')
    except (ValueError, OSError) as error:
        raise SystemExit(str(error))
