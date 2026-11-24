#!/usr/bin/env python3
"""Seal and verify the deployed FEED GAP UI contract while the live state is GAP."""

import json
from pathlib import Path
import re
import sys
import urllib.request


def verify(index, javascript, css, state):
    """Check deployed source + API, not rendered DOM (which needs a browser)."""
    def require(condition, message):
        if not condition:
            raise ValueError(message)

    def function(name):
        match = re.search(r"function\s+" + name + r"\s*\([^)]*\)\s*\{(.*?)(?=\nfunction |\Z)",
                          javascript, re.S)
        require(match is not None, "missing UI function: " + name)
        return re.sub(r"\s+", "", match.group(1))

    feed = state.get("feed", {})
    require(feed.get("integrity") == "GAP", "live feed is not GAP")
    require(feed.get("trading_gate") == "INHIBITED_FEED_GAP", "feed gap did not close trading gate")
    require('id="feed-gap-banner"' in index and "FEED GAP" in index, "missing GAP banner")
    require('id="submit-order"' in index, "missing manual order button")
    gap = function("renderFeedGap")
    require('gap=feedIntegrity(state)==="GAP"' in gap and
            'banner.hidden=!(gap||stale)' in gap and
            'document.body.classList.toggle("feed-gap",gap||stale)' in gap,
            "missing GAP/STALE banner or book styling guard")
    require('if(feedIntegrity(state)!=="HEALTHY")return' in function("orderUnavailable"),
            "missing shared unhealthy-feed order guard")
    manual = function("renderOrderSubmit")
    require('reason=orderUnavailable(app.state)' in manual and
            'button.disabled=app.submittingOrder||Boolean(reason)' in manual,
            "manual button does not use shared order guard")
    require('button.disabled=busy||app.submittingOrder||Boolean(orderUnavailable(state,transport))'
            in function("renderTransportLab"), "transport buttons do not use shared order guard")
    for selector in ("body.feed-gap .book-card", ".submit-order:disabled", ".transport-submit:disabled"):
        require(selector in css, "missing CSS: " + selector)
    return {"result": "PASS", "check_kind": "DEPLOYED_SOURCE_AND_API",
            "live_feed_integrity": feed["integrity"], "banner_dom": True,
            "book_gray_css": True, "manual_order_disabled": True, "transport_orders_disabled": True}


def main():
    if len(sys.argv) != 3:
        raise SystemExit("usage: assert-feed-gap-ui.py API_URL OUTPUT_DIR")
    api = sys.argv[1].rstrip("/")
    output = Path(sys.argv[2])
    output.mkdir(parents=True, exist_ok=True)
    assets = {}
    for name, path in (("index.html", "/"), ("terminal.js", "/terminal.js"),
                       ("terminal.css", "/terminal.css"), ("state.json", "/api/state")):
        with urllib.request.urlopen(api + path, timeout=3) as response:
            body = response.read()
        (output / ("gui-gap-" + name)).write_bytes(body)
        assets[name] = body.decode("utf-8")
    print(json.dumps(verify(assets["index.html"], assets["terminal.js"], assets["terminal.css"],
                            json.loads(assets["state.json"])), separators=(",", ":")))

if __name__ == "__main__":
    main()
