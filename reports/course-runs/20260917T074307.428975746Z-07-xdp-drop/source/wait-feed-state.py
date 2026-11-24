#!/usr/bin/env python3
"""Wait for the live feed guardian to expose a specific integrity state."""

import argparse
import json
import time
import urllib.request


parser = argparse.ArgumentParser()
parser.add_argument("api")
parser.add_argument("integrity", choices=("HEALTHY", "GAP", "RECOVERING"))
parser.add_argument("--timeout", type=float, default=25.0)
parser.add_argument("--session-not", default="")
args = parser.parse_args()

deadline = time.time() + args.timeout
last = {}
while time.time() < deadline:
    with urllib.request.urlopen(args.api, timeout=2) as response:
        state = json.load(response)
    feed = state.get("feed") or {}
    health = (state.get("health") or {}).get("trader_auto") or {}
    session = str(state.get("session") or "")
    observed = str(feed.get("integrity") or "")
    ready = health.get("status") == "ONLINE" and observed == args.integrity
    if args.integrity == "HEALTHY":
        ready = (
            ready
            and str(feed.get("session") or "") == session
            and int(feed.get("next_expected") or 0) > 0
        )
    if args.integrity == "GAP":
        ready = ready and int(feed.get("pending") or 0) > 0
    if args.session_not:
        ready = ready and session and session != args.session_not
    last = {
        "session": session,
        "market_mode": state.get("market_mode"),
        "trader_auto": health.get("status"),
        "feed": feed,
    }
    if ready:
        print(json.dumps(last, ensure_ascii=True, separators=(",", ":")))
        raise SystemExit(0)
    time.sleep(0.25)

print(json.dumps(last, ensure_ascii=True, separators=(",", ":")))
raise SystemExit(1)
