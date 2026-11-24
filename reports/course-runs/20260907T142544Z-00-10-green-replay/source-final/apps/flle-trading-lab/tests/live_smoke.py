#!/usr/bin/env python3
"""Functional smoke test for the historical replay lab; not a benchmark."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from typing import Any


def request(base: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("ascii")
    value = urllib.request.Request(
        base + path,
        data=data,
        headers={"Content-Type": "application/json"} if data else {},
        method="POST" if data else "GET",
    )
    with urllib.request.urlopen(value, timeout=4) as response:
        return json.load(response)


def wait_state(base: str, predicate: Any, timeout: float = 8.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = request(base, "/api/state")
        if predicate(state):
            return state
        time.sleep(0.1)
    raise AssertionError("state transition timed out")


def wait_order(base: str, user_ref: int, timeout: float = 8.0) -> dict[str, Any]:
    state = wait_state(
        base,
        lambda value: any(
            int(order.get("client_order_id", 0)) == user_ref and order.get("result")
            for order in value.get("orders", [])
        ),
        timeout,
    )
    return next(order for order in state["orders"] if int(order.get("client_order_id", 0)) == user_ref)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://10.1.1.101:8088")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    initial = wait_state(
        base,
        lambda value: all(value["health"][name]["status"] == "ONLINE" for name in ("exchange", "trader_auto", "trader_manual", "gateway"))
        and set(value["instruments"]) == {"AAPL", "NVDA"},
        15,
    )
    assert initial["historical_market"] and initial["paper_execution"]
    assert initial["replay"]["market_date"] == "2026-06-12"
    assert initial["replay"]["window"] == "REGULAR_SESSION"
    assert initial["replay"]["first_source_clock"] == "09:30:00.000000000"
    assert initial["replay"]["last_source_clock"] == "16:00:00.000000000"
    assert "skipped_ns" not in initial["replay"]
    original_mode = initial["market_mode"]
    original_speed = float(initial["replay"]["speed"])
    original_strategy = dict(initial["strategy"])
    print(
        f"source={initial['replay']['source']} date={initial['replay']['market_date']} "
        f"clock={initial['replay']['source_clock']} loop={initial['replay']['loop']}"
    )

    try:
        request(base, "/api/strategy", {**original_strategy, "enabled": False})
        request(base, "/api/replay", {"action": "PAUSE"})
        paused = wait_state(base, lambda value: value["replay"]["status"] == "PAUSED")
        paused_clock = int(paused["replay"]["source_timestamp_ns"])
        time.sleep(0.4)
        assert int(request(base, "/api/state")["replay"]["source_timestamp_ns"]) == paused_clock
        request(base, "/api/replay", {"action": "SPEED", "speed": 2})
        request(base, "/api/replay", {"action": "RESUME"})
        wait_state(base, lambda value: value["replay"]["status"] == "PLAYING" and int(value["replay"]["source_timestamp_ns"]) > paused_clock)
        print("replay_control=PASS pause_clock_stable=true resume_advances=true speed=2x")

        before = request(base, "/api/state")
        request(base, "/api/market", {"market_mode": "DUAL"})
        dual = wait_state(
            base,
            lambda value: value["market_mode"] == "DUAL"
            and int(value["feed"]["duplicates"]) > int(before["feed"]["duplicates"]),
        )
        assert int(dual["feed"]["pending"]) == 0
        print("mold_dual_feed=PASS duplicate_suppression=true")

        quote = dual["trader_books"]["AAPL"]
        order = request(base, "/api/order", {"symbol": "AAPL", "side": "BUY", "quantity": 1, "limit_price_x10000": int(quote["asks"][0][0]) + 1_000_000})
        completed = wait_order(base, int(order["client_order_id"]))
        assert completed["result"] == "ORDER_EXECUTED"
        assert completed["clordid"].startswith("MANU")
        print(f"ouch_order=PASS user_ref={order['client_order_id']} result=ORDER_EXECUTED")

        before_restart = request(base, "/api/state")
        loop_before = int(before_restart["replay"]["loop"])
        paper_epoch_before = int(before_restart["paper_epoch"])
        request(base, "/api/replay", {"action": "RESTART"})
        restarted = wait_state(
            base,
            lambda value: int(value["replay"]["loop"]) > loop_before
            and int(value["paper_epoch"]) > paper_epoch_before
            and not value["orders"]
            and not value["fills"]
            and all(int(position) == 0 for position in value["positions"].values())
            and int(value["latency"]["samples"]) == 0,
            20,
        )
        print(f"replay_restart=PASS loop={restarted['replay']['loop']} paper_state=CLEARED")
    finally:
        request(base, "/api/strategy", original_strategy)
        request(base, "/api/market", {"market_mode": original_mode})
        request(base, "/api/replay", {"action": "SPEED", "speed": original_speed})
        request(base, "/api/replay", {"action": "RESUME"})
        wait_state(
            base,
            lambda value: value["market_mode"] == original_mode
            and float(value["replay"]["speed"]) == original_speed
            and value["replay"]["status"] == "PLAYING"
            and bool(value["strategy"]["enabled"]) == bool(original_strategy["enabled"]),
            5,
        )

    print("LIVE_SMOKE_PASS protocol=ITCH5/MoldUDP64+OUCH5/SoupBinTCP")


if __name__ == "__main__":
    main()
