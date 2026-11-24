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


def verify_source_manifest(source: Path) -> str:
    manifest_path = source / "SHA256SUMS"
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
        observed = hashlib.sha256(target.read_bytes()).hexdigest()
        if observed != digest:
            raise RuntimeError(
                f"source hash mismatch: path={relative} expected={digest} "
                f"observed={observed}"
            )
    return hashlib.sha256(manifest_path.read_bytes()).hexdigest()


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
    if expected_binary not in process.get("cmdline", ""):
        raise RuntimeError(f"native process command mismatch: {path}")

    state = json.loads(originals["state.json"])
    expected_label = {
        "SOCKET": "POSIX_SOCKET",
        "OPENONLOAD": "OPENONLOAD",
        "TCPDIRECT": "TCPDIRECT_ZF",
        "DPDK": "DPDK_FSTACK",
    }[key]
    state_orders = state.get("stats", {}).get("orders")
    state_fills = state.get("stats", {}).get("fills")
    order_thread_tid = state.get("software_latency", {}).get("order_thread_tid")
    if (
        state.get("status") != "ONLINE"
        or state.get("order_transport") != expected_label
        or isinstance(state_orders, bool)
        or not isinstance(state_orders, int)
        or state_orders < 1
        or isinstance(state_fills, bool)
        or not isinstance(state_fills, int)
        or state_fills < 1
        or isinstance(order_thread_tid, bool)
        or not isinstance(order_thread_tid, int)
        or order_thread_tid < 1
    ):
        raise RuntimeError(f"native STATE contract failed: {path}")

    independently_matched: list[str] = []
    hardware_witness: dict[str, int] | None = None
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
        needles = (
            "Using IOMMU type 1",
            "Probe PCI driver: net_sfc_efx",
            "running FW variant is ultra-low-latency",
        )
        matched = []
        for needle in needles:
            lines = [
                line for line in originals["fstack.log"].splitlines()
                if needle in line
            ]
            if not lines:
                raise RuntimeError(f"DPDK native log lacks {needle!r}: {path}")
            matched.append(lines[0])
        independently_matched = matched + [
            "driver=vfio-pci",
            "iommu_group=7",
            "group_device=0000:03:00.0",
            "unsafe_noiommu=N",
        ]
        counter_kind = "trader_orders"
        counter_value = state_orders

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
        "order_thread_tid": order_thread_tid,
        "counter_kind": counter_kind,
        "counter_value": counter_value,
        "independently_matched": independently_matched,
        "hardware_witness": hardware_witness,
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
    if pre["order_thread_tid"] != post["order_thread_tid"]:
        raise RuntimeError(f"native order thread changed inside cell: {path}")
    if pre["counter_kind"] != post["counter_kind"]:
        raise RuntimeError(f"native counter kind changed inside cell: {path}")
    if post["counter_value"] <= pre["counter_value"]:
        raise RuntimeError(f"native path counter did not grow inside cell: {path}")
    hardware_witness = None
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
        "order_thread_tid": pre["order_thread_tid"],
        "cell_duration_ns": duration,
        "counter_kind": pre["counter_kind"],
        "path_counter_before": pre["counter_value"],
        "path_counter_after": post["counter_value"],
        "native_pre_matches": pre["independently_matched"],
        "native_post_matches": post["independently_matched"],
        "hardware_witness": hardware_witness,
    }


