#!/usr/bin/env python3
"""Find one live MANUAL OUCH O -> A -> E exchange in a TCP pcap."""

from __future__ import annotations

import argparse
import re
import struct
from pathlib import Path

from pcap_tools import parse_ethernet_ipv4, parse_tcp, read_pcap, reassemble, text

OUCH_TYPE = {
    "O": "Enter Order",
    "A": "Order Accepted",
    "E": "Order Executed",
    "J": "Order Rejected",
}
SOUP_TYPE = {
    "U": "Unsequenced Data",
    "S": "Sequenced Data",
}


def soup_frames(stream: bytes) -> list[tuple[str, bytes]]:
    """按 Packet Length 从重组后的 TCP 字节里切出 Soup 逻辑包。"""
    frames, cursor = [], 0
    while cursor + 2 <= len(stream):
        length = struct.unpack_from("!H", stream, cursor)[0]
        if length < 1 or cursor + 2 + length > len(stream):
            break
        frames.append((chr(stream[cursor + 2]), stream[cursor + 3:cursor + 2 + length]))
        cursor += 2 + length
    return frames


def format_mac(raw: bytes) -> str:
    """把 6 字节 MAC 写成冒号分隔的十六进制。"""
    return ":".join(f"{byte:02x}" for byte in raw)


def find_enter_frame(packets: list, port: int, order: bytes) -> dict | None:
    """找到把完整 Soup U + OUCH Enter Order 装在一个 TCP payload 里的那一帧。"""
    needle = struct.pack("!H", 48) + b"U" + order
    for number, captured in enumerate(packets, start=1):
        ip = parse_ethernet_ipv4(captured.data)
        if not ip:
            continue
        tcp = parse_tcp(ip)
        if not tcp or not tcp.payload:
            continue
        if ip.source != "20.1.1.2" or ip.destination != "20.1.1.1":
            continue
        if tcp.source_port != port or tcp.destination_port != 43120:
            continue
        if needle in tcp.payload:
            return {"number": number, "frame": captured.data, "ip": ip, "tcp": tcp, "order": order}
    return None


