#!/usr/bin/env python3
"""Wait for telemetry to show the same missing sequence and paused replay."""
import json
import sys
import time
import urllib.request


def is_held(state, observed):
    feed = state.get("feed") or {}
    return (state.get("session") == observed["session"]
            and feed.get("session") == observed["feed"]["session"]
            and feed.get("next_expected") == observed["feed"]["next_expected"]
            and feed.get("integrity") == "GAP"
            and feed.get("trading_gate") == "INHIBITED_FEED_GAP"
            and (state.get("replay") or {}).get("status") == "PAUSED")


if __name__ == "__main__":
    observed = json.load(open(sys.argv[2], encoding="utf-8"))
    deadline = time.monotonic() + 10
    state = {}
    while time.monotonic() < deadline:
        with urllib.request.urlopen(sys.argv[1], timeout=2) as response:
            state = json.load(response)
        if is_held(state, observed):
            print(json.dumps(state, separators=(",", ":")))
            raise SystemExit(0)
        time.sleep(0.25)
    print(json.dumps(state, separators=(",", ":")))
    raise SystemExit("same-session GAP/PAUSED was not confirmed; inspect before restarting")
