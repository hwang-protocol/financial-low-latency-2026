#!/usr/bin/env python3
"""Compare MANUAL C++ profiles while an independent AUTO process tracks the environment."""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from flle_trading.gateway import send_command  # noqa: E402


MODES = ("DEQUE_CV", "FIXED_CV", "SPSC_SPIN")
PLACEMENTS = ("floating", "dedicated", "shared", "rx")


def http_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=3) as response:
        return json.load(response)


def nearest_rank(values: list[int], percentile: float) -> int:
    ordered = sorted(values)
    return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]


def percentile_interval(values: list[int]) -> dict[str, int]:
    return {
        "low_ns": nearest_rank(values, 0.025),
        "high_ns": nearest_rank(values, 0.975),
    }


def bootstrap_p99(values: list[int], resamples: int, rng: random.Random) -> dict:
    estimates = []
    size = len(values)
    for _ in range(resamples):
        estimates.append(nearest_rank(
            [values[rng.randrange(size)] for _ in range(size)], 0.99
        ))
    return {
        "p99_ns": nearest_rank(values, 0.99),
        "ci95": percentile_interval(estimates),
    }


def bootstrap_p50(values: list[int], resamples: int, rng: random.Random) -> dict:
    estimates = []
    size = len(values)
    for _ in range(resamples):
        estimates.append(nearest_rank(
            [values[rng.randrange(size)] for _ in range(size)], 0.50
        ))
    return {
        "p50_ns": nearest_rank(values, 0.50),
        "ci95": percentile_interval(estimates),
    }


def bootstrap_p99_difference(left: list[int], right: list[int], resamples: int,
                             rng: random.Random) -> dict:
    estimates = []
    left_size = len(left)
    right_size = len(right)
    for _ in range(resamples):
        left_p99 = nearest_rank(
            [left[rng.randrange(left_size)] for _ in range(left_size)], 0.99
        )
        right_p99 = nearest_rank(
            [right[rng.randrange(right_size)] for _ in range(right_size)], 0.99
        )
        estimates.append(left_p99 - right_p99)
    return {
        "difference_ns": nearest_rank(left, 0.99) - nearest_rank(right, 0.99),
        "ci95": percentile_interval(estimates),
    }


def bootstrap_p50_difference(left: list[int], right: list[int], resamples: int,
                             rng: random.Random) -> dict:
    estimates = []
    left_size = len(left)
    right_size = len(right)
    for _ in range(resamples):
        left_p50 = nearest_rank(
            [left[rng.randrange(left_size)] for _ in range(left_size)], 0.50
        )
        right_p50 = nearest_rank(
            [right[rng.randrange(right_size)] for _ in range(right_size)], 0.50
        )
        estimates.append(left_p50 - right_p50)
    return {
        "difference_ns": nearest_rank(left, 0.50) - nearest_rank(right, 0.50),
        "ci95": percentile_interval(estimates),
    }


def parse_profiles(value: str) -> list[tuple[str, str]]:
    profiles: list[tuple[str, str]] = []
    for raw in value.split(","):
        parts = raw.strip().split(":")
        if len(parts) != 2 or parts[0] not in MODES or parts[1] not in PLACEMENTS:
            raise argparse.ArgumentTypeError(
                "profiles must use MODE:placement, for example DEQUE_CV:floating"
            )
        profiles.append((parts[0], parts[1]))
    if not 1 <= len(profiles) <= 2:
        raise argparse.ArgumentTypeError("one or two profiles are required")
    return profiles


def set_affinity(host: str, port: int, placement: str,
                 dedicated_cpu: int | None = None,
                 shared_cpu: int | None = None) -> tuple[str, int]:
    state = send_command(host, port, "STATE")
    software = state["software_latency"]
    tid = int(software["order_thread_tid"])
    if tid < 2:
        raise SystemExit("order thread TID is unavailable")
    if placement == "floating":
        cpus = subprocess.check_output(
            ["ssh", f"root@{host}", "cat", "/sys/devices/system/cpu/online"],
            text=True,
        ).strip()
    elif placement == "dedicated":
        if dedicated_cpu is None or dedicated_cpu < 0:
            raise SystemExit("dedicated placement requires an explicit CPU")
        cpus = str(dedicated_cpu)
    elif placement == "shared":
        if shared_cpu is None or shared_cpu < 0:
            raise SystemExit("shared placement requires an explicit CPU")
        cpus = str(shared_cpu)
    else:
        cpu = int(software["order_rx_cpu"])
        if cpu < 0:
            raise SystemExit("a floating round must establish order_rx_cpu before rx pinning")
        cpus = str(cpu)
    if not cpus or any(character not in "0123456789,-" for character in cpus):
        raise SystemExit("invalid CPU list")
    script = (
        f"set -eu\n"
        f"test \"$(cat /proc/{tid}/comm)\" = flle-order\n"
        f"taskset -pc '{cpus}' '{tid}'\n"
    )
    subprocess.run(
        ["ssh", f"root@{host}", "bash", "-s"], input=script, text=True,
        check=True, stdout=subprocess.DEVNULL,
    )
    return cpus, tid


