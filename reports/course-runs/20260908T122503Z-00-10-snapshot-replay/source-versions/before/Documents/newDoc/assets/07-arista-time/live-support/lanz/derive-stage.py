#!/usr/bin/env python3
"""Derive one fixed-count lower-trigger stage from TRex and delayed VM2 evidence."""

import argparse
import json
import re


SELECTED_ETHTOOL = (
    "port_rx_bytes",
    "port_rx_good_bytes",
    "port_rx_bad_bytes",
    "port_rx_packets",
    "port_rx_good",
    "port_rx_bad",
    "port_rx_pause",
    "port_rx_control",
    "port_rx_unicast",
    "port_rx_multicast",
    "port_rx_broadcast",
    "port_rx_1024_to_15xx",
    "port_rx_15xx_to_jumbo",
    "port_rx_gtjumbo",
    "port_rx_bad_gtjumbo",
    "port_rx_overflow",
    "port_rx_nodesc_drops",
    "port_rx_pm_trunc_bb_overflow",
    "port_rx_pm_discard_bb_overflow",
    "port_rx_pm_trunc_vfifo_full",
    "port_rx_pm_discard_vfifo_full",
    "port_rx_pm_trunc_qbb",
    "port_rx_pm_discard_qbb",
    "port_rx_pm_discard_mapping",
    "port_rx_dp_q_disabled_packets",
    "port_rx_dp_di_dropped_packets",
    "rx_noskb_drops",
    "rx_nodesc_trunc",
    "rx_reset",
    "rx_tobe_disc",
    "rx_eth_crc_err",
    "rx_frm_trunc",
    "rx_xdp_drops",
    "rx_xdp_bad_drops",
)

HARDWARE_DROP_OR_ERROR_FIELDS = (
    "port_rx_bad_bytes",
    "port_rx_bad",
    "port_rx_bad_gtjumbo",
    "port_rx_overflow",
    "port_rx_nodesc_drops",
    "port_rx_pm_trunc_bb_overflow",
    "port_rx_pm_discard_bb_overflow",
    "port_rx_pm_trunc_vfifo_full",
    "port_rx_pm_discard_vfifo_full",
    "port_rx_pm_trunc_qbb",
    "port_rx_pm_discard_qbb",
    "port_rx_pm_discard_mapping",
    "port_rx_dp_q_disabled_packets",
    "port_rx_dp_di_dropped_packets",
    "rx_noskb_drops",
    "rx_nodesc_trunc",
    "rx_reset",
    "rx_tobe_disc",
    "rx_eth_crc_err",
    "rx_frm_trunc",
    "rx_xdp_drops",
    "rx_xdp_bad_drops",
)


def parse_snapshot(path):
    sections = {"meta": {}, "sysfs": {}, "ethtool": {}}
    current = "meta"
    with open(path, encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if line == "=== sysfs ===":
                current = "sysfs"
                continue
            if line == "=== ethtool ===":
                current = "ethtool"
                continue
            equal = re.fullmatch(r"([A-Za-z0-9_]+)=(.+)", line)
            colon = re.fullmatch(r"([A-Za-z0-9_]+):\s*(-?[0-9]+)", line)
            if equal:
                key, value = equal.groups()
                try:
                    value = int(value)
                except ValueError:
                    pass
                sections[current][key] = value
            elif colon:
                key, value = colon.groups()
                sections[current][key] = int(value)
    return sections


def numeric_delta(before, after, keys):
    result = {}
    for key in keys:
        if key in before and key in after:
            result[key] = after[key] - before[key]
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--trex", required=True)
    parser.add_argument("--before", required=True)
    parser.add_argument("--after", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    with open(args.trex, encoding="utf-8") as handle:
        trex = json.load(handle)
    before = parse_snapshot(args.before)
    after = parse_snapshot(args.after)
    sysfs_keys = sorted(set(before["sysfs"]) & set(after["sysfs"]))
    sysfs_delta = numeric_delta(before["sysfs"], after["sysfs"], sysfs_keys)
    ethtool_delta = numeric_delta(before["ethtool"], after["ethtool"], SELECTED_ETHTOOL)

    actual_tx_packets = trex["actual_total_opackets_delta"]
    receiver_packets = ethtool_delta.get("port_rx_packets")
    target_size_packets = ethtool_delta.get("port_rx_1024_to_15xx")
    hardware_drop_or_error_delta = {
        key: ethtool_delta[key]
        for key in HARDWARE_DROP_OR_ERROR_FIELDS
        if key in ethtool_delta
    }
    target_size_exact = target_size_packets == actual_tx_packets
    hardware_clean = all(value == 0 for value in hardware_drop_or_error_delta.values())
    accepted = trex["status"] == "PASS" and target_size_exact and hardware_clean
    result = {
        "stage": trex["stage"],
        "status": "PASS" if accepted else "FAIL",
        "trex": {
            "ingress_mode": trex["ingress_mode"],
            "active_tx_ports": trex["active_tx_ports"],
            "configured_pps_per_ingress": trex["configured_pps_per_ingress"],
            "requested_packets_per_active_ingress": trex[
                "requested_packets_per_active_ingress"
            ],
            "nominal_aggregate_wire_gbps": trex["nominal_aggregate_wire_gbps"],
            "actual_total_opackets_delta": actual_tx_packets,
            "actual_total_obytes_delta": trex["actual_total_obytes_delta"],
            "actual_obytes_per_packet": trex["actual_obytes_per_packet"],
            "start_to_wait_complete_wall_seconds": trex["start_to_wait_complete_wall_seconds"],
            "counter_bytes_over_api_wall_gbps": trex["counter_bytes_over_api_wall_gbps"],
            "port_counter_deltas": trex["port_counter_deltas"],
            "io_error_deltas": trex["io_error_deltas"],
        },
        "vm2": {
            "before_captured_at_utc": before["meta"].get("captured_at_utc"),
            "after_captured_at_utc": after["meta"].get("captured_at_utc"),
            "sysfs_delta": sysfs_delta,
            "selected_ethtool_delta": ethtool_delta,
            "target_size_packets": target_size_packets,
            "target_size_exact_to_trex_tx": target_size_exact,
            "hardware_drop_or_error_delta": hardware_drop_or_error_delta,
            "hardware_drop_or_error_clean": hardware_clean,
            "port_rx_packets_minus_trex_tx_packets": (
                receiver_packets - actual_tx_packets if receiver_packets is not None else None
            ),
        },
    }
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
