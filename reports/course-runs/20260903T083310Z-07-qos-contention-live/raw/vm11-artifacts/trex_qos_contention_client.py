#!/usr/bin/env python3
"""Drive the two BCM ports as a bounded low-priority load into one egress."""

import argparse
import json
import math
import pathlib
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
    STLTXCont,
    STLTXSingleBurst,
)


PORTS = (0, 1)
SOURCE_MACS = {0: "00:0a:f7:f8:48:a0", 1: "00:0a:f7:f8:48:a1"}
PORT_FIELDS = ("opackets", "obytes", "ipackets", "ibytes", "ierrors", "oerrors")


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


def packet(src_mac, dst_mac, run_id, stage, size):
    marker = f"FLLE-QOS|RUN={run_id}|STAGE={stage}|".encode("ascii")
    frame = Ether(src=src_mac, dst=dst_mac, type=0x88B5) / Raw(load=marker)
    if len(frame) > size:
        raise ValueError(f"marker frame {len(frame)} exceeds requested size {size}")
    frame /= Raw(load=b"q" * (size - len(frame)))
    builder = STLPktBuilder(pkt=frame)
    if builder.get_pkt_len() != size:
        raise AssertionError((builder.get_pkt_len(), size))
    return builder


def deltas(before, after):
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
        observations.append({"attempt": attempt, "links": links, "consecutive": consecutive})
        print(
            f"LINK_STABLE attempt={attempt} links={links} consecutive={consecutive}",
            flush=True,
        )
        if consecutive >= 10:
            break
        time.sleep(0.2)
    if consecutive < 10:
        raise RuntimeError("dual links did not become stable")
    time.sleep(5)
    info = client.get_port_info(ports=list(PORTS))
    if [entry.get("link") for entry in info] != ["UP", "UP"]:
        raise RuntimeError(f"link changed during settle: {info}")
    return {"observations": observations, "post_settle": sanitize(info)}


def warmup(client, run_id, tx_port, rx_port):
    before = client.get_stats(ports=list(PORTS))
    stream = STLStream(
        name=f"flle-qos-warmup-{tx_port}-{rx_port}",
        packet=packet(
            SOURCE_MACS[tx_port], SOURCE_MACS[rx_port], run_id, "warmup", 128
        ),
        mode=STLTXSingleBurst(total_pkts=256, pps=1000),
    )
    client.add_streams(stream, ports=[tx_port])
    client.start(ports=[tx_port], force=True)
    client.wait_on_traffic(ports=[tx_port], timeout=20, rx_delay_ms=1000)
    time.sleep(2)
    after = client.get_stats(ports=list(PORTS))
    client.remove_all_streams(ports=[tx_port])
    delta = deltas(before, after)
    if delta[str(tx_port)]["opackets"] != 256:
        raise RuntimeError(f"warmup tx mismatch: {delta}")
    if delta[str(rx_port)]["ipackets"] < 256:
        raise RuntimeError(f"warmup rx mismatch: {delta}")
    if any(delta[str(port)][field] for port in PORTS for field in ("ierrors", "oerrors")):
        raise RuntimeError(f"warmup errors: {delta}")
    return {"tx_port": tx_port, "rx_port": rx_port, "deltas": delta}


def run_prepare(client, args):
    return {
        "run_id": args.run_id,
        "mode": "prepare",
        "started_at_utc": utc_now(),
        "readiness": stable_link_gate(client),
        "warmup": [warmup(client, args.run_id, 0, 1), warmup(client, args.run_id, 1, 0)],
        "status": "PASS",
        "finished_at_utc": utc_now(),
    }