def load_and_validate(
    source: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    original = json.loads((source / "summary.json").read_text(encoding="utf-8"))
    if original.get("schema") != "flle.ch06-four-order-paths.v7":
        raise RuntimeError(f"unexpected source schema: {original.get('schema')!r}")
    expected_order = [list(row) for row in measure.BALANCED_PHASE_ORDER]
    if original.get("phase_order") != expected_order:
        raise RuntimeError("source phase order is not the fixed Williams design")

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
            if any(sample.get("result") != "E" for sample in samples):
                raise RuntimeError(f"non-executed sample in {path}")
            for metric, sample_field in SAMPLE_FIELDS.items():
                recomputed = measure.summarize(
                    [int(sample[sample_field]) for sample in samples]
                )
                if any(
                    int(row[metric][field]) != recomputed[field]
                    for field in ("p50_ns", "p95_ns", "p99_ns", "mean_ns", "max_ns")
                ):
                    raise RuntimeError(f"stored round summary mismatch: {path} {metric}")
            cell_audits.append(validate_cell_audit(source, row, path))
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
    submission_identity, sample_identity = measure.validate_final_identity_gates(
        rounds, 100, 1000
    )
    if submission_identity != original.get("submission_identity"):
        raise RuntimeError("submission identity summary does not match source")
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
    before_state = json.loads(
        (source / "raw" / "exchange-ledger-before.json").read_text(encoding="utf-8")
    )
    after_state = json.loads(
        (source / "raw" / "exchange-ledger-after.json").read_text(encoding="utf-8")
    )
    if (
        before_state.get("paper_ledger_entries") != ledger["before"]
        or after_state.get("paper_ledger_entries") != ledger["after"]
        or before_state.get("replay_loop") != ledger["replay_loop"]
        or after_state.get("replay_loop") != ledger["replay_loop"]
        or before_state.get("session") != ledger["session"]
        or after_state.get("session") != ledger["session"]
    ):
        raise RuntimeError("raw Exchange ledger snapshots do not match the hard gate")
    return original, rounds, cell_audits


def build_analysis(source: Path) -> dict[str, Any]:
    source_manifest_sha256 = verify_source_manifest(source)
    original, rows, cell_audits = load_and_validate(source)
    live_programs = verify_live_analysis_programs(original)
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
    return {
        "schema": "flle.ch06-four-order-paths-balanced-analysis.v3",
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
            "order_design": original["runtime_contract"]["order_balance"],
            "warmup_boundary": "100 orders per cell reduce carryover but do not prove its elimination",
        },
        "exchange_ledger_gate": original["exchange_ledger_gate"],
        "submission_identity": original["submission_identity"],
        "sample_identity": original["sample_identity"],
        "runtime_acceptance": {
            "cell_native_path_receipts": len(cell_audits),
            "expected_cell_native_path_receipts": 16,
            "pre_post_original_sets": len(cell_audits) * 2,
            "validation": "INDEPENDENT_REPARSE_OF_NATIVE_ORIGINALS_NOT_CONTROLLER_BOOLEANS",
            "gateway_stopped_during_measurement": True,
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
            "cells": cell_audits,
        },
        "kernel_minus_onload_same_round_p50_ns": paired_p50,
        "summary": summary,
    }


def write_analysis(source: Path, result: dict[str, Any]) -> Path:
    output = source / "balanced-analysis"
    output.mkdir(exist_ok=True)
    (output / "summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    onload_hardware = result["runtime_acceptance"][
        "onload_ctpio_hardware_witness"
    ]
    lines = [
        "# Chapter 06 balance-preserving analysis",
        "",
        "主表先在每个 Williams 单元内计算 nearest-rank 分位数，再把四个单元等权平均。",
        "四格才是平衡重复单位；4000 笔合并分布和四轮中位数保留在 JSON 中，只作描述。",
        "OpenOnload 四格原生 stackdump 另验 CTPIO："
        f"ctpio_pkts delta 合计 {onload_hardware['ctpio_pkts_delta_sum']}，"
        f"DMA fallback delta 合计 {onload_hardware['ctpio_dma_fallbacks_delta_sum']}；"
        "这是硬件路径收据，不冒充订单数。",
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
    print("平衡合同：每路每位置一次；12 种行内有序前序各一次；四格等权")
    print("身份硬门：submitted total=unique=17600；measured total=unique=16000")
    print("原生路径收据：16/16 格 pre/post 独立复解；PID/start_ticks 与计数增长一致")
    print("程序来源：analyzer 与 measure 模块均匹配 formal RUN 封存 SHA")
    ledger = result["exchange_ledger_gate"]
    print(
        "账本与回放："
        f"delta=expected={ledger['delta']} replay_loop={ledger['replay_loop']} "
        f"session={ledger['session']}"
    )
    print("边界：warmup 只减弱 carryover；合并分布和四轮中位数只作描述")
    print(f"evidence={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
