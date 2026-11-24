#!/usr/bin/env python3
"""Prove that the common GUI/API order gate rejects trading during a feed gap."""

import json
import sys
import urllib.error
import urllib.request


api = (sys.argv[1] if len(sys.argv) > 1 else "http://10.1.1.101:8088").rstrip("/")
payload = json.dumps({
    "symbol": "AAPL",
    "side": "BUY",
    "quantity": 1,
    "limit_price_x10000": 999999999999,
    "transport": "SOCKET",
}).encode("ascii")
request = urllib.request.Request(
    api + "/api/order", data=payload, method="POST",
    headers={"Content-Type": "application/json"},
)
try:
    urllib.request.urlopen(request, timeout=3)
except urllib.error.HTTPError as error:
    body = json.loads(error.read())
    if error.code == 400 and body.get("error") == "FEED_NOT_HEALTHY":
        print(json.dumps({"http_status": error.code, **body}, separators=(",", ":")))
        raise SystemExit(0)
    raise
raise SystemExit("order was accepted while feed integrity was not healthy")