def run_load(client, args):
    if not (100000 <= args.pps <= 800000):
        raise ValueError("pps per ingress must be in [100000, 800000]")
    if not (3 <= args.duration <= 20):
        raise ValueError("duration must be in [3, 20] seconds")
    if args.packet_size != 1514:
        raise ValueError("contention frame must be 1514 bytes without FCS")
    info = client.get_port_info(ports=list(PORTS))
    if [entry.get("link") for entry in info] != ["UP", "UP"]:
        raise RuntimeError(f"links not both UP: {info}")
    for port in PORTS:
        client.add_streams(
            STLStream(
                name=f"flle-qos-load-{args.stage}-p{port}",
                packet=packet(
                    SOURCE_MACS[port], args.dst_mac, args.run_id, args.stage, args.packet_size
                ),
                mode=STLTXCont(pps=args.pps),
            ),
            ports=[port],
        )
    before = client.get_stats(ports=list(PORTS))
    started_utc = utc_now()
    started_ns = time.perf_counter_ns()
    client.start(ports=list(PORTS), duration=args.duration, force=True)
    pathlib.Path(args.ready).write_text(
        json.dumps(
            {
                "run_id": args.run_id,
                "stage": args.stage,
                "status": "RUNNING",
                "started_at_utc": started_utc,
                "duration_seconds": args.duration,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    client.wait_on_traffic(ports=list(PORTS), timeout=args.duration + 30, rx_delay_ms=0)
    finished_ns = time.perf_counter_ns()
    time.sleep(1)
    after = client.get_stats(ports=list(PORTS))
    client.remove_all_streams(ports=list(PORTS))
    delta = deltas(before, after)
    elapsed = (finished_ns - started_ns) / 1_000_000_000
    total_packets = sum(delta[str(port)]["opackets"] for port in PORTS)
    total_bytes = sum(delta[str(port)]["obytes"] for port in PORTS)
    errors = {
        f"port_{port}_{field}": delta[str(port)][field]
        for port in PORTS
        for field in ("ierrors", "oerrors")
    }
    result = {
        "run_id": args.run_id,
        "mode": "load",
        "stage": args.stage,
        "status": "PASS",
        "started_at_utc": started_utc,
        "finished_at_utc": utc_now(),
        "configured_pps_per_ingress": args.pps,
        "configured_duration_seconds": args.duration,
        "actual_wait_seconds": elapsed,
        "frame_without_fcs_bytes": args.packet_size,
        "destination_mac": args.dst_mac,
        "nominal_aggregate_wire_gbps": 2 * args.pps * (args.packet_size + 24) * 8 / 1e9,
        "actual_total_opackets_delta": total_packets,
        "actual_total_obytes_delta": total_bytes,
        "counter_bytes_over_wait_gbps": total_bytes * 8 / elapsed / 1e9,
        "port_counter_deltas": delta,
        "io_error_deltas": errors,
        "warnings": sanitize(client.get_warnings()),
    }
    if total_packets <= 0 or any(errors.values()):
        result["status"] = "FAIL"
        raise RuntimeError(f"load acceptance failed: {result}")
    return result


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--mode", choices=("prepare", "load"), required=True)
    parser.add_argument("--summary", required=True)
    parser.add_argument("--ready")
    parser.add_argument("--stage")
    parser.add_argument("--dst-mac")
    parser.add_argument("--pps", type=int, default=600000)
    parser.add_argument("--duration", type=int, default=8)
    parser.add_argument("--packet-size", type=int, default=1514)
    return parser.parse_args()


def main():
    args = parse_args()
    if args.mode == "load" and not all((args.ready, args.stage, args.dst_mac)):
        raise SystemExit("load mode requires --ready, --stage and --dst-mac")
    result = {
        "run_id": args.run_id,
        "mode": args.mode,
        "status": "FAIL",
        "started_at_utc": utc_now(),
    }
    exit_code = 1
    client = STLClient(
        server="127.0.0.1",
        username="flle-qos",
        verbose_level="error",
        sync_timeout=5,
        async_timeout=5,
    )
    try:
        client.connect()
        client.acquire(ports=list(PORTS), force=True)
        result = run_prepare(client, args) if args.mode == "prepare" else run_load(client, args)
        exit_code = 0
    except Exception as exc:
        result["error"] = repr(exc)
        result["traceback"] = traceback.format_exc()
        print(result["traceback"], file=sys.stderr)
    finally:
        try:
            client.stop(ports=list(PORTS))
        except Exception:
            pass
        try:
            client.remove_all_streams(ports=list(PORTS))
        except Exception:
            pass
        try:
            client.release(ports=list(PORTS))
        except Exception:
            pass
        try:
            client.disconnect()
        except Exception:
            pass
        pathlib.Path(args.summary).write_text(
            json.dumps(sanitize(result), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
