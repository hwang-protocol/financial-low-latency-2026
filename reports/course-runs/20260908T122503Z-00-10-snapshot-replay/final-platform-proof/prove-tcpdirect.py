#!/usr/bin/env python3
"""Submit a position-neutral pair of real Socket/SoupBinTCP/OUCH orders."""

import json
import sys
import time
import urllib.request
from pathlib import Path


api = sys.argv[1].rstrip("/")
output = Path(sys.argv[2])
output.mkdir(parents=True, exist_ok=True)


def get_state():
    with urllib.request.urlopen(api + "/api/state", timeout=3) as response:
        return json.load(response)


def post(path, payload):
    request = urllib.request.Request(
        api + path, data=json.dumps(payload).encode("ascii"), method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=3) as response:
        return json.load(response)


# replay_started clears the gateway projection immediately; the Chapter 06
# order-only clients are rehydrated by the one-second management poll.
time.sleep(2.0)
before = get_state()
feed = before.get("feed") or {}
assert feed.get("integrity") == "HEALTHY", feed
assert ((before.get("health") or {}).get("trader_auto") or {}).get("status") == "ONLINE"
position = int((before.get("positions") or {}).get("AAPL", 0))
orders = (
    ("SELL", 1, "reduce-risk"),
    ("BUY", 999999999999, "restore-position"),
) if position >= 0 else (
    ("BUY", 999999999999, "reduce-risk"),
    ("SELL", 1, "restore-position"),
)
results = []
for side, limit, label in orders:
    reply = post("/api/order", {
        "symbol": "AAPL", "side": side, "quantity": 1,
        "limit_price_x10000": limit, "transport": "TCPDIRECT",
    })
    order_id = int(reply["client_order_id"])
    deadline = time.time() + 10
    while time.time() < deadline:
        state = get_state()
        rows = [row for row in state.get("orders", [])
                if int(row.get("client_order_id", 0)) == order_id]
        if rows and rows[0].get("result") == "ORDER_EXECUTED":
            row = rows[0]
            assert int(row.get("order_rtt_ns", 0)) > 0
            result = {"label": label, "client_order_id": order_id,
                      "side": side, "result": row["result"],
                      "order_rtt_ns": int(row["order_rtt_ns"])}
            results.append(result)
            (output / f"{label}.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            break
        time.sleep(0.1)
    else:
        raise SystemExit(f"order {order_id} did not execute")

deadline = time.time() + 5
while True:
    after = get_state()
    if int(after["positions"]["AAPL"]) == position:
        break
    if time.time() >= deadline:
        raise SystemExit(
            f"position did not converge after neutral pair: "
            f"{position}->{after['positions']['AAPL']}"
        )
    time.sleep(0.1)
summary = {
    "result": "PASS",
    "feed": after["feed"],
    "orders": results,
    "position_AAPL": [position, int(after["positions"]["AAPL"])],
}
(output / "recovery.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps(summary, ensure_ascii=True, separators=(",", ":")))
