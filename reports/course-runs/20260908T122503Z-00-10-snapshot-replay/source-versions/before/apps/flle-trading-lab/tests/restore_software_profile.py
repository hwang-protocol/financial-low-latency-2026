#!/usr/bin/env python3
"""Restore the verified post-lab Trader queue and CPU-role profile."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_ROOT))

from flle_trading.gateway import send_command  # noqa: E402
from software_measurement import constrain_peer_threads, set_affinity  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="10.1.1.2")
    args = parser.parse_args()
    changed = send_command(args.host, 48122, "SOFTWARE_PROFILE|SPSC_SPIN")
    _, manual_tid = set_affinity(args.host, 48122, "dedicated", 2, 0)
    _, auto_tid = set_affinity(args.host, 48121, "dedicated", 3, 0)
    _, manual_peers = constrain_peer_threads(args.host, manual_tid, "0-1")
    _, auto_peers = constrain_peer_threads(args.host, auto_tid, "0-1")
    print(f'已恢复盯着看，配置名 {changed["order_queue"]}')
    print(f'MANUAL 下单线程坐在 CPU 2，杂活在 {manual_peers}')
    print(f'AUTO 下单线程坐在 CPU 3，杂活在 {auto_peers}')


if __name__ == "__main__":
    main()