def constrain_peer_threads(host: str, order_tid: int,
                           housekeeping_cpus: str) -> tuple[int, int]:
    if (not housekeeping_cpus or
            any(character not in "0123456789,-" for character in housekeeping_cpus)):
        raise SystemExit("invalid housekeeping CPU list")
    script = f"""set -eu
tgid=$(awk '$1 == "Tgid:" {{print $2}}' /proc/{order_tid}/status)
count=0
for task in /proc/$tgid/task/*; do
  tid=${{task##*/}}
  [ "$tid" = "{order_tid}" ] && continue
  case "$(cat "$task/comm")" in flle-*) ;; *) exit 71 ;; esac
  taskset -pc '{housekeeping_cpus}' "$tid" >/dev/null
  count=$((count + 1))
done
printf '%s %s\n' "$tgid" "$count"
"""
    output = subprocess.check_output(
        ["ssh", f"root@{host}", "bash", "-s"], input=script, text=True,
    ).strip().split()
    if len(output) != 2 or int(output[1]) < 1:
        raise SystemExit("failed to constrain peer threads")
    return int(output[0]), int(output[1])


def collect_receipt(args: argparse.Namespace, port: int, order_ids: list[int],
                    paper_epoch: int, generation: int, round_index: int,
                    phase: str, profile: str, client: str) -> list[dict]:
    deadline = time.monotonic() + 30
    captured: dict[int, dict] = {}
    receipt: dict = {}
    while time.monotonic() < deadline:
        receipt = send_command(args.trader_host, port, "MEASUREMENT_SAMPLES")
        captured = {int(item["client_order_id"]): item for item in receipt["samples"]}
        if all(order_id in captured for order_id in order_ids):
            break
        time.sleep(0.05)
    missing = [order_id for order_id in order_ids if order_id not in captured]
    if missing:
        raise SystemExit(
            f"missing {len(missing)} {client} C++ samples in round {round_index} {phase}"
        )
    if (int(receipt["paper_epoch"]) != paper_epoch or
            int(receipt["measurement_generation"]) != generation):
        raise SystemExit(f"{client} measurement identity changed")
    return [
        {
            "round": round_index,
            "profile": profile,
            "client": client,
            "client_order_id": order_id,
            "phase": phase,
            "index": offset,
            "queue_to_send_ns": int(captured[order_id]["queue_to_send_ns"]),
            "order_rtt_ns": int(captured[order_id]["order_rtt_ns"]),
            "submit_to_final_ns": int(captured[order_id]["submit_to_final_ns"]),
            "result": str(captured[order_id]["result"]),
        }
        for offset, order_id in enumerate(order_ids)
    ]


def capture_paired_phase(args: argparse.Namespace, count: int, phase: str,
                         buy_limit: int, sell_limit: int, paper_epoch: int,
                         round_index: int, profile: str) -> tuple[list[dict], list[dict]]:
    # Re-evaluate the safe first leg before every phase.  Each even-sized phase
    # remains position-neutral, while a concurrently running AUTO strategy may
    # move its account between phases during a long repeated experiment.
    live = http_json(args.base_url.rstrip("/") + "/api/state")
    manual_position = int(live["client_positions"]["trader_manual"]["AAPL"])
    control_position = int(live["client_positions"]["trader_auto"]["AAPL"])
    manual_first_side = "SELL" if manual_position > 0 else "BUY"
    control_first_side = "SELL" if control_position > 0 else "BUY"
    manual_reset = send_command(
        args.trader_host, args.trader_port, "MEASUREMENT_RESET"
    )
    control_reset = send_command(
        args.trader_host, args.control_port, "MEASUREMENT_RESET"
    )
    manual_generation = int(manual_reset["measurement_generation"])
    control_generation = int(control_reset["measurement_generation"])
    manual_order_ids: list[int] = []
    control_order_ids: list[int] = []
    control_index = 0
    start_ns = time.monotonic_ns() + 100_000_000
    for offset in range(count):
        remaining = start_ns + offset * args.interval_us * 1_000 - time.monotonic_ns()
        if remaining > 0:
            time.sleep(remaining / 1_000_000_000)
        manual_side = manual_first_side if offset % 2 == 0 else (
            "BUY" if manual_first_side == "SELL" else "SELL"
        )
        requests = [(args.trader_port, manual_side, manual_order_ids)]
        if offset % args.control_every == 0:
            control_side = control_first_side if control_index % 2 == 0 else (
                "BUY" if control_first_side == "SELL" else "SELL"
            )
            requests.append((args.control_port, control_side, control_order_ids))
            control_index += 1
        if len(requests) == 2 and control_index % 2 == 0:
            requests.reverse()
        for port, side, destination in requests:
            price = buy_limit if side == "BUY" else sell_limit
            response = send_command(
                args.trader_host, port,
                f"MEASUREMENT_ORDER|AAPL|{side}|1|{price}",
            )
            destination.append(int(response["client_order_id"]))
    manual = collect_receipt(
        args, args.trader_port, manual_order_ids, paper_epoch,
        manual_generation, round_index, phase, profile, "MANUAL",
    )
    control = collect_receipt(
        args, args.control_port, control_order_ids, paper_epoch,
        control_generation, round_index, phase, profile, "AUTO_CONTROL",
    )
    return manual, control


