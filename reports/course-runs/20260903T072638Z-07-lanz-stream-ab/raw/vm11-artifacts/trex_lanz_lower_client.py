#!/usr/bin/env python3
"""Plain-stream L2 readiness plus fixed-count single/dual LANZ probes."""

import argparse
import json
import math
import sys
import time
import traceback
from datetime import datetime, timezone

sys.path.insert(0, "/opt/trex/v3.08/automation/trex_control_plane/interactive")
from trex.stl.api import (  # noqa: E402
    Ether,
    Raw,
    STLClient,
    STLPktBuilder,
    STLStream,
    STLTXSingleBurst,
)


PORTS = (0, 1)
PORT_FIELDS = ("opackets", "obytes", "ipackets", "ibytes", "ierrors", "oerrors")
SOURCE_MACS = {0: "00:0a:f7:f8:48:a0", 1: "00:0a:f7:f8:48:a1"}
ALLOWED_PPS = {1000, 5000, 10000, 25000, 50000, 75000, 100000}
MEASURED_COUNT = 4096


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sanitize(value):
    if isinstance(value, dict):
        return {str(key): sanitize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def make_l2_packet(src_mac, dst_mac, run_id, phase, label, size):
    marker = f"FLLE-LANZ|RUN={run_id}|PHASE={phase}|SRC={label}|".encode("ascii")
    base = Ether(src=src_mac, dst=dst_mac, type=0x88B5) / Raw(load=marker)
    if len(base) > size:
        raise ValueError(f"marker frame {len(base)} exceeds frozen size {size}")
    packet = base / Raw(load=b"x" * (size - len(base)))
    builder = STLPktBuilder(pkt=packet)
    if builder.get_pkt_len() != size:
        raise AssertionError((builder.get_pkt_len(), size))
    return builder


def port_deltas(before, after):
    return {
        str(port): {
            field: after[port].get(field, 0) - before[port].get(field, 0)
            for field in PORT_FIELDS
        }
        for port in PORTS
    }


def stable_link_gate(client):
    observations = []
    consecutive = 0
    for attempt in range(1, 151):
        info = client.get_port_info(ports=list(PORTS))
        links = [entry.get("link") for entry in info]
        consecutive = consecutive + 1 if links == ["UP", "UP"] else 0
        observation = {
            "attempt": attempt,
            "checked_at_utc": utc_now(),
            "links": links,
            "consecutive_up": consecutive,
        }
        observations.append(observation)
        print(f"LINK_STABLE attempt={attempt} links={links} consecutive={consecutive}", flush=True)
        if consecutive >= 10:
            break
        time.sleep(0.2)
    if consecutive < 10:
        raise RuntimeError("did not reach 10 consecutive dual-UP observations")
    settle_started = utc_now()
    time.sleep(5)
    post = client.get_port_info(ports=list(PORTS))
    if [entry.get("link") for entry in post] != ["UP", "UP"]:
        raise RuntimeError(f"link changed during fixed settle: {post}")
    return {
        "stable_consecutive_required": 10,
        "stable_check_interval_seconds": 0.2,
        "fixed_settle_seconds": 5,
        "settle_started_at_utc": settle_started,
        "settle_finished_at_utc": utc_now(),
        "observations": observations,
        "port_info_after_settle": sanitize(post),
    }


def run_warmup_direction(client, run_id, tx_port, rx_port):
    before = client.get_stats(ports=list(PORTS))
    builder = make_l2_packet(
        SOURCE_MACS[tx_port], SOURCE_MACS[rx_port], run_id, "warmup", f"p{tx_port}", 128
    )
    stream = STLStream(
        name=f"flle-lanz-warmup-p{tx_port}-p{rx_port}",
        packet=builder,
        mode=STLTXSingleBurst(total_pkts=256, pps=1000),
    )
    client.add_streams(stream, ports=[tx_port])
    started = utc_now()
    client.start(ports=[tx_port], force=True)
    client.wait_on_traffic(ports=[tx_port], timeout=20, rx_delay_ms=1000)
    time.sleep(2)
    after = client.get_stats(ports=list(PORTS))
    client.remove_all_streams(ports=[tx_port])
    deltas = port_deltas(before, after)
    errors = [deltas[str(port)][field] for port in PORTS for field in ("ierrors", "oerrors")]
    accepted = (
        deltas[str(tx_port)]["opackets"] == 256
        and deltas[str(rx_port)]["ipackets"] >= 256
        and all(value == 0 for value in errors)
    )
    if not accepted:
        raise RuntimeError(f"warmup direction p{tx_port}->p{rx_port} failed: {deltas}")
    return {
        "tx_port": tx_port,
        "rx_port": rx_port,
        "started_at_utc": started,
        "finished_at_utc": utc_now(),
        "requested_packets": 256,
        "configured_pps": 1000,
        "frame_without_fcs_bytes": 128,
        "port_counter_deltas": deltas,
        "status": "PASS",
    }


def run_prepare(client, args):
    result = {
        "run_id": args.run_id,
        "mode": "prepare",
        "status": "FAIL",
        "started_at_utc": utc_now(),
    }
    result["readiness"] = stable_link_gate(client)
    result["port_attributes"] = {
        str(port): sanitize(client.get_port_attr(port)) for port in PORTS
    }
    result["warmup"] = [
        run_warmup_direction(client, args.run_id, 0, 1),
        run_warmup_direction(client, args.run_id, 1, 0),
    ]
    result["post_warmup_stats"] = sanitize(client.get_stats(ports=list(PORTS)))
    result["status"] = "PASS"
    result["finished_at_utc"] = utc_now()
    return result


def run_burst(client, args):
    if args.pps not in ALLOWED_PPS:
        raise ValueError(f"pps outside frozen stage allowlist: {args.pps}")
    if args.count != MEASURED_COUNT:
        raise ValueError(f"measured count must remain fixed at {MEASURED_COUNT}: {args.count}")
    if args.packet_size != 1514:
        raise ValueError(f"measured frame must be 1514 bytes without FCS: {args.packet_size}")
    info = client.get_port_info(ports=list(PORTS))
    if [entry.get("link") for entry in info] != ["UP", "UP"]:
        raise RuntimeError(f"burst links not both UP: {info}")

    tx_ports = (0,) if args.ingress_mode == "single0" else PORTS
    for port in tx_ports:
        builder = make_l2_packet(
            SOURCE_MACS[port], args.dst_mac, args.run_id, args.stage, f"p{port}", args.packet_size
        )
        stream = STLStream(
            name=f"flle-lanz-{args.stage}-p{port}",
            packet=builder,
            mode=STLTXSingleBurst(total_pkts=args.count, pps=args.pps),
        )
        client.add_streams(stream, ports=[port])

    before = client.get_stats(ports=list(PORTS))
    started_utc = utc_now()
    started_ns = time.perf_counter_ns()
    client.start(ports=list(tx_ports), force=True)
    client.wait_on_traffic(ports=list(tx_ports), timeout=30, rx_delay_ms=0)
    finished_ns = time.perf_counter_ns()
    finished_utc = utc_now()
    after = client.get_stats(ports=list(PORTS))
    client.remove_all_streams(ports=list(PORTS))
    deltas = port_deltas(before, after)

    elapsed_seconds = (finished_ns - started_ns) / 1_000_000_000
    total_packets = sum(deltas[str(port)]["opackets"] for port in tx_ports)
    total_obytes = sum(deltas[str(port)]["obytes"] for port in tx_ports)
    expected_packets = len(tx_ports) * args.count
    errors = {
        f"port_{port}_{field}": deltas[str(port)][field]
        for port in PORTS
        for field in ("ierrors", "oerrors")
    }
    active_counts_exact = all(
        deltas[str(port)]["opackets"] == args.count for port in tx_ports
    )
    inactive_ports = tuple(port for port in PORTS if port not in tx_ports)
    inactive_tx_zero = all(
        deltas[str(port)]["opackets"] == 0 for port in inactive_ports
    )
    status = (
        "PASS"
        if total_packets == expected_packets
        and active_counts_exact
        and inactive_tx_zero
        and all(v == 0 for v in errors.values())
        else "FAIL"
    )
    result = {
        "run_id": args.run_id,
        "mode": "burst",
        "stage": args.stage,
        "ingress_mode": args.ingress_mode,
        "active_tx_ports": list(tx_ports),
        "inactive_tx_ports": list(inactive_ports),
        "status": status,
        "started_at_utc": started_utc,
        "finished_at_utc": finished_utc,
        "start_to_wait_complete_wall_seconds": elapsed_seconds,
        "configured_pps_per_ingress": args.pps,
        "requested_packets_per_active_ingress": args.count,
        "frame_without_fcs_bytes": args.packet_size,
        "expected_trx_counter_bytes_per_packet_including_fcs": args.packet_size + 4,
        "wire_accounting_bytes_per_packet": args.packet_size + 24,
        "nominal_aggregate_l2_plus_fcs_gbps": len(tx_ports) * args.pps * (args.packet_size + 4) * 8 / 1e9,
        "nominal_aggregate_wire_gbps": len(tx_ports) * args.pps * (args.packet_size + 24) * 8 / 1e9,
        "destination_mac": args.dst_mac,
        "source_macs": SOURCE_MACS,
        "port_counter_deltas": deltas,
        "actual_total_opackets_delta": total_packets,
        "actual_total_obytes_delta": total_obytes,
        "actual_obytes_per_packet": total_obytes / total_packets if total_packets else None,
        "counter_bytes_over_api_wall_gbps": total_obytes * 8 / elapsed_seconds / 1e9,
        "io_error_deltas": errors,
        "active_counts_exact": active_counts_exact,
        "inactive_tx_zero": inactive_tx_zero,
        "port_info_before": sanitize(info),
        "warnings": sanitize(client.get_warnings()),
    }
    if status != "PASS":
        raise RuntimeError(f"burst ordinary-port acceptance failed: {result}")
    return result


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--mode", choices=("prepare", "burst"), required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--stage")
    parser.add_argument("--ingress-mode", choices=("single0", "dual"))
    parser.add_argument("--dst-mac")
    parser.add_argument("--pps", type=int)
    parser.add_argument("--count", type=int)
    parser.add_argument("--packet-size", type=int, default=1514)
    return parser.parse_args()


