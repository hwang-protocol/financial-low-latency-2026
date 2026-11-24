#!/usr/bin/env python3
"""Build the balance-preserving Chapter 06 table from fixed four-path raw files."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
import measure_four_transports as measure


SAMPLE_FIELDS = {
    "order_rtt": "order_rtt_ns",
    "queue_to_send": "queue_to_send_ns",
    "submit_to_final": "submit_to_final_ns",
}
EXPECTED_SOURCE_SCHEMA = "flle.ch06-four-order-paths.v13"
ANALYSIS_SCHEMA = "flle.ch06-four-order-paths-balanced-analysis.v11"
PRESEND_SPIKE_THRESHOLD_NS = 19_000_000
EXPECTED_OBSERVER_ABSENCE = [
    {"host": "10.1.1.101", "port": 8088, "state": "ABSENT"},
    {"host": "10.1.1.2", "port": 48606, "state": "ABSENT"},
]


def validate_observer_absence_contract(
    runtime_contract: Any,
) -> list[dict[str, Any]]:
    """Require the exact two endpoint-absence observations from run start."""

    if not isinstance(runtime_contract, dict):
        raise RuntimeError("runtime contract is missing")
    observed = runtime_contract.get("observer_absence_before_measurement")
    if observed != EXPECTED_OBSERVER_ABSENCE:
        raise RuntimeError(
            "observer absence contract is not exact: "
            f"observed={observed!r} expected={EXPECTED_OBSERVER_ABSENCE!r}"
        )
    return [dict(item) for item in observed]


def verify_source_manifest(source: Path) -> str:
    if source.is_symlink():
        raise RuntimeError("formal source directory must not be a symlink")
    manifest_path = source / "SHA256SUMS"
    if manifest_path.is_symlink():
        raise RuntimeError("formal SHA256SUMS must not be a symlink")
    lines = manifest_path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise RuntimeError("source SHA256SUMS is empty")
    observed_paths: set[str] = set()
    for line in lines:
        digest, relative = line.split("  ", 1)
        if re.fullmatch(r"[0-9a-f]{64}", digest) is None:
            raise RuntimeError(f"invalid source SHA256 digest: {digest!r}")
        relative_path = Path(relative)
        if (
            relative_path.is_absolute()
            or ".." in relative_path.parts
            or relative in observed_paths
        ):
            raise RuntimeError(f"unsafe or duplicate source manifest path: {relative!r}")
        observed_paths.add(relative)
        target = source / relative
        path_chain = [
            source.joinpath(*relative_path.parts[:index])
            for index in range(1, len(relative_path.parts) + 1)
        ]
        if any(candidate.is_symlink() for candidate in path_chain):
            raise RuntimeError(f"formal source file must not be a symlink: {relative}")
        observed = hashlib.sha256(target.read_bytes()).hexdigest()
        if observed != digest:
            raise RuntimeError(
                f"source hash mismatch: path={relative} expected={digest} "
                f"observed={observed}"
            )
    return hashlib.sha256(manifest_path.read_bytes()).hexdigest()


def require_source_manifest_unchanged(source: Path, expected_sha256: str) -> None:
    observed = verify_source_manifest(source)
    if observed != expected_sha256:
        raise RuntimeError("formal source manifest changed during analysis")


def require_exact_source_manifest_paths(
    source: Path, expected_paths: set[str]
) -> None:
    observed_paths = {
        line.split("  ", 1)[1]
        for line in (source / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    }
    if observed_paths != expected_paths:
        raise RuntimeError(
            "formal SHA256SUMS file set is not exact: "
            f"missing={sorted(expected_paths - observed_paths)} "
            f"unexpected={sorted(observed_paths - expected_paths)}"
        )


def verify_execution_provenance(
    source: Path, original: dict[str, Any]
) -> list[dict[str, Any]]:
    expected_paths = {
        "provenance/transport_labctl.sh",
        "provenance/measure_four_transports.py",
        "provenance/analyze_four_transport_raw.py",
    }
    provenance = original.get("execution_provenance")
    rows = provenance.get("sealed_programs") if isinstance(provenance, dict) else None
    if not isinstance(provenance, dict) or provenance.get("capture_contract") != (
        "START_SNAPSHOT_END_BYTES_UNCHANGED"
    ):
        raise RuntimeError("execution provenance has no start/end byte-stability gate")
    observed_paths = {
        row.get("path") for row in rows if isinstance(row, dict)
    } if isinstance(rows, list) else set()
    if (
        not isinstance(rows, list)
        or len(rows) != len(expected_paths)
        or observed_paths != expected_paths
    ):
        raise RuntimeError("execution provenance does not seal all three programs")
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"path", "sha256", "bytes"}:
            raise RuntimeError(f"invalid sealed program entry: {row!r}")
        payload = (source / row["path"]).read_bytes()
        if (
            hashlib.sha256(payload).hexdigest() != row["sha256"]
            or len(payload) != row["bytes"]
        ):
            raise RuntimeError(f"sealed program mismatch: {row['path']}")
    return rows


def verify_live_analysis_programs(original: dict[str, Any]) -> dict[str, str]:
    """Bind both executable analysis files to the bytes sealed by the RUN."""

    rows = original.get("execution_provenance", {}).get("sealed_programs", [])
    sealed = {
        row.get("path"): row
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("path"), str)
    }
    live_paths = {
        "analysis_script_sha256": (
            "provenance/analyze_four_transport_raw.py",
            Path(__file__).resolve(),
        ),
        "measurement_script_sha256": (
            "provenance/measure_four_transports.py",
            Path(measure.__file__).resolve(),
        ),
    }
    digests: dict[str, str] = {}
    for output_name, (sealed_name, live_path) in live_paths.items():
        row = sealed.get(sealed_name)
        digest = hashlib.sha256(live_path.read_bytes()).hexdigest()
        if not isinstance(row, dict) or row.get("sha256") != digest:
            role = "analyzer" if output_name.startswith("analysis_") else "measure module"
            raise RuntimeError(
                f"live {role} differs from the program sealed by the formal run; "
                "run provenance/analyze_four_transport_raw.py for an exact reproduction"
            )
        digests[output_name] = digest
    return digests


def pooled_metric_summary(
    rounds: list[dict[str, Any]], metric: str
) -> dict[str, int | str]:
    sample_field = SAMPLE_FIELDS[metric]
    per_cell_counts = [len(row["raw_samples"]) for row in rounds]
    if len(set(per_cell_counts)) != 1 or not per_cell_counts or per_cell_counts[0] < 1:
        raise RuntimeError(
            f"{metric} cells are not equally weighted: counts={per_cell_counts}"
        )
    values = [
        int(sample[sample_field])
        for row in rounds
        for sample in row["raw_samples"]
    ]
    summary: dict[str, int | str] = measure.summarize(values)
    summary.update(
        {
            "cells": len(rounds),
            "samples_per_cell": per_cell_counts[0],
            "aggregation": "POOLED_EQUAL_CELL_COUNTS",
        }
    )
    return summary


def equal_cell_mean_summary(
    rounds: list[dict[str, Any]], metric: str
) -> dict[str, int | str]:
    fields = ("p50_ns", "p95_ns", "p99_ns", "mean_ns")
    result: dict[str, int | str] = {
        field: math.floor(
            sum(int(row[metric][field]) for row in rounds) / len(rounds) + 0.5
        )
        for field in fields
    }
    result["max_ns"] = max(int(row[metric]["max_ns"]) for row in rounds)
    result["cells"] = len(rounds)
    result["aggregation"] = "EQUAL_CELL_MEAN_OF_ROUND_STATISTICS_HALF_UP"
    result["max_aggregation"] = "GLOBAL_MAX_ACROSS_4_CELLS_NOT_A_CELL_MEAN"
    return result


def _read_manifest_original(
    source: Path, item: dict[str, Any], path: Path
) -> tuple[Path, str]:
    relative = item.get("path")
    if not isinstance(relative, str):
        raise RuntimeError(f"native manifest path is invalid: {path}")
    target = source / relative
    try:
        target.relative_to(source)
    except ValueError as error:
        raise RuntimeError(f"native manifest escaped source: {relative}") from error
    payload = target.read_bytes()
    observed = hashlib.sha256(payload).hexdigest()
    if observed != item.get("sha256") or len(payload) != item.get("bytes"):
        raise RuntimeError(
            f"native original does not match compact manifest: {relative}"
        )
    return target, payload.decode("utf-8", errors="strict")


def _parse_key_value_lines(text: str, source_name: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        if "=" not in line:
            raise RuntimeError(f"invalid key/value line in {source_name}: {line!r}")
        key, value = line.split("=", 1)
        if not key or key in values:
            raise RuntimeError(f"duplicate/empty key in {source_name}: {key!r}")
        values[key] = value
    return values


def _parse_exchange_server_endpoint_observations(
    text: str, exchange_pid: int, source_name: str
) -> list[dict[str, str]]:
    """Return target-port endpoints observed under the current Exchange PID.

    The Exchange can retain more than one established connection from the
    trader host across VFIO transitions.  This is server-side observation, not
    a binding between any one endpoint and the DPDK client PID.
    """

    observations: list[dict[str, str]] = []
    for line in text.splitlines():
        fields = line.split()
        if (
            len(fields) >= 5
            and fields[2] == "20.1.1.1:43120"
            and re.fullmatch(r"20\.1\.1\.2:[0-9]+", fields[3])
            and f"pid={exchange_pid}," in line
        ):
            observations.append(
                {
                    "local_endpoint": fields[2],
                    "peer_endpoint": fields[3],
                    "ss_line": line,
                }
            )
    if not observations:
        raise RuntimeError(
            "DPDK Exchange-side current PID has no target endpoint: "
            f"{source_name}"
        )
    return observations


def _parse_exchange_listener_observations(
    process: dict[str, str], exchange_pid: int, source_name: str
) -> list[str]:
    try:
        listener_count = int(process["listener_count"])
    except (KeyError, ValueError) as error:
        raise RuntimeError(
            f"invalid Exchange listener count in {source_name}"
        ) from error
    listener_items = sorted(
        (
            int(match.group(1)),
            value,
        )
        for key, value in process.items()
        if (match := re.fullmatch(r"listener_ss_line_([0-9]+)", key))
    )
    if listener_count < 1 or len(listener_items) != listener_count:
        raise RuntimeError(f"incomplete Exchange listener snapshot: {source_name}")
    observations = []
    for expected, (number, line) in enumerate(listener_items, start=1):
        if (
            number != expected
            or "20.1.1.1:43120" not in line.split()
            or f"pid={exchange_pid}," not in line
        ):
            raise RuntimeError(f"invalid Exchange listener snapshot: {source_name}")
        observations.append(line)
    return observations


def _parse_exact_argv(
    process: dict[str, str], source_name: str
) -> list[str]:
    try:
        count = int(process["argv_count"])
    except (KeyError, ValueError) as error:
        raise RuntimeError(f"invalid argv_count in {source_name}") from error
    argv_keys = {
        key for key in process if re.fullmatch(r"argv_[0-9]{2}", key)
    }
    expected_keys = {f"argv_{index:02d}" for index in range(count)}
    if count < 1 or count > 99 or argv_keys != expected_keys:
        raise RuntimeError(
            f"argv entries are not contiguous/exact in {source_name}"
        )
    return [process[f"argv_{index:02d}"] for index in range(count)]


def _validate_native_state_contract(
    state: dict[str, Any], key: str, source_name: str
) -> dict[str, Any]:
    """Independently rebuild the runtime contract from native STATE."""

    expected_label = {
        "SOCKET": "POSIX_SOCKET",
        "OPENONLOAD": "OPENONLOAD",
        "TCPDIRECT": "TCPDIRECT_ZF",
        "DPDK": "DPDK_FSTACK",
    }[key]
    expected_market = (
        "CENTRAL_GATEWAY_BOOK" if key == "DPDK" else "COMMON_GATEWAY_BOOK"
    )
    expected_fields = {
        "status": "ONLINE",
        "role": "MANUAL",
        "market_protocol": expected_market,
        "order_protocol": "OUCH_5.0_OVER_SOUPBINTCP",
        "order_transport": expected_label,
        "market_receiver_ready": False,
    }
    if any(state.get(name) != value for name, value in expected_fields.items()):
        raise RuntimeError(
            f"native STATE business/transport contract failed: {source_name}"
        )
    if state.get("paper_epoch") != 1:
        raise RuntimeError(f"native STATE paper epoch is not fixed: {source_name}")

    integer_fields = (
        "user_ref_base", "user_ref_span", "user_ref_end_exclusive",
        "user_ref_next",
    )
    if any(
        isinstance(state.get(field), bool)
        or not isinstance(state.get(field), int)
        for field in integer_fields
    ):
        raise RuntimeError(f"native STATE user_ref fields are invalid: {source_name}")
    base = state["user_ref_base"]
    span = state["user_ref_span"]
    end = state["user_ref_end_exclusive"]
    next_ref = state["user_ref_next"]
    if (
        base < 1
        or span < 1
        or end != base + span
        or not base <= next_ref <= end
        or end > 4294967296
    ):
        raise RuntimeError(
            f"native STATE user_ref namespace is inconsistent: {source_name}"
        )

    stats = state.get("stats")
    if not isinstance(stats, dict) or any(
        isinstance(stats.get(field), bool)
        or not isinstance(stats.get(field), int)
        or stats[field] < 1
        for field in ("orders", "fills")
    ):
        raise RuntimeError(f"native STATE has no completed order/fill: {source_name}")

    software = state.get("software_latency")
    if not isinstance(software, dict):
        raise RuntimeError(f"native STATE lacks software_latency: {source_name}")
    expected_engine = {
        "SOCKET": "KERNEL_SOCKET",
        "OPENONLOAD": "ONLOAD_USER_STACK",
        "TCPDIRECT": "ZF_REACTOR_POLL",
        "DPDK": "FSTACK_POLL",
    }[key]
    observed_engine = software.get(
        "network_engine", software.get("network_reactor")
    )
    if (
        software.get("queue_mode") != "DEQUE_CV"
        or software.get("queue_locked") is not True
        or software.get("queue_full_drops") != 0
        or observed_engine != expected_engine
    ):
        raise RuntimeError(
            f"native STATE queue/network-engine contract failed: {source_name}"
        )

    expected_threads = {"order": (2, 1), "management": (3, 1)}
    if key == "DPDK":
        expected_threads["bridge"] = (3, 1)
    placement: dict[str, int] = {}
    for role, (cpu, allowed_count) in expected_threads.items():
        values = {
            "tid": software.get(f"{role}_thread_tid"),
            "cpu": software.get(f"{role}_thread_cpu"),
            "allowed_count": software.get(f"{role}_thread_allowed_count"),
        }
        if (
            isinstance(values["tid"], bool)
            or not isinstance(values["tid"], int)
            or values["tid"] < 1
            or values["cpu"] != cpu
            or values["allowed_count"] != allowed_count
        ):
            raise RuntimeError(
                f"native STATE {role} thread placement failed: {source_name}"
            )
        placement[f"{role}_thread_tid"] = values["tid"]
        placement[f"{role}_thread_cpu"] = values["cpu"]
        placement[f"{role}_thread_allowed_count"] = values["allowed_count"]

    if key == "TCPDIRECT":
        nagle = {
            "applicable": False,
            "tcp_nodelay": None,
            "verification": "ZF_API_NO_POSIX_TCP_NODELAY",
        }
        if (
            state.get("tcp_nodelay") is not None
            or state.get("nagle_semantics") != nagle["verification"]
        ):
            raise RuntimeError(
                f"native TCPDirect Nagle contract failed: {source_name}"
            )
    else:
        expected_semantics = (
            "FSTACK_GETSOCKOPT_VERIFIED"
            if key == "DPDK"
            else "POSIX_CONNECT_GETSOCKOPT_VERIFIED"
        )
        if (
            state.get("tcp_nodelay") is not True
            or state.get("nagle_semantics") != expected_semantics
        ):
            raise RuntimeError(
                f"native TCP_NODELAY contract failed: {source_name}"
            )
        nagle = {
            "applicable": True,
            "tcp_nodelay": True,
            "verification": "RUNTIME_GETSOCKOPT_NONZERO",
        }
    if key == "DPDK" and state.get("heartbeat_enabled") is not False:
        raise RuntimeError(
            f"native DPDK heartbeat must be disabled: {source_name}"
        )

    measurement = state.get("measurement_latency")
    if not isinstance(measurement, dict) or any(
        isinstance(measurement.get(field), bool)
        or not isinstance(measurement.get(field), int)
        or measurement[field] < 0
        for field in ("generation", "ready_samples")
    ):
        raise RuntimeError(
            f"native measurement generation is invalid: {source_name}"
        )
    return {
        "transport_label": expected_label,
        "market_protocol": expected_market,
        "network_engine": expected_engine,
        "queue_mode": "DEQUE_CV",
        "queue_locked": True,
        "queue_full_drops": 0,
        "heartbeat_enabled": False if key == "DPDK" else None,
        "nagle": nagle,
        "user_ref_base": base,
        "user_ref_span": span,
        "user_ref_end_exclusive": end,
        "user_ref_next": next_ref,
        "measurement_generation": measurement["generation"],
        "measurement_ready_samples": measurement["ready_samples"],
        "thread_placement": placement,
    }


def _validate_client_process_contract(
    process: dict[str, str], state_contract: dict[str, Any], key: str,
    pid: int, exe_path: str, source_name: str,
) -> dict[str, Any]:
    """Rebuild exact client argv, listener, environment, and /proc affinity."""

    run_dir = Path(exe_path).parents[3]
    observed_argv = _parse_exact_argv(process, source_name)
    if key == "DPDK":
        expected_argv = [
            exe_path,
            "--conf", (run_dir / "dpdk-session/f-stack.effective.ini").as_posix(),
            "--proc-type=primary",
            "--proc-id=0",
        ]
    else:
        port = {
            "SOCKET": "48122",
            "OPENONLOAD": "48123",
            "TCPDIRECT": "48124",
        }[key]
        prefix = {
            "SOCKET": "SOCK",
            "OPENONLOAD": "ONLD",
            "TCPDIRECT": "TCPD",
        }[key]
        expected_argv = [
            exe_path,
            "--role", "MANUAL",
            "--data-ip", "20.1.1.2",
            "--exchange-data-ip", "20.1.1.1",
            "--management-ip", "10.1.1.2",
            "--telemetry-host", "10.1.1.101",
            "--book-checkpoint", (run_dir / "opening-book.checkpoint").as_posix(),
            "--market-receiver", "0",
            "--order-queue", "DEQUE_CV",
            "--lock-order-queue", "1",
            "--order-cpu", "2",
            "--management-cpu", "3",
            "--management-port", port,
            "--user-ref-base", str(state_contract["user_ref_base"]),
            "--user-ref-span", str(state_contract["user_ref_span"]),
            "--clordid-prefix", prefix,
            "--order-transport-label", state_contract["transport_label"],
        ]
    if observed_argv != expected_argv:
        raise RuntimeError(
            f"native client argv contract is not exact: {source_name}"
        )

    management_port = {
        "SOCKET": 48122,
        "OPENONLOAD": 48123,
        "TCPDIRECT": 48124,
        "DPDK": 48125,
    }[key]
    try:
        listener_count = int(process["management_listener_count"])
    except (KeyError, ValueError) as error:
        raise RuntimeError(
            f"invalid management listener count: {source_name}"
        ) from error
    listener_items = sorted(
        (int(match.group(1)), value)
        for name, value in process.items()
        if (match := re.fullmatch(r"management_listener_ss_line_([0-9]+)", name))
    )
    if (
        listener_count != 1
        or len(listener_items) != 1
        or listener_items[0][0] != 1
        or f"10.1.1.2:{management_port}" not in listener_items[0][1].split()
        or f"pid={pid}," not in listener_items[0][1]
    ):
        raise RuntimeError(
            f"native management listener/PID contract failed: {source_name}"
        )

    placement = state_contract["thread_placement"]
    roles = ("order", "management", "bridge") if key == "DPDK" else (
        "order", "management"
    )
    for role in roles:
        tid = placement[f"{role}_thread_tid"]
        cpu = placement[f"{role}_thread_cpu"]
        if (
            process.get(f"thread_{role}_tid") != str(tid)
            or process.get(f"thread_{role}_cpus_allowed_list") != str(cpu)
            or not process.get(f"thread_{role}_name")
        ):
            raise RuntimeError(
                f"native /proc {role} thread contract failed: {source_name}"
            )
    if process.get("thread_management_name") != "flle-mgmt":
        raise RuntimeError(
            f"native management thread name is invalid: {source_name}"
        )
    if key != "DPDK" and process.get("thread_order_name") != "flle-order":
        raise RuntimeError(f"native order thread name is invalid: {source_name}")
    if key == "DPDK" and process.get("thread_bridge_name") != "flle-bridge":
        raise RuntimeError(f"native bridge thread name is invalid: {source_name}")

    try:
        receipt_generation = int(process["measurement_generation"])
        receipt_ready = int(process["measurement_ready_samples"])
    except (KeyError, ValueError) as error:
        raise RuntimeError(
            f"invalid process measurement receipt: {source_name}"
        ) from error
    if (
        receipt_generation != state_contract["measurement_generation"]
        or receipt_ready != state_contract["measurement_ready_samples"]
    ):
        raise RuntimeError(
            f"process/STATE measurement receipt differs: {source_name}"
        )

    if key == "OPENONLOAD":
        expected_environment = {
            "env_EF_POLL_USEC": "100000",
            "env_EF_TCP_FASTSTART_INIT": "0",
            "env_EF_TCP_FASTSTART_IDLE": "0",
        }
    elif key == "DPDK":
        lease_token = process.get("env_FLLE_DPDK_LEASE_TOKEN", "")
        if re.fullmatch(r"[A-Za-z0-9._-]+", lease_token) is None:
            raise RuntimeError(
                f"native DPDK lease token environment is invalid: {source_name}"
            )
        expected_environment = {
            "env_FLLE_DPDK_GATE_PID_FILE":
                (run_dir / "trader-dpdk-gate.pid").as_posix(),
            "env_FLLE_DPDK_LEASE_TOKEN": lease_token,
            "env_FLLE_DPDK_DEADMAN": "1800",
            "env_FLLE_DPDK_USER_REF_BASE": str(state_contract["user_ref_base"]),
            "env_FLLE_DPDK_USER_REF_SPAN": str(state_contract["user_ref_span"]),
            "env_FLLE_MANAGEMENT_PORT": "48125",
            "env_FLLE_TELEMETRY_HOST": "10.1.1.101",
            "env_FLLE_DPDK_HELPER_CPU": "3",
            "env_FLLE_DPDK_HEARTBEAT": "0",
            "env_FLLE_DPDK_DATA_IP": "<ABSENT>",
            "env_FLLE_EXCHANGE_DATA_IP": "<ABSENT>",
            "env_FLLE_ORDER_PORT": "<ABSENT>",
            "env_FLLE_MANAGEMENT_IP": "<ABSENT>",
            "env_FLLE_TELEMETRY_PORT": "<ABSENT>",
        }
    else:
        expected_environment = {}
    if any(process.get(name) != value
           for name, value in expected_environment.items()):
        raise RuntimeError(
            f"native process environment contract failed: {source_name}"
        )
    return {
        "argv": observed_argv,
        "management_listener": listener_items[0][1],
        "thread_affinity": {
            role: process[f"thread_{role}_cpus_allowed_list"] for role in roles
        },
        "environment": expected_environment,
    }


def _parse_onload_native(
    text: str, pid: int, source_name: str
) -> tuple[list[str], dict[str, int]]:
    lines = text.splitlines()
    headers = [
        (index, int(match.group(1)))
        for index, line in enumerate(lines)
        if (match := re.match(r"^  Onload .* pid=([0-9]+) ", line))
    ]
    target_headers = [item for item in headers if item[1] == pid]
    if len(target_headers) != 1:
        raise RuntimeError(
            f"Onload target PID stack is not unique in {source_name}: pid={pid}"
        )
    stack_start = target_headers[0][0]
    stack_end = next(
        (index for index, _ in headers if index > stack_start), len(lines)
    )
    endpoint_pattern = re.compile(
        r"^TCP .*lcl=20\.1\.1\.2:[0-9]+ "
        r"rmt=20\.1\.1\.1:43120 ESTABLISHED$"
    )
    endpoints = [
        index
        for index in range(stack_start + 1, stack_end)
        if endpoint_pattern.match(lines[index])
    ]
    if len(endpoints) != 1:
        raise RuntimeError(
            f"Onload target endpoint is not unique in PID stack: {source_name}"
        )
    tcp_start = endpoints[0]
    tcp_end = next(
        (
            index
            for index in range(tcp_start + 1, stack_end)
            if lines[index].startswith("TCP ") or lines[index].startswith("-----")
        ),
        stack_end,
    )
    valid = [
        line for line in lines[tcp_start:tcp_end] if "Onloaded(Valid)" in line
    ]
    if len(valid) != 1:
        raise RuntimeError(
            "Onload endpoint and Onloaded(Valid) are not in one unique TCP "
            f"block: {source_name}"
        )
    ctpio_packets = [
        line
        for line in lines[stack_start:stack_end]
        if re.fullmatch(r"ctpio_pkts: [0-9]+", line)
    ]
    ctpio_fallbacks = [
        line
        for line in lines[stack_start:stack_end]
        if re.fullmatch(r"ctpio_dma_fallbacks: [0-9]+", line)
    ]
    if len(ctpio_packets) != 1 or len(ctpio_fallbacks) != 1:
        raise RuntimeError(
            f"Onload stack-level CTPIO counters are not unique: {source_name}"
        )
    packet_count = int(ctpio_packets[0].split(": ", 1)[1])
    fallback_count = int(ctpio_fallbacks[0].split(": ", 1)[1])
    return (
        [
            lines[stack_start],
            lines[tcp_start],
            valid[0],
            ctpio_packets[0],
            ctpio_fallbacks[0],
        ],
        {
            "ctpio_pkts": packet_count,
            "ctpio_dma_fallbacks": fallback_count,
        },
    )


def validate_native_receipt_from_originals(
    source: Path,
    row: dict[str, Any],
    phase: str,
    path: Path,
) -> dict[str, Any]:
    """Rebuild path identity from native files; no controller boolean is trusted."""

    key = str(row["transport"])
    round_number = int(row["round"])
    position = int(row["position"])
    manifest = row["cell_audit"]["native_receipts"].get(phase)
    measure.validate_native_receipt_manifest(
        manifest, key, round_number, position, phase
    )
    originals: dict[str, str] = {}
    by_path: dict[str, str] = {}
    for item in manifest["files"]:
        target, text = _read_manifest_original(source, item, path)
        originals[target.name] = text
        by_path[item["path"]] = text
    for excerpt in manifest["matching_excerpts"]:
        if excerpt["text"] not in by_path[excerpt["path"]].splitlines():
            raise RuntimeError(
                f"stored matching excerpt is not an exact native line: {path}"
            )

    process = _parse_key_value_lines(originals["process.txt"], "process.txt")
    try:
        pid = int(process["pid"])
        start_ticks = int(process["start_ticks"])
    except (KeyError, ValueError) as error:
        raise RuntimeError(f"invalid native process identity: {path}") from error
    if pid < 1 or start_ticks < 1 or not process.get("boot_id"):
        raise RuntimeError(f"invalid native process identity values: {path}")
    expected_binary = (
        "flle-trader-tcpdirect"
        if key == "TCPDIRECT"
        else "flle-trader-dpdk"
        if key == "DPDK"
        else "flle-trader"
    )
    expected_exe_suffix = (
        "/transport-runtime/flle-ch05-four-path/bin/" + expected_binary,
        "/transport-runtime/flle-ch06-four-path/bin/" + expected_binary,
    )
    exe_path = process.get("exe_path", "")
    exe_sha256 = process.get("exe_sha256", "")
    exe_manifest_sha256 = process.get("exe_manifest_sha256", "")
    checkpoint_sha256 = process.get("checkpoint_sha256", "")
    input_receipt = _parse_key_value_lines(
        originals["data-plane-input.receipt"], "data-plane-input.receipt"
    )
    sealed_input_fields = (
        "runtime_sha256",
        "runtime_manifest_sha256",
        "opening_book_sha256",
        "itch_sha256",
    )
    if (
        not exe_path.endswith(expected_exe_suffix)
        or re.fullmatch(r"[0-9a-f]{64}", exe_sha256) is None
        or exe_sha256 != exe_manifest_sha256
        or any(
            re.fullmatch(r"[0-9a-f]{64}", input_receipt.get(field, ""))
            is None
            for field in sealed_input_fields
        )
        or checkpoint_sha256 != input_receipt.get("opening_book_sha256")
    ):
        raise RuntimeError(
            f"native client runtime executable identity is not sealed: {path}"
        )
    runtime_identity = {
        "exe_path": exe_path,
        "exe_sha256": exe_sha256,
        "exe_manifest_sha256": exe_manifest_sha256,
        "runtime_archive_sha256": input_receipt["runtime_sha256"],
        "runtime_manifest_sha256": input_receipt[
            "runtime_manifest_sha256"
        ],
        "checkpoint_sha256": checkpoint_sha256,
        "itch_sha256": input_receipt["itch_sha256"],
    }

    state = json.loads(originals["state.json"])
    state_contract = _validate_native_state_contract(
        state, key, f"{path} {phase} state.json"
    )
    process_contract = _validate_client_process_contract(
        process,
        state_contract,
        key,
        pid,
        exe_path,
        f"{path} {phase} process.txt",
    )
    state_orders = state["stats"]["orders"]
    order_thread_tid = state_contract["thread_placement"]["order_thread_tid"]

    independently_matched: list[str] = []
    hardware_witness: dict[str, int] | None = None
    server_endpoint_witness: dict[str, Any] | None = None
    path_health_witness: dict[str, Any] | None = None
    ownership_lease_witness: dict[str, Any] | None = None
    if key == "SOCKET":
        endpoint = [
            line
            for line in originals["ss-established.txt"].splitlines()
            if "20.1.1.2:" in line
            and "20.1.1.1:43120" in line
            and f"pid={pid}," in line
        ]
        if len(endpoint) != 1:
            raise RuntimeError(f"Socket PID/endpoint match is not unique: {path}")
        independently_matched = endpoint
        counter_kind = "trader_orders"
        counter_value = state_orders
    elif key == "OPENONLOAD":
        independently_matched, hardware_witness = _parse_onload_native(
            originals["onload-stackdump.txt"], pid, "onload-stackdump.txt"
        )
        counter_kind = "trader_orders"
        counter_value = state_orders
    elif key == "TCPDIRECT":
        list_matches = []
        for line in originals["zf-list.txt"].splitlines():
            match = re.fullmatch(
                r"flle-tcpdirect\s+id=([0-9]+)\s+pid=([0-9]+)", line
            )
            if match and int(match.group(2)) == pid:
                list_matches.append((line, int(match.group(1))))
        if len(list_matches) != 1:
            raise RuntimeError(f"ZF stack/PID match is not unique: {path}")
        attr_lines = originals["zf-attr.txt"].splitlines()
        if attr_lines.count("ctpio=3") != 1 or attr_lines.count("ctpio_mode=sf-np") != 1:
            raise RuntimeError(f"ZF CTPIO parameter contract failed: {path}")
        endpoint_pattern = re.compile(
            r"^TCP flle-tcpdirect:[0-9]+ lcl=20\.1\.1\.2:[0-9]+ "
            r"rmt=20\.1\.1\.1:43120 .*ESTABLISHED$"
        )
        endpoints = [
            line for line in originals["zf-dump.txt"].splitlines()
            if endpoint_pattern.match(line)
        ]
        txq_lines = [
            line for line in originals["zf-dump.txt"].splitlines()
            if line.startswith("  txq:") and re.search(r"\badded=[0-9]+\b", line)
        ]
        if len(endpoints) != 1 or len(txq_lines) != 1:
            raise RuntimeError(f"ZF endpoint/txq native contract failed: {path}")
        retransmit_match = re.search(r"\bretransmits=([0-9]+)\b", endpoints[0])
        endpoint_identity = re.match(
            r"^TCP ([^ ]+) lcl=([^ ]+) rmt=([^ ]+) ", endpoints[0]
        )
        if retransmit_match is None or endpoint_identity is None:
            raise RuntimeError(f"ZF endpoint has no retransmits counter: {path}")
        path_health_witness = {
            "scope": "ZF_ENDPOINT_CUMULATIVE_RETRANSMITS",
            "stack_endpoint": endpoint_identity.group(1),
            "local_endpoint": endpoint_identity.group(2),
            "remote_endpoint": endpoint_identity.group(3),
            "retransmits": int(retransmit_match.group(1)),
            "not_mapped_to_latency_samples": True,
        }
        counter_value = int(
            re.search(r"\badded=([0-9]+)\b", txq_lines[0]).group(1)
        )
        counter_kind = "zf_txq_added"
        independently_matched = [
            list_matches[0][0],
            "ctpio=3",
            "ctpio_mode=sf-np",
            endpoints[0],
            txq_lines[0],
        ]
    else:
        gate = _parse_key_value_lines(
            originals["gate-start.receipt"], "gate-start.receipt"
        )
        lease = _parse_key_value_lines(
            originals["lease-start.receipt"], "lease-start.receipt"
        )
        lease_status = _parse_key_value_lines(
            originals["lease-status.txt"], "lease-status.txt"
        )
        gate_fields = (
            "runtime_manifest_sha256",
            "wrapper_sha256",
            "binary_sha256",
            "config_sha256",
        )
        try:
            gate_pid = int(gate["gate_pid"])
        except (KeyError, ValueError) as error:
            raise RuntimeError(f"DPDK ownership gate PID is invalid: {path}") from error
        lease_token = gate.get("lease_token", "")
        expected_lease = {
            "lease_unit": lease.get("lease_unit", ""),
            "lease_seconds": "1800",
            "lease_token": lease_token,
            "recovery_executor": "systemd_timer_independent_of_wrapper",
        }
        if (
            gate_pid < 1
            or gate.get("gate_cpus_allowed_list") != "0"
            or gate.get("runtime_manifest_sha256")
            != input_receipt["runtime_manifest_sha256"]
            or gate.get("binary_sha256") != exe_sha256
            or any(
                re.fullmatch(r"[0-9a-f]{64}", gate.get(field, "")) is None
                for field in gate_fields
            )
            or re.fullmatch(r"[A-Za-z0-9._-]+", lease_token) is None
            or lease != expected_lease
            or re.fullmatch(
                r"flle-x2522-lease-[0-9a-f]{20}",
                lease.get("lease_unit", ""),
            ) is None
            or lease_status != {
                "lease_unit": lease.get("lease_unit", ""),
                "lease_token": lease_token,
                "ownership_state": "OWNED",
                "timer_active": "active",
                "timer_sub": "waiting",
                "service_active": "inactive",
            }
            or process_contract["environment"].get(
                "env_FLLE_DPDK_LEASE_TOKEN"
            ) != lease_token
        ):
            raise RuntimeError(f"DPDK ownership gate identity is not sealed: {path}")
        ownership_lease_witness = {
            "gate_pid": gate_pid,
            "gate_cpus_allowed_list": "0",
            **expected_lease,
            **{
                key: lease_status[key]
                for key in (
                    "ownership_state", "timer_active", "timer_sub",
                    "service_active",
                )
            },
        }
        port_stats = state.get("dpdk_port_stats")
        required_port_fields = (
            "port_id", "ipackets", "opackets", "imissed",
            "ierrors", "oerrors", "rx_nombuf",
        )
        if not isinstance(port_stats, dict) or any(
            type(port_stats.get(field)) is not int or port_stats[field] < 0
            for field in required_port_fields
        ) or port_stats["port_id"] != 0:
            raise RuntimeError(f"DPDK STATE lacks valid rte_eth_stats: {path}")
        queue_full_drops = state.get("software_latency", {}).get(
            "queue_full_drops"
        )
        if type(queue_full_drops) is not int or queue_full_drops != 0:
            raise RuntimeError(f"DPDK application queue drop was nonzero: {path}")
        hardware_witness = {
            field: int(port_stats[field]) for field in required_port_fields
        }
        hardware_witness["queue_full_drops"] = queue_full_drops
        if manifest.get("hardware_counters") != port_stats:
            raise RuntimeError(
                f"DPDK manifest hardware counters differ from STATE: {path}"
            )
        owner = _parse_key_value_lines(originals["owner.txt"], "owner.txt")
        if (
            owner != {
                "driver": "vfio-pci",
                "iommu_group": "7",
                "group_device": "0000:03:00.0",
                "unsafe_noiommu": "N",
            }
        ):
            raise RuntimeError(f"DPDK safe owner contract failed: {path}")
        exchange_process = _parse_key_value_lines(
            originals["exchange-process.txt"], "exchange-process.txt"
        )
        try:
            exchange_pid = int(exchange_process["pid"])
            exchange_start_ticks = int(exchange_process["start_ticks"])
            exchange_argv_count = int(exchange_process["argv_count"])
        except (KeyError, ValueError) as error:
            raise RuntimeError(f"invalid Exchange process identity: {path}") from error
        if (
            exchange_pid < 1
            or exchange_start_ticks < 1
            or not exchange_process.get("boot_id")
        ):
            raise RuntimeError(f"invalid Exchange process identity values: {path}")
        exchange_exe = exchange_process.get("exe_path", "")
        contract = exchange_process.get("exchange_contract", "FROZEN_V13")
        native_exchange = contract == "NATIVE_AB_V1"
        if contract not in ("FROZEN_V13", "NATIVE_AB_V1"):
            raise RuntimeError(f"unknown Exchange runtime contract: {path}")
        if native_exchange:
            if not re.fullmatch(r"/var/tmp/flle-trading-lab-[A-Za-z0-9._-]+/flle-exchange", exchange_exe):
                raise RuntimeError(f"invalid native Exchange path: {path}")
            exchange_run_dir = Path(exchange_exe).parent
            entry = exchange_process.get("exchange_manifest_entry", "").split()
            if entry != [exchange_process.get("exe_sha256"), "flle-exchange"]:
                raise RuntimeError(f"native Exchange manifest entry mismatch: {path}")
        else:
            if not exchange_exe.endswith(("/transport-runtime/flle-ch05-four-path/bin/flle-exchange", "/transport-runtime/flle-ch06-four-path/bin/flle-exchange")):
                raise RuntimeError(f"invalid frozen Exchange path: {path}")
            exchange_run_dir = Path(exchange_exe).parents[3]
        exchange_argv = [
            exchange_process.get(f"argv_{index:02d}", "")
            for index in range(exchange_argv_count)
        ]
        expected_exchange_argv = [
            exchange_exe,
            "--telemetry-host", "10.1.1.101",
            "--replay-file", (exchange_run_dir / "AAPL_NVDA.itch").as_posix(),
            "--book-checkpoint",
            (exchange_run_dir / "opening-book.checkpoint").as_posix(),
            "--market-date", "2026-06-12",
            "--market-mode", "MULTICAST_A" if native_exchange else "UNICAST",
            "--replay-speed", "1",
        ]
        exchange_sha = exchange_process.get("exe_sha256", "")
        generator_sha = exchange_process.get("checkpoint_generator_sha256", "")
        checkpoint_sha = exchange_process.get("checkpoint_sha256", "")
        itch_sha = exchange_process.get("itch_sha256", "")
        if (
            exchange_argv != expected_exchange_argv
            or exchange_sha != exchange_process.get("exe_manifest_sha256")
            or generator_sha
            != exchange_process.get("checkpoint_generator_manifest_sha256")
            or checkpoint_sha != input_receipt["opening_book_sha256"]
            or itch_sha != input_receipt["itch_sha256"]
            or any(
                re.fullmatch(r"[0-9a-f]{64}", value) is None
                for value in (
                    exchange_sha, generator_sha, checkpoint_sha, itch_sha
                )
            )
        ):
            raise RuntimeError(
                f"Exchange runtime/checkpoint identity is not sealed: {path}"
            )
        exchange_listeners = _parse_exchange_listener_observations(
            exchange_process, exchange_pid, "exchange-process.txt"
        )
        exchange_endpoints = _parse_exchange_server_endpoint_observations(
            originals["exchange-ss-established.txt"],
            exchange_pid,
            "exchange-ss-established.txt",
        )
        server_endpoint_witness = {
            "scope": "EXCHANGE_SERVER_OBSERVED_PEER_ENDPOINT",
            "not_a_client_pid_binding": True,
            "host": "10.1.1.1",
            "observed_peer_host": "10.1.1.2",
            "boot_id": exchange_process["boot_id"],
            "pid": exchange_pid,
            "start_ticks": exchange_start_ticks,
            "exe_path": exchange_exe,
            "exe_sha256": exchange_sha,
            "checkpoint_generator_sha256": generator_sha,
            "checkpoint_sha256": checkpoint_sha,
            "itch_sha256": itch_sha,
            "listener_count": len(exchange_listeners),
            "listener_ss_lines": exchange_listeners,
            "endpoint_count": len(exchange_endpoints),
            "observed_endpoints": exchange_endpoints,
        }
        required_log_patterns = (
            ("Using IOMMU type 1", r"Using IOMMU type 1"),
            (
                "X2522 PMD",
                r"Probe PCI driver: net_sfc_efx .*"
                r"device: 0000:03:00\.0(?: |$)",
            ),
            (
                "X2522 ULL firmware / ultra-low-latency",
                r"sfc_efx 0000:03:00\.0 .*"
                r"running FW variant is ultra-low-latency",
            ),
        )
        matched = []
        for label, pattern in required_log_patterns:
            lines = [
                line for line in originals["fstack.log"].splitlines()
                if re.search(pattern, line)
            ]
            if not lines:
                raise RuntimeError(f"DPDK native log lacks {label!r}: {path}")
            matched.append(lines[0])
        independently_matched = matched + [
            f"pid={exchange_pid}",
            f"exe_path={exchange_exe}",
            f"exe_sha256={exchange_sha}",
            f"checkpoint_generator_sha256={generator_sha}",
            f"checkpoint_sha256={checkpoint_sha}",
            f"itch_sha256={itch_sha}",
            f"listener_count={len(exchange_listeners)}",
            f"argv_count={exchange_argv_count}",
            *(
                f"argv_{index:02d}={value}"
                for index, value in enumerate(exchange_argv)
            ),
            *(
                f"listener_ss_line_{index}={line}"
                for index, line in enumerate(exchange_listeners, start=1)
            ),
            *(item["ss_line"] for item in exchange_endpoints),
            "driver=vfio-pci",
            "iommu_group=7",
            "group_device=0000:03:00.0",
            "unsafe_noiommu=N",
        ]
        counter_kind = "dpdk_port_packets"
        counter_value = port_stats["ipackets"] + port_stats["opackets"]

    independently_matched = [
        *originals["process.txt"].splitlines(),
        *(f"{field}={input_receipt[field]}" for field in sealed_input_fields),
        *independently_matched,
    ]
    if key == "DPDK":
        independently_matched.extend(
            f"{field}={gate[field]}"
            for field in (
                "gate_pid",
                "gate_cpus_allowed_list",
                "runtime_manifest_sha256",
                "wrapper_sha256",
                "binary_sha256",
                "config_sha256",
                "lease_token",
            )
        )
        independently_matched.extend(
            f"{field}={lease[field]}"
            for field in (
                "lease_unit", "lease_seconds", "lease_token",
                "recovery_executor",
            )
        )
    if (
        manifest["counter_kind"] != counter_kind
        or manifest["counter_value"] != counter_value
    ):
        raise RuntimeError(
            f"native counter was not independently reproduced: {path} phase={phase}"
        )
    excerpt_texts = {item["text"] for item in manifest["matching_excerpts"]}
    required_excerpt_texts = {f"pid={pid}", *independently_matched}
    if not required_excerpt_texts.issubset(excerpt_texts):
        raise RuntimeError(
            "compact matching excerpts omit independently required native lines: "
            f"{path} phase={phase} "
            f"missing={sorted(required_excerpt_texts - excerpt_texts)}"
        )
    return {
        "phase": phase,
        "boot_id": process["boot_id"],
        "pid": pid,
        "start_ticks": start_ticks,
        "runtime_identity": runtime_identity,
        "state_contract": state_contract,
        "process_contract": process_contract,
        "order_thread_tid": order_thread_tid,
        "counter_kind": counter_kind,
        "counter_value": counter_value,
        "independently_matched": independently_matched,
        "hardware_witness": hardware_witness,
        "server_endpoint_witness": server_endpoint_witness,
        "path_health_witness": path_health_witness,
        "ownership_lease_witness": ownership_lease_witness,
    }


def validate_cell_audit(
    source: Path, row: dict[str, Any], path: Path
) -> dict[str, Any]:
    audit = row.get("cell_audit")
    if not isinstance(audit, dict):
        raise RuntimeError(f"missing cell_audit: {path}")
    start = audit.get("start_monotonic_ns")
    end = audit.get("end_monotonic_ns")
    duration = audit.get("duration_ns")
    if not all(
        isinstance(value, int) and not isinstance(value, bool)
        for value in (start, end, duration)
    ):
        raise RuntimeError(f"invalid cell clock fields: {path}")
    if start < 1 or end <= start or duration != end - start:
        raise RuntimeError(f"inconsistent cell clock interval: {path}")
    native = audit.get("native_receipts")
    if not isinstance(native, dict) or set(native) != {"pre", "post"}:
        raise RuntimeError(f"cell lacks pre/post native receipts: {path}")
    pre = validate_native_receipt_from_originals(source, row, "pre", path)
    post = validate_native_receipt_from_originals(source, row, "post", path)
    identity = (pre["boot_id"], pre["pid"], pre["start_ticks"])
    if identity != (post["boot_id"], post["pid"], post["start_ticks"]):
        raise RuntimeError(f"native process generation changed inside cell: {path}")
    if pre["runtime_identity"] != post["runtime_identity"]:
        raise RuntimeError(f"native runtime executable changed inside cell: {path}")
    stable_state_fields = (
        "transport_label", "market_protocol", "network_engine", "queue_mode",
        "queue_locked", "queue_full_drops", "heartbeat_enabled", "nagle",
        "user_ref_base", "user_ref_span", "user_ref_end_exclusive",
        "thread_placement",
    )
    if any(
        pre["state_contract"][field] != post["state_contract"][field]
        for field in stable_state_fields
    ):
        raise RuntimeError(f"native runtime contract changed inside cell: {path}")
    if (
        pre["process_contract"]["argv"] != post["process_contract"]["argv"]
        or pre["process_contract"]["environment"]
        != post["process_contract"]["environment"]
        or pre["process_contract"]["thread_affinity"]
        != post["process_contract"]["thread_affinity"]
    ):
        raise RuntimeError(f"native process contract changed inside cell: {path}")
    if pre["order_thread_tid"] != post["order_thread_tid"]:
        raise RuntimeError(f"native order thread changed inside cell: {path}")
    if pre["counter_kind"] != post["counter_kind"]:
        raise RuntimeError(f"native counter kind changed inside cell: {path}")
    if post["counter_value"] <= pre["counter_value"]:
        raise RuntimeError(f"native path counter did not grow inside cell: {path}")
    hardware_witness = None
    server_endpoint_witness = None
    path_health_witness = None
    ownership_lease_witness = None
    if row["transport"] == "OPENONLOAD":
        pre_hardware = pre["hardware_witness"]
        post_hardware = post["hardware_witness"]
        if post_hardware["ctpio_pkts"] <= pre_hardware["ctpio_pkts"]:
            raise RuntimeError(f"Onload CTPIO packet counter did not grow: {path}")
        if (
            post_hardware["ctpio_dma_fallbacks"]
            != pre_hardware["ctpio_dma_fallbacks"]
        ):
            raise RuntimeError(f"Onload CTPIO DMA fallback counter grew: {path}")
        hardware_witness = {
            "counter_scope": "CURRENT_PID_ONLOAD_STACK",
            "ctpio_pkts_before": pre_hardware["ctpio_pkts"],
            "ctpio_pkts_after": post_hardware["ctpio_pkts"],
            "ctpio_pkts_delta": (
                post_hardware["ctpio_pkts"] - pre_hardware["ctpio_pkts"]
            ),
            "ctpio_dma_fallbacks_before": pre_hardware["ctpio_dma_fallbacks"],
            "ctpio_dma_fallbacks_after": post_hardware["ctpio_dma_fallbacks"],
            "ctpio_dma_fallbacks_delta": 0,
        }
    if row["transport"] == "DPDK":
        if (
            pre["ownership_lease_witness"] is None
            or pre["ownership_lease_witness"]
            != post["ownership_lease_witness"]
        ):
            raise RuntimeError(f"DPDK ownership lease changed inside cell: {path}")
        ownership_lease_witness = pre["ownership_lease_witness"]
        pre_hardware = pre["hardware_witness"]
        post_hardware = post["hardware_witness"]
        if not isinstance(pre_hardware, dict) or not isinstance(post_hardware, dict):
            raise RuntimeError(f"DPDK cell lacks port statistics: {path}")
        packet_deltas = {
            field: post_hardware[field] - pre_hardware[field]
            for field in ("ipackets", "opackets")
        }
        if any(value <= 0 for value in packet_deltas.values()):
            raise RuntimeError(f"DPDK RX/TX port counters did not both grow: {path}")
        drop_fields = ("imissed", "ierrors", "oerrors", "rx_nombuf")
        drop_deltas = {
            field: post_hardware[field] - pre_hardware[field]
            for field in drop_fields
        }
        if any(value != 0 for value in drop_deltas.values()):
            raise RuntimeError(f"DPDK port drop/error counter grew: {path}")
        hardware_witness = {
            "counter_scope": "CURRENT_FSTACK_DPDK_PORT_0_RTE_ETH_STATS",
            "ipackets_before": pre_hardware["ipackets"],
            "ipackets_after": post_hardware["ipackets"],
            "ipackets_delta": packet_deltas["ipackets"],
            "opackets_before": pre_hardware["opackets"],
            "opackets_after": post_hardware["opackets"],
            "opackets_delta": packet_deltas["opackets"],
            **{f"{field}_before": pre_hardware[field] for field in drop_fields},
            **{f"{field}_after": post_hardware[field] for field in drop_fields},
            **{f"{field}_delta": drop_deltas[field] for field in drop_fields},
            "queue_full_drops_before": pre_hardware["queue_full_drops"],
            "queue_full_drops_after": post_hardware["queue_full_drops"],
        }
        pre_server = pre["server_endpoint_witness"]
        post_server = post["server_endpoint_witness"]
        if not isinstance(pre_server, dict) or not isinstance(post_server, dict):
            raise RuntimeError(f"DPDK cell lacks Exchange-side endpoint proof: {path}")
        identity_fields = (
            "boot_id", "pid", "start_ticks", "exe_sha256",
            "checkpoint_generator_sha256", "checkpoint_sha256",
            "itch_sha256",
        )
        if tuple(pre_server[field] for field in identity_fields) != tuple(
            post_server[field] for field in identity_fields
        ):
            raise RuntimeError(f"Exchange process changed inside DPDK cell: {path}")
        server_endpoint_witness = {
            "scope": "EXCHANGE_SERVER_OBSERVED_PEER_ENDPOINT",
            "not_a_client_pid_binding": True,
            "observation_semantics": (
                "AT_LEAST_ONE_TARGET_ENDPOINT_PER_SNAPSHOT;"
                "SETS_MAY_DIFFER_AND_DO_NOT_BIND_A_CLIENT_PID"
            ),
            "exchange_host": "10.1.1.1",
            "observed_peer_host": "10.1.1.2",
            "exchange_boot_id": pre_server["boot_id"],
            "exchange_pid": pre_server["pid"],
            "exchange_start_ticks": pre_server["start_ticks"],
            "exchange_exe_sha256": pre_server["exe_sha256"],
            "checkpoint_generator_sha256": pre_server[
                "checkpoint_generator_sha256"
            ],
            "checkpoint_sha256": pre_server["checkpoint_sha256"],
            "itch_sha256": pre_server["itch_sha256"],
            "pre_listener_count": pre_server["listener_count"],
            "post_listener_count": post_server["listener_count"],
            "pre_listener_ss_lines": pre_server["listener_ss_lines"],
            "post_listener_ss_lines": post_server["listener_ss_lines"],
            "pre_endpoint_count": pre_server["endpoint_count"],
            "post_endpoint_count": post_server["endpoint_count"],
            "pre_observed_endpoints": pre_server["observed_endpoints"],
            "post_observed_endpoints": post_server["observed_endpoints"],
        }
    if row["transport"] == "TCPDIRECT":
        pre_health = pre["path_health_witness"]
        post_health = post["path_health_witness"]
        if not isinstance(pre_health, dict) or not isinstance(post_health, dict):
            raise RuntimeError(f"TCPDirect cell lacks retransmit observation: {path}")
        retransmit_delta = (
            post_health["retransmits"] - pre_health["retransmits"]
        )
        endpoint_fields = ("stack_endpoint", "local_endpoint", "remote_endpoint")
        if tuple(pre_health[field] for field in endpoint_fields) != tuple(
            post_health[field] for field in endpoint_fields
        ):
            raise RuntimeError(f"TCPDirect endpoint changed inside cell: {path}")
        if retransmit_delta < 0:
            raise RuntimeError(
                f"TCPDirect endpoint retransmits moved backward: {path}"
            )
        path_health_witness = {
            "scope": "ZF_ENDPOINT_CUMULATIVE_RETRANSMITS",
            "retransmits_before": pre_health["retransmits"],
            "retransmits_after": post_health["retransmits"],
            "retransmits_delta": retransmit_delta,
            "local_endpoint": pre_health["local_endpoint"],
            "remote_endpoint": pre_health["remote_endpoint"],
            "interpretation": "PATH_HEALTH_CLUE_NOT_MAPPED_TO_LATENCY_SAMPLES",
        }
    generation_name = (
        "onload" if row["transport"] == "OPENONLOAD" else str(row["transport"]).lower()
    )
    return {
        "transport": row["transport"],
        "round": row["round"],
        "boot_id": identity[0],
        "pid": identity[1],
        "start_ticks": identity[2],
        "generation": f"{generation_name}-{identity[1]}-{identity[2]}",
        "runtime_identity": pre["runtime_identity"],
        "state_contract_pre": pre["state_contract"],
        "state_contract_post": post["state_contract"],
        "process_contract": pre["process_contract"],
        "order_thread_tid": pre["order_thread_tid"],
        "cell_duration_ns": duration,
        "counter_kind": pre["counter_kind"],
        "path_counter_before": pre["counter_value"],
        "path_counter_after": post["counter_value"],
        "native_pre_matches": pre["independently_matched"],
        "native_post_matches": post["independently_matched"],
        "hardware_witness": hardware_witness,
        "server_endpoint_witness": server_endpoint_witness,
        "path_health_witness": path_health_witness,
        "ownership_lease_witness": ownership_lease_witness,
    }


def validate_common_clock_sample(
    sample: dict[str, Any], path: Path, index: int
) -> None:
    values = [
        sample.get("queue_to_send_ns"),
        sample.get("order_rtt_ns"),
        sample.get("submit_to_final_ns"),
    ]
    if any(
        isinstance(value, bool) or not isinstance(value, int)
        for value in values
    ):
        raise RuntimeError(f"non-integer clock field in {path} sample {index}")
    queue_ns, rtt_ns, total_ns = values
    if queue_ns < 0 or rtt_ns <= 0 or total_ns != queue_ns + rtt_ns:
        raise RuntimeError(f"common-clock identity failed in {path} sample {index}")


def validate_row_runtime_contract(
    row: dict[str, Any], native: dict[str, Any], path: Path
) -> None:
    """Cross-check compact row claims against independently parsed originals."""

    key = str(row["transport"])
    state_pre = native["state_contract_pre"]
    state_post = native["state_contract_post"]
    expected_hugepages = 256 if key == "DPDK" else 128
    expected_contract = {
        "symbol": "AAPL",
        "quantity": 1,
        "order_type": "IOC_LIMIT_CROSSING",
        "protocol": "OUCH_5.0_OVER_SOUPBINTCP",
        "queue_mode": "DEQUE_CV",
        "queue_locked": True,
        "single_flight": True,
        "accepted_telemetry_in_timer": False,
        "clock": "CLOCK_MONOTONIC",
        "timer_start": "OUCH_ENCODED_BEFORE_SOUP_FRAME",
        "timer_end": "FINAL_EXECUTED_DECODED",
        "data_cpu": 2,
        "management_cpu": 3,
        "observed_hugepages_2mb": expected_hugepages,
        "nagle": state_post["nagle"],
    }
    if row.get("contract") != expected_contract:
        raise RuntimeError(f"compact row runtime contract is not exact: {path}")
    if row.get("network_engine") != state_post["network_engine"]:
        raise RuntimeError(f"compact row network engine differs from STATE: {path}")

    expected_placement = {
        name: value
        for name, value in state_post["thread_placement"].items()
        if not name.endswith("_tid")
    }
    if row.get("thread_placement") != expected_placement:
        raise RuntimeError(
            f"compact row thread placement differs from native STATE: {path}"
        )

    generation = row.get("measurement_generation")
    warmup_generation = row.get("warmup_generation")
    if (
        isinstance(generation, bool)
        or not isinstance(generation, int)
        or generation < 2
        or isinstance(warmup_generation, bool)
        or not isinstance(warmup_generation, int)
        or warmup_generation != generation - 1
        or state_pre["measurement_generation"] != generation - 1
        or state_pre["measurement_ready_samples"] != 1
        or state_post["measurement_generation"] != generation
        or state_post["measurement_ready_samples"] != row.get("measurement_orders")
    ):
        raise RuntimeError(
            f"native pre/post measurement generation is not closed: {path}"
        )

    warmup_ids = row.get("warmup_submission_ids")
    measurement_ids = row.get("measurement_submission_ids")
    if (
        not isinstance(warmup_ids, list)
        or not isinstance(measurement_ids, list)
        or len(warmup_ids) != row.get("warmup_orders")
        or len(measurement_ids) != row.get("measurement_orders")
        or any(type(value) is not int for value in [*warmup_ids, *measurement_ids])
    ):
        raise RuntimeError(f"submission ID lists are malformed: {path}")
    all_ids = [*warmup_ids, *measurement_ids]
    base = state_post["user_ref_base"]
    end = state_post["user_ref_end_exclusive"]
    if (
        any(not base <= value < end for value in all_ids)
        or state_pre["user_ref_next"] != warmup_ids[0] + 1
        or state_post["user_ref_next"] != measurement_ids[-1] + 1
    ):
        raise RuntimeError(
            f"submission IDs do not close against native user_ref state: {path}"
        )


def load_and_validate(
    source: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    original = json.loads((source / "summary.json").read_text(encoding="utf-8"))
    if original.get("schema") != EXPECTED_SOURCE_SCHEMA:
        raise RuntimeError(f"unexpected source schema: {original.get('schema')!r}")
    expected_order = [list(row) for row in measure.BALANCED_PHASE_ORDER]
    if original.get("phase_order") != expected_order:
        raise RuntimeError("source phase order is not the fixed Williams design")
    validate_observer_absence_contract(original.get("runtime_contract"))

    rounds = []
    cell_audits = []
    for round_number, order in enumerate(measure.BALANCED_PHASE_ORDER, start=1):
        for position, transport in enumerate(order, start=1):
            path = source / "raw" / f"{transport.lower()}-r{round_number}.json"
            row = json.loads(path.read_text(encoding="utf-8"))
            if (
                row.get("transport") != transport
                or row.get("round") != round_number
                or row.get("position") != position
            ):
                raise RuntimeError(f"raw identity mismatch: {path}")
            if row.get("warmup_orders") != 100 or row.get("measurement_orders") != 1000:
                raise RuntimeError(f"raw sample contract mismatch: {path}")
            samples = row.get("raw_samples")
            if not isinstance(samples, list) or len(samples) != 1000:
                raise RuntimeError(f"raw sample count mismatch: {path}")
            warmup_samples = row.get("warmup_raw_samples")
            if not isinstance(warmup_samples, list) or len(warmup_samples) != 100:
                raise RuntimeError(f"warmup raw sample count mismatch: {path}")
            if any(sample.get("result") != "E" for sample in warmup_samples):
                raise RuntimeError(f"non-executed warmup sample in {path}")
            if any(sample.get("result") != "E" for sample in samples):
                raise RuntimeError(f"non-executed sample in {path}")
            for index, sample in enumerate(warmup_samples):
                validate_common_clock_sample(sample, path, index)
            for index, sample in enumerate(samples):
                validate_common_clock_sample(sample, path, index)
            generation = row.get("measurement_generation")
            if (
                isinstance(generation, bool)
                or not isinstance(generation, int)
                or generation < 1
            ):
                raise RuntimeError(f"invalid measurement generation: {path}")
            for metric, sample_field in SAMPLE_FIELDS.items():
                recomputed = measure.summarize(
                    [int(sample[sample_field]) for sample in samples]
                )
                if any(
                    int(row[metric][field]) != recomputed[field]
                    for field in ("p50_ns", "p95_ns", "p99_ns", "mean_ns", "max_ns")
                ):
                    raise RuntimeError(f"stored round summary mismatch: {path} {metric}")
            cell_audit = validate_cell_audit(source, row, path)
            validate_row_runtime_contract(row, cell_audit, path)
            cell_audits.append(cell_audit)
            rounds.append(row)

    referenced_native = {
        item["path"]
        for row in rounds
        for phase in ("pre", "post")
        for item in row["cell_audit"]["native_receipts"][phase]["files"]
    }
    actual_native = {
        path.relative_to(source).as_posix()
        for path in (source / "native-receipts").rglob("*")
        if path.is_file()
    }
    if actual_native != referenced_native:
        raise RuntimeError(
            "native originals and compact manifests differ: "
            f"missing={sorted(referenced_native - actual_native)} "
            f"unexpected={sorted(actual_native - referenced_native)}"
        )
    expected_raw_paths = {
        f"raw/{transport.lower()}-r{round_number}.json"
        for round_number, order in enumerate(
            measure.BALANCED_PHASE_ORDER, start=1
        )
        for transport in order
    } | {
        "raw/exchange-ledger-before.json",
        "raw/exchange-ledger-after.json",
    }
    required_manifest_paths = referenced_native | expected_raw_paths | {
        "README.md",
        "summary.json",
        "provenance/transport_labctl.sh",
        "provenance/measure_four_transports.py",
        "provenance/analyze_four_transport_raw.py",
    }
    require_exact_source_manifest_paths(source, required_manifest_paths)
    native_gate = original.get("native_receipt_gate")
    if native_gate != {
        "cells": 16,
        "pre_post_manifests": 32,
        "original_files": len(actual_native),
    }:
        raise RuntimeError(f"native receipt summary gate mismatch: {native_gate}")
    verify_execution_provenance(source, original)

    measure.validate_position_and_predecessor_balance()
    (
        submission_identity,
        warmup_sample_identity,
        sample_identity,
    ) = measure.validate_final_identity_gates(rounds, 100, 1000)
    if submission_identity != original.get("submission_identity"):
        raise RuntimeError("submission identity summary does not match source")
    if warmup_sample_identity != original.get("warmup_sample_identity"):
        raise RuntimeError("warmup sample identity summary does not match source")
    if sample_identity != original.get("sample_identity"):
        raise RuntimeError("sample identity summary does not match source")
    ledger = original.get("exchange_ledger_gate", {})
    if (
        ledger.get("delta") != 17600
        or ledger.get("expected") != 17600
        or not isinstance(ledger.get("replay_loop"), int)
        or not ledger.get("session")
    ):
        raise RuntimeError(f"exchange ledger/replay gate is incomplete: {ledger}")
    replay_gate = original.get("exchange_replay_gate")
    if not isinstance(replay_gate, dict):
        raise RuntimeError("fixed-book replay gate is missing")
    before_replay = replay_gate.get("before", {})
    paused_first = replay_gate.get("paused_first", {})
    paused_stable = replay_gate.get("paused_stable", {})
    restored_replay = replay_gate.get("restored", {})
    stable_fields = (
        "session", "replay_loop", "source_timestamp_ns",
        "replay_messages", "market_sequence",
    )
    expected_renewal_checkpoints = ["before-initial-sfc"]
    current_mode = "SFC"
    for round_number, order in enumerate(measure.BALANCED_PHASE_ORDER, start=1):
        for position, transport in enumerate(order, start=1):
            suffix = f"r{round_number}-p{position}-{transport.lower()}"
            expected_renewal_checkpoints.append(f"before-{suffix}")
            required_mode = str(measure.TRANSPORTS[transport]["mode"])
            if required_mode != current_mode:
                expected_renewal_checkpoints.append(f"after-switch-{suffix}")
                current_mode = required_mode
    expected_renewal_checkpoints.append("before-final-ledger")
    renewals = replay_gate.get("lease_renewals")
    if (
        replay_gate.get("stable_fields") != list(stable_fields)
        or replay_gate.get("pause_lease_ms") != measure.FORMAL_PAUSE_LEASE_MS
        or before_replay.get("replay_status") != "PLAYING"
        or paused_first.get("replay_status") != "PAUSED"
        or paused_stable.get("replay_status") != "PAUSED"
        or paused_first.get("replay_pause_lease_ms")
        != measure.FORMAL_PAUSE_LEASE_MS
        or paused_stable.get("replay_pause_lease_ms")
        != measure.FORMAL_PAUSE_LEASE_MS
        or any(
            isinstance(state.get("replay_pause_lease_remaining_ms"), bool)
            or not isinstance(state.get("replay_pause_lease_remaining_ms"), int)
            or not 0 < state["replay_pause_lease_remaining_ms"]
            <= measure.FORMAL_PAUSE_LEASE_MS
            for state in (paused_first, paused_stable)
        )
        or restored_replay.get("replay_status") != "PLAYING"
        or restored_replay.get("replay_pause_lease_ms") != 0
        or restored_replay.get("replay_pause_lease_remaining_ms") != 0
        or any(
            paused_first.get(field) != paused_stable.get(field)
            for field in stable_fields
        )
        or restored_replay.get("session") != before_replay.get("session")
        or not isinstance(renewals, list)
        or any(not isinstance(item, dict) for item in renewals)
        or [item.get("checkpoint") for item in renewals]
        != expected_renewal_checkpoints
        or any(
            not isinstance(item, dict)
            or item.get("replay_status") != "PAUSED"
            or item.get("pause_lease_ms") != measure.FORMAL_PAUSE_LEASE_MS
            or isinstance(item.get("remaining_ms"), bool)
            or not isinstance(item.get("remaining_ms"), int)
            or not 0 < item["remaining_ms"] <= measure.FORMAL_PAUSE_LEASE_MS
            or any(
                item.get(field) != paused_stable.get(field)
                for field in stable_fields
            )
            for item in renewals
        )
    ):
        raise RuntimeError(f"fixed-book replay gate is invalid: {replay_gate}")
    before_state = json.loads(
        (source / "raw" / "exchange-ledger-before.json").read_text(encoding="utf-8")
    )
    after_state = json.loads(
        (source / "raw" / "exchange-ledger-after.json").read_text(encoding="utf-8")
    )
    ledger_values = (
        before_state.get("paper_ledger_entries"),
        after_state.get("paper_ledger_entries"),
        ledger.get("before"),
        ledger.get("after"),
        ledger.get("delta"),
    )
    if (
        any(isinstance(value, bool) or not isinstance(value, int)
            for value in ledger_values)
        or
        before_state.get("paper_ledger_entries") != ledger["before"]
        or after_state.get("paper_ledger_entries") != ledger["after"]
        or after_state.get("paper_ledger_entries")
        - before_state.get("paper_ledger_entries")
        != ledger["delta"]
        or ledger["after"] - ledger["before"] != ledger["delta"]
        or before_state.get("replay_loop") != ledger["replay_loop"]
        or after_state.get("replay_loop") != ledger["replay_loop"]
        or before_state.get("session") != ledger["session"]
        or after_state.get("session") != ledger["session"]
        or before_state.get("replay_status") != "PAUSED"
        or after_state.get("replay_status") != "PAUSED"
        or any(
            before_state.get(field) != after_state.get(field)
            for field in (
                "session", "replay_loop", "source_timestamp_ns",
                "replay_messages", "market_sequence",
            )
        )
        or any(
            before_state.get(field) != paused_stable.get(field)
            or after_state.get(field) != paused_stable.get(field)
            for field in stable_fields
        )
    ):
        raise RuntimeError("raw Exchange ledger snapshots do not match the hard gate")
    return original, rounds, cell_audits


def summarize_tcpdirect_presend_boundary(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    tcpdirect_rows = [row for row in rows if row["transport"] == "TCPDIRECT"]
    if len(tcpdirect_rows) != 4:
        raise RuntimeError("TCPDirect pre-send boundary requires four cells")
    tcpdirect_warmup = [
        int(sample["queue_to_send_ns"])
        for row in tcpdirect_rows
        for sample in row["warmup_raw_samples"]
    ]
    tcpdirect_measured = [
        int(sample["queue_to_send_ns"])
        for row in tcpdirect_rows
        for sample in row["raw_samples"]
    ]
    return {
        "threshold_ns": PRESEND_SPIKE_THRESHOLD_NS,
        "warmup_samples": len(tcpdirect_warmup),
        "warmup_at_or_above_threshold": sum(
            value >= PRESEND_SPIKE_THRESHOLD_NS for value in tcpdirect_warmup
        ),
        "warmup_first_sample_at_or_above_threshold": sum(
            int(row["warmup_raw_samples"][0]["queue_to_send_ns"])
            >= PRESEND_SPIKE_THRESHOLD_NS
            for row in tcpdirect_rows
        ),
        "warmup_max_ns": max(tcpdirect_warmup),
        "measured_samples": len(tcpdirect_measured),
        "measured_at_or_above_threshold": sum(
            value >= PRESEND_SPIKE_THRESHOLD_NS for value in tcpdirect_measured
        ),
        "measured_max_ns": max(tcpdirect_measured),
        "scope": "OBSERVED_SUBMIT_TO_OUCH_SEND_WINDOW_NOT_CAUSAL_SUBTIMERS",
    }


def build_analysis(source: Path) -> dict[str, Any]:
    source_manifest_sha256 = verify_source_manifest(source)
    original, rows, cell_audits = load_and_validate(source)
    observer_absence = validate_observer_absence_contract(
        original.get("runtime_contract")
    )
    live_programs = verify_live_analysis_programs(original)
    tcpdirect_presend_boundary = summarize_tcpdirect_presend_boundary(rows)
    summary = {}
    for transport in measure.TRANSPORT_ORDER:
        transport_rows = [row for row in rows if row["transport"] == transport]
        summary[transport] = {
            "label": measure.TRANSPORTS[transport]["label"],
            "balanced_equal_cell_mean": {
                metric: equal_cell_mean_summary(transport_rows, metric)
                for metric in SAMPLE_FIELDS
            },
            "pooled_empirical_descriptive": {
                metric: pooled_metric_summary(transport_rows, metric)
                for metric in SAMPLE_FIELDS
            },
            "median_of_rounds_descriptive": original["summary"][transport],
            "round_ranges": {
                metric: {
                    field: {
                        "min_ns": min(int(row[metric][field]) for row in transport_rows),
                        "max_ns": max(int(row[metric][field]) for row in transport_rows),
                    }
                    for field in ("p50_ns", "p95_ns", "p99_ns")
                }
                for metric in SAMPLE_FIELDS
            },
        }
    paired_p50 = []
    for round_number in range(1, 5):
        socket_row = next(
            row for row in rows
            if row["transport"] == "SOCKET" and row["round"] == round_number
        )
        onload_row = next(
            row for row in rows
            if row["transport"] == "OPENONLOAD" and row["round"] == round_number
        )
        paired_p50.append(
            int(socket_row["order_rtt"]["p50_ns"])
            - int(onload_row["order_rtt"]["p50_ns"])
        )
    onload_hardware_cells = [
        row["hardware_witness"]
        for row in cell_audits
        if row["transport"] == "OPENONLOAD"
    ]
    if len(onload_hardware_cells) != 4 or any(
        row is None for row in onload_hardware_cells
    ):
        raise RuntimeError("four Onload cells must each carry a CTPIO witness")
    dpdk_server_cells = [
        row["server_endpoint_witness"]
        for row in cell_audits
        if row["transport"] == "DPDK"
    ]
    if len(dpdk_server_cells) != 4 or any(
        row is None for row in dpdk_server_cells
    ):
        raise RuntimeError(
            "four DPDK cells must each carry an Exchange-side endpoint witness"
        )
    exchange_identity_fields = (
        "exchange_boot_id",
        "exchange_pid",
        "exchange_start_ticks",
        "exchange_exe_sha256",
        "checkpoint_generator_sha256",
        "checkpoint_sha256",
        "itch_sha256",
    )
    exchange_generations = {
        tuple(row[field] for field in exchange_identity_fields)
        for row in dpdk_server_cells
    }
    if len(exchange_generations) != 1:
        raise RuntimeError("Exchange process/input generation changed across DPDK cells")
    dpdk_hardware_cells = [
        row["hardware_witness"]
        for row in cell_audits
        if row["transport"] == "DPDK"
    ]
    if len(dpdk_hardware_cells) != 4 or any(
        row is None for row in dpdk_hardware_cells
    ):
        raise RuntimeError(
            "four DPDK cells must each carry RX/TX/drop port statistics"
        )
    dpdk_lease_cells = [
        row["ownership_lease_witness"]
        for row in cell_audits
        if row["transport"] == "DPDK"
    ]
    if (
        len(dpdk_lease_cells) != 4
        or any(row is None for row in dpdk_lease_cells)
        or any(
            row["lease_seconds"] != "1800"
            or row["recovery_executor"]
            != "systemd_timer_independent_of_wrapper"
            for row in dpdk_lease_cells
        )
    ):
        raise RuntimeError(
            "four DPDK cells must each carry an independent ownership lease"
        )
    tcpdirect_health_cells = [
        row["path_health_witness"]
        for row in cell_audits
        if row["transport"] == "TCPDIRECT"
    ]
    if len(tcpdirect_health_cells) != 4 or any(
        row is None for row in tcpdirect_health_cells
    ):
        raise RuntimeError(
            "four TCPDirect cells must each carry a retransmit observation"
        )
    result = {
        "schema": ANALYSIS_SCHEMA,
        "run_id": original["run_id"],
        "source_schema": original["schema"],
        "source_manifest_sha256": source_manifest_sha256,
        **live_programs,
        "analysis_matches_sealed_program": True,
        "measurement_module_matches_sealed_program": True,
        "method": {
            "primary": "EQUAL_CELL_MEAN_OF_4_ROUND_NEAREST_RANK_STATISTICS",
            "reason": "the four cells are the repeated balanced units; their linear equal-weight mean retains one cell for every position and first-order predecessor context",
            "secondary": "the pooled 4000-sample empirical distribution weights cells equally by count but is kept descriptive because the 1000 observations inside one cell are not 1000 independent design replicates; the median of four round statistics is also descriptive because it selects only two cells",
            "maximum_semantics": "max_ns is the single global maximum across the four cells; unlike p50/p95/p99/mean it is not an equal-cell mean",
            "order_design": original["runtime_contract"]["order_balance"],
            "warmup_boundary": "100 orders per cell reduce carryover but do not prove its elimination",
        },
        "exchange_ledger_gate": original["exchange_ledger_gate"],
        "exchange_replay_gate": original["exchange_replay_gate"],
        "submission_identity": original["submission_identity"],
        "warmup_sample_identity": original["warmup_sample_identity"],
        "sample_identity": original["sample_identity"],
        "runtime_acceptance": {
            "cell_native_path_receipts": len(cell_audits),
            "expected_cell_native_path_receipts": 16,
            "pre_post_original_sets": len(cell_audits) * 2,
            "validation": "INDEPENDENT_REPARSE_OF_NATIVE_ORIGINALS_NOT_CONTROLLER_BOOLEANS",
            "observer_absence_before_measurement": observer_absence,
            "onload_ctpio_hardware_witness": {
                "cells": len(onload_hardware_cells),
                "ctpio_pkts_delta_sum": sum(
                    row["ctpio_pkts_delta"] for row in onload_hardware_cells
                ),
                "ctpio_dma_fallbacks_delta_sum": sum(
                    row["ctpio_dma_fallbacks_delta"]
                    for row in onload_hardware_cells
                ),
                "scope": "CURRENT_PID_ONLOAD_STACK_PER_CELL_NOT_ORDER_COUNTER",
            },
            "dpdk_exchange_server_endpoint_witness": {
                "cells": len(dpdk_server_cells),
                "scope": "EXCHANGE_SERVER_OBSERVED_PEER_ENDPOINT",
                "not_a_client_pid_binding": True,
                "exchange_host": "10.1.1.1",
                "observed_peer_host": "10.1.1.2",
                "one_exchange_generation_across_all_cells": True,
                "exchange_identity": dict(
                    zip(exchange_identity_fields, next(iter(exchange_generations)))
                ),
                "pre_listener_counts": [
                    row["pre_listener_count"] for row in dpdk_server_cells
                ],
                "post_listener_counts": [
                    row["post_listener_count"] for row in dpdk_server_cells
                ],
                "pre_endpoint_counts": [
                    row["pre_endpoint_count"] for row in dpdk_server_cells
                ],
                "post_endpoint_counts": [
                    row["post_endpoint_count"] for row in dpdk_server_cells
                ],
                "observation_semantics": (
                    "AT_LEAST_ONE_TARGET_ENDPOINT_PER_SNAPSHOT;"
                    "SETS_MAY_DIFFER_AND_DO_NOT_BIND_A_CLIENT_PID"
                ),
            },
            "dpdk_port_hardware_witness": {
                "cells": len(dpdk_hardware_cells),
                "cells_with_rx_tx_growth": sum(
                    row["ipackets_delta"] > 0 and row["opackets_delta"] > 0
                    for row in dpdk_hardware_cells
                ),
                "ipackets_delta_sum": sum(
                    row["ipackets_delta"] for row in dpdk_hardware_cells
                ),
                "opackets_delta_sum": sum(
                    row["opackets_delta"] for row in dpdk_hardware_cells
                ),
                "drop_error_delta_sum": {
                    field: sum(
                        row[f"{field}_delta"] for row in dpdk_hardware_cells
                    )
                    for field in ("imissed", "ierrors", "oerrors", "rx_nombuf")
                },
                "queue_full_drops_before_after": [
                    [row["queue_full_drops_before"], row["queue_full_drops_after"]]
                    for row in dpdk_hardware_cells
                ],
                "scope": "CURRENT_FSTACK_DPDK_PORT_0_RTE_ETH_STATS_PER_CELL",
            },
            "dpdk_independent_ownership_lease": {
                "cells": len(dpdk_lease_cells),
                "lease_seconds": 1800,
                "recovery_executor": "systemd_timer_independent_of_wrapper",
                "per_cell_tokens": [
                    row["lease_token"] for row in dpdk_lease_cells
                ],
                "pre_post_identity_matched_per_cell": True,
            },
            "tcpdirect_retransmit_observation": {
                "cells": len(tcpdirect_health_cells),
                "retransmits_delta_sum": sum(
                    row["retransmits_delta"] for row in tcpdirect_health_cells
                ),
                "cells_with_growth": sum(
                    row["retransmits_delta"] > 0
                    for row in tcpdirect_health_cells
                ),
                "scope": "ZF_ENDPOINT_CUMULATIVE_RETRANSMITS",
                "interpretation": "PATH_HEALTH_CLUE_NOT_MAPPED_TO_LATENCY_SAMPLES",
            },
            "tcpdirect_presend_warmup_boundary": tcpdirect_presend_boundary,
            "cells": cell_audits,
        },
        "kernel_minus_onload_same_round_p50_ns": paired_p50,
        "summary": summary,
    }
    require_source_manifest_unchanged(source, source_manifest_sha256)
    return result


def prepare_analysis_output(output: Path) -> None:
    allowed = {"README.md", "summary.json", "SHA256SUMS"}
    if output.is_symlink() or (output.exists() and not output.is_dir()):
        raise RuntimeError("balanced-analysis output must be a real directory")
    if not output.exists():
        output.mkdir()
        return
    entries = list(output.iterdir())
    invalid = [
        entry.name
        for entry in entries
        if entry.name not in allowed or not entry.is_file() or entry.is_symlink()
    ]
    if invalid:
        raise RuntimeError(
            f"balanced-analysis contains stale or non-file entries: {sorted(invalid)}"
        )


def verify_analysis_payload_set(output: Path) -> None:
    expected = {"README.md", "summary.json"}
    invalid_entries = [
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_dir()
        or path.is_symlink()
        or (path.name == "SHA256SUMS" and path.parent != output)
    ]
    if invalid_entries:
        raise RuntimeError(
            "balanced-analysis contains nested/symlink entries: "
            f"{sorted(invalid_entries)}"
        )
    observed = {
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_file() and path.name != "SHA256SUMS"
    }
    if observed != expected:
        raise RuntimeError(
            "balanced-analysis payload set is not exact: "
            f"missing={sorted(expected - observed)} "
            f"unexpected={sorted(observed - expected)}"
        )


def write_analysis(source: Path, result: dict[str, Any]) -> Path:
    output = source / "balanced-analysis"
    prepare_analysis_output(output)
    (output / "summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    onload_hardware = result["runtime_acceptance"][
        "onload_ctpio_hardware_witness"
    ]
    tcpdirect_health = result["runtime_acceptance"][
        "tcpdirect_retransmit_observation"
    ]
    tcpdirect_presend = result["runtime_acceptance"][
        "tcpdirect_presend_warmup_boundary"
    ]
    dpdk_port = result["runtime_acceptance"]["dpdk_port_hardware_witness"]
    dpdk_lease = result["runtime_acceptance"][
        "dpdk_independent_ownership_lease"
    ]
    lines = [
        "# Chapter 06 balance-preserving analysis",
        "",
        "主表先在每个 Williams 单元内计算 nearest-rank 分位数，再把四个单元等权平均。",
        "四格才是平衡重复单位；4000 笔合并分布和四轮中位数保留在 JSON 中，只作描述。",
        "每格 pre/post 都从原始 /proc NUL argv、管理监听、线程 affinity 与 STATE"
        " 独立重建应用合同；不接受控制器布尔值代替路径证据。",
        "OpenOnload 四格原生 stackdump 另验 CTPIO："
        f"ctpio_pkts delta 合计 {onload_hardware['ctpio_pkts_delta_sum']}，"
        f"DMA fallback delta 合计 {onload_hardware['ctpio_dma_fallbacks_delta_sum']}；"
        "这是硬件路径收据，不冒充订单数。",
        "DPDK 四格另从 Exchange 侧复解当前服务端 PID 下至少一个"
        " 20.1.1.2 目标端点；端点集合允许随快照变化，也不是 DPDK 客户端"
        " PID 绑定证明。",
        "DPDK 四格 port 0 的 RX/TX 均增长："
        f"ipackets delta 合计 {dpdk_port['ipackets_delta_sum']}，"
        f"opackets delta 合计 {dpdk_port['opackets_delta_sum']}；"
        "imissed / ierrors / oerrors / rx_nombuf 的格内 delta 全为 0。",
        "DPDK 四格各自封存 1800 秒 systemd 独立所有权租约；"
        f"验收格数 {dpdk_lease['cells']}，token 在 gate / client / lease 间一致。",
        "TCPDirect 四格 ZF endpoint retransmits delta 合计 "
        f"{tcpdirect_health['retransmits_delta_sum']}；它只作路径健康线索，"
        "不能映射到某笔延迟样本。",
        "TCPDirect 发送前窗口的 19 ms 阈值观察：warmup "
        f"{tcpdirect_presend['warmup_at_or_above_threshold']} / "
        f"{tcpdirect_presend['warmup_samples']}，正式样本 "
        f"{tcpdirect_presend['measured_at_or_above_threshold']} / "
        f"{tcpdirect_presend['measured_samples']}；它证明本 RUN 的预热边界"
        "挡住了这些首用尖峰，不把尖峰归因到某个未单独计时的内部步骤。",
        "后处理所用 analyzer 与 measure 模块均逐字匹配 formal RUN 封存副本。",
        "",
        "| Transport | send→final P50 / P95 / P99 | queue→final P50 / P95 / P99 |",
        "| --- | ---: | ---: |",
    ]
    for transport in measure.TRANSPORT_ORDER:
        item = result["summary"][transport]
        order = item["balanced_equal_cell_mean"]["order_rtt"]
        total = item["balanced_equal_cell_mean"]["submit_to_final"]
        lines.append(
            f"| {item['label']} | {order['p50_ns']} / {order['p95_ns']} / "
            f"{order['p99_ns']} ns | {total['p50_ns']} / {total['p95_ns']} / "
            f"{total['p99_ns']} ns |"
        )
    (output / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    verify_analysis_payload_set(output)
    manifest = []
    for target in sorted(
        path
        for path in output.iterdir()
        if path.is_file() and path.name != "SHA256SUMS"
    ):
        manifest.append(
            f"{hashlib.sha256(target.read_bytes()).hexdigest()}  {target.name}"
        )
    (output / "SHA256SUMS").write_text("\n".join(manifest) + "\n", encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("comparison_dir", type=Path)
    args = parser.parse_args()
    result = build_analysis(args.comparison_dir)
    output = write_analysis(args.comparison_dir, result)
    print("===== 平衡主表：四个 Williams 单元统计量等权平均 =====")
    print("路径                    send→final P50    P95       P99        queue→final P50")
    for transport in measure.TRANSPORT_ORDER:
        item = result["summary"][transport]
        order = item["balanced_equal_cell_mean"]["order_rtt"]
        total = item["balanced_equal_cell_mean"]["submit_to_final"]
        print(
            f"{item['label']:<24}{order['p50_ns']:>10} ns  "
            f"{order['p95_ns']:>8} ns  {order['p99_ns']:>8} ns  "
            f"{total['p50_ns']:>12} ns"
        )
    print("测量方法：4×4 Williams；每路每位置一次；每格 100 笔预热 + 1000 笔正式")
    print("订单结果：warmup Executed=1600（不统计）；measured Executed=16000")
    print("路径验证：16/16 个测试单元均命中计划 Transport")
    ledger = result["exchange_ledger_gate"]
    print(
        "总账闭合："
        f"submitted=expected={ledger['delta']}"
    )
    print(f"evidence={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
