#!/usr/bin/env python3
"""Single-host socket mini-labs used by Chapter 3 teaching cards."""

import argparse
import select
import socket
import struct


HEADER = struct.Struct("!HBBHHIQQI")
TICK = struct.Struct("!H4sHIII")


def make_tick(sequence):
    body = TICK.pack(0x4D44, b"AAPL", 0, 1234501, 10, sequence)
    return HEADER.pack(0x464C, 1, 1, 0, 32, 20, 7, 701, sequence) + body


def decode_tick(data):
    if len(data) != 52:
        raise ValueError("BAD_PACKET_SIZE")
    head = HEADER.unpack(data[:32])
    body = TICK.unpack(data[32:])
    if head[:6] != (0x464C, 1, 1, 0, 32, 20):
        raise ValueError("BAD_HEADER")
    if body[0] != 0x4D44 or body[5] != head[8]:
        raise ValueError("BAD_TICK")
    return head, body


def udp_pair():
    receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver.bind(("127.0.0.1", 0))
    receiver.settimeout(1)
    sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sender.bind(("127.0.0.1", 0))
    return sender, receiver


def tcp_pair():
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    client = socket.create_connection(listener.getsockname(), timeout=1)
    server, unused_peer = listener.accept()
    listener.close()
    return client, server


def frame(payload):
    return struct.pack("!I", len(payload)) + payload


def read_exact(sock, size):
    data = b""
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            raise RuntimeError("early EOF")
        data += chunk
    return data


def read_frame(sock):
    size = struct.unpack("!I", read_exact(sock, 4))[0]
    return read_exact(sock, size)


def run_udp_datagram():
    sender, receiver = udp_pair()
    try:
        for sequence in range(5):
            sender.sendto(make_tick(sequence), receiver.getsockname())
        for unused in range(5):
            data, unused_peer = receiver.recvfrom(2048)
            head, body = decode_tick(data)
            print(
                "bytes=%d magic=0x%04x version=%d session=%d sequence=%d symbol=%s"
                % (len(data), head[0], head[1], head[6], head[8], body[1].decode())
            )
    finally:
        sender.close()
        receiver.close()


def run_udp_gap_duplicate():
    sender, receiver = udp_pair()
    seen = set()
    highest = -1
    events = []
    try:
        for sequence in [0, 1, 3, 3, 4]:
            sender.sendto(make_tick(sequence), receiver.getsockname())
        for unused in range(5):
            data, unused_peer = receiver.recvfrom(2048)
            sequence = decode_tick(data)[0][8]
            if sequence in seen:
                event = "DUPLICATE"
            elif sequence > highest + 1:
                event = "GAP"
            else:
                event = "NEW"
            seen.add(sequence)
            highest = max(highest, sequence)
            events.append(event)
            print("sequence=%d event=%s" % (sequence, event))
        print(
            "gap_count=%d duplicate_count=%d"
            % (events.count("GAP"), events.count("DUPLICATE"))
        )
    finally:
        sender.close()
        receiver.close()


def run_tcp_framing():
    client, server = tcp_pair()
    try:
        server.sendall(frame(b"ACK") + frame(b"EXECUTION"))
        first = read_frame(client)
        second = read_frame(client)
        print("frame1=%s frame2=%s" % (first.decode(), second.decode()))
    finally:
        client.close()
        server.close()


def run_order_responses():
    client, server = tcp_pair()
    try:
        client.sendall(frame(b"ORDER:7001"))
        order = read_frame(server).decode()
        correlation = order.split(":")[1]
        server.sendall(frame(("ACK:" + correlation).encode()))
        server.sendall(frame(("EXECUTION:" + correlation).encode()))
        print(read_frame(client).decode())
        print(read_frame(client).decode())
    finally:
        client.close()
        server.close()


def recv_or_zero(receiver):
    try:
        receiver.recvfrom(256)
        return 1
    except socket.timeout:
        return 0


