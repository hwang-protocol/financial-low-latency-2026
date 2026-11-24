#!/usr/bin/env python3
"""SIMULATED Exchange order service for the FLLE Market Day capstone."""

import argparse
import datetime
import hashlib
import json
import os
import pathlib
import re
import signal
import socket
import socketserver
import struct
import threading


ORDER_SCHEMA = "flle.order-command.v1"
RESPONSE_SCHEMA = "flle.order-response.v1"
RUN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
CORRELATION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
FRAME_HEADER = struct.Struct("!I")
MAX_FRAME = 64 * 1024


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(
        timespec="milliseconds"
    ).replace("+00:00", "Z")


def compact_json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def atomic_json(path, value):
    temporary = path.with_suffix(path.suffix + ".new")
    with temporary.open("w", encoding="utf-8") as handle:
        handle.write(compact_json(value) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def receive_exact(connection, length):
    chunks = []
    remaining = length
    while remaining:
        chunk = connection.recv(remaining)
        if not chunk:
            raise ConnectionError("peer closed before the complete frame arrived")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def receive_frame(connection):
    header = receive_exact(connection, FRAME_HEADER.size)
    (length,) = FRAME_HEADER.unpack(header)
    if not 1 <= length <= MAX_FRAME:
        raise ValueError("frame length must be from 1 byte to 64 KiB")
    return json.loads(receive_exact(connection, length).decode("utf-8"))


def send_frame(connection, value):
    payload = compact_json(value).encode("utf-8")
    if len(payload) > MAX_FRAME:
        raise ValueError("response frame exceeds 64 KiB")
    connection.sendall(FRAME_HEADER.pack(len(payload)) + payload)


def validate_order(payload, run_id):
    if not isinstance(payload, dict):
        raise ValueError("order frame must contain a JSON object")
    if payload.get("schema") != ORDER_SCHEMA:
        raise ValueError("order schema must be " + ORDER_SCHEMA)
    if payload.get("run_id") != run_id:
        raise ValueError("order RUN_ID does not match the service RUN_ID")
    if payload.get("simulated") is not True:
        raise ValueError("order must explicitly carry simulated=true")
    correlation = str(payload.get("correlation", ""))
    if not CORRELATION_RE.fullmatch(correlation):
        raise ValueError("correlation has an invalid value")
    phase = str(payload.get("phase", "")).upper()
    if phase not in {
        "OPEN", "CALM", "BURST", "FAULT", "RECOVER", "CLOSE", "UNSPECIFIED"
    }:
        raise ValueError("phase has an invalid value")
    origin = str(payload.get("origin", "")).lower()
    if origin not in {"ui", "api"}:
        raise ValueError("origin must be ui or api")
    symbol = str(payload.get("symbol", "")).upper()
    side = str(payload.get("side", "")).upper()
    quantity = payload.get("quantity")
    if symbol != "AAPL":
        raise ValueError("SIMULATED order symbol must be AAPL")
    if side not in {"BUY", "SELL"}:
        raise ValueError("side must be BUY or SELL")
    if not isinstance(quantity, int) or isinstance(quantity, bool):
        raise ValueError("quantity must be an integer")
    if not 1 <= quantity <= 1000:
        raise ValueError("quantity must be from 1 to 1000")
    return {
        "schema": ORDER_SCHEMA,
        "run_id": run_id,
        "correlation": correlation,
        "phase": phase,
        "origin": origin,
        "symbol": symbol,
        "side": side,
        "quantity": quantity,
        "simulated": True,
    }


def canonical_fingerprint(order):
    canonical = {
        key: order[key]
        for key in (
            "schema", "run_id", "correlation", "symbol", "side", "quantity",
            "simulated",
        )
    }
    return hashlib.sha256(compact_json(canonical).encode("utf-8")).hexdigest()


class OrderBook:
    """Persistent idempotency ledger; one action per RUN_ID/correlation."""

    def __init__(self, run_id, run_dir):
        self.run_id = run_id
        self.root = run_dir / "order-service"
        self.root.mkdir(parents=True, exist_ok=True, mode=0o750)
        self.requests_path = self.root / "requests.ndjson"
        self.state_path = self.root / "state.json"
        self.pid_path = self.root / "order-service.pid"
        self.lock = threading.Lock()
        self.applied = {}
        self.action_count = 0
        self.request_count = 0
        self.started_at = utc_now()
        self._load()
        atomic_json(self.state_path, self._state_unlocked())

    def _load(self):
        if not self.requests_path.exists():
            return
        with self.requests_path.open(encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                try:
                    record = json.loads(line)
                except json.JSONDecodeError as error:
                    raise RuntimeError(
                        "corrupt requests.ndjson line %d: %s"
                        % (line_number, error)
                    )
                if record.get("schema") != "flle.order-service-record.v1":
                    raise RuntimeError(
                        "order-service record schema drift at line %d" % line_number
                    )
                if record.get("run_id") != self.run_id:
                    raise RuntimeError(
                        "order-service RUN_ID drift at line %d" % line_number
                    )
                expected = self.request_count + 1
                if record.get("request_sequence") != expected:
                    raise RuntimeError(
                        "order-service request sequence drift at line %d"
                        % line_number
                    )
                self.request_count = expected
                if record.get("disposition") == "APPLIED":
                    correlation = record["order"]["correlation"]
                    if correlation in self.applied:
                        raise RuntimeError(
                            "duplicate APPLIED correlation at line %d" % line_number
                        )
                    self.applied[correlation] = {
                        "fingerprint": record["fingerprint"],
                        "order": record["order"],
                        "responses": record["responses"],
                    }
                    self.action_count += 1
                if record.get("action_count") != self.action_count:
                    raise RuntimeError(
                        "order-service action_count drift at line %d" % line_number
                    )

    def _state_unlocked(self):
        return {
            "schema": "flle.order-service-state.v1",
            "run_id": self.run_id,
            "simulated": True,
            "request_count": self.request_count,
            "unique_correlations": len(self.applied),
            "action_count": self.action_count,
            "started_at": self.started_at,
            "updated_at": utc_now(),
        }

    def _append_record_unlocked(self, record):
        with self.requests_path.open("a", encoding="utf-8") as handle:
            handle.write(compact_json(record) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        atomic_json(self.state_path, self._state_unlocked())

    def process(self, order, peer):
        fingerprint = canonical_fingerprint(order)
        correlation = order["correlation"]
        with self.lock:
            prior = self.applied.get(correlation)
            self.request_count += 1
            if prior is None:
                self.action_count += 1
                action_count = self.action_count
                identity = hashlib.sha256(
                    ("%s\0%s" % (self.run_id, correlation)).encode("utf-8")
                ).hexdigest()[:16]
                accepted_at = utc_now()
                common = {
                    "schema": RESPONSE_SCHEMA,
                    "run_id": self.run_id,
                    "correlation": correlation,
                    "origin": order["origin"],
                    "symbol": order["symbol"],
                    "side": order["side"],
                    "quantity": order["quantity"],
                    "order_id": "ORD-" + identity,
                    "action_count": action_count,
                    "replay": False,
                    "simulated": True,
                }
                responses = [
                    {
                        **common,
                        "type": "ACK",
                        "status": "ACCEPTED",
                        "accepted_at": accepted_at,
                    },
                    {
                        **common,
                        "type": "EXECUTION",
                        "status": "FILLED",
                        "execution_id": "EXE-" + identity,
                        "executed_at": utc_now(),
                    },
                ]
                disposition = "APPLIED"
                self.applied[correlation] = {
                    "fingerprint": fingerprint,
                    "order": order,
                    "responses": responses,
                }
            elif prior["fingerprint"] == fingerprint:
                action_count = self.action_count
                responses = [
                    {**response, "replay": True}
                    for response in prior["responses"]
                ]
                disposition = "REPLAY"
            else:
                action_count = self.action_count
                responses = [
                    {
                        "schema": RESPONSE_SCHEMA,
                        "run_id": self.run_id,
                        "correlation": correlation,
                        "origin": order["origin"],
                        "type": "REJECT",
                        "status": "CORRELATION_CONFLICT",
                        "action_count": action_count,
                        "replay": False,
                        "simulated": True,
                    }
                ]
                disposition = "CONFLICT"
            record = {
                "schema": "flle.order-service-record.v1",
                "request_sequence": self.request_count,
                "run_id": self.run_id,
                "received_at": utc_now(),
                "peer": peer,
                "order": order,
                "fingerprint": fingerprint,
                "disposition": disposition,
                "action_count": action_count,
                "responses": responses,
            }
            self._append_record_unlocked(record)
            return {
                "disposition": disposition,
                "action_count": action_count,
                "responses": responses,
            }


class OrderRequestHandler(socketserver.BaseRequestHandler):
    def handle(self):
        peer_ip = self.client_address[0]
        if peer_ip != self.server.allowed_peer:
            print(
                "%s event=peer_rejected peer=%s" % (utc_now(), peer_ip),
                flush=True,
            )
            return
        connection = self.request
        connection.settimeout(self.server.socket_timeout)
        connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        try:
            payload = receive_frame(connection)
            order = validate_order(payload, self.server.order_book.run_id)
            result = self.server.order_book.process(order, peer_ip)
            for response in result["responses"]:
                send_frame(connection, response)
            print(
                "%s event=order_result peer=%s correlation=%s "
                "disposition=%s action_count=%d"
                % (
                    utc_now(), peer_ip, order["correlation"],
                    result["disposition"], result["action_count"],
                ),
                flush=True,
            )
        except (
            ConnectionError, json.JSONDecodeError, UnicodeDecodeError,
            ValueError, socket.timeout,
        ) as error:
            if "result" in locals():
                print(
                    "%s event=response_delivery_interrupted peer=%s "
                    "correlation=%s disposition=%s reason=%s"
                    % (
                        utc_now(), peer_ip, order["correlation"],
                        result["disposition"], str(error).replace("\n", " "),
                    ),
                    flush=True,
                )
                return
            rejection = {
                "schema": RESPONSE_SCHEMA,
                "run_id": self.server.order_book.run_id,
                "correlation": (
                    payload.get("correlation", "INVALID")
                    if isinstance(locals().get("payload"), dict) else "INVALID"
                ),
                "type": "REJECT",
                "status": "INVALID_REQUEST",
                "reason": str(error),
                "action_count": self.server.order_book.action_count,
                "replay": False,
                "simulated": True,
            }
            try:
                send_frame(connection, rejection)
            except (BrokenPipeError, ConnectionError, OSError, ValueError):
                pass
            print(
                "%s event=request_rejected peer=%s reason=%s"
                % (utc_now(), peer_ip, str(error).replace("\n", " ")),
                flush=True,
            )


class OrderServer(socketserver.ThreadingTCPServer):
    daemon_threads = False
    allow_reuse_address = True


def claim_pid(path):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError:
        raise SystemExit("order-service pid file already exists: " + str(path))
    with os.fdopen(descriptor, "w", encoding="ascii") as handle:
        handle.write(str(os.getpid()) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-dir", required=True, type=pathlib.Path)
    parser.add_argument("--bind", default="20.1.1.1")
    parser.add_argument("--port", type=int, default=43300)
    parser.add_argument("--allow-peer", default="20.1.1.2")
    parser.add_argument("--socket-timeout", type=float, default=5.0)
    args = parser.parse_args()
    if not RUN_RE.fullmatch(args.run_id):
        raise SystemExit("invalid --run-id")
    if not 1 <= args.port <= 65535:
        raise SystemExit("--port must be from 1 to 65535")
    if not 0.1 <= args.socket_timeout <= 60:
        raise SystemExit("--socket-timeout must be from 0.1 to 60 seconds")
    run_dir = args.run_dir.resolve()
    if run_dir == pathlib.Path("/"):
        raise SystemExit("--run-dir cannot be /")
    order_book = OrderBook(args.run_id, run_dir)
    claim_pid(order_book.pid_path)
    stop = threading.Event()
    try:
        server = OrderServer((args.bind, args.port), OrderRequestHandler)
    except Exception:
        order_book.pid_path.unlink(missing_ok=True)
        raise
    server.order_book = order_book
    server.allowed_peer = args.allow_peer
    server.socket_timeout = args.socket_timeout
    server.timeout = 0.5

    def request_stop(signum, unused_frame):
        print("%s signal=%d action=stop" % (utc_now(), signum), flush=True)
        stop.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    print(
        "%s status=ready bind=%s port=%d allowed_peer=%s run_id=%s "
        "framing=uint32-be-json"
        % (utc_now(), args.bind, args.port, args.allow_peer, args.run_id),
        flush=True,
    )
    try:
        while not stop.is_set():
            server.handle_request()
    finally:
        server.server_close()
        try:
            if (
                order_book.pid_path.read_text(encoding="ascii").strip()
                == str(os.getpid())
            ):
                order_book.pid_path.unlink()
        except FileNotFoundError:
            pass
        print(
            "%s status=stopped run_id=%s action_count=%d"
            % (utc_now(), args.run_id, order_book.action_count),
            flush=True,
        )


if __name__ == "__main__":
    main()
