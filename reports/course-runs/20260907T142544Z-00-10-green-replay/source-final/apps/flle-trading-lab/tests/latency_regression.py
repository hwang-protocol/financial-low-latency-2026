#!/usr/bin/env python3
"""Guard against delayed-ACK/Nagle tails on the C++ order path; not a benchmark."""

from __future__ import annotations

import argparse
import time

from live_smoke import request, wait_order, wait_state


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://10.1.1.101:8088")
    parser.add_argument("--samples", type=int, default=120)
    parser.add_argument("--p99-limit-ns", type=int, default=10_000_000)
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    initial = wait_state(
        base,
        lambda value: set(value.get("trader_books", {})) == {"AAPL", "NVDA"}
        and value.get("replay", {}).get("status") == "PLAYING",
        20,
    )
    original_strategy = dict(initial["strategy"])
    original_mode = initial["market_mode"]
    original_speed = float(initial["replay"]["speed"])
    epoch_before = int(initial["paper_epoch"])
    cleanup_epoch = epoch_before
    try:
        request(base, "/api/strategy", {**original_strategy, "enabled": False})
        request(base, "/api/market", {"market_mode": "MULTICAST"})
        request(base, "/api/replay", {"action": "SPEED", "speed": 1})
        request(base, "/api/replay", {"action": "RESTART"})
        measurement_state = wait_state(
            base,
            lambda value: int(value["paper_epoch"]) > epoch_before
            and set(value.get("trader_books", {})) == {"AAPL", "NVDA"}
            and int(value["client_latency"]["trader_manual"]["samples"]) == 0,
            20,
        )
        cleanup_epoch = int(measurement_state["paper_epoch"])
        for index in range(args.samples):
            state = request(base, "/api/state")
            side = "BUY" if index % 2 == 0 else "SELL"
            level = state["trader_books"]["AAPL"]["asks" if side == "BUY" else "bids"][0]
            marketable_limit = int(level[0]) + 1_000_000 if side == "BUY" else max(1, int(level[0]) - 1_000_000)
            order = request(
                base,
                "/api/order",
                {"symbol": "AAPL", "side": side, "quantity": 1, "limit_price_x10000": marketable_limit},
            )
            result = wait_order(base, int(order["client_order_id"]), 4)
            assert result["result"] == "ORDER_EXECUTED"
        measured = wait_state(base, lambda value: int(value["client_latency"]["trader_manual"]["samples"]) >= args.samples, 5)
        latency = measured["client_latency"]["trader_manual"]
        assert int(latency["samples"]) == args.samples
        assert int(latency["p99_ns"]) < args.p99_limit_ns, latency
        print(
            "LATENCY_REGRESSION_PASS "
            f"samples={latency['samples']} p50_ns={latency['p50_ns']} "
            f"p99_ns={latency['p99_ns']} max_ns={latency['max_ns']} "
            f"limit_ns={args.p99_limit_ns}"
        )
    finally:
        request(base, "/api/strategy", original_strategy)
        request(base, "/api/market", {"market_mode": original_mode})
        request(base, "/api/replay", {"action": "SPEED", "speed": original_speed})
        request(base, "/api/replay", {"action": "RESTART"})
        wait_state(
            base,
            lambda value: int(value["paper_epoch"]) > cleanup_epoch
            and value["market_mode"] == original_mode
            and float(value["replay"]["speed"]) == original_speed
            and bool(value["strategy"]["enabled"]) == bool(original_strategy["enabled"]),
            20,
        )
        time.sleep(0.2)


if __name__ == "__main__":
    main()
