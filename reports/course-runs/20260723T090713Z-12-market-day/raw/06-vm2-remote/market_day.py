#!/usr/bin/env python3
"""Minimal networked Market Day application used by chapter 12."""

import os
import pathlib
import select
import socket
import struct
import sys
import time
import zlib


HEADER = struct.Struct("!HBBHHIQQI")
TICK = struct.Struct("!H4sHIII")
FRAME_LEN = struct.Struct("!I")
EXCHANGE_IP = "20.1.1.1"
TRADER_IP = "20.1.1.2"
MARKET_RUN_ID = ""


def emit(event, **fields):
    parts = [
        "event=" + event,
        "node=" + socket.gethostname(),
        "monotonic_ns=" + str(time.monotonic_ns()),
    ]
    if MARKET_RUN_ID:
        parts.append("run_id=" + MARKET_RUN_ID)
    for key, value in fields.items():
        parts.append("%s=%s" % (key, value))
    print(" ".join(parts), flush=True)


def remember_pid(phase, role):
    root = pathlib.Path(__file__).resolve().parent
    path = root / ("%s-%s-%d.pid" % (phase.lower(), role, os.getpid()))
    path.write_text(str(os.getpid()) + "\n", encoding="ascii")
    emit("process_start", phase=phase, role=role, pid=os.getpid())


def session_for(run_id):
    return zlib.crc32(run_id.encode("utf-8"))


def correlation_for(run_id, phase):
    text = (run_id + ":" + phase).encode("utf-8")
    return zlib.crc32(text)