def stats(rows: list[dict], field: str) -> dict[str, int]:
    values = [int(row[field]) for row in rows if row["phase"] == "measured"]
    ordered = sorted(values)
    return {
        "p50_ns": ordered[(len(ordered) - 1) // 2],
        "p99_ns": ordered[(len(ordered) - 1) * 99 // 100],
        "max_ns": ordered[-1],
    }


def control_half_drift(rows: list[dict]) -> dict:
    measured = [int(row["order_rtt_ns"]) for row in rows if row["phase"] == "measured"]
    half = len(measured) // 2
    first = nearest_rank(measured[:half], 0.50)
    second = nearest_rank(measured[half:], 0.50)
    drift = abs(second - first) * 100.0 / max(1, first)
    return {"first_p50_ns": first, "second_p50_ns": second,
            "drift_pct": round(drift, 2)}


def counterbalanced_plan(profiles: list[tuple[str, str]], repeat: int) -> list[tuple[str, str]]:
    if len(profiles) == 1:
        return profiles * repeat
    if repeat % 2:
        raise SystemExit("two-profile comparisons require an even repeat count")
    left, right = profiles
    plan: list[tuple[str, str]] = []
    for block in range(repeat // 2):
        plan.extend(
            (left, right, right, left) if block % 2 == 0
            else (right, left, left, right)
        )
    return plan


def directional_environment_gate(queue_effect: dict, control_check: dict,
                                 base_margin_ns: int) -> dict:
    """Keep detected headwind, but cap detected tailwind at half the queue effect."""
    queue_verdict = queue_effect["verdict"]
    queue_difference = int(queue_effect["difference_ns"])
    control_difference = int(control_check["difference_ns"])
    control_low = int(control_check["ci95"]["low_ns"])
    control_high = int(control_check["ci95"]["high_ns"])
    inside_base_margin = (
        control_low >= -base_margin_ns and control_high <= base_margin_ns
    )
    control_detected = control_low > 0 or control_high < 0
    tailwind_limit_ns = max(0, abs(queue_difference) // 2)
    if queue_verdict == "RIGHT_LOWER":
        detected_tailwind = control_low > 0
        detected_headwind = control_high < 0
    elif queue_verdict == "LEFT_LOWER":
        detected_tailwind = control_high < 0
        detected_headwind = control_low > 0
    else:
        detected_tailwind = False
        detected_headwind = False

    if not inside_base_margin:
        verdict = "OUTSIDE_BASE_EQUIVALENCE_MARGIN"
        comparable = False
    elif not control_detected:
        verdict = "NO_DETECTED_DIFFERENCE_WITHIN_MARGIN"
        comparable = True
    elif detected_headwind:
        verdict = "DETECTED_HEADWIND_WITHIN_MARGIN"
        comparable = True
    elif detected_tailwind:
        tailwind_magnitude = abs(control_difference)
        comparable = (
            queue_verdict != "NO_DETECTED_DIFFERENCE" and
            tailwind_magnitude <= tailwind_limit_ns
        )
        verdict = (
            "DETECTED_TAILWIND_WITHIN_LIMIT" if comparable
            else "DETECTED_TAILWIND_EXCEEDS_LIMIT"
        )
    else:
        verdict = "DETECTED_DIFFERENCE_WITHOUT_QUEUE_DIRECTION"
        comparable = False
    return {
        "base_equivalence_margin_ns": base_margin_ns,
        "tailwind_limit_ns": tailwind_limit_ns,
        "direction": (
            "tailwind" if detected_tailwind else
            "headwind" if detected_headwind else
            "not_detected" if not control_detected else "undetermined"
        ),
        "verdict": verdict,
        "comparable": comparable,
    }


def paired_direction_gate(round_receipts: list[dict], left: str, right: str,
                          queue_verdict: str, required_pct: float) -> dict:
    """Require a detected pooled effect to recur in adjacent counterbalanced pairs."""
    if len(round_receipts) % 2:
        raise SystemExit("counterbalanced rounds must form adjacent pairs")
    pair_differences: list[int] = []
    for offset in range(0, len(round_receipts), 2):
        pair = round_receipts[offset:offset + 2]
        by_profile = {item["profile"]: item for item in pair}
        if set(by_profile) != {left, right}:
            raise SystemExit("each adjacent counterbalanced pair must contain both profiles")
        pair_differences.append(
            int(by_profile[left]["queue_to_send"]["p99_ns"]) -
            int(by_profile[right]["queue_to_send"]["p99_ns"])
        )
    if queue_verdict == "RIGHT_LOWER":
        supporting = sum(value > 0 for value in pair_differences)
    elif queue_verdict == "LEFT_LOWER":
        supporting = sum(value < 0 for value in pair_differences)
    else:
        return {
            "applicable": False, "supporting_pairs": 0,
            "total_pairs": len(pair_differences), "required_pairs": 0,
            "required_pct": required_pct, "pass": True,
            "pair_differences_ns": pair_differences,
            "verdict": "NOT_APPLICABLE_NO_DETECTED_EFFECT",
        }
    required_pairs = math.ceil(len(pair_differences) * required_pct / 100.0)
    passed = supporting >= required_pairs
    return {
        "applicable": True, "supporting_pairs": supporting,
        "total_pairs": len(pair_differences), "required_pairs": required_pairs,
        "required_pct": required_pct, "pass": passed,
        "pair_differences_ns": pair_differences,
        "verdict": "CONSISTENT" if passed else "INCONSISTENT",
    }


def format_ns(value: int) -> str:
    """把纳秒写成课堂可读的一行。"""
    return f"{value} ns（{value / 1000:.1f} µs）"


def profile_zh(name: str) -> str:
    """把配置名收成课堂已经听过的说法。"""
    mode, _, placement = name.partition("/")
    mode_zh = {
        "DEQUE_CV": "原来的格子",
        "FIXED_CV": "固定格子",
        "SPSC_SPIN": "盯着看",
    }.get(mode, mode)
    placement_zh = {
        "dedicated": "独占座位",
        "shared": "挤在杂活核",
        "floating": "座位还没锁",
        "rx": "跟着收包核",
    }.get(placement, placement)
    return f"{mode_zh}（{placement_zh}）"


def verdict_zh(code: str) -> str:
    """把机器判决收成一句人话。"""
    mapping = {
        "VALID_COMPARISON": "能用",
        "REJECTED_WITHIN_ROUND_DRIFT": "不能用：AUTO 这一轮自己跳得太多",
        "REJECTED_ENVIRONMENT_CONTROL_DIFFERENCE": "不能用：两边现场对不上",
        "REJECTED_INCONSISTENT_PAIR_DIRECTION": "不能用：快慢方向对不齐",
        "REJECTED_SINGLE_PROFILE_SPREAD": "不能用：同一套自己跳得太多",
        "REJECTED_RX_TARGET_DRIFT": "不能用：收包座位漂了",
        "REJECTED_MULTIPLE_GATES": "不能用：好几道门没过",
        "NO_DETECTED_DIFFERENCE": "说不出谁更快",
        "NO_DETECTED_DIFFERENCE_WITHIN_MARGIN": "两边现场差不多，还能比",
        "RIGHT_LOWER": "后面那套更快",
        "LEFT_LOWER": "前面那套更快",
        "DETECTED_TAILWIND_WITHIN_LIMIT": "AUTO 有点顺风，但还在门内",
        "DETECTED_HEADWIND_WITHIN_MARGIN": "AUTO 有点逆风，但还在门内",
        "OUTSIDE_BASE_EQUIVALENCE_MARGIN": "两边现场差太多，不能比",
        "DETECTED_TAILWIND_EXCEEDS_LIMIT": "AUTO 顺风太大，这一轮不能比",
        "DETECTED_DIFFERENCE_WITHOUT_QUEUE_DIRECTION": "AUTO 两边对不上",
        "CONSISTENT": "相邻几对都是同一边更快",
        "INCONSISTENT": "相邻几对方向对不齐",
        "NOT_APPLICABLE_NO_DETECTED_EFFECT": "没比出快慢，不看方向",
    }
    return mapping.get(code, code)


def print_effect(title: str, effect: dict) -> None:
    """把两套对比收成谁更快、可信范围是不是两头同一边。"""
    left = profile_zh(effect["left"])
    right = profile_zh(effect["right"])
    diff = int(effect["difference_ns"])
    low = int(effect["ci95"]["low_ns"])
    high = int(effect["ci95"]["high_ns"])
    verdict = effect["verdict"]
    print(title)
    print(f"  {left} 对比 {right}")
    if verdict == "NO_DETECTED_DIFFERENCE":
        print(f"  差了 {format_ns(abs(diff))}，可信范围 {low} .. {high} ns")
        print("  一头小于 0、一头大于 0，0 也在里面")
        print("  所以：说不出谁更快")
    elif verdict == "RIGHT_LOWER":
        print(f"  {right} 更快 {format_ns(diff)}")
        print(f"  可信范围 {low} .. {high} ns，两头都是 {right} 更快")
        print(f"  所以：{right} 更快")
    else:
        print(f"  {left} 更快 {format_ns(abs(diff))}")
        print(f"  可信范围 {low} .. {high} ns，两头都是 {left} 更快")
        print(f"  所以：{left} 更快")
    print("")


def print_classroom_summary(summary: dict, _last: dict, *,
                            pair_gate: str, spread_gate: str,
                            rx_gate: str) -> None:
    """把本轮结论按人话打到终端。"""
    total_rounds = int(summary["round_count"])
    stable_rounds = int(summary["stable_rounds"])
    drops = summary.get("queue_full_drops") or {}
    print("~~~~~~~~~~~~~~~~~~~~~测量摘要~~~~~~~~~~~~~~~~~~~~~")
    print(f"这一轮能不能用：{verdict_zh(summary['comparison_verdict'])}")
    print(f"AUTO 有没有自己乱跳：{stable_rounds}/{total_rounds} 轮都稳")
    if spread_gate != "n/a":
        item = summary["profiles"][0]
        print(
            f"{total_rounds} 轮交棒最快 {format_ns(int(item['round_queue_p99_min_ns']))}，"
            f"最慢 {format_ns(int(item['round_queue_p99_max_ns']))}；"
            f"最慢是最快的 {spread_gate} 倍"
            f"（门限 {summary['single_profile_spread_limit']:.2f}）"
        )
    if int(drops.get("manual", 0)) == 0 and int(drops.get("auto_control", 0)) == 0:
        print("格子有没有装满丢掉：没有")
    else:
        print(
            f"格子有没有装满丢掉：MANUAL {drops.get('manual')} / "
            f"AUTO {drops.get('auto_control')}"
        )
    print(
        f"先热身 {summary['precondition_samples']} 笔，"
        f"每轮预热 {summary['warmup_per_round']}、"
        f"计入 {summary['samples_per_round']}，"
        f"共 {total_rounds} 轮"
    )
    print("")
    for item in summary["profiles"]:
        print(profile_zh(item["profile"]))
        print("  同一把尺子，都是 p99")
        print(f"  MANUAL 计入 {item['pooled_manual_samples']} 笔")
        print(f"    交棒：{format_ns(int(item['queue_to_send_p99']['p99_ns']))}")
        print(f"    发出去到回执：{format_ns(int(item['manual_order_rtt_p99']['p99_ns']))}")
        print(f"    整段：{format_ns(int(item['submit_to_final_p99']['p99_ns']))}")
        print(f"  AUTO 计入 {item['pooled_auto_control_samples']} 笔")
        print(f"    交棒：{format_ns(int(item['auto_queue_to_send_p99']['p99_ns']))}")
        print(f"    发出去到回执：{format_ns(int(item['auto_order_rtt_p99']['p99_ns']))}")
        print(f"    整段：{format_ns(int(item['auto_submit_to_final_p99']['p99_ns']))}")
        print(
            f"    往返中位：{format_ns(int(item['environment_control_rtt_p50']['p50_ns']))}"
            "（只看稳不稳）"
        )
        print("")
    queue_effect = summary.get("queue_effect")
    if queue_effect:
        print_effect("交棒谁更快", queue_effect)
    total_effect = summary.get("total_effect")
    if total_effect:
        print_effect("整段谁更快", total_effect)
    environment = summary.get("environment_control_check")
    if environment:
        low = int(environment["ci95"]["low_ns"])
        high = int(environment["ci95"]["high_ns"])
        print("AUTO 两边现场差多少")
        print(f"  差了 {format_ns(abs(int(environment['difference_ns'])))}")
        print(f"  可信范围 {low} .. {high} ns")
        print(f"  所以：{verdict_zh(environment['verdict'])}")
        print("")
    if pair_gate != "n/a":
        print(f"相邻快慢方向：{pair_gate} 对都是同一边更快")
    if rx_gate != "n/a":
        print(f"收包座位有没有漂：{rx_gate}")
    print(f"MANUAL 独占座位时坐 CPU {summary['treatment_cpu']}")
    if any(item["profile"].endswith("/shared") for item in summary["profiles"]):
        print(f"MANUAL 挤杂活核时坐 CPU {summary['shared_cpu']}")
    print(f"AUTO 一直坐 CPU {summary['control_cpu']}")
    print("行情还在播，AUTO 策略没关")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profiles", type=parse_profiles, required=True)
    parser.add_argument("--repeat", type=int, default=4)
    parser.add_argument("--base-url", default="http://10.1.1.101:8088")
    parser.add_argument("--trader-host", default="10.1.1.2")
    parser.add_argument("--trader-port", type=int, default=48122)
    parser.add_argument("--control-port", type=int, default=48121)
    parser.add_argument("--treatment-cpu", type=int, default=2)
    parser.add_argument("--control-cpu", type=int, default=3)
    parser.add_argument("--shared-cpu", type=int, default=1)
    parser.add_argument("--housekeeping-cpus", default="0-1")
    parser.add_argument("--precondition-samples", type=int, default=1_000)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--samples", type=int, default=200)
    parser.add_argument("--interval-us", type=int, default=20_000)
    parser.add_argument("--control-every", type=int, default=5)
    parser.add_argument("--stability-limit-pct", type=float, default=40.0)
    parser.add_argument("--environment-equivalence-pct", type=float, default=40.0)
    parser.add_argument("--direction-consistency-pct", type=float, default=87.5)
    parser.add_argument("--single-profile-spread-limit", type=float, default=1.5)
    parser.add_argument("--bootstrap-resamples", type=int, default=4_000)
    parser.add_argument("--bootstrap-seed", type=int, default=20_260_828)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if (args.repeat < 2 or args.precondition_samples < 100 or
            args.warmup < 1 or args.samples < 100 or
            args.samples % 2 or args.interval_us < 1_000 or
            args.control_every < 1 or args.control_every > args.warmup or
            not 0 < args.stability_limit_pct <= 100 or
            not 0 < args.environment_equivalence_pct <= 100 or
            not 50 < args.direction_consistency_pct <= 100 or
            args.treatment_cpu < 0 or args.control_cpu < 0 or
            args.shared_cpu < 0 or
            len({args.treatment_cpu, args.control_cpu, args.shared_cpu}) != 3 or
            args.single_profile_spread_limit < 1.0 or
            args.bootstrap_resamples < 1_000):
        raise SystemExit("repeat>=2, precondition>=100, warmup>=1, even samples>=100, interval-us>=1000, control-every within warmup, stability/equivalence limits 0..100, direction consistency 50..100 and bootstrap>=1000 are required")

    before = http_json(args.base_url.rstrip("/") + "/api/state")
    if before["replay"]["status"] != "PLAYING":
        raise SystemExit("market replay must stay PLAYING")
    if any(before["health"][name]["status"] != "ONLINE"
           for name in ("exchange", "trader_auto", "trader_manual", "gateway")):
        raise SystemExit("all four application components must be ONLINE")
    book = before["trader_books"]["AAPL"]
    buy_limit = int(book["asks"][0][0]) + 1_000_000
    sell_limit = max(1, int(book["bids"][0][0]) - 1_000_000)
    all_rows: list[dict] = []
    round_receipts: list[dict] = []
    expected_epoch: int | None = None
    plan = counterbalanced_plan(args.profiles, args.repeat)

    precondition_mode, precondition_placement = plan[0]
    changed = send_command(
        args.trader_host, args.trader_port,
        f"SOFTWARE_PROFILE|{precondition_mode}",
    )
    if changed.get("order_queue") != precondition_mode:
        raise SystemExit("precondition software profile did not change")
    _, precondition_treatment_tid = set_affinity(
        args.trader_host, args.trader_port, precondition_placement,
        args.treatment_cpu, args.shared_cpu,
    )
    _, precondition_control_tid = set_affinity(
        args.trader_host, args.control_port, "dedicated", args.control_cpu
    )
    manual_tgid, manual_peer_threads = constrain_peer_threads(
        args.trader_host, precondition_treatment_tid, args.housekeeping_cpus
    )
    control_tgid, control_peer_threads = constrain_peer_threads(
        args.trader_host, precondition_control_tid, args.housekeeping_cpus
    )
    precondition_direct = send_command(args.trader_host, args.trader_port, "STATE")
    precondition_control = send_command(args.trader_host, args.control_port, "STATE")
    precondition_epoch = int(precondition_direct["paper_epoch"])
    if (precondition_direct.get("role") != "MANUAL" or
            precondition_control.get("role") != "AUTO" or
            int(precondition_control["paper_epoch"]) != precondition_epoch):
        raise SystemExit("precondition treatment/control identity changed")
    precondition_manual, precondition_auto = capture_paired_phase(
        args, args.precondition_samples, "precondition", buy_limit, sell_limit,
        precondition_epoch, 0,
        f"{precondition_mode}/{precondition_placement}",
    )
    if any(row["result"] != "E"
           for row in precondition_manual + precondition_auto):
        raise SystemExit("every precondition IOC must execute")
    all_rows.extend(precondition_manual + precondition_auto)

    for round_index, (mode, requested_placement) in enumerate(plan, 1):
        profile = f"{mode}/{requested_placement}"
        changed = send_command(args.trader_host, args.trader_port, f"SOFTWARE_PROFILE|{mode}")
        if changed.get("order_queue") != mode:
            raise SystemExit(f"software profile did not change in round {round_index}")
        cpu_list, tid = set_affinity(
            args.trader_host, args.trader_port, requested_placement,
            args.treatment_cpu, args.shared_cpu,
        )
        control_cpu_list, control_tid = set_affinity(
            args.trader_host, args.control_port, "dedicated", args.control_cpu
        )
        direct = send_command(args.trader_host, args.trader_port, "STATE")
        control_direct = send_command(args.trader_host, args.control_port, "STATE")
        software = direct["software_latency"]
        epoch = int(direct["paper_epoch"])
        if expected_epoch is None:
            expected_epoch = epoch
        if (epoch != expected_epoch or int(control_direct["paper_epoch"]) != epoch or
                software["queue_mode"] != mode or
                control_direct["software_latency"]["queue_mode"] != "DEQUE_CV"):
            raise SystemExit("paper epoch or treatment/control queue mode changed")
        if direct.get("role") != "MANUAL" or control_direct.get("role") != "AUTO":
            raise SystemExit("treatment/control role identity changed")
        warmup_manual, warmup_control = capture_paired_phase(
            args, args.warmup, "warmup", buy_limit, sell_limit, epoch,
            round_index, profile,
        )
        measured_manual, measured_control = capture_paired_phase(
            args, args.samples, "measured", buy_limit, sell_limit, epoch,
            round_index, profile,
        )
        manual_rows = warmup_manual + measured_manual
        control_rows = warmup_control + measured_control
        rows = manual_rows + control_rows
        if any(row["result"] != "E" for row in rows):
            raise SystemExit(f"every IOC must execute in round {round_index}")
        direct_after = send_command(args.trader_host, args.trader_port, "STATE")
        control_after = send_command(args.trader_host, args.control_port, "STATE")
        software_after = direct_after["software_latency"]
        control_software_after = control_after["software_latency"]
        queue = stats(manual_rows, "queue_to_send_ns")
        manual_order = stats(manual_rows, "order_rtt_ns")
        total = stats(manual_rows, "submit_to_final_ns")
        environment_control = stats(control_rows, "order_rtt_ns")
        for source, expected in (
            (software_after["queue_to_send"], queue),
            (direct_after["measurement_latency"], manual_order),
            (software_after["submit_to_final"], total),
            (control_after["measurement_latency"], environment_control),
        ):
            if any(int(source[key]) != expected[key] for key in expected):
                raise SystemExit(f"C++ and raw percentile mismatch in round {round_index}")
        affinity_state = (
            "pinned" if int(software_after["order_thread_allowed_count"]) == 1
            else "floating"
        )
        expected_affinity = (
            "floating" if requested_placement == "floating" else "pinned"
        )
        if affinity_state != expected_affinity:
            raise SystemExit(f"affinity placement mismatch in round {round_index}")
        if (int(control_software_after["order_thread_allowed_count"]) != 1 or
                int(control_software_after["order_thread_cpu"]) !=
                args.control_cpu):
            raise SystemExit("AUTO environment control left its dedicated CPU")
        if (requested_placement == "dedicated" and
                int(software_after["order_thread_cpu"]) != args.treatment_cpu):
            raise SystemExit("MANUAL treatment left its dedicated CPU")
        if (requested_placement == "shared" and
                int(software_after["order_thread_cpu"]) != args.shared_cpu):
            raise SystemExit("MANUAL treatment left its shared CPU")
        if (requested_placement == "rx" and
                int(software_after["order_rx_cpu"]) == args.control_cpu):
            raise SystemExit("RX placement collided with the AUTO control CPU")
        drift = control_half_drift(control_rows)
        drift["pass"] = drift["drift_pct"] <= args.stability_limit_pct
        round_receipts.append({
            "round": round_index, "profile": profile, "mode": mode,
            "placement": requested_placement, "affinity_state": affinity_state,
            "cpu_list": cpu_list, "order_thread_tid": tid,
            "order_thread_cpu": int(software_after["order_thread_cpu"]),
            "order_rx_cpu": int(software_after["order_rx_cpu"]),
            "rx_target_aligned": (
                requested_placement != "rx" or
                int(cpu_list) == int(software_after["order_rx_cpu"])
            ),
            "control_cpu_list": control_cpu_list,
            "control_order_thread_tid": control_tid,
            "queue_to_send": queue, "manual_order_rtt": manual_order,
            "submit_to_final": total,
            "environment_control_rtt": environment_control,
            "environment_control_half_drift": drift,
        })
        all_rows.extend(rows)

    after = http_json(args.base_url.rstrip("/") + "/api/state")
    direct_after = send_command(args.trader_host, args.trader_port, "STATE")
    control_after = send_command(args.trader_host, args.control_port, "STATE")
    if int(after["replay"]["loop"]) != int(before["replay"]["loop"]):
        raise SystemExit("replay loop changed")
    if after["strategy"]["enabled"] != before["strategy"]["enabled"]:
        raise SystemExit("AUTO strategy changed")
    if (int(direct_after["software_latency"]["queue_full_drops"]) != 0 or
            int(control_after["software_latency"]["queue_full_drops"]) != 0):
        raise SystemExit("treatment or environment-control queue reported a full drop")

    rng = random.Random(args.bootstrap_seed)
    profile_summaries = []
    pooled_values: dict[str, dict[str, list[int]]] = {}
    for mode, requested_placement in args.profiles:
        profile = f"{mode}/{requested_placement}"
        selected = [item for item in round_receipts
                    if item["mode"] == mode and
                    item["placement"] == requested_placement]
        manual_measured = [
            row for row in all_rows
            if row["profile"] == profile and row["phase"] == "measured" and
            row["client"] == "MANUAL"
        ]
        control_measured = [
            row for row in all_rows
            if row["profile"] == profile and row["phase"] == "measured" and
            row["client"] == "AUTO_CONTROL"
        ]
        queue_values = [int(row["queue_to_send_ns"]) for row in manual_measured]
        manual_rtt_values = [int(row["order_rtt_ns"]) for row in manual_measured]
        total_values = [int(row["submit_to_final_ns"]) for row in manual_measured]
        environment_control_values = [
            int(row["order_rtt_ns"]) for row in control_measured
        ]
        auto_queue_values = [int(row["queue_to_send_ns"]) for row in control_measured]
        auto_total_values = [
            int(row["submit_to_final_ns"]) for row in control_measured
        ]
        pooled_values[profile] = {
            "queue_to_send": queue_values,
            "manual_order_rtt": manual_rtt_values,
            "submit_to_final": total_values,
            "environment_control_rtt": environment_control_values,
        }
        round_queue = [int(item["queue_to_send"]["p99_ns"]) for item in selected]
        profile_summaries.append({
            "profile": profile, "rounds": len(selected),
            "pooled_manual_samples": len(manual_measured),
            "pooled_auto_control_samples": len(control_measured),
            "queue_to_send_p99": bootstrap_p99(
                queue_values, args.bootstrap_resamples, rng
            ),
            "manual_order_rtt_p99": bootstrap_p99(
                manual_rtt_values, args.bootstrap_resamples, rng
            ),
            "auto_queue_to_send_p99": bootstrap_p99(
                auto_queue_values, args.bootstrap_resamples, rng
            ),
            "auto_order_rtt_p99": bootstrap_p99(
                environment_control_values, args.bootstrap_resamples, rng
            ),
            "auto_submit_to_final_p99": bootstrap_p99(
                auto_total_values, args.bootstrap_resamples, rng
            ),
            "environment_control_rtt_p50": bootstrap_p50(
                environment_control_values, args.bootstrap_resamples, rng
            ),
            "submit_to_final_p99": bootstrap_p99(
                total_values, args.bootstrap_resamples, rng
            ),
            "round_queue_p99_min_ns": min(round_queue),
            "round_queue_p99_max_ns": max(round_queue),
            "round_queue_p99_spread_ratio": round(
                max(round_queue) / max(1, min(round_queue)), 2
            ),
            "environment_control_half_drift_max_pct": max(
                item["environment_control_half_drift"]["drift_pct"]
                for item in selected
            ),
        })
    stable_rounds = sum(
        item["environment_control_half_drift"]["pass"] for item in round_receipts
    )
    within_round_stable = stable_rounds == len(round_receipts)
    queue_effect = None
    manual_rtt_effect = None
    total_effect = None
    environment_control_check = None
    environment_control_comparable = True
    direction_consistency = None
    direction_consistent = True
    single_profile_spread_ratio = profile_summaries[0][
        "round_queue_p99_spread_ratio"
    ]
    single_profile_stable = (
        len(profile_summaries) != 1 or
        single_profile_spread_ratio <= args.single_profile_spread_limit
    )
    rx_rounds = [item for item in round_receipts if item["placement"] == "rx"]
    rx_aligned_rounds = sum(item["rx_target_aligned"] for item in rx_rounds)
    rx_target_stable = rx_aligned_rounds == len(rx_rounds)
    if len(profile_summaries) == 2:
        left = profile_summaries[0]["profile"]
        right = profile_summaries[1]["profile"]
        queue_effect = bootstrap_p99_difference(
            pooled_values[left]["queue_to_send"],
            pooled_values[right]["queue_to_send"],
            args.bootstrap_resamples, rng,
        )
        queue_low = queue_effect["ci95"]["low_ns"]
        queue_high = queue_effect["ci95"]["high_ns"]
        queue_effect["left"] = left
        queue_effect["right"] = right
        queue_effect["ratio"] = round(
            profile_summaries[0]["queue_to_send_p99"]["p99_ns"] /
            max(1, profile_summaries[1]["queue_to_send_p99"]["p99_ns"]), 2
        )
        queue_effect["verdict"] = (
            "RIGHT_LOWER" if queue_low > 0 else
            "LEFT_LOWER" if queue_high < 0 else "NO_DETECTED_DIFFERENCE"
        )
        manual_rtt_effect = bootstrap_p99_difference(
            pooled_values[left]["manual_order_rtt"],
            pooled_values[right]["manual_order_rtt"],
            args.bootstrap_resamples, rng,
        )
        manual_rtt_effect["left"] = left
        manual_rtt_effect["right"] = right
        manual_low = manual_rtt_effect["ci95"]["low_ns"]
        manual_high = manual_rtt_effect["ci95"]["high_ns"]
        manual_rtt_effect["verdict"] = (
            "RIGHT_LOWER" if manual_low > 0 else
            "LEFT_LOWER" if manual_high < 0 else "NO_DETECTED_DIFFERENCE"
        )
        total_effect = bootstrap_p99_difference(
            pooled_values[left]["submit_to_final"],
            pooled_values[right]["submit_to_final"],
            args.bootstrap_resamples, rng,
        )
        total_effect["left"] = left
        total_effect["right"] = right
        total_low = total_effect["ci95"]["low_ns"]
        total_high = total_effect["ci95"]["high_ns"]
        total_effect["verdict"] = (
            "RIGHT_LOWER" if total_low > 0 else
            "LEFT_LOWER" if total_high < 0 else "NO_DETECTED_DIFFERENCE"
        )
        environment_control_check = bootstrap_p50_difference(
            pooled_values[left]["environment_control_rtt"],
            pooled_values[right]["environment_control_rtt"],
            args.bootstrap_resamples, rng,
        )
        environment_control_check["left"] = left
        environment_control_check["right"] = right
        control_low = environment_control_check["ci95"]["low_ns"]
        control_high = environment_control_check["ci95"]["high_ns"]
        equivalence_margin = round(min(
            profile_summaries[0]["environment_control_rtt_p50"]["p50_ns"],
            profile_summaries[1]["environment_control_rtt_p50"]["p50_ns"],
        ) * args.environment_equivalence_pct / 100.0)
        directional_gate = directional_environment_gate(
            queue_effect, environment_control_check, equivalence_margin
        )
        environment_control_check.update(directional_gate)
        environment_control_comparable = directional_gate["comparable"]
        direction_consistency = paired_direction_gate(
            round_receipts, left, right, queue_effect["verdict"],
            args.direction_consistency_pct,
        )
        direction_consistent = direction_consistency["pass"]
    failed_gates = sum((
        not within_round_stable,
        not environment_control_comparable,
        not direction_consistent,
        not single_profile_stable,
        not rx_target_stable,
    ))
    if failed_gates > 1:
        comparison_verdict = "REJECTED_MULTIPLE_GATES"
    elif not within_round_stable:
        comparison_verdict = "REJECTED_WITHIN_ROUND_DRIFT"
    elif not environment_control_comparable:
        comparison_verdict = "REJECTED_ENVIRONMENT_CONTROL_DIFFERENCE"
    elif not direction_consistent:
        comparison_verdict = "REJECTED_INCONSISTENT_PAIR_DIRECTION"
    elif not single_profile_stable:
        comparison_verdict = "REJECTED_SINGLE_PROFILE_SPREAD"
    elif not rx_target_stable:
        comparison_verdict = "REJECTED_RX_TARGET_DRIFT"
    else:
        comparison_verdict = "VALID_COMPARISON"
    summary = {
        "profile": "HOST_NATIVE_SOFTWARE_BUSY_SPIN_ISOLATED_AUTO_SENTINEL_V14",
        "profiles": profile_summaries, "repeat_per_profile": args.repeat,
        "round_plan": [f"{mode}/{placement}" for mode, placement in plan],
        "round_count": len(round_receipts), "warmup_per_round": args.warmup,
        "precondition_samples": args.precondition_samples,
        "samples_per_round": args.samples, "interval_us": args.interval_us,
        "control_every": args.control_every,
        "treatment_cpu": args.treatment_cpu,
        "control_cpu": args.control_cpu,
        "shared_cpu": args.shared_cpu,
        "housekeeping_cpus": args.housekeeping_cpus,
        "manual_tgid": manual_tgid,
        "manual_peer_threads": manual_peer_threads,
        "control_tgid": control_tgid,
        "control_peer_threads": control_peer_threads,
        "stability_limit_pct": args.stability_limit_pct,
        "environment_equivalence_pct": args.environment_equivalence_pct,
        "direction_consistency_pct": args.direction_consistency_pct,
        "single_profile_spread_limit": args.single_profile_spread_limit,
        "bootstrap_resamples": args.bootstrap_resamples,
        "bootstrap_seed": args.bootstrap_seed,
        "stable_rounds": stable_rounds,
        "within_round_stable": within_round_stable,
        "environment_control_comparable": environment_control_comparable,
        "direction_consistent": direction_consistent,
        "single_profile_stable": single_profile_stable,
        "rx_target_stable": rx_target_stable,
        "rx_aligned_rounds": rx_aligned_rounds,
        "rx_total_rounds": len(rx_rounds),
        "queue_effect": queue_effect, "manual_rtt_effect": manual_rtt_effect,
        "total_effect": total_effect,
        "environment_control_check": environment_control_check,
        "direction_consistency": direction_consistency,
        "comparison_verdict": comparison_verdict, "rounds": round_receipts,
        "source_advance_ns": int(after["replay"]["source_timestamp_ns"]) -
        int(before["replay"]["source_timestamp_ns"]),
        "auto_strategy_unchanged": True,
        "queue_full_drops": {"manual": 0, "auto_control": 0},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=all_rows[0].keys())
        writer.writeheader()
        writer.writerows(all_rows)
    summary_path = args.output.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    pair_gate = (
        "n/a" if (direction_consistency is None or
                   not direction_consistency["applicable"]) else
        f'{direction_consistency["supporting_pairs"]}/{direction_consistency["total_pairs"]}'
    )
    spread_gate = (
        f"{single_profile_spread_ratio:.2f}" if len(profile_summaries) == 1
        else "n/a"
    )
    rx_gate = "n/a" if not rx_rounds else f"{rx_aligned_rounds}/{len(rx_rounds)}"
    print_classroom_summary(
        summary, round_receipts[-1],
        pair_gate=pair_gate, spread_gate=spread_gate, rx_gate=rx_gate,
    )


if __name__ == "__main__":
    main()
