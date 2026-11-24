#!/usr/bin/env python3
"""Measure four real OUCH order transports with one application contract.

Run this on Low-Latency-Ops after ``transport_labctl.sh start``.  Each order is
single-flight and crosses the paper exchange immediately.  The business
contract and DEQUE_CV entry stay fixed while the client implementations differ.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
import re
import shutil
import socket
import statistics
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any


TRANSPORTS = {
    "SOCKET": {"port": 48122, "label": "Kernel Socket", "mode": "SFC"},
    "OPENONLOAD": {"port": 48123, "label": "OpenOnload", "mode": "SFC"},
    "TCPDIRECT": {"port": 48124, "label": "TCPDirect", "mode": "SFC"},
    "DPDK": {"port": 48125, "label": "DPDK + F-Stack TCP", "mode": "DPDK"},
}
TRANSPORT_ORDER = ("SOCKET", "OPENONLOAD", "TCPDIRECT", "DPDK")
BALANCED_PHASE_ORDER = (
    ("SOCKET", "OPENONLOAD", "DPDK", "TCPDIRECT"),
    ("OPENONLOAD", "TCPDIRECT", "SOCKET", "DPDK"),
    ("TCPDIRECT", "DPDK", "OPENONLOAD", "SOCKET"),
    ("DPDK", "SOCKET", "TCPDIRECT", "OPENONLOAD"),
)
HUGEPAGES_2MB_PATH = (
    "/sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages"
)
NATIVE_RECEIPT_FILES = {
    "SOCKET": {"process.txt", "ss-established.txt", "state.json"},
    "OPENONLOAD": {"onload-stackdump.txt", "process.txt", "state.json"},
    "TCPDIRECT": {
        "process.txt",
        "state.json",
        "zf-attr.txt",
        "zf-dump.txt",
        "zf-list.txt",
    },
    "DPDK": {"fstack.log", "owner.txt", "process.txt", "state.json"},
}
NATIVE_COUNTER_KIND = {
    "SOCKET": "trader_orders",
    "OPENONLOAD": "trader_orders",
    "TCPDIRECT": "zf_txq_added",
    "DPDK": "trader_orders",
}


def management_command(host: str, port: int, line: str) -> dict[str, Any]:
    with socket.create_connection((host, port), timeout=3) as connection:
        connection.sendall((line + "\n").encode("ascii"))
        chunks = bytearray()
        while not chunks.endswith(b"\n"):
            chunk = connection.recv(65536)
            if not chunk:
                break
            chunks.extend(chunk)
    value = json.loads(chunks.decode("ascii"))
    if not isinstance(value, dict):
        raise RuntimeError(f"management response is not an object: {line}")
    return value


def read_exchange_ledger_snapshot(host: str, port: int) -> dict[str, Any]:
    state = management_command(host, port, "STATE")
    entries = state.get("paper_ledger_entries")
    if isinstance(entries, bool) or not isinstance(entries, int) or entries < 0:
        raise RuntimeError(
            "exchange STATE did not return a non-negative integer "
            f"paper_ledger_entries: {entries!r}"
        )
    replay_loop = state.get("replay_loop")
    session = state.get("session")
    if (
        isinstance(replay_loop, bool)
        or not isinstance(replay_loop, int)
        or replay_loop < 1
        or not isinstance(session, str)
        or not session
    ):
        raise RuntimeError(
            "exchange STATE did not return a stable replay identity: "
            f"replay_loop={replay_loop!r} session={session!r}"
        )
    return {
        "entries": entries,
        "replay_loop": replay_loop,
        "session": session,
        "state": state,
    }


def capture_exchange_ledger_growth(
    host: str, port: int, before: dict[str, Any], expected: int
) -> dict[str, Any]:
    after = read_exchange_ledger_snapshot(host, port)
    if (
        after["replay_loop"] != before["replay_loop"]
        or after["session"] != before["session"]
    ):
        raise RuntimeError(
            "exchange replay identity changed during measurement: "
            f"before_loop={before['replay_loop']} after_loop={after['replay_loop']} "
            f"before_session={before['session']!r} after_session={after['session']!r}"
        )
    delta = after["entries"] - before["entries"]
    if delta != expected:
        direction = "too_few_cached_or_missing" if delta < expected else "too_many_external"
        raise RuntimeError(
            "exchange ledger growth contract failed: "
            f"before={before['entries']} after={after['entries']} "
            f"delta={delta} expected={expected} "
            f"diagnosis={direction}"
        )
    return {
        "host": host,
        "port": port,
        "before": before["entries"],
        "after": after["entries"],
        "delta": delta,
        "expected": expected,
        "replay_loop": before["replay_loop"],
        "session": before["session"],
        "before_state": before["state"],
        "after_state": after["state"],
    }


def invoke_control_action(
    control_script: Path,
    run_id: str,
    action: str,
    target: str | None = None,
    timeout: int = 180,
) -> dict[str, Any]:
    command = [str(control_script), action, run_id]
    if target is not None:
        command.append(target)
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(
            f"control action failed: action={action} target={target} "
            f"detail={detail[-2000:]}"
        )
    for line in reversed(completed.stdout.splitlines()):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise RuntimeError(
        f"control action returned no JSON: action={action} target={target}"
    )


def switch_data_plane_mode(
    control_script: Path, run_id: str, mode: str
) -> dict[str, Any]:
    response = invoke_control_action(
        control_script, run_id, mode.lower(), timeout=180
    )
    if response.get("mode") != mode or response.get("transition") != "READY":
        raise RuntimeError(f"data-plane switch to {mode} did not reach READY: {response}")
    return response


def current_path_identity(
    control_script: Path, run_id: str, key: str
) -> dict[str, Any]:
    state = invoke_control_action(control_script, run_id, "status", timeout=15)
    return require_path_receipt(state, key, require_path=False)


def native_receipt_prefix(
    key: str, round_number: int, position: int, phase: str
) -> str:
    if key not in TRANSPORTS:
        raise RuntimeError(f"unknown native receipt transport: {key!r}")
    if round_number not in range(1, 5) or position not in range(1, 5):
        raise RuntimeError(
            "native receipt round/position must both be in 1..4: "
            f"round={round_number} position={position}"
        )
    if phase not in {"pre", "post"}:
        raise RuntimeError(f"invalid native receipt phase: {phase!r}")
    return f"native-receipts/{round_number}-{position}-{key.lower()}/{phase}"


def validate_native_receipt_manifest(
    manifest: dict[str, Any],
    key: str,
    round_number: int,
    position: int,
    phase: str,
) -> dict[str, Any]:
    """Validate only the compact reference envelope returned by the collector."""

    expected_keys = {
        "files",
        "counter_kind",
        "counter_value",
        "matching_excerpts",
    }
    if not isinstance(manifest, dict) or set(manifest) != expected_keys:
        raise RuntimeError(
            f"{key} native receipt has unexpected fields: "
            f"{sorted(manifest) if isinstance(manifest, dict) else manifest!r}"
        )
    prefix = native_receipt_prefix(
        key, round_number, position, phase
    )
    files = manifest.get("files")
    if not isinstance(files, list):
        raise RuntimeError(f"{key} native receipt files is not a list")
    observed_names: set[str] = set()
    observed_paths: set[str] = set()
    for item in files:
        if not isinstance(item, dict) or set(item) != {"path", "sha256", "bytes"}:
            raise RuntimeError(f"{key} native receipt file entry is invalid: {item!r}")
        path = item.get("path")
        digest = item.get("sha256")
        byte_count = item.get("bytes")
        if not isinstance(path, str) or not path.startswith(prefix + "/"):
            raise RuntimeError(f"{key} native receipt path escaped its cell: {path!r}")
        name = path.removeprefix(prefix + "/")
        if "/" in name or not name:
            raise RuntimeError(f"{key} native receipt path is not a direct file: {path!r}")
        if name in observed_names or path in observed_paths:
            raise RuntimeError(f"{key} native receipt repeats file: {path}")
        if not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise RuntimeError(f"{key} native receipt has invalid SHA: {item!r}")
        if isinstance(byte_count, bool) or not isinstance(byte_count, int) or byte_count < 1:
            raise RuntimeError(f"{key} native receipt has invalid byte count: {item!r}")
        observed_names.add(name)
        observed_paths.add(path)
    if observed_names != NATIVE_RECEIPT_FILES[key]:
        raise RuntimeError(
            f"{key} native receipt file contract failed: "
            f"expected={sorted(NATIVE_RECEIPT_FILES[key])} "
            f"observed={sorted(observed_names)}"
        )
    if manifest.get("counter_kind") != NATIVE_COUNTER_KIND[key]:
        raise RuntimeError(
            f"{key} native receipt counter kind mismatch: "
            f"{manifest.get('counter_kind')!r}"
        )
    counter_value = manifest.get("counter_value")
    if (
        isinstance(counter_value, bool)
        or not isinstance(counter_value, int)
        or counter_value < 1
    ):
        raise RuntimeError(
            f"{key} native receipt counter is invalid: {counter_value!r}"
        )
    excerpts = manifest.get("matching_excerpts")
    if not isinstance(excerpts, list) or not excerpts:
        raise RuntimeError(f"{key} native receipt has no matching excerpts")
    for excerpt in excerpts:
        if not isinstance(excerpt, dict) or set(excerpt) != {"path", "text"}:
            raise RuntimeError(
                f"{key} native receipt excerpt is invalid: {excerpt!r}"
            )
        if excerpt.get("path") not in observed_paths:
            raise RuntimeError(
                f"{key} native receipt excerpt references an unknown file: {excerpt!r}"
            )
        if not isinstance(excerpt.get("text"), str) or not excerpt["text"]:
            raise RuntimeError(f"{key} native receipt excerpt is empty: {excerpt!r}")
    return manifest


def onload_ctpio_counters_from_manifest(
    manifest: dict[str, Any]
) -> dict[str, int]:
    values: dict[str, int] = {}
    patterns = {
        "ctpio_pkts": re.compile(r"^ctpio_pkts: ([0-9]+)$"),
        "ctpio_dma_fallbacks": re.compile(
            r"^ctpio_dma_fallbacks: ([0-9]+)$"
        ),
    }
    texts = [item["text"] for item in manifest["matching_excerpts"]]
    for name, pattern in patterns.items():
        matches = [pattern.fullmatch(text) for text in texts]
        numbers = [int(match.group(1)) for match in matches if match]
        if len(numbers) != 1:
            raise RuntimeError(
                f"Onload native manifest has no unique {name}: {texts!r}"
            )
        values[name] = numbers[0]
    return values


def capture_native_path_receipt(
    control_script: Path,
    run_id: str,
    key: str,
    round_number: int,
    position: int,
    phase: str,
) -> dict[str, Any]:
    """Persist native tool output outside the timed window and return references."""

    target = f"{key}:{round_number}:{position}:{phase}"
    manifest = invoke_control_action(
        control_script,
        run_id,
        "native-receipt",
        target=target,
        timeout=45,
    )
    return validate_native_receipt_manifest(
        manifest, key, round_number, position, phase
    )


def require_path_receipt(
    state: dict[str, Any], key: str, require_path: bool
) -> dict[str, Any]:
    expected_mode = str(TRANSPORTS[key]["mode"])
    if state.get("mode") != expected_mode or state.get("transition") != "READY":
        raise RuntimeError(f"{key} attestation returned a non-ready mode: {state}")
    receipt_name = key.lower() if key != "OPENONLOAD" else "onload"
    receipt = state.get("hardware_receipts", {}).get(receipt_name)
    if not isinstance(receipt, dict) or receipt.get("launch_verified") is not True:
        raise RuntimeError(f"{key} current generation has no launch receipt: {state}")
    if require_path and receipt.get("verified") is not True:
        raise RuntimeError(f"{key} current generation has no path witness: {state}")
    for integer_field in ("pid", "start_ticks", "attested_monotonic_ns"):
        value = receipt.get(integer_field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise RuntimeError(
                f"{key} receipt field {integer_field} is invalid: {receipt}"
            )
    path_counter = receipt.get("path_counter")
    if (
        isinstance(path_counter, bool)
        or not isinstance(path_counter, int)
        or path_counter < 0
    ):
        raise RuntimeError(f"{key} receipt path_counter is invalid: {receipt}")
    for text_field in ("boot_id", "generation", "verification"):
        if not isinstance(receipt.get(text_field), str) or not receipt[text_field]:
            raise RuntimeError(f"{key} receipt field {text_field} is invalid: {receipt}")
    return {
        "mode": state["mode"],
        "owner": state.get("owner"),
        "receipt_name": receipt_name,
        "receipt": receipt,
    }


def read_hugepages_2mb(host: str) -> int:
    command = [
        "ssh",
        "-o",
        "BatchMode=yes",
        "-o",
        "StrictHostKeyChecking=yes",
        f"root@{host}",
        "cat",
        HUGEPAGES_2MB_PATH,
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RuntimeError(
            f"failed to read 2 MiB hugepages on root@{host}: {error}"
        ) from error
    if completed.returncode != 0:
        raise RuntimeError(
            f"failed to read 2 MiB hugepages on root@{host}: "
            f"ssh_rc={completed.returncode} stderr={completed.stderr.strip()!r}"
        )
    lines = completed.stdout.splitlines()
    if (
        len(lines) != 1
        or not lines[0]
        or any(character < "0" or character > "9" for character in lines[0])
    ):
        raise RuntimeError(
            f"invalid 2 MiB hugepage value on root@{host}: {completed.stdout!r}"
        )
    return int(lines[0])


def require_hugepages_2mb(host: str, key: str) -> int:
    expected = 256 if TRANSPORTS[key]["mode"] == "DPDK" else 128
    observed = read_hugepages_2mb(host)
    if observed != expected:
        raise RuntimeError(
            f"{key} 2 MiB hugepage contract failed on root@{host}: "
            f"expected={expected} observed={observed}"
        )
    return observed


def wait_state(host: str, port: int, predicate: Any, timeout: float = 10) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last: dict[str, Any] = {}
    while time.monotonic() < deadline:
        try:
            last = management_command(host, port, "STATE")
            if predicate(last):
                return last
        except (OSError, ValueError, json.JSONDecodeError):
            pass
        time.sleep(0.002)
    raise TimeoutError(f"port {port} did not reach required state; last={last}")


def nearest_rank(values: list[int], percentile: float) -> int:
    ordered = sorted(values)
    if not ordered:
        return 0
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


def summarize(values: list[int]) -> dict[str, int]:
    return {
        "samples": len(values),
        "p50_ns": nearest_rank(values, 0.50),
        "p95_ns": nearest_rank(values, 0.95),
        "p99_ns": nearest_rank(values, 0.99),
        "mean_ns": round(statistics.fmean(values)) if values else 0,
        "max_ns": max(values, default=0),
    }


def first_side(state: dict[str, Any]) -> str:
    position = int(state.get("positions", {}).get("AAPL", 0))
    if position > 0:
        return "SELL"
    if position < 0:
        return "BUY"
    return "BUY"


def opposite(side: str) -> str:
    return "SELL" if side == "BUY" else "BUY"


def crossing_price(side: str) -> int:
    return 999_999_999_999 if side == "BUY" else 1


def submit_single_flight(
    host: str,
    port: int,
    command_name: str,
    side: str,
    counter_name: str,
    expected: int,
) -> int:
    response = management_command(
        host,
        port,
        f"{command_name}|AAPL|{side}|1|{crossing_price(side)}",
    )
    if response.get("ok") is not True:
        raise RuntimeError(f"order rejected before enqueue: {response}")
    client_order_id = response.get("client_order_id")
    if isinstance(client_order_id, bool) or not isinstance(client_order_id, int):
        raise RuntimeError(
            "order submission did not return an integer client_order_id: "
            f"{response}"
        )
    wait_state(
        host,
        port,
        lambda state: int(state[counter_name].get("samples", 0)) >= expected,
    )
    return client_order_id


def measure_round(
    host: str,
    key: str,
    round_number: int,
    position: int,
    warmup: int,
    samples: int,
    control_script: Path,
    run_id: str,
) -> dict[str, Any]:
    config = TRANSPORTS[key]
    port = int(config["port"])
    identity_at_start = current_path_identity(control_script, run_id, key)
    state = wait_state(host, port, lambda value: value.get("status") == "ONLINE")
    software = state.get("software_latency", {})
    if software.get("queue_mode") != "DEQUE_CV" or software.get("queue_locked") is not True:
        raise RuntimeError(f"{key} did not lock the common DEQUE_CV handoff: {software}")
    if (
        int(software.get("order_thread_cpu", -1)) != 2
        or int(software.get("order_thread_allowed_count", 0)) != 1
        or int(software.get("management_thread_cpu", -1)) != 3
        or int(software.get("management_thread_allowed_count", 0)) != 1
    ):
        raise RuntimeError(f"{key} did not preserve the CPU 2/3 contract: {software}")
    if key == "DPDK" and (
        int(software.get("bridge_thread_cpu", -1)) != 3
        or int(software.get("bridge_thread_allowed_count", 0)) != 1
        or state.get("tcp_nodelay") is not True
    ):
        raise RuntimeError(f"DPDK helper/Nagle contract failed: {state}")

    observed_hugepages_2mb = require_hugepages_2mb(host, key)
    side = first_side(state)
    warmup_start = int(state.get("latency", {}).get("samples", 0))
    warmup_submission_ids: list[int] = []
    warmup_submission_ids.append(
        submit_single_flight(
            host,
            port,
            "ORDER",
            side,
            "latency",
            warmup_start + 1,
        )
    )
    side = opposite(side)
    native_pre = capture_native_path_receipt(
        control_script,
        run_id,
        key,
        round_number,
        position,
        "pre",
    )
    identity_after_native_pre = current_path_identity(
        control_script, run_id, key
    )
    for index in range(1, warmup):
        warmup_submission_ids.append(
            submit_single_flight(
                host,
                port,
                "ORDER",
                side,
                "latency",
                warmup_start + index + 1,
            )
        )
        side = opposite(side)

    reset = management_command(host, port, "MEASUREMENT_RESET")
    if reset.get("ok") is not True:
        raise RuntimeError(f"{key} measurement reset failed: {reset}")
    identity_before_measurement = current_path_identity(
        control_script, run_id, key
    )
    cell_start_monotonic_ns = time.monotonic_ns()
    measurement_submission_ids: list[int] = []
    for index in range(samples):
        measurement_submission_ids.append(
            submit_single_flight(
                host,
                port,
                "MEASUREMENT_ORDER",
                side,
                "measurement_latency",
                index + 1,
            )
        )
        side = opposite(side)

    raw = management_command(host, port, "MEASUREMENT_SAMPLES")
    cell_end_monotonic_ns = time.monotonic_ns()
    rows = raw.get("samples", [])
    if not isinstance(rows, list):
        raise RuntimeError(f"{key} MEASUREMENT_SAMPLES samples is not a list")
    if len(rows) != samples:
        raise RuntimeError(f"{key} expected {samples} samples, got {len(rows)}")
    validate_measurement_submission_mapping(
        key,
        round_number,
        measurement_submission_ids,
        rows,
    )
    if any(row.get("result") != "E" for row in rows):
        raise RuntimeError(f"{key} produced a non-executed final response")

    order_rtt = [int(row["order_rtt_ns"]) for row in rows]
    queue_to_send = [int(row["queue_to_send_ns"]) for row in rows]
    submit_to_final = [int(row["submit_to_final_ns"]) for row in rows]
    identity_after_measurement = current_path_identity(
        control_script, run_id, key
    )
    final_state = management_command(host, port, "STATE")
    observed_nodelay = final_state.get("tcp_nodelay")
    observed_nagle_semantics = final_state.get("nagle_semantics")
    if key == "TCPDIRECT":
        if (
            observed_nodelay is not None
            or observed_nagle_semantics != "ZF_API_NO_POSIX_TCP_NODELAY"
        ):
            raise RuntimeError(
                f"{key} Nagle contract is not the ZF N/A contract: "
                f"nodelay={observed_nodelay!r} "
                f"semantics={observed_nagle_semantics!r}"
            )
        nagle_contract = {
            "applicable": False,
            "tcp_nodelay": None,
            "verification": "ZF_API_NO_POSIX_TCP_NODELAY",
        }
    else:
        expected_semantics = (
            "FSTACK_GETSOCKOPT_VERIFIED"
            if key == "DPDK"
            else "POSIX_CONNECT_GETSOCKOPT_VERIFIED"
        )
        if (
            observed_nodelay is not True
            or observed_nagle_semantics != expected_semantics
        ):
            raise RuntimeError(
                f"{key} did not verify TCP_NODELAY at runtime: "
                f"nodelay={observed_nodelay!r} "
                f"semantics={observed_nagle_semantics!r}"
            )
        nagle_contract = {
            "applicable": True,
            "tcp_nodelay": True,
            "verification": "RUNTIME_GETSOCKOPT_NONZERO",
        }
    native_post = capture_native_path_receipt(
        control_script,
        run_id,
        key,
        round_number,
        position,
        "post",
    )
    identity_after_native_post = current_path_identity(
        control_script, run_id, key
    )
    receipt_sequence = [
        identity_at_start["receipt"],
        identity_after_native_pre["receipt"],
        identity_before_measurement["receipt"],
        identity_after_measurement["receipt"],
        identity_after_native_post["receipt"],
    ]
    generations = {
        (
            receipt["boot_id"],
            receipt["pid"],
            receipt["start_ticks"],
            receipt["generation"],
        )
        for receipt in receipt_sequence
    }
    if len(generations) != 1:
        raise RuntimeError(
            f"{key} process generation changed inside round {round_number}: "
            f"receipts={receipt_sequence}"
        )
    if (
        native_post["counter_value"]
        <= native_pre["counter_value"]
    ):
        raise RuntimeError(
            f"{key} native path counter did not grow in round {round_number}: "
            f"kind={native_pre['counter_kind']} "
            f"before={native_pre['counter_value']} "
            f"after={native_post['counter_value']}"
        )
    if key == "OPENONLOAD":
        ctpio_pre = onload_ctpio_counters_from_manifest(native_pre)
        ctpio_post = onload_ctpio_counters_from_manifest(native_post)
        if ctpio_post["ctpio_pkts"] <= ctpio_pre["ctpio_pkts"]:
            raise RuntimeError(
                f"{key} CTPIO packet counter did not grow in round {round_number}: "
                f"before={ctpio_pre['ctpio_pkts']} "
                f"after={ctpio_post['ctpio_pkts']}"
            )
        if (
            ctpio_post["ctpio_dma_fallbacks"]
            != ctpio_pre["ctpio_dma_fallbacks"]
        ):
            raise RuntimeError(
                f"{key} CTPIO DMA fallback counter grew in round {round_number}: "
                f"before={ctpio_pre['ctpio_dma_fallbacks']} "
                f"after={ctpio_post['ctpio_dma_fallbacks']}"
            )
    return {
        "transport": key,
        "label": config["label"],
        "mode": config["mode"],
        "round": round_number,
        "position": position,
        "warmup_orders": warmup,
        "measurement_orders": samples,
        "warmup_submission_ids": warmup_submission_ids,
        "measurement_submission_ids": measurement_submission_ids,
        "measurement_generation": reset.get("measurement_generation"),
        "cell_audit": {
            "clock": "CLOCK_MONOTONIC_ON_LOW_LATENCY_OPS",
            "start_monotonic_ns": cell_start_monotonic_ns,
            "end_monotonic_ns": cell_end_monotonic_ns,
            "duration_ns": cell_end_monotonic_ns - cell_start_monotonic_ns,
            "native_receipts": {
                "pre": native_pre,
                "post": native_post,
            },
        },
        "contract": {
            "symbol": "AAPL",
            "quantity": 1,
            "order_type": "IOC_LIMIT_CROSSING",
            "protocol": "OUCH_5.0_OVER_SOUPBINTCP",
            "queue_mode": "DEQUE_CV",
            "queue_locked": True,
            "single_flight": True,
            "accepted_telemetry_in_timer": False,
            "clock": raw.get("clock"),
            "timer_start": "OUCH_ENCODED_BEFORE_SOUP_FRAME",
            "timer_end": "FINAL_EXECUTED_DECODED",
            "data_cpu": 2,
            "management_cpu": 3,
            "observed_hugepages_2mb": observed_hugepages_2mb,
            "nagle": nagle_contract,
        },
        "network_engine": final_state.get("software_latency", {}).get(
            "network_engine",
            final_state.get("software_latency", {}).get("network_reactor", ""),
        ),
        "thread_placement": {
            name: final_state.get("software_latency", {}).get(name)
            for name in (
                "order_thread_cpu",
                "order_thread_allowed_count",
                "management_thread_cpu",
                "management_thread_allowed_count",
                "bridge_thread_cpu",
                "bridge_thread_allowed_count",
            )
            if name in final_state.get("software_latency", {})
        },
        "order_rtt": summarize(order_rtt),
        "queue_to_send": summarize(queue_to_send),
        "submit_to_final": summarize(submit_to_final),
        "raw_samples": rows,
    }


def median_round_summary(rounds: list[dict[str, Any]], metric: str) -> dict[str, int]:
    def median_ns(field: str) -> int:
        values = sorted(int(row[metric][field]) for row in rounds)
        middle = len(values) // 2
        if len(values) % 2:
            return values[middle]
        return (values[middle - 1] + values[middle] + 1) // 2

    return {
        "rounds": len(rounds),
        "p50_ns": median_ns("p50_ns"),
        "p95_ns": median_ns("p95_ns"),
        "p99_ns": median_ns("p99_ns"),
        "mean_ns": median_ns("mean_ns"),
        "max_ns": max(row[metric]["max_ns"] for row in rounds),
    }


def sample_location(round_result: dict[str, Any], sample_index: int) -> str:
    transport = str(round_result.get("transport", "UNKNOWN"))
    round_number = round_result.get("round", "UNKNOWN")
    return f"{transport.lower()}-r{round_number}.json sample={sample_index}"


def submission_location(
    round_result: dict[str, Any], phase: str, submission_index: int
) -> str:
    transport = str(round_result.get("transport", "UNKNOWN"))
    round_number = round_result.get("round", "UNKNOWN")
    return (
        f"{transport.lower()}-r{round_number}.json "
        f"phase={phase} submission={submission_index}"
    )


def require_client_order_id(value: Any, location: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise RuntimeError(
            "client_order_id is not an integer: "
            f"value={value!r} current={location}"
        )
    return value


def validate_measurement_submission_mapping(
    transport: str,
    round_number: int,
    measurement_submission_ids: list[int],
    raw_samples: list[dict[str, Any]],
) -> None:
    """Require the measured submission and response identities to match exactly."""

    submitted = [
        require_client_order_id(
            value,
            f"{transport.lower()}-r{round_number}.json "
            f"phase=measurement submission={index}",
        )
        for index, value in enumerate(measurement_submission_ids, start=1)
    ]
    raw_ids: list[int] = []
    for index, sample in enumerate(raw_samples, start=1):
        location = f"{transport.lower()}-r{round_number}.json sample={index}"
        if not isinstance(sample, dict):
            raise RuntimeError(f"sample is not an object: current={location}")
        raw_ids.append(require_client_order_id(sample.get("client_order_id"), location))

    if len(submitted) != len(raw_ids):
        raise RuntimeError(
            f"{transport} round {round_number} measurement submission/raw count "
            f"mismatch: submitted={len(submitted)} raw={len(raw_ids)}"
        )
    submitted_set = set(submitted)
    raw_set = set(raw_ids)
    if submitted_set != raw_set:
        raise RuntimeError(
            f"{transport} round {round_number} measurement submission/raw set "
            f"mismatch: missing_from_raw={sorted(submitted_set - raw_set)} "
            f"unexpected_in_raw={sorted(raw_set - submitted_set)}"
        )
    if submitted != raw_ids:
        mismatch = next(
            index
            for index, (submitted_id, raw_id) in enumerate(
                zip(submitted, raw_ids), start=1
            )
            if submitted_id != raw_id
        )
        raise RuntimeError(
            f"{transport} round {round_number} measurement submission/raw order "
            f"mismatch at index={mismatch}: "
            f"submitted={submitted[mismatch - 1]} raw={raw_ids[mismatch - 1]}"
        )


def require_submission_count(
    round_result: dict[str, Any], field: str, expected_field: str
) -> list[int]:
    transport = str(round_result.get("transport", "UNKNOWN"))
    round_number = round_result.get("round", "UNKNOWN")
    values = round_result.get(field)
    if not isinstance(values, list):
        raise RuntimeError(
            f"{transport} round {round_number} {field} is not a list"
        )
    expected = round_result.get(expected_field)
    if isinstance(expected, bool) or not isinstance(expected, int) or expected < 0:
        raise RuntimeError(
            f"{transport} round {round_number} {expected_field} is not a "
            f"non-negative integer: {expected!r}"
        )
    if len(values) != expected:
        raise RuntimeError(
            f"{transport} round {round_number} {field} count mismatch: "
            f"expected={expected} observed={len(values)}"
        )
    return values


def validate_and_summarize_submission_identity(
    rounds: list[dict[str, Any]],
) -> dict[str, Any]:
    """Reject reused IDs across every warmup and measured submission."""

    first_global: dict[int, str] = {}
    transport_ids = {key: set() for key in TRANSPORT_ORDER}
    transport_totals = {key: 0 for key in TRANSPORT_ORDER}
    per_round_ranges: list[dict[str, Any]] = []

    for round_result in rounds:
        transport = str(round_result.get("transport", ""))
        if transport not in TRANSPORTS:
            raise RuntimeError(
                f"unknown transport in submission identity gate: {transport!r}"
            )
        warmup_ids = require_submission_count(
            round_result, "warmup_submission_ids", "warmup_orders"
        )
        measurement_ids = require_submission_count(
            round_result, "measurement_submission_ids", "measurement_orders"
        )
        first_in_round: dict[int, str] = {}
        round_ids: set[int] = set()
        for phase, values in (
            ("warmup", warmup_ids),
            ("measurement", measurement_ids),
        ):
            for submission_index, value in enumerate(values, start=1):
                location = submission_location(
                    round_result, phase, submission_index
                )
                client_order_id = require_client_order_id(value, location)
                if client_order_id in first_in_round:
                    raise RuntimeError(
                        f"duplicate client_order_id={client_order_id} within "
                        f"submission file: current={location}; "
                        f"first={first_in_round[client_order_id]}"
                    )
                if client_order_id in first_global:
                    raise RuntimeError(
                        f"duplicate client_order_id={client_order_id} across "
                        f"submission files: current={location}; "
                        f"first={first_global[client_order_id]}"
                    )
                first_in_round[client_order_id] = location
                first_global[client_order_id] = location
                round_ids.add(client_order_id)
                transport_ids[transport].add(client_order_id)
                transport_totals[transport] += 1
        per_round_ranges.append(
            {
                "transport": transport,
                "round": int(round_result["round"]),
                "warmup_total": len(warmup_ids),
                "measurement_total": len(measurement_ids),
                "total": len(warmup_ids) + len(measurement_ids),
                "unique": len(round_ids),
                "min_client_order_id": min(round_ids, default=None),
                "max_client_order_id": max(round_ids, default=None),
            }
        )

    transport_rank = {key: index for index, key in enumerate(TRANSPORT_ORDER)}
    per_round_ranges.sort(
        key=lambda item: (transport_rank[item["transport"]], item["round"])
    )
    per_transport = []
    for transport in TRANSPORT_ORDER:
        ids = transport_ids[transport]
        per_transport.append(
            {
                "transport": transport,
                "total": transport_totals[transport],
                "unique": len(ids),
                "min_client_order_id": min(ids, default=None),
                "max_client_order_id": max(ids, default=None),
            }
        )
    return {
        "field": "client_order_id",
        "scope": "WARMUP_AND_MEASUREMENT_SUBMISSIONS",
        "total": sum(transport_totals.values()),
        "unique": len(first_global),
        "per_transport": per_transport,
        "per_round_ranges": per_round_ranges,
    }


def validate_and_summarize_sample_identity(
    rounds: list[dict[str, Any]],
) -> dict[str, Any]:
    """Reject reused measured response IDs and summarize their provenance."""

    first_global: dict[int, str] = {}
    transport_ids = {key: set() for key in TRANSPORT_ORDER}
    transport_totals = {key: 0 for key in TRANSPORT_ORDER}
    per_round_ranges: list[dict[str, Any]] = []

    for round_result in rounds:
        transport = str(round_result.get("transport", ""))
        if transport not in TRANSPORTS:
            raise RuntimeError(f"unknown transport in sample identity gate: {transport!r}")
        round_ids: set[int] = set()
        first_in_round: dict[int, str] = {}
        raw_samples = round_result.get("raw_samples")
        if not isinstance(raw_samples, list):
            raise RuntimeError(
                f"{transport} round {round_result.get('round')!r} raw_samples is not a list"
            )
        measurement_submission_ids = round_result.get("measurement_submission_ids")
        if not isinstance(measurement_submission_ids, list):
            raise RuntimeError(
                f"{transport} round {round_result.get('round')!r} "
                "measurement_submission_ids is not a list"
            )
        validate_measurement_submission_mapping(
            transport,
            int(round_result["round"]),
            measurement_submission_ids,
            raw_samples,
        )
        for sample_index, sample in enumerate(raw_samples, start=1):
            location = sample_location(round_result, sample_index)
            if not isinstance(sample, dict):
                raise RuntimeError(f"sample is not an object: current={location}")
            client_order_id = require_client_order_id(
                sample.get("client_order_id"), location
            )
            if client_order_id in first_in_round:
                raise RuntimeError(
                    f"duplicate client_order_id={client_order_id} within raw file: "
                    f"current={location}; first={first_in_round[client_order_id]}"
                )
            if client_order_id in first_global:
                raise RuntimeError(
                    f"duplicate client_order_id={client_order_id} across raw files: "
                    f"current={location}; first={first_global[client_order_id]}"
                )
            first_in_round[client_order_id] = location
            first_global[client_order_id] = location
            round_ids.add(client_order_id)
            transport_ids[transport].add(client_order_id)
            transport_totals[transport] += 1
        per_round_ranges.append(
            {
                "transport": transport,
                "round": int(round_result["round"]),
                "total": len(raw_samples),
                "unique": len(round_ids),
                "min_client_order_id": min(round_ids, default=None),
                "max_client_order_id": max(round_ids, default=None),
            }
        )

    transport_rank = {key: index for index, key in enumerate(TRANSPORT_ORDER)}
    per_round_ranges.sort(
        key=lambda item: (transport_rank[item["transport"]], item["round"])
    )
    per_transport = []
    for transport in TRANSPORT_ORDER:
        ids = transport_ids[transport]
        per_transport.append(
            {
                "transport": transport,
                "total": transport_totals[transport],
                "unique": len(ids),
                "min_client_order_id": min(ids, default=None),
                "max_client_order_id": max(ids, default=None),
            }
        )
    return {
        "field": "client_order_id",
        "scope": "MEASUREMENT_RESPONSES",
        "total": sum(transport_totals.values()),
        "unique": len(first_global),
        "per_transport": per_transport,
        "per_round_ranges": per_round_ranges,
    }


def validate_position_and_predecessor_balance(
    design: tuple[tuple[str, ...], ...] = BALANCED_PHASE_ORDER,
) -> dict[str, Any]:
    """Hard-gate every position and every within-round ordered predecessor."""

    expected_transports = set(TRANSPORT_ORDER)
    size = len(TRANSPORT_ORDER)
    if len(design) != size:
        raise RuntimeError(
            f"order design must contain {size} rounds, got {len(design)}"
        )
    for round_number, row in enumerate(design, start=1):
        if len(row) != size or set(row) != expected_transports:
            raise RuntimeError(
                f"order design round {round_number} must contain every "
                f"transport exactly once: {row}"
            )

    position_balance = []
    for transport in TRANSPORT_ORDER:
        counts = {
            str(position): sum(
                row[position - 1] == transport for row in design
            )
            for position in range(1, size + 1)
        }
        if any(count != 1 for count in counts.values()):
            raise RuntimeError(
                f"order design position balance failed for {transport}: {counts}"
            )
        position_balance.append(
            {"transport": transport, "position_counts": counts}
        )

    predecessor_counts = Counter(
        (row[index - 1], row[index])
        for row in design
        for index in range(1, size)
    )
    expected_predecessors = {
        (predecessor, current)
        for predecessor in TRANSPORT_ORDER
        for current in TRANSPORT_ORDER
        if predecessor != current
    }
    if (
        set(predecessor_counts) != expected_predecessors
        or any(count != 1 for count in predecessor_counts.values())
    ):
        missing = sorted(expected_predecessors - set(predecessor_counts))
        unexpected = sorted(set(predecessor_counts) - expected_predecessors)
        repeated = sorted(
            (pair, count)
            for pair, count in predecessor_counts.items()
            if count != 1
        )
        raise RuntimeError(
            "order design first-order predecessor balance failed: "
            f"missing={missing} unexpected={unexpected} repeated={repeated}"
        )
    transport_rank = {key: index for index, key in enumerate(TRANSPORT_ORDER)}
    predecessor_balance = [
        {
            "predecessor": predecessor,
            "current": current,
            "count": predecessor_counts[(predecessor, current)],
        }
        for predecessor, current in sorted(
            expected_predecessors,
            key=lambda pair: (
                transport_rank[pair[0]],
                transport_rank[pair[1]],
            ),
        )
    ]
    cross_round_boundaries = [
        {"predecessor": design[index][-1], "current": design[index + 1][0]}
        for index in range(len(design) - 1)
    ]
    complete_predecessor_counts = predecessor_counts.copy()
    complete_predecessor_counts.update(
        (item["predecessor"], item["current"])
        for item in cross_round_boundaries
    )
    if set(complete_predecessor_counts) != expected_predecessors:
        raise RuntimeError(
            "complete execution sequence does not cover all possible ordered "
            "predecessors"
        )
    return {
        "rounds": size,
        "position_balance": position_balance,
        "within_round_first_order_predecessor_balance": predecessor_balance,
        "cross_round_boundaries": cross_round_boundaries,
        "complete_sequence_predecessor_coverage": [
            {
                "predecessor": predecessor,
                "current": current,
                "count": complete_predecessor_counts[(predecessor, current)],
            }
            for predecessor, current in sorted(
                expected_predecessors,
                key=lambda pair: (
                    transport_rank[pair[0]],
                    transport_rank[pair[1]],
                ),
            )
        ],
    }


def validate_final_identity_gates(
    rounds: list[dict[str, Any]], warmup: int, samples: int
) -> tuple[dict[str, Any], dict[str, Any]]:
    expected_execution = [
        (round_number, transport)
        for round_number, order in enumerate(BALANCED_PHASE_ORDER, start=1)
        for transport in order
    ]
    observed_execution = [
        (int(row["round"]), str(row["transport"])) for row in rounds
    ]
    if observed_execution != expected_execution:
        raise RuntimeError(
            "executed phase order does not match the balanced design: "
            f"expected={expected_execution} observed={observed_execution}"
        )
    submission_identity = validate_and_summarize_submission_identity(rounds)
    sample_identity = validate_and_summarize_sample_identity(rounds)
    files = len(expected_execution)
    expected_submissions = files * (warmup + samples)
    expected_samples = files * samples
    if (
        submission_identity["total"] != expected_submissions
        or submission_identity["unique"] != expected_submissions
    ):
        raise RuntimeError(
            "all-submission identity total failed: "
            f"expected={expected_submissions} "
            f"total={submission_identity['total']} "
            f"unique={submission_identity['unique']}"
        )
    if (
        sample_identity["total"] != expected_samples
        or sample_identity["unique"] != expected_samples
    ):
        raise RuntimeError(
            "measured response identity total failed: "
            f"expected={expected_samples} total={sample_identity['total']} "
            f"unique={sample_identity['unique']}"
        )
    return submission_identity, sample_identity


def fetch_native_receipt_tree(host: str, run_id: str, destination: Path) -> Path:
    """Copy the remote immutable originals without parsing command output."""

    if re.fullmatch(r"[A-Za-z0-9._-]+", run_id) is None:
        raise RuntimeError(f"unsafe RUN_ID for native receipt fetch: {run_id!r}")
    destination.mkdir(parents=True, exist_ok=False)
    remote = f"root@{host}:/var/tmp/flle-trading-lab-{run_id}/native-receipts"
    completed = subprocess.run(
        [
            "scp",
            "-q",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=yes",
            "-r",
            remote,
            str(destination),
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "failed to fetch native receipt originals: "
            f"rc={completed.returncode} stderr={completed.stderr.strip()!r}"
        )
    root = destination / "native-receipts"
    if not root.is_dir():
        raise RuntimeError(f"native receipt fetch created no tree: {root}")
    return root


def validate_downloaded_native_receipts(
    rounds: list[dict[str, Any]], receipt_root: Path
) -> dict[str, int]:
    """Require an exact on-disk file set and match every compact manifest."""

    expected_paths: set[str] = set()
    manifests = 0
    for row in rounds:
        key = str(row["transport"])
        round_number = int(row["round"])
        position = int(row["position"])
        native = row.get("cell_audit", {}).get("native_receipts")
        if not isinstance(native, dict) or set(native) != {"pre", "post"}:
            raise RuntimeError(
                f"{key} round {round_number} has no pre/post native manifests"
            )
        for phase in ("pre", "post"):
            manifest = validate_native_receipt_manifest(
                native[phase], key, round_number, position, phase
            )
            manifests += 1
            for item in manifest["files"]:
                relative = str(item["path"])
                expected_paths.add(relative)
                target = receipt_root.parent / relative
                payload = target.read_bytes()
                observed_sha = hashlib.sha256(payload).hexdigest()
                if observed_sha != item["sha256"] or len(payload) != item["bytes"]:
                    raise RuntimeError(
                        f"native receipt file mismatch: path={relative} "
                        f"expected_sha={item['sha256']} observed_sha={observed_sha} "
                        f"expected_bytes={item['bytes']} observed_bytes={len(payload)}"
                    )
            for excerpt in manifest["matching_excerpts"]:
                target = receipt_root.parent / str(excerpt["path"])
                lines = target.read_text(encoding="utf-8").splitlines()
                if excerpt["text"] not in lines:
                    raise RuntimeError(
                        "native receipt matching excerpt is not an exact source line: "
                        f"path={excerpt['path']} text={excerpt['text']!r}"
                    )
    actual_paths = {
        path.relative_to(receipt_root.parent).as_posix()
        for path in receipt_root.rglob("*")
        if path.is_file()
    }
    if actual_paths != expected_paths:
        raise RuntimeError(
            "native receipt tree/manifest file set mismatch: "
            f"missing={sorted(expected_paths - actual_paths)} "
            f"unexpected={sorted(actual_paths - expected_paths)}"
        )
    if manifests != 32:
        raise RuntimeError(
            f"native receipt phase count must be 32, observed={manifests}"
        )
    return {
        "cells": manifests // 2,
        "pre_post_manifests": manifests,
        "original_files": len(actual_paths),
    }


def write_report(
    output: Path,
    result: dict[str, Any],
    native_receipts_source: Path | None = None,
    sealed_program_sources: dict[str, Path] | None = None,
) -> None:
    output.mkdir(parents=True, exist_ok=False)
    if native_receipts_source is not None:
        shutil.copytree(native_receipts_source, output / "native-receipts")
    if sealed_program_sources:
        provenance = output / "provenance"
        provenance.mkdir()
        sealed = []
        for output_name, source in sorted(sealed_program_sources.items()):
            payload = source.read_bytes()
            target = provenance / output_name
            target.write_bytes(payload)
            sealed.append(
                {
                    "path": target.relative_to(output).as_posix(),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "bytes": len(payload),
                }
            )
        result["execution_provenance"] = {"sealed_programs": sealed}
    raw = output / "raw"
    raw.mkdir()
    for row in result["rounds"]:
        target = raw / f"{row['transport'].lower()}-r{row['round']}.json"
        target.write_text(json.dumps(row, ensure_ascii=False, indent=2) + "\n")
    compact = {key: value for key, value in result.items() if key != "rounds"}
    ledger = dict(compact["exchange_ledger_gate"])
    before_state = ledger.pop("before_state")
    after_state = ledger.pop("after_state")
    compact["exchange_ledger_gate"] = ledger
    (raw / "exchange-ledger-before.json").write_text(
        json.dumps(before_state, ensure_ascii=False, indent=2) + "\n"
    )
    (raw / "exchange-ledger-after.json").write_text(
        json.dumps(after_state, ensure_ascii=False, indent=2) + "\n"
    )
    (output / "summary.json").write_text(
        json.dumps(compact, ensure_ascii=False, indent=2) + "\n"
    )
    warmup_per_round = int(result["parameters"]["warmup_per_round"])
    lines = [
        "# Chapter 06 four real order transports",
        "",
        f"RUN_ID: `{result['run_id']}`",
        "",
        "四条路径都使用 1 股可立即成交 IOC、SoupBinTCP/OUCH、逐笔单飞和锁定的 DEQUE_CV 应用交接。",
        "四轮顺序同时平衡位置与行内一阶前序：每条路径各占一次第 1 / 2 / 3 / 4 位，"
        f"12 种不同的有序前序各在轮内出现一次；每格先用 {warmup_per_round} 笔 warmup "
        "减弱前一路径的残留影响，但不宣称将其消除。",
        "连续轮次之间还有 3 条边界，它们会不可避免地重复已有前序；因此完整执行序列只承诺"
        "12 种可能前序都至少出现，不把 15 次连续切换泛称为全部各一次。"
        "DPDK 到位时独占 VFIO，随后按下一路径所需 mode 切换。",
        "",
    ]
    submission_identity = result["submission_identity"]
    sample_identity = result["sample_identity"]
    exchange_ledger_gate = result["exchange_ledger_gate"]
    lines.extend(
        [
            "全部提交身份硬门（warmup + measurement）："
            f"submitted total=unique={submission_identity['total']}；"
            f"{len(submission_identity['per_round_ranges'])} 份结果均通过文件内与全局唯一性检查。",
            "正式样本身份硬门："
            f"measured total=unique={sample_identity['total']}；"
            "每轮 measurement 提交 ID 与 MEASUREMENT_SAMPLES 返回 ID 的顺序和集合精确一致。",
            "交易所账本硬门："
            f"before={exchange_ledger_gate['before']}，"
            f"after={exchange_ledger_gate['after']}，"
            f"delta=expected={exchange_ledger_gate['delta']}；"
            "少增会抓住缓存复用，多增会抓住 GUI 或外来订单。",
            "每格在首笔 warmup 后保存 pre 原件，再用剩余 warmup 隔开重型探针；"
            "1000 笔结束后保存 post 原件，两次都在计时窗外。",
            "",
            "下表是四轮统计量中位数，只作描述；"
            "平衡主表由后处理器对四个 Williams 单元等权。",
            "",
            "| Transport | send→final P50 / P95 / P99 | queue→final P50 / P95 / P99 |",
            "| --- | ---: | ---: |",
        ]
    )
    for key in TRANSPORT_ORDER:
        values = result["summary"][key]
        lines.append(
            f"| {TRANSPORTS[key]['label']} | "
            f"{values['order_rtt']['p50_ns']} / {values['order_rtt']['p95_ns']} / "
            f"{values['order_rtt']['p99_ns']} ns | "
            f"{values['submit_to_final']['p50_ns']} / "
            f"{values['submit_to_final']['p95_ns']} / "
            f"{values['submit_to_final']['p99_ns']} ns |"
        )
    (output / "README.md").write_text("\n".join(lines) + "\n")
    manifest = []
    for target in sorted(path for path in output.rglob("*") if path.is_file()):
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        manifest.append(f"{digest}  {target.relative_to(output)}")
    (output / "SHA256SUMS").write_text("\n".join(manifest) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--control-script", type=Path, required=True)
    parser.add_argument("--trader-host", default="10.1.1.2")
    parser.add_argument("--exchange-host", default="10.1.1.1")
    parser.add_argument("--exchange-port", type=int, default=48120)
    parser.add_argument("--warmup", type=int, default=100)
    parser.add_argument("--samples", type=int, default=1000)
    parser.add_argument(
        "--rounds",
        type=int,
        default=4,
        help="must be 4 to preserve position and first-order predecessor balance",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("Documents/reports/course-runs"),
    )
    args = parser.parse_args()
    if args.warmup < 1 or args.samples < 1:
        parser.error("warmup >= 1 and samples >= 1 are required")
    if args.rounds != len(BALANCED_PHASE_ORDER):
        parser.error(
            "--rounds must be 4 for position and first-order predecessor balance"
        )
    order_balance = validate_position_and_predecessor_balance()
    expected_files = len(BALANCED_PHASE_ORDER) * len(TRANSPORT_ORDER)
    expected_exchange_growth = expected_files * (args.warmup + args.samples)
    exchange_ledger_before = read_exchange_ledger_snapshot(
        args.exchange_host, args.exchange_port
    )

    results: list[dict[str, Any]] = []
    restored = False
    control_script = args.control_script.resolve(strict=True)
    try:
        switch_data_plane_mode(control_script, args.run_id, "SFC")
        current_mode = "SFC"
        for round_number, order in enumerate(BALANCED_PHASE_ORDER, start=1):
            for position, key in enumerate(order, start=1):
                required_mode = str(TRANSPORTS[key]["mode"])
                if required_mode != current_mode:
                    switch_data_plane_mode(
                        control_script, args.run_id, required_mode
                    )
                    current_mode = required_mode
                print(
                    f"measure={key} round={round_number} position={position}",
                    flush=True,
                )
                measured = measure_round(
                    args.trader_host,
                    key,
                    round_number,
                    position,
                    args.warmup,
                    args.samples,
                    control_script,
                    args.run_id,
                )
                results.append(measured)
                validate_and_summarize_submission_identity(results)
                validate_and_summarize_sample_identity(results)
        exchange_ledger_gate = capture_exchange_ledger_growth(
            args.exchange_host,
            args.exchange_port,
            exchange_ledger_before,
            expected_exchange_growth,
        )
        submission_identity, sample_identity = validate_final_identity_gates(
            results, args.warmup, args.samples
        )
        switch_data_plane_mode(control_script, args.run_id, "SFC")
        restored = True
    finally:
        if not restored:
            try:
                switch_data_plane_mode(control_script, args.run_id, "SFC")
            except Exception as error:  # deadman remains the independent fallback
                print(f"restore_warning={error}", flush=True)

    summary: dict[str, Any] = {}
    for key in TRANSPORT_ORDER:
        rows = [row for row in results if row["transport"] == key]
        summary[key] = {
            "label": TRANSPORTS[key]["label"],
            "order_rtt": median_round_summary(rows, "order_rtt"),
            "queue_to_send": median_round_summary(rows, "queue_to_send"),
            "submit_to_final": median_round_summary(rows, "submit_to_final"),
        }
    result = {
        "schema": "flle.ch06-four-order-paths.v7",
        "run_id": args.run_id,
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "phase_order": [list(row) for row in BALANCED_PHASE_ORDER],
        "limitations": [
            "DPDK owns the X2522 through vfio-pci and cannot be interleaved per order with the three sfc paths; the controller switches mode when DPDK reaches its balanced position.",
            "The 12 distinct ordered predecessor pairs occur once on within-round edges. The three cross-round edges necessarily repeat existing pairs, so the complete sequence guarantees only that all 12 possible predecessors occur at least once.",
            "Each transport cell begins with configured warmup orders to reduce carryover before measured submissions; this does not claim to eliminate carryover.",
            "The first warmup establishes traffic, then a PID-bound path witness is captured; the remaining warmups separate that heavyweight probe from measured submissions.",
            "The Gateway and its one-second status poll are stopped during formal cells; mode changes and receipt gates use the local fixed controller directly.",
            "During the sfc phase all three clients and their Exchange sessions remain online; the two paths not being sampled sleep on DEQUE_CV.",
            "During the DPDK phase the sfc clients are stopped and the DPDK client runs exclusively.",
            "DEQUE_CV fixes the application handoff; TCPDirect and F-Stack still poll their network reactors.",
            "OpenOnload uses --profile=latency, so its result combines the accelerated user-space path with profile polling.",
        ],
        "runtime_contract": {
            "application_handoff": "DEQUE_CV",
            "data_cpu": 2,
            "management_cpu": 3,
            "dpdk_bridge_cpu": 3,
            "fstack_idle_sleep_us": 0,
            "fstack_pkt_tx_delay_us": 0,
            "sfc_hugepages_2mb": 128,
            "dpdk_hugepages_2mb": 256,
            "onload_profile": "latency",
            "order_design": "POSITION_AND_WITHIN_ROUND_FIRST_ORDER_PREDECESSOR_BALANCED_4X4",
            "round_aggregation": "DESCRIPTIVE_MEDIAN_OF_4_ROUND_STATISTICS_HALF_UP_TO_INTEGER_NS",
            "order_balance": order_balance,
            "final_data_plane_mode": "SFC",
            "formal_gateway_state": "STOPPED_DURING_MEASUREMENT_RESTARTED_AFTERWARD",
            "native_path_receipts": "PRE_AND_POST_NATIVE_ORIGINALS_OUTSIDE_TIMER",
        },
        "parameters": {
            "warmup_per_round": args.warmup,
            "samples_per_round": args.samples,
            "rounds": args.rounds,
        },
        "exchange_ledger_gate": exchange_ledger_gate,
        "submission_identity": submission_identity,
        "sample_identity": sample_identity,
        "summary": summary,
        "rounds": results,
    }
    destination = args.output_root / args.run_id / "four-path-comparison"
    with tempfile.TemporaryDirectory(
        prefix=f"flle-native-receipts-{args.run_id}-"
    ) as temporary:
        fetched_root = fetch_native_receipt_tree(
            args.trader_host,
            args.run_id,
            Path(temporary) / "fetch",
        )
        result["native_receipt_gate"] = validate_downloaded_native_receipts(
            results, fetched_root
        )
        write_report(
            destination,
            result,
            native_receipts_source=fetched_root,
            sealed_program_sources={
                "transport_labctl.sh": control_script,
                "measure_four_transports.py": Path(__file__).resolve(),
                "analyze_four_transport_raw.py": (
                    Path(__file__).resolve().with_name(
                        "analyze_four_transport_raw.py"
                    )
                ),
            },
        )
    print("\n===== 描述性副表：同一订单合同的四轮统计量中位数 =====")
    print("路径                    send→final P50    P95       P99        queue→final P50")
    for key in TRANSPORT_ORDER:
        values = summary[key]
        print(
            f"{values['label']:<24}"
            f"{values['order_rtt']['p50_ns']:>10} ns  "
            f"{values['order_rtt']['p95_ns']:>8} ns  "
            f"{values['order_rtt']['p99_ns']:>8} ns  "
            f"{values['submit_to_final']['p50_ns']:>12} ns"
        )
    print("合同：1 股可成交 IOC；SoupBinTCP/OUCH；逐笔单飞；DEQUE_CV；数据 CPU 2；辅助 CPU 3")
    print(
        "全部提交身份："
        f"submitted total=unique={submission_identity['total']}；"
        f"result_files={len(submission_identity['per_round_ranges'])}"
    )
    print(
        "正式样本身份："
        f"measured total=unique={sample_identity['total']}；"
        "submission_to_raw=ORDER_AND_SET_EXACT"
    )
    print(
        "交易所账本硬门："
        f"before={exchange_ledger_gate['before']} "
        f"after={exchange_ledger_gate['after']} "
        f"delta=expected={exchange_ledger_gate['delta']}"
    )
    print(
        "顺序平衡：每条路径每位置一次；12 种行内有序前序各一次；"
        "每格 warmup 只减弱 carryover；末尾 SFC"
    )
    print(
        "原生收据：16 格 pre/post 共 32 套；原件、摘要和执行脚本均进 SHA；"
        "重型探针不进计时样本"
    )
    print("边界：DPDK 独占 VFIO 分阶段测；Onload latency profile、ZF/F-Stack reactor 会轮询")
    print(f"evidence={destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
