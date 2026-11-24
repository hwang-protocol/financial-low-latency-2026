#!/usr/bin/env python3
"""Current-RUN TRex readiness and fixed-profile Market Day pressure."""

import argparse
import json
import math
import sys
import time
import traceback

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
FIELDS = ("opackets", "obytes", "ipackets", "ibytes", "ierrors", "oerrors")
SOURCE_MACS = {0: "00:0a:f7:f8:48:a0", 1: "00:0a:f7:f8:48:a1"}
DESTINATION_MAC = "00:0f:53:d3:af:21"
PHASE_PPS = {"CALM": 10000, "BURST": 25000}
COUNT = 4096
FRAME_BYTES = 1514


def clean(value):
    if isinstance(value, dict):
        return {str(key): clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def packet(run_id, phase, port, size, destination=DESTINATION_MAC):
    marker = (
        "FLLE-MARKET-DAY|RUN=%s|PHASE=%s|PORT=%d|"
        % (run_id, phase, port)
    ).encode("ascii")
    base = Ether(
        src=SOURCE_MACS[port], dst=destination, type=0x88B5
    ) / Raw(load=marker)
    if len(base) > size:
        raise ValueError("marker exceeds fixed frame size")
    result = STLPktBuilder(pkt=base / Raw(load=b"x" * (size - len(base))))
    if result.get_pkt_len() != size:
        raise RuntimeError("TRex packet builder changed the frame size")
    return result


def deltas(before, after):
    return {
        str(port): {
            field: after[port].get(field, 0) - before[port].get(field, 0)
            for field in FIELDS
        }
        for port in PORTS
    }


def stable_links(client, evidence):
    observations = evidence.setdefault("observations", [])
    consecutive = 0
    for attempt in range(1, 151):
        info = client.get_port_info(ports=list(PORTS))
        links = [item.get("link") for item in info]
        consecutive = consecutive + 1 if links == ["UP", "UP"] else 0
        observation = {
            "attempt": attempt,
            "monotonic_ns": time.monotonic_ns(),
            "links": links,
            "consecutive": consecutive,
        }
        observations.append(observation)
        print(
            "event=trex_link monotonic_ns=%d attempt=%d links=%s consecutive=%d"
            % (
                observation["monotonic_ns"],
                attempt,
                ",".join(str(item) for item in links),
                consecutive,
            ),
            flush=True,
        )
        if consecutive >= 10:
            break
        time.sleep(0.2)
    if consecutive < 10:
        raise RuntimeError("TRex ports did not remain dual-UP")
    time.sleep(5)
    final = client.get_port_info(ports=list(PORTS))
    evidence["after_settle"] = clean(final)
    if [item.get("link") for item in final] != ["UP", "UP"]:
        raise RuntimeError("TRex link changed during settle")


def warmup(client, run_id, tx_port, rx_port, evidence):
    evidence.update({
        "tx_port": tx_port,
        "rx_port": rx_port,
        "configured_pps": 1000,
        "requested_packets": 256,
        "frame_without_fcs_bytes": 128,
    })
    before = client.get_stats(ports=list(PORTS))
    evidence["port_counters_before"] = clean(before)
    stream = STLStream(
        name="market-day-warmup-%d" % tx_port,
        packet=packet(
            run_id, "OPEN", tx_port, 128, SOURCE_MACS[rx_port]
        ),
        mode=STLTXSingleBurst(total_pkts=256, pps=1000),
    )
    client.add_streams(stream, ports=[tx_port])
    try:
        client.start(ports=[tx_port], force=True)
        client.wait_on_traffic(ports=[tx_port], timeout=20, rx_delay_ms=1000)
        time.sleep(2)
    finally:
        after = client.get_stats(ports=list(PORTS))
        evidence["port_counters_after"] = clean(after)
        evidence["deltas"] = deltas(before, after)
    client.remove_all_streams(ports=[tx_port])
    delta = evidence["deltas"]
    if (
        delta[str(tx_port)]["opackets"] != 256
        or delta[str(rx_port)]["ipackets"] < 256
    ):
        raise RuntimeError("TRex warmup counters disagree: %r" % delta)


def prepare(client, run_id, result):
    result.update({
        "run_id": run_id,
        "mode": "prepare",
        "clock_domain": "vm-broadcom-01 CLOCK_MONOTONIC",
        "started_monotonic_ns": time.monotonic_ns(),
        "links": {},
        "warmup": [],
    })
    stable_links(client, result["links"])
    for tx_port, rx_port in ((0, 1), (1, 0)):
        evidence = {}
        result["warmup"].append(evidence)
        warmup(client, run_id, tx_port, rx_port, evidence)
    result["finished_monotonic_ns"] = time.monotonic_ns()


def pressure(client, run_id, phase, result):
    pps = PHASE_PPS[phase]
    result.update({
        "run_id": run_id,
        "mode": "pressure",
        "phase": phase,
        "clock_domain": "vm-broadcom-01 CLOCK_MONOTONIC",
        "configured_pps_per_ingress": pps,
        "requested_packets_per_ingress": COUNT,
        "frame_without_fcs_bytes": FRAME_BYTES,
        "nominal_aggregate_wire_gbps": (
            2 * pps * (FRAME_BYTES + 24) * 8 / 1_000_000_000
        ),
    })
    info = client.get_port_info(ports=list(PORTS))
    result["port_info"] = clean(info)
    if [item.get("link") for item in info] != ["UP", "UP"]:
        raise RuntimeError("TRex ports are not dual-UP")
    for port in PORTS:
        stream = STLStream(
            name="market-day-%s-%d" % (phase.lower(), port),
            packet=packet(run_id, phase, port, FRAME_BYTES),
            mode=STLTXSingleBurst(total_pkts=COUNT, pps=pps),
        )
        client.add_streams(stream, ports=[port])
    before = client.get_stats(ports=list(PORTS))
    result["port_counters_before"] = clean(before)
    started = time.monotonic_ns()
    result["started_monotonic_ns"] = started
    try:
        client.start(ports=list(PORTS), force=True)
        client.wait_on_traffic(ports=list(PORTS), timeout=30, rx_delay_ms=0)
    finally:
        result["finished_monotonic_ns"] = time.monotonic_ns()
        after = client.get_stats(ports=list(PORTS))
        result["port_counters_after"] = clean(after)
        result["port_counter_deltas"] = deltas(before, after)
    client.remove_all_streams(ports=list(PORTS))
    delta = result["port_counter_deltas"]
    errors = [
        delta[str(port)][field]
        for port in PORTS
        for field in ("ierrors", "oerrors")
    ]
    if any(delta[str(port)]["opackets"] != COUNT for port in PORTS):
        raise RuntimeError("TRex TX count differs from fixed profile")
    if any(errors):
        raise RuntimeError("TRex ordinary port I/O error counter changed")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--mode", choices=("prepare", "pressure"), required=True)
    parser.add_argument("--phase", choices=("CALM", "BURST"))
    parser.add_argument("--summary", required=True)
    args = parser.parse_args()
    if args.mode == "pressure" and not args.phase:
        parser.error("--phase is required with pressure")
    client = STLClient(
        server="127.0.0.1", username="flle-market-day",
        verbose_level="error", sync_timeout=5, async_timeout=5
    )
    result = {"run_id": args.run_id, "mode": args.mode}
    if args.phase:
        result["phase"] = args.phase
    code = 1
    try:
        client.connect()
        client.acquire(ports=list(PORTS), force=True)
        if args.mode == "prepare":
            prepare(client, args.run_id, result)
        else:
            pressure(client, args.run_id, args.phase, result)
        code = 0
    except Exception as error:
        result["error"] = repr(error)
        result["traceback"] = traceback.format_exc()
        traceback.print_exc()
    finally:
        try:
            if client.is_connected():
                client.stop(ports=list(PORTS))
                client.remove_all_streams(ports=list(PORTS))
                client.disconnect(stop_traffic=True, release_ports=True)
        except Exception as error:
            result["cleanup_error"] = repr(error)
            code = 1
        with open(args.summary, "w", encoding="utf-8") as handle:
            json.dump(clean(result), handle, indent=2, sort_keys=True)
            handle.write("\n")
        print(json.dumps(clean(result), sort_keys=True), flush=True)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