def run_multicast_membership():
    group = "239.255.23.5"
    loopback = "127.0.0.1"
    receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    receiver.bind(("", 0))
    receiver.settimeout(0.15)
    sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sender.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(loopback))
    sender.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
    destination = (group, receiver.getsockname()[1])
    membership = socket.inet_aton(group) + socket.inet_aton(loopback)
    try:
        sender.sendto(b"PRE", destination)
        pre = recv_or_zero(receiver)
        receiver.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, membership)
        sender.sendto(b"JOINED", destination)
        joined = receiver.recvfrom(256)[0].decode()
        receiver.setsockopt(socket.IPPROTO_IP, socket.IP_DROP_MEMBERSHIP, membership)
        sender.sendto(b"POST", destination)
        post = recv_or_zero(receiver)
        print("pre=%d joined=%s post=%d" % (pre, joined, post))
    finally:
        sender.close()
        receiver.close()


def feed_sockets():
    feed_a = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    feed_b = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    feed_a.bind(("127.0.0.1", 0))
    feed_b.bind(("127.0.0.1", 0))
    sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return sender, [feed_a, feed_b], {feed_a: "A", feed_b: "B"}


def receive_ready(feeds):
    ready = select.select(feeds, [], [], 1)[0]
    if not ready:
        raise TimeoutError("no feed datagram")
    return ready


def run_feed_first_valid():
    sender, feeds, names = feed_sockets()
    accepted = {}
    duplicates = 0
    try:
        sender.sendto(make_tick(0), feeds[0].getsockname())
        for current in receive_ready(feeds):
            sequence = decode_tick(current.recv(2048))[0][8]
            accepted[sequence] = names[current]
        sender.sendto(make_tick(0), feeds[1].getsockname())
        for current in receive_ready(feeds):
            sequence = decode_tick(current.recv(2048))[0][8]
            if sequence in accepted:
                duplicates += 1
            else:
                accepted[sequence] = names[current]
        print("accepted_source=%s duplicates=%d" % (accepted[0], duplicates))
    finally:
        sender.close()
        for current in feeds:
            current.close()


def drain_feed_packets(feeds, names, receipt_target):
    accepted = {}
    receipts = 0
    while receipts < receipt_target:
        for current in receive_ready(feeds):
            sequence = decode_tick(current.recv(2048))[0][8]
            receipts += 1
            if sequence not in accepted:
                accepted[sequence] = names[current]
    return accepted


def run_feed_recovery():
    sender, feeds, names = feed_sockets()
    try:
        for sequence in [0, 1, 2, 3, 5]:
            sender.sendto(make_tick(sequence), feeds[0].getsockname())
        sender.sendto(make_tick(4), feeds[1].getsockname())
        accepted = drain_feed_packets(feeds, names, 6)
        print(
            "sequence4_source=%s unified=%s"
            % (accepted[4], sorted(accepted))
        )
    finally:
        sender.close()
        for current in feeds:
            current.close()


def run_feed_true_gap():
    sender, feeds, names = feed_sockets()
    try:
        for current in feeds:
            for sequence in [0, 1, 2, 3, 5]:
                sender.sendto(make_tick(sequence), current.getsockname())
        accepted = drain_feed_packets(feeds, names, 10)
        missing = [number for number in range(6) if number not in accepted]
        print("missing=%s" % missing)
    finally:
        sender.close()
        for current in feeds:
            current.close()


RUNNERS = {
    "udp-datagram": run_udp_datagram,
    "udp-gap-duplicate": run_udp_gap_duplicate,
    "tcp-framing": run_tcp_framing,
    "order-responses": run_order_responses,
    "multicast-membership": run_multicast_membership,
    "feed-first-valid": run_feed_first_valid,
    "feed-recovery": run_feed_recovery,
    "feed-true-gap": run_feed_true_gap,
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("lab", choices=RUNNERS)
    args = parser.parse_args()
    RUNNERS[args.lab]()


if __name__ == "__main__":
    main()
