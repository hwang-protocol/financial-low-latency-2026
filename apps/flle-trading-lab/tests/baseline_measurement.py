#!/usr/bin/env python3
"""Capture a repeatable C++ OUCH RTT baseline while market replay stays live."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
import time
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from flle_trading.gateway import send_command  # noqa: E402


def http_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=3) as response:
        return json.load(response)


def nearest_rank(values: list[int], percentile: float) -> int:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]


def capture_phase(args: argparse.Namespace, count: int, phase: str, start_index: int,
                  first_side: str, buy_limit: int, sell_limit: int,
                  paper_epoch: int) -> tuple[list[dict], int]:
    reset = send_command(args.trader_host, args.trader_port, "MEASUREMENT_RESET")
    generation = int(reset["measurement_generation"])
    if int(reset["paper_epoch"]) != paper_epoch:
        raise SystemExit("paper epoch changed before measurement phase")
    order_ids: list[int] = []
    start_ns = time.monotonic_ns() + 100_000_000
    for offset in range(count):
        index = start_index + offset
        deadline = start_ns + offset * args.interval_us * 1_000
        remaining = deadline - time.monotonic_ns()
        if remaining > 0:
            time.sleep(remaining / 1_000_000_000)
        side = first_side if index % 2 == 0 else ("BUY" if first_side == "SELL" else "SELL")
        limit_price = buy_limit if side == "BUY" else sell_limit
        response = send_command(
            args.trader_host, args.trader_port,
            f"MEASUREMENT_ORDER|AAPL|{side}|1|{limit_price}",
        )
        order_ids.append(int(response["client_order_id"]))

    deadline = time.monotonic() + 30
    captured: dict[int, dict] = {}
    receipt: dict = {}
    while time.monotonic() < deadline:
        receipt = send_command(args.trader_host, args.trader_port, "MEASUREMENT_SAMPLES")
        captured = {int(item["client_order_id"]): item for item in receipt["samples"]}
        if all(order_id in captured for order_id in order_ids):
            break
        time.sleep(0.05)
    missing = [order_id for order_id in order_ids if order_id not in captured]
    if missing:
        raise SystemExit(f"missing {len(missing)} C++ RTT samples in {phase}")
    if int(receipt["paper_epoch"]) != paper_epoch or int(receipt["measurement_generation"]) != generation:
        raise SystemExit("measurement identity changed during phase")
    rows = [
        {
            "client_order_id": order_id,
            "phase": phase,
            "index": start_index + offset,
            "order_rtt_ns": int(captured[order_id]["order_rtt_ns"]),
            "result": str(captured[order_id]["result"]),
        }
        for offset, order_id in enumerate(order_ids)
    ]
    return rows, generation


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://10.1.1.101:8088")
    parser.add_argument("--trader-host", default="10.1.1.2")
    parser.add_argument("--trader-port", type=int, default=48122)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--samples", type=int, default=200)
    parser.add_argument("--interval-us", type=int, default=20_000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.warmup < 1 or args.samples < 2 or args.interval_us < 1_000:
        raise SystemExit("warmup>=1, samples>=2 and interval-us>=1000 are required")

    before_state = http_json(args.base_url.rstrip("/") + "/api/state")
    if before_state["replay"]["status"] != "PLAYING":
        raise SystemExit("market replay must stay PLAYING")
    if any(before_state["health"][name]["status"] != "ONLINE" for name in ("exchange", "trader_auto", "trader_manual", "gateway")):
        raise SystemExit("all four application components must be ONLINE")
    book = before_state["trader_books"]["AAPL"]
    ask = int(book["asks"][0][0])
    bid = int(book["bids"][0][0])
    buy_limit = ask + 1_000_000
    sell_limit = max(1, bid - 1_000_000)
    initial_position = int(before_state["client_positions"]["trader_manual"]["AAPL"])
    first_side = "SELL" if initial_position > 0 else "BUY"
    epoch = int(send_command(args.trader_host, args.trader_port, "STATE")["paper_epoch"])
    warmup_rows, _ = capture_phase(
        args, args.warmup, "warmup", 0, first_side, buy_limit, sell_limit, epoch
    )
    measured_rows, generation = capture_phase(
        args, args.samples, "measured", args.warmup, first_side,
        buy_limit, sell_limit, epoch
    )
    rows = warmup_rows + measured_rows
    if any(row["result"] != "E" for row in rows):
        raise SystemExit("the fixed profile requires every sampled IOC to execute")

    after_state = http_json(args.base_url.rstrip("/") + "/api/state")
    if int(after_state["replay"]["loop"]) != int(before_state["replay"]["loop"]):
        raise SystemExit("replay loop changed during measurement")
    if after_state["strategy"]["enabled"] != before_state["strategy"]["enabled"]:
        raise SystemExit("AUTO strategy state changed during measurement")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    measured = [row["order_rtt_ns"] for row in rows if row["phase"] == "measured"]
    summary = {
        "profile": "HOST_NATIVE_ORDER_RTT_50HZ_V1",
        "measurement": "OUCH_SEND_TO_FINAL_RESPONSE",
        "clock": "CLOCK_MONOTONIC",
        "paper_epoch": epoch,
        "measurement_generation": generation,
        "replay_loop": int(after_state["replay"]["loop"]),
        "warmup": args.warmup,
        "samples": args.samples,
        "interval_us": args.interval_us,
        "p50_ns": nearest_rank(measured, 0.50),
        "p99_ns": nearest_rank(measured, 0.99),
        "max_ns": max(measured),
        "source_advance_ns": int(after_state["replay"]["source_timestamp_ns"])
        - int(before_state["replay"]["source_timestamp_ns"]),
        "auto_strategy_unchanged": True,
    }
    measured_state = send_command(args.trader_host, args.trader_port, "STATE")["measurement_latency"]
    for key in ("samples", "p50_ns", "p99_ns", "max_ns", "generation"):
        summary_key = "measurement_generation" if key == "generation" else key
        if int(measured_state[key]) != int(summary[summary_key]):
            raise SystemExit(f"C++ measurement summary mismatch: {key}")
    summary_path = args.output.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f'profile={summary["profile"]} warmup={args.warmup} measured={args.samples} interval_us={args.interval_us}')
    print(f'measurement={summary["measurement"]} clock={summary["clock"]}')
    print(f'paper_epoch={epoch} measurement_generation={generation} replay_loop={summary["replay_loop"]} replay_status=PLAYING')
    print(f'p50_ns={summary["p50_ns"]} p99_ns={summary["p99_ns"]} max_ns={summary["max_ns"]}')
    print(f'source_advance_ns={summary["source_advance_ns"]} auto_strategy_unchanged=true')
    print(f'raw_csv={args.output} summary_json={summary_path}')


if __name__ == "__main__":
    main()