def nearest_rank(values, percentile):
    ordered = sorted(values)
    index = max(0, (len(ordered) * percentile + 99) // 100 - 1)
    return ordered[index]


def make_tick(run_id, phase, sequence):
    session = session_for(run_id)
    correlation = correlation_for(run_id, phase)
    body = TICK.pack(0x4D44, b"AAPL", 0, 1234501, 10, sequence)
    head = HEADER.pack(
        0x464C, 1, 1, 0, 32, len(body),
        session, correlation, sequence
    )
    return head + body


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


def frame(text):
    data = text.encode("utf-8")
    return FRAME_LEN.pack(len(data)) + data


def read_exact(connection, size):
    data = b""
    while len(data) < size:
        chunk = connection.recv(size - len(data))
        if not chunk:
            raise EOFError("early EOF")
        data += chunk
    return data


def read_frame(connection):
    size = FRAME_LEN.unpack(read_exact(connection, 4))[0]
    return read_exact(connection, size).decode("utf-8")


def make_listener(port):
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind((EXCHANGE_IP, port))
    listener.listen(2)
    listener.settimeout(8)
    return listener


def send_order_and_read(run_id, phase, tcp_port):
    correlation = correlation_for(run_id, phase)
    text = "ORDER|%s|%d|AAPL|BUY|10" % (run_id, correlation)
    connection = socket.create_connection((EXCHANGE_IP, tcp_port), timeout=5)
    connection.settimeout(5)
    connection.sendall(frame(text))
    emit("order_tx", phase=phase, correlation=correlation, bytes=len(text))
    ack = read_frame(connection)
    execution = read_frame(connection)
    emit("response_rx", phase=phase, value=ack)
    emit("response_rx", phase=phase, value=execution)
    connection.close()
    return correlation


def serve_one_order(listener, run_id, phase):
    connection, peer = listener.accept()
    connection.settimeout(5)
    order = read_frame(connection)
    fields = order.split("|")
    correlation = int(fields[2])
    emit(
        "order_rx", phase=phase, peer=peer[0],
        correlation=correlation, symbol=fields[3], side=fields[4]
    )
    connection.sendall(frame("ACK|%d" % correlation))
    connection.sendall(frame("EXECUTION|%d" % correlation))
    emit("response_tx", phase=phase, types="ACK,EXECUTION",
         correlation=correlation)
    connection.close()
    listener.close()
    return correlation


def exchange_market(phase, run_id, udp_port, tcp_port):
    remember_pid(phase, "exchange")
    listener = make_listener(tcp_port)
    emit("tcp_listen", phase=phase, address=EXCHANGE_IP, port=tcp_port)
    sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sender.bind((EXCHANGE_IP, 0))
    time.sleep(0.35)
    if phase == "CALM" or phase == "BURST":
        spacing = 0.005 if phase == "CALM" else 0.0
        correlation = correlation_for(run_id, phase)
        for sequence in range(32):
            packet = make_tick(run_id, phase, sequence)
            sender.sendto(packet, (TRADER_IP, udp_port))
            emit("tick_tx", phase=phase, feed="A",
                 sequence=sequence, correlation=correlation, bytes=len(packet))
            if spacing:
                time.sleep(spacing)
        ticks_sent = 32
    else:
        correlation = correlation_for(run_id, phase)
        for sequence in [0, 1, 2, 3, 5, 6, 7]:
            sender.sendto(
                make_tick(run_id, phase, sequence), (TRADER_IP, udp_port)
            )
            emit("tick_tx", phase=phase, feed="A", sequence=sequence,
                 correlation=correlation, bytes=52)
        for sequence in range(8):
            sender.sendto(
                make_tick(run_id, phase, sequence), (TRADER_IP, udp_port + 1)
            )
            emit("tick_tx", phase=phase, feed="B", sequence=sequence,
                 correlation=correlation, bytes=52)
        ticks_sent = 15
    sender.close()
    correlation = serve_one_order(listener, run_id, phase)
    emit("summary", phase=phase, ticks_sent=ticks_sent,
         orders_applied=1, correlation=correlation)


def receive_single_feed(phase, run_id, udp_port, tcp_port):
    receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    receiver.bind((TRADER_IP, udp_port))
    receiver.settimeout(5)
    remember_pid(phase, "trader")
    times = []
    sequences = []
    for unused in range(32):
        data, peer = receiver.recvfrom(2048)
        head, body = decode_tick(data)
        now = time.monotonic_ns()
        times.append(now)
        sequences.append(head[8])
        emit("tick_rx", phase=phase, feed="A", sequence=head[8],
             session=head[6], correlation=head[7], bytes=len(data),
             symbol=body[1].decode("ascii"), peer=peer[0])
    receiver.close()
    intervals = [
        times[index] - times[index - 1] for index in range(1, len(times))
    ]
    emit(
        "arrival_gap_distribution", phase=phase,
        metric="trader_tick_interarrival", samples=len(intervals),
        clock_domain="vm-2522-02_CLOCK_MONOTONIC",
        p50_ns=nearest_rank(intervals, 50),
        p99_ns=nearest_rank(intervals, 99),
        p999_ns=nearest_rank(intervals, 100),
    )
    emit(
        "decision", phase=phase, rule="AAPL_BUY_10",
        correlation=correlation_for(run_id, phase)
    )
    correlation = send_order_and_read(run_id, phase, tcp_port)
    window = times[-1] - times[0]
    gaps = sorted(set(range(32)) - set(sequences))
    emit("summary", phase=phase, ticks_received=len(sequences),
         unique=len(set(sequences)), duplicate=len(sequences)-len(set(sequences)),
         gap_remaining="none" if not gaps else ",".join(map(str, gaps)),
         tick_window_ns=window, order_actions=1, correlation=correlation)


def receive_fault(run_id, udp_port, tcp_port):
    phase = "FAULT"
    remember_pid(phase, "trader")
    sockets = []
    names = {}
    for name, port in [("A", udp_port), ("B", udp_port + 1)]:
        receiver = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        receiver.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        receiver.bind((TRADER_IP, port))
        receiver.setblocking(False)
        sockets.append(receiver)
        names[receiver] = name
    accepted = {}
    duplicate = 0
    received = 0
    while received < 15:
        ready = select.select(sockets, [], [], 5)[0]
        if not ready:
            raise TimeoutError("Feed A/B receive timeout")
        for receiver in ready:
            data, peer = receiver.recvfrom(2048)
            head, body = decode_tick(data)
            sequence = head[8]
            received += 1
            if sequence in accepted:
                duplicate += 1
                emit("duplicate_drop", phase=phase, feed=names[receiver],
                     sequence=sequence, correlation=head[7], peer=peer[0])
            else:
                accepted[sequence] = names[receiver]
                emit("tick_accept", phase=phase, feed=names[receiver],
                     sequence=sequence, session=head[6], correlation=head[7],
                     symbol=body[1].decode("ascii"))
    for receiver in sockets:
        receiver.close()
    emit(
        "decision", phase=phase, rule="AAPL_BUY_10",
        correlation=correlation_for(run_id, phase)
    )
    correlation = send_order_and_read(run_id, phase, tcp_port)
    gaps = sorted(set(range(8)) - set(accepted))
    emit("summary", phase=phase, datagrams_received=received,
         unique=len(accepted), duplicate=duplicate,
         sequence4_source=accepted.get(4, "missing"),
         gap_remaining="none" if not gaps else ",".join(map(str, gaps)),
         order_actions=1, correlation=correlation)


def recover_exchange(run_id, tcp_port):
    phase = "RECOVER"
    remember_pid(phase, "exchange")
    listener = make_listener(tcp_port)
    emit("tcp_listen", phase=phase, address=EXCHANGE_IP, port=tcp_port)
    applied = set()
    action_count = 0
    for generation in [1, 2]:
        connection, peer = listener.accept()
        connection.settimeout(5)
        order = read_frame(connection)
        correlation = int(order.split("|")[2])
        if correlation not in applied:
            applied.add(correlation)
            action_count += 1
            emit("order_apply", phase=phase, generation=generation,
                 correlation=correlation, action_count=action_count)
        else:
            emit("order_replay", phase=phase, generation=generation,
                 correlation=correlation, action_count=action_count)
        connection.sendall(frame("ACK|%d" % correlation))
        time.sleep(0.15)
        try:
            connection.sendall(frame("EXECUTION|%d" % correlation))
            delivery = "DELIVERED"
        except OSError:
            delivery = "INTERRUPTED"
        emit("execution_delivery", phase=phase, generation=generation,
             correlation=correlation, result=delivery)
        connection.close()
    listener.close()
    emit("summary", phase=phase, connections=2,
         unique_correlations=len(applied), action_count=action_count)


def recover_trader(run_id, tcp_port, generation):
    phase = "RECOVER"
    remember_pid(phase, "trader-g%d" % generation)
    correlation = correlation_for(run_id, phase)
    text = "ORDER|%s|%d|AAPL|BUY|10" % (run_id, correlation)
    connection = socket.create_connection((EXCHANGE_IP, tcp_port), timeout=5)
    connection.settimeout(5)
    connection.sendall(frame(text))
    emit("order_tx", phase=phase, generation=generation,
         correlation=correlation)
    ack = read_frame(connection)
    emit("response_rx", phase=phase, generation=generation, value=ack)
    if generation == 1:
        connection.setsockopt(
            socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0)
        )
        connection.close()
        emit("trader_exit", phase=phase, generation=generation,
             after="ACK", restart="required")
    else:
        execution = read_frame(connection)
        emit("response_rx", phase=phase, generation=generation,
             value=execution)
        connection.close()
        emit("summary", phase=phase, generation=generation,
             correlation=correlation, responses="ACK,EXECUTION")


def main():
    global MARKET_RUN_ID
    role = sys.argv[1]
    if role == "exchange":
        phase, run_id = sys.argv[2], sys.argv[3]
        MARKET_RUN_ID = run_id
        exchange_market(phase, run_id, int(sys.argv[4]), int(sys.argv[5]))
    elif role == "trader":
        phase, run_id = sys.argv[2], sys.argv[3]
        MARKET_RUN_ID = run_id
        if phase == "FAULT":
            receive_fault(run_id, int(sys.argv[4]), int(sys.argv[5]))
        else:
            receive_single_feed(
                phase, run_id, int(sys.argv[4]), int(sys.argv[5])
            )
    elif role == "recover-exchange":
        MARKET_RUN_ID = sys.argv[2]
        recover_exchange(sys.argv[2], int(sys.argv[3]))
    elif role == "recover-trader":
        MARKET_RUN_ID = sys.argv[2]
        recover_trader(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))
    else:
        raise SystemExit("unknown role")


if __name__ == "__main__":
    main()