def print_packet_details(sample: dict) -> None:
    """按 Wireshark Packet Details 树打印 Enter Order 所在帧，字段名用官方英文。"""
    frame = sample["frame"]
    ip = sample["ip"]
    tcp = sample["tcp"]
    order = sample["order"]
    print(f"Frame {sample['number']}: {len(frame)} bytes on wire, {len(frame)} bytes captured")
    print(f"Ethernet II, Src: {format_mac(frame[6:12])}, Dst: {format_mac(frame[0:6])}")
    print(f"Internet Protocol Version 4, Src: {ip.source}, Dst: {ip.destination}")
    print(f"Transmission Control Protocol, Src Port: {tcp.source_port}, Dst Port: {tcp.destination_port}")
    print("SoupBinTCP")
    print("    Packet Length: 48")
    print(f"    Packet Type: U ({SOUP_TYPE['U']})")
    print("Nasdaq OUCH 5.0")
    print(f"    Type: O ({OUCH_TYPE['O']})")
    print(f"    UserRefNum: {struct.unpack_from('!I', order, 1)[0]}")
    print(f"    Side: {chr(order[5])}")
    print(f"    Quantity: {struct.unpack_from('!I', order, 6)[0]}")
    print(f"    Symbol: {text(order[10:18])}")
    print(f"    Price: {struct.unpack_from('!Q', order, 18)[0]}")
    print(f"    Time In Force: {chr(order[26])}")
    print(f"    Display: {chr(order[27])}")
    print(f"    Capacity: {chr(order[28])}")
    print(f"    InterMarket Sweep Eligibility: {chr(order[29])}")
    print(f"    CrossType: {chr(order[30])}")
    print(f"    ClOrdID: {text(order[31:45])}")
    print(f"    Appendage Length: {struct.unpack_from('!H', order, 45)[0]}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("pcap")
    parser.add_argument("sessions")
    parser.add_argument("--first-trade", type=Path, help="Select the client order ID reported by the trade check")
    args = parser.parse_args()
    expected_ref = None
    if args.first_trade:
        refs = re.findall(r"^order_id=(\d+)\b", args.first_trade.read_text(encoding="utf-8"), re.MULTILINE)
        assert len(refs) == 1, "expected exactly one completed client order ID in first-trade output"
        expected_ref = int(refs[0])
    session_text = Path(args.sessions).read_text(encoding="utf-8")
    auto_pid = int(re.search(r"auto_pid=(\d+)", session_text).group(1))
    manual_pid = int(re.search(r"manual_pid=(\d+)", session_text).group(1))
    established = re.findall(r"20\.1\.1\.2:(\d+)\s+20\.1\.1\.1:43120\s+.*?pid=(\d+)", session_text)
    manual_ports = {int(port) for port, pid in established if int(pid) == manual_pid}
    assert len(manual_ports) == 1, "expected one established MANUAL connection; collect sessions after submitting the order"
    manual_port = next(iter(manual_ports))
    magic, linktype, packets = read_pcap(args.pcap)
    assert linktype == 1
    flows: dict[int, dict[str, list[tuple[int, bytes]]]] = {}
    for captured in packets:
        ip = parse_ethernet_ipv4(captured.data)
        if not ip:
            continue
        tcp = parse_tcp(ip)
        if not tcp or not tcp.payload:
            continue
        if ip.source == "20.1.1.2" and ip.destination == "20.1.1.1" and tcp.destination_port == 43120:
            flows.setdefault(tcp.source_port, {"client": [], "server": []})["client"].append((tcp.sequence, tcp.payload))
        elif ip.source == "20.1.1.1" and ip.destination == "20.1.1.2" and tcp.source_port == 43120:
            flows.setdefault(tcp.destination_port, {"client": [], "server": []})["server"].append((tcp.sequence, tcp.payload))
    selected = None
    for port, directions in flows.items():
        if port != manual_port:
            continue
        client = soup_frames(reassemble(directions["client"]))
        for outer, payload in client:
            if outer == "U" and len(payload) == 47 and payload[:1] == b"O" and text(payload[31:45]).startswith("MANU"):
                if expected_ref is not None and struct.unpack_from("!I", payload, 1)[0] != expected_ref:
                    continue
                selected = (port, payload, soup_frames(reassemble(directions["server"])))
                break
        if selected:
            break
    assert selected, f"expected MANUAL OUCH Enter Order for client ID {expected_ref} in the capture"
    port, order, server = selected
    assert port == manual_port, "captured MANUAL flow does not belong to MANUAL PID"
    user_ref = struct.unpack_from("!I", order, 1)[0]
    side = {66: "BUY", 83: "SELL"}[order[5]]
    quantity = struct.unpack_from("!I", order, 6)[0]
    symbol = text(order[10:18])
    limit_price = struct.unpack_from("!Q", order, 18)[0]
    clordid = text(order[31:45])
    responses = [payload for outer, payload in server if outer == "S" and len(payload) >= 13 and struct.unpack_from("!I", payload, 9)[0] == user_ref]
    accepted = next((payload for payload in responses if len(payload) == 64 and payload[:1] == b"A"), None)
    executed = next((payload for payload in responses if len(payload) == 36 and payload[:1] == b"E"), None)
    assert accepted is not None and executed is not None, f"capture lacks accepted/executed responses for client ID {user_ref}"
    accepted_ref = struct.unpack_from("!Q", accepted, 36)[0]
    fill_quantity = struct.unpack_from("!I", executed, 13)[0]
    fill_price = struct.unpack_from("!Q", executed, 17)[0]
    match_number = struct.unpack_from("!Q", executed, 26)[0]
    assert struct.unpack_from("!I", accepted, 9)[0] == user_ref == struct.unpack_from("!I", executed, 9)[0]
    assert text(accepted[48:62]) == clordid and fill_quantity == quantity
    print(f"pcap_magic={magic} linktype={linktype} established_sessions={len(established)} captured_payload_flows={len(flows)} auto_pid={auto_pid} manual_pid={manual_pid}")
    print(f"manual_flow=20.1.1.2:{port}->20.1.1.1:43120 soup_client=U soup_server=S")
    print(f"OUCH_O user_ref={user_ref} clordid={clordid} symbol={symbol} side={side} quantity={quantity} limit_x10000={limit_price}")
    print(f"OUCH_A user_ref={user_ref} order_ref={accepted_ref} state={chr(accepted[47])}")
    print(f"OUCH_E user_ref={user_ref} filled={fill_quantity} fill_x10000={fill_price} match={match_number}")
    print("identity=user_ref:O=A=E clordid:O=A verdict=LIVE_ORDER_FLOW_PASS")
    sample = find_enter_frame(packets, port, order)
    if sample:
        print_packet_details(sample)


if __name__ == "__main__":
    main()
