#!/usr/bin/env python3
"""Prove independent manual and automatic clients can trade concurrently."""

from __future__ import annotations

import argparse
import json
import time
import urllib.request
from typing import Any, Callable


def request(base: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("ascii")
    req = urllib.request.Request(
        base + path,
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
        method="POST" if data else "GET",
    )
    with urllib.request.urlopen(req, timeout=4) as response:
        return json.load(response)


def wait_state(base: str, predicate: Callable[[dict[str, Any]], bool], timeout: float = 20) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = request(base, "/api/state")
        if predicate(state):
            return state
        time.sleep(0.1)
    raise AssertionError("concurrent trading condition timed out")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://10.1.1.101:8088")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    initial = wait_state(
        base,
        lambda state: state["replay"]["status"] == "PLAYING"
        and all(state["health"][name]["status"] == "ONLINE" for name in ("exchange", "trader_auto", "trader_manual", "gateway"))
        and "AAPL" in state["trader_books"],
    )
    original_strategy = dict(initial["strategy"])
    started_ns = int(initial["server_ns"])
    try:
        request(base, "/api/strategy", {"enabled": True, "imbalance_threshold": 0.05, "quantity": 1, "max_position": 10000, "cooldown_ms": 100})
        quote = request(base, "/api/state")["trader_books"]["AAPL"]
        queued = request(
            base,
            "/api/order",
            {"symbol": "AAPL", "side": "BUY", "quantity": 1, "limit_price_x10000": int(quote["asks"][0][0]) + 1_000_000},
        )
        manual_id = int(queued["client_order_id"])
        state = wait_state(
            base,
            lambda value: any(int(order.get("client_order_id", 0)) == manual_id and order.get("result") == "ORDER_EXECUTED" for order in value["orders"])
            and any(order.get("origin") == "AUTO_STRATEGY" and order.get("result") == "ORDER_EXECUTED" and int(order.get("event_ns", 0)) > started_ns for order in value["orders"]),
        )
    finally:
        request(base, "/api/strategy", original_strategy)

    manual = next(order for order in state["orders"] if int(order.get("client_order_id", 0)) == manual_id)
    automatic = next(order for order in reversed(state["orders"]) if order.get("origin") == "AUTO_STRATEGY" and order.get("result") == "ORDER_EXECUTED" and int(order.get("event_ns", 0)) > started_ns)
    assert manual["clordid"].startswith("MANU") and int(manual["client_order_id"]) >= 2_100_000_000
    assert automatic["clordid"].startswith("AUTO") and int(automatic["client_order_id"]) < 2_100_000_000
    state = wait_state(
        base,
        lambda value: {int(order["client_order_id"]) for order in value["exchange_ledger"]}.issuperset(
            {int(manual["client_order_id"]), int(automatic["client_order_id"])}
        ),
    )
    assert int(state["exchange_ledger_entries"]) >= 2
    server_ids = {int(order["client_order_id"]) for order in state["exchange_ledger"]}
    assert int(manual["client_order_id"]) in server_ids and int(automatic["client_order_id"]) in server_ids
    print(f"manual_order={manual['client_order_id']} origin=MANUAL_GUI result={manual['result']}")
    print(f"automatic_order={automatic['client_order_id']} origin=AUTO_STRATEGY result={automatic['result']}")
    print(f"exchange_ledger_entries={state['exchange_ledger_entries']} unified_history=PASS")
    print("verdict=CONCURRENT_CLIENTS_PASS")


if __name__ == "__main__":
    main()