def main():
    args = parse_args()
    if args.mode == "burst" and None in (
        args.stage,
        args.ingress_mode,
        args.dst_mac,
        args.pps,
        args.count,
    ):
        raise SystemExit(
            "burst mode requires --stage, --ingress-mode, --dst-mac, --pps and --count"
        )
    client = STLClient(
        server="127.0.0.1", username="flle-lanz", verbose_level="error", sync_timeout=5, async_timeout=5
    )
    result = {
        "run_id": args.run_id,
        "mode": args.mode,
        "status": "FAIL",
        "started_at_utc": utc_now(),
    }
    exit_code = 1
    try:
        client.connect()
        client.acquire(ports=list(PORTS), force=True)
        result = run_prepare(client, args) if args.mode == "prepare" else run_burst(client, args)
        exit_code = 0
    except Exception as exc:
        result["error"] = repr(exc)
        result["error_type"] = type(exc).__name__
        result["traceback"] = traceback.format_exc()
        result["finished_at_utc"] = utc_now()
        print(f"CLIENT_ERROR {exc!r}", file=sys.stderr, flush=True)
        traceback.print_exc(file=sys.stderr)
    finally:
        try:
            if client.is_connected():
                client.stop(ports=list(PORTS))
                client.remove_all_streams(ports=list(PORTS))
                client.disconnect(stop_traffic=True, release_ports=True)
        except Exception as cleanup_exc:
            result["client_cleanup_error"] = repr(cleanup_exc)
            result["status"] = "FAIL"
            exit_code = 1
        with open(args.summary, "w", encoding="utf-8") as handle:
            json.dump(sanitize(result), handle, indent=2, sort_keys=True)
            handle.write("\n")
        print(json.dumps({"status": result.get("status"), "summary": args.summary}, sort_keys=True), flush=True)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
