#!/usr/bin/env python3
"""Seal and verify the deployed FEED GAP UI contract while the live state is GAP."""

import json
from pathlib import Path
import sys
import urllib.request


if len(sys.argv) != 3:
    raise SystemExit("usage: assert-feed-gap-ui.py API_URL OUTPUT_DIR")

api = sys.argv[1].rstrip("/")
output = Path(sys.argv[2])
output.mkdir(parents=True, exist_ok=True)


def fetch(path: str) -> bytes:
    with urllib.request.urlopen(api + path, timeout=3) as response:
        return response.read()


assets = {
    "gui-gap-index.html": fetch("/"),
    "gui-gap-terminal.js": fetch("/terminal.js"),
    "gui-gap-terminal.css": fetch("/terminal.css"),
    "gui-gap-state.json": fetch("/api/state"),
}
for name, body in assets.items():
    (output / name).write_bytes(body)

index = assets["gui-gap-index.html"].decode("utf-8")
javascript = assets["gui-gap-terminal.js"].decode("utf-8")
css = assets["gui-gap-terminal.css"].decode("utf-8")
state = json.loads(assets["gui-gap-state.json"])

assert state["feed"]["integrity"] == "GAP", state["feed"]
assert 'id="feed-gap-banner"' in index and "FEED GAP" in index
assert 'id="submit-order"' in index
assert 'document.body.classList.toggle("feed-gap", gap)' in javascript
assert '$("submit-order").disabled=!feedHealthy' in javascript
assert "button.disabled=!(available&&canTrade)" in javascript
assert "body.feed-gap .book-card" in css
assert ".submit-order:disabled" in css
assert ".transport-submit:disabled" in css

print(json.dumps({
    "result": "PASS",
    "live_feed_integrity": state["feed"]["integrity"],
    "banner_dom": True,
    "book_gray_css": True,
    "manual_order_disabled": True,
    "transport_orders_disabled": True,
}, separators=(",", ":")))
