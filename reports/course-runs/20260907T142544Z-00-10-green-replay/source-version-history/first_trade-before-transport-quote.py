#!/usr/bin/env python3
"""Submit one paper IOC while the historical market keeps replaying."""

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


def wait_state(base: str, predicate: Callable[[dict[str, Any]], bool], timeout: float = 15) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = request(base, "/api/state")
        if predicate(state):
            return state
        time.sleep(0.1)
    raise AssertionError("state transition timed out")


def ready_for_manual_trade(state: dict[str, Any]) -> bool:
    profile = state.get("experiment_profile", "SOFTWARE")
    names = ("exchange", "trader_manual", "gateway")
    if profile == "SOFTWARE":
        names += ("trader_auto",)
    elif profile != "TRANSPORT":
        return False
    book = state.get("trader_books", {}).get("AAPL", {})
    return (all(state.get("health", {}).get(name, {}).get("status") == "ONLINE" for name in names)
            and state.get("data_plane_mode") == "SFC"
            and state.get("data_plane_transition") == "READY"
            and state.get("feed", {}).get("integrity") == "HEALTHY"
            and state.get("replay", {}).get("status") == "PLAYING"
            and bool(book.get("asks")) and bool(book.get("bids")))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://10.1.1.101:8088")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    initial = wait_state(
        base,
        ready_for_manual_trade,
    )
    assert initial["historical_market"] and initial["paper_execution"]
    strategy_enabled = bool(initial["strategy"]["enabled"])
    completed: dict[str, Any] = {}
    attempts = 0
    live = request(base, "/api/state")
    manual_position = int(live["client_positions"]["trader_manual"]["AAPL"])
    side = "SELL" if manual_position > 0 else "BUY"
    source_before = int(live["replay"]["source_timestamp_ns"])
    replay_loop = int(live["replay"]["loop"])
    for attempts in range(1, 4):
        quote_state = request(base, "/api/state")
        assert quote_state["replay"]["status"] == "PLAYING"
        assert bool(quote_state["strategy"]["enabled"]) == strategy_enabled
        quote = quote_state["trader_books"]["AAPL"]
        limit_price = max(1, int(quote["bids"][0][0]) - 50_000) if side == "SELL" else int(quote["asks"][0][0]) + 50_000
        queued = request(base, "/api/order", {"symbol": "AAPL", "side": side, "quantity": 1, "limit_price_x10000": limit_price})
        order_id = int(queued["client_order_id"])
        state = wait_state(base, lambda value: any(int(order.get("client_order_id", 0)) == order_id and order.get("result") for order in value["orders"]))
        candidate = next(order for order in state["orders"] if int(order.get("client_order_id", 0)) == order_id)
        assert candidate["origin"] == "MANUAL_GUI"
        if candidate["result"] == "ORDER_EXECUTED":
            completed = candidate
            break
        assert int(candidate["filled_quantity"]) == 0
        assert int(candidate["position_delta"]) == 0
    assert completed, "three live IOC attempts found no executable AAPL quote"
    expected_delta = -1 if side == "SELL" else 1
    assert int(completed["filled_quantity"]) == 1
    assert int(completed["position_delta"]) == expected_delta
    assert any(int(fill.get("client_order_id", 0)) == int(completed["client_order_id"]) for fill in state["fills"])
    wait_state(
        base,
        lambda value: any(int(order.get("client_order_id", 0)) == int(completed["client_order_id"]) and order.get("result") == "ORDER_EXECUTED" for order in value["exchange_ledger"]),
    )
    market_after = wait_state(
        base,
        lambda value: value["replay"]["status"] == "PLAYING"
        and int(value["replay"]["loop"]) == replay_loop
        and int(value["replay"]["source_timestamp_ns"]) > source_before
        and bool(value["strategy"]["enabled"]) == strategy_enabled
        and any(int(order.get("client_order_id", 0)) == int(completed["client_order_id"]) for order in value["exchange_ledger"]),
    )

    source_after = int(market_after["replay"]["source_timestamp_ns"])
    print(f"system=READY source=NASDAQ_PUBLIC_ITCH_SAMPLE date={initial['replay']['market_date']} replay=PLAYING")
    print(f"market_clock={live['replay']['source_clock']}->{market_after['replay']['source_clock']} source_advance_ns={source_after - source_before}")
    print(f"order_id={completed['client_order_id']} attempts={attempts} origin={completed['origin']} symbol=AAPL side={completed['side']} quantity=1")
    print(f"limit_price_x10000={completed['limit_price_x10000']} fill_price_x10000={completed['fill_price_x10000']}")
    print(f"result={completed['result']} filled={completed['filled_quantity']}")
    print(f"position_delta={int(completed['position_delta']):+d} manual_position={completed['position']} order_rtt_ns={completed['order_rtt_ns']}")
    print(f"history=CLIENT_AND_EXCHANGE strategy_unchanged={str(strategy_enabled == bool(market_after['strategy']['enabled'])).lower()}")
    print("verdict=FIRST_TRADE_PASS")


if __name__ == "__main__":
    main()
