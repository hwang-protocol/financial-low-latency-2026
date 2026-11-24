#!/usr/bin/env python3
"""Management adapter from the FLLE terminal gateway to the Trader data path."""

import argparse
import datetime
import http.server
import json
import os
import pathlib
import re
import signal
import socket
import struct
import threading
import time
import urllib.parse


ORDER_SCHEMA = "flle.order-command.v1"
RESPONSE_SCHEMA = "flle.order-response.v1"
EVENT_SCHEMA = "flle.market-event.v1"
ADAPTER_SCHEMA = "flle.order-adapter-result.v1"
RUN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
CORRELATION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
FRAME_HEADER = struct.Struct("!I")
MAX_FRAME = 64 * 1024
MAX_BODY = 64 * 1024


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
            raise EOFError
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def receive_frame(connection):
    header = receive_exact(connection, FRAME_HEADER.size)
    (length,) = FRAME_HEADER.unpack(header)
    if not 1 <= length <= MAX_FRAME:
        raise ValueError("response frame length must be from 1 byte to 64 KiB")
    return json.loads(receive_exact(connection, length).decode("utf-8"))


def send_frame(connection, value):
    payload = compact_json(value).encode("utf-8")
    if len(payload) > MAX_FRAME:
        raise ValueError("order frame exceeds 64 KiB")
    connection.sendall(FRAME_HEADER.pack(len(payload)) + payload)


def validate_order(payload, run_id):
    if not isinstance(payload, dict):
        raise ValueError("order body must be a JSON object")
    if payload.get("schema") != ORDER_SCHEMA:
        raise ValueError("order schema must be " + ORDER_SCHEMA)
    if payload.get("run_id") != run_id:
        raise ValueError("order RUN_ID does not match adapter RUN_ID")
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
    if symbol != "AAPL" or side not in {"BUY", "SELL"}:
        raise ValueError("SIMULATED ticket accepts AAPL BUY or SELL")
    if (
        not isinstance(quantity, int)
        or isinstance(quantity, bool)
        or not 1 <= quantity <= 1000
    ):
        raise ValueError("quantity must be an integer from 1 to 1000")
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


def validate_response(response, order):
    if not isinstance(response, dict):
        raise ValueError("Exchange response frame must be a JSON object")
    if response.get("schema") != RESPONSE_SCHEMA:
        raise ValueError("Exchange response schema drift")
    if response.get("run_id") != order["run_id"]:
        raise ValueError("Exchange response RUN_ID drift")
    if response.get("correlation") != order["correlation"]:
        raise ValueError("Exchange response correlation drift")
    if response.get("simulated") is not True:
        raise ValueError("Exchange response lost simulated=true")
    response_type = response.get("type")
    if response_type not in {"ACK", "EXECUTION", "REJECT"}:
        raise ValueError("Exchange response type drift")
    if (
        not isinstance(response.get("action_count"), int)
        or isinstance(response.get("action_count"), bool)
        or response["action_count"] < 0
    ):
        raise ValueError("Exchange response action_count drift")
    if not isinstance(response.get("replay"), bool):
        raise ValueError("Exchange response replay flag drift")
    expected_status = {
        "ACK": "ACCEPTED",
        "EXECUTION": "FILLED",
        "REJECT": "CORRELATION_CONFLICT",
    }[response_type]
    if response.get("status") != expected_status:
        raise ValueError("Exchange response status drift")
    if response_type in {"ACK", "EXECUTION"}:
        if not response.get("order_id"):
            raise ValueError("Exchange response order_id drift")
        for key in ("symbol", "side", "quantity"):
            if response.get(key) != order[key]:
                raise ValueError("Exchange response %s drift" % key)
    if response_type == "EXECUTION" and not response.get("execution_id"):
        raise ValueError("Exchange response execution_id drift")
    return response


class AdapterState:
    def __init__(self, run_id, run_dir):
        self.run_id = run_id
        self.root = run_dir / "order-adapter"
        self.root.mkdir(parents=True, exist_ok=True, mode=0o750)
        self.requests_path = self.root / "requests.ndjson"
        self.state_path = self.root / "state.json"
        self.pid_path = self.root / "order-adapter.pid"
        self.lock = threading.Lock()
        self.request_count = 0
        self.success_count = 0
        self.conflict_count = 0
        self.failure_count = 0
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
                        "corrupt adapter requests.ndjson line %d: %s"
                        % (line_number, error)
                    )
                if record.get("schema") != "flle.order-adapter-record.v1":
                    raise RuntimeError(
                        "adapter record schema drift at line %d" % line_number
                    )
                if record.get("run_id") != self.run_id:
                    raise RuntimeError(
                        "adapter RUN_ID drift at line %d" % line_number
                    )
                expected = self.request_count + 1
                if record.get("request_sequence") != expected:
                    raise RuntimeError(
                        "adapter request sequence drift at line %d" % line_number
                    )
                self.request_count = expected
                disposition = record.get("disposition")
                if disposition in {"APPLIED", "REPLAY"}:
                    self.success_count += 1
                elif disposition == "CONFLICT":
                    self.conflict_count += 1
                else:
                    self.failure_count += 1

    def snapshot(self):
        with self.lock:
            return self._state_unlocked()

    def _state_unlocked(self):
        return {
            "schema": "flle.order-adapter-state.v1",
            "run_id": self.run_id,
            "simulated": True,
            "request_count": self.request_count,
            "success_count": self.success_count,
            "conflict_count": self.conflict_count,
            "failure_count": self.failure_count,
            "started_at": self.started_at,
            "updated_at": utc_now(),
        }

    def record(self, order, peer, disposition, elapsed_ns, result=None, error=None):
        with self.lock:
            self.request_count += 1
            if disposition in {"APPLIED", "REPLAY"}:
                self.success_count += 1
            elif disposition == "CONFLICT":
                self.conflict_count += 1
            else:
                self.failure_count += 1
            record = {
                "schema": "flle.order-adapter-record.v1",
                "request_sequence": self.request_count,
                "run_id": self.run_id,
                "received_at": utc_now(),
                "peer": peer,
                "order": order,
                "disposition": disposition,
                "elapsed_ns": elapsed_ns,
            }
            if result is not None:
                record["result"] = result
            if error is not None:
                record["error"] = str(error)
            with self.requests_path.open("a", encoding="utf-8") as handle:
                handle.write(compact_json(record) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            atomic_json(self.state_path, self._state_unlocked())


class AdapterHandler(http.server.BaseHTTPRequestHandler):
    server_version = "FLLEOrderAdapter/1"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        print(
            "%s peer=%s %s" % (utc_now(), self.client_address[0], fmt % args),
            flush=True,
        )

    def send_json(self, status, value):
        body = (compact_json(value) + "\n").encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            self.close_connection = True

    def send_error_json(self, status, message):
        self.send_json(
            status,
            {
                "schema": ADAPTER_SCHEMA,
                "status": "error",
                "run_id": self.server.run_id,
                "error": message,
                "simulated": True,
            },
        )

    def do_GET(self):
        if urllib.parse.urlparse(self.path).path != "/healthz":
            self.send_error_json(404, "route not found")
            return
        self.send_json(
            200,
            {
                "status": "ready",
                "run_id": self.server.run_id,
                "exchange": "%s:%d"
                % (self.server.exchange_ip, self.server.exchange_port),
                "trader_data_ip": self.server.trader_data_ip,
                "state": self.server.adapter_state.snapshot(),
            },
        )

    def do_POST(self):
        if urllib.parse.urlparse(self.path).path != "/v1/orders":
            self.send_error_json(404, "route not found")
            return
        peer_ip = self.client_address[0]
        if peer_ip != self.server.allowed_peer:
            self.send_error_json(403, "peer is not the configured terminal gateway")
            return
        started_ns = time.monotonic_ns()
        order = None
        try:
            content_type = self.headers.get("Content-Type", "").split(";", 1)[0]
            if content_type != "application/json":
                raise ValueError("orders require Content-Type application/json")
            try:
                length = int(self.headers.get("Content-Length", ""))
            except ValueError:
                raise ValueError("Content-Length is required")
            if not 1 <= length <= MAX_BODY:
                raise ValueError("request body must be from 1 byte to 64 KiB")
            order = validate_order(
                json.loads(self.rfile.read(length).decode("utf-8")),
                self.server.run_id,
            )
            result = self.exchange_roundtrip(order)
            elapsed_ns = time.monotonic_ns() - started_ns
            events = self.build_events(order, result, elapsed_ns)
            response = {
                "schema": ADAPTER_SCHEMA,
                "status": (
                    "accepted"
                    if result["disposition"] in {"APPLIED", "REPLAY"}
                    else "rejected"
                ),
                "run_id": self.server.run_id,
                "correlation": order["correlation"],
                "origin": order["origin"],
                "disposition": result["disposition"],
                "action_count": result["action_count"],
                "responses": result["responses"],
                "events": events,
                "elapsed_ns": elapsed_ns,
                "simulated": True,
            }
            self.server.adapter_state.record(
                order, peer_ip, result["disposition"], elapsed_ns, result=response
            )
            status = 409 if result["disposition"] == "CONFLICT" else 200
            self.send_json(status, response)
        except (
            ConnectionError, EOFError, json.JSONDecodeError, OSError,
            socket.timeout, UnicodeDecodeError, ValueError,
        ) as error:
            elapsed_ns = time.monotonic_ns() - started_ns
            self.server.adapter_state.record(
                order, peer_ip, "FAILED", elapsed_ns, error=error
            )
            if isinstance(error, (ValueError, json.JSONDecodeError, UnicodeDecodeError)):
                status = 400
            else:
                status = 502
            self.send_error_json(status, str(error))

    def exchange_roundtrip(self, order):
        responses = []
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as connection:
            connection.settimeout(self.server.socket_timeout)
            connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            connection.bind((self.server.trader_data_ip, 0))
            connection.connect(
                (self.server.exchange_ip, self.server.exchange_port)
            )
            local_endpoint = "%s:%d" % connection.getsockname()
            remote_endpoint = "%s:%d" % connection.getpeername()
            send_frame(connection, order)
            while True:
                try:
                    response = receive_frame(connection)
                except EOFError:
                    break
                responses.append(validate_response(response, order))
                if response["type"] in {"EXECUTION", "REJECT"}:
                    break
        if not responses:
            raise ConnectionError("Exchange returned no response frames")
        response_types = [response["type"] for response in responses]
        if response_types == ["ACK", "EXECUTION"]:
            disposition = "REPLAY" if responses[-1].get("replay") else "APPLIED"
        elif response_types == ["REJECT"] and responses[0].get("status") == (
            "CORRELATION_CONFLICT"
        ):
            disposition = "CONFLICT"
        else:
            raise ValueError(
                "Exchange response sequence must be ACK,EXECUTION or REJECT"
            )
        return {
            "disposition": disposition,
            "action_count": responses[-1]["action_count"],
            "responses": responses,
            "local_endpoint": local_endpoint,
            "remote_endpoint": remote_endpoint,
        }

    def build_events(self, order, result, elapsed_ns):
        common = {
            "origin": order["origin"],
            "correlation": order["correlation"],
            "symbol": order["symbol"],
            "side": order["side"],
            "quantity": order["quantity"],
        }
        events = [
            {
                "schema": EVENT_SCHEMA,
                "run_id": self.server.run_id,
                "source": "trader-order-adapter",
                "phase": order["phase"],
                "kind": "order_tx",
                "simulated": True,
                "fields": {
                    **common,
                    "transport": "TCP_UINT32_BE_JSON",
                    "local_endpoint": result["local_endpoint"],
                    "remote_endpoint": result["remote_endpoint"],
                },
            }
        ]
        for response in result["responses"]:
            fields = {
                **common,
                "response_type": response["type"],
                "status": response["status"],
                "replay": response["replay"],
                "action_count": response["action_count"],
            }
            for key in ("order_id", "execution_id"):
                if key in response:
                    fields[key] = response[key]
            events.append(
                {
                    "schema": EVENT_SCHEMA,
                    "run_id": self.server.run_id,
                    "source": "exchange-order-service",
                    "phase": order["phase"],
                    "kind": "response_rx",
                    "simulated": True,
                    "fields": fields,
                }
            )
        events.append(
            {
                "schema": EVENT_SCHEMA,
                "run_id": self.server.run_id,
                "source": "trader-order-adapter",
                "phase": order["phase"],
                "kind": "order_roundtrip",
                "simulated": True,
                "fields": {
                    **common,
                    "disposition": result["disposition"],
                    "action_count": result["action_count"],
                    "elapsed_ns": elapsed_ns,
                    "response_types": ",".join(
                        response["type"] for response in result["responses"]
                    ),
                },
            }
        )
        return events


class AdapterServer(http.server.ThreadingHTTPServer):
    daemon_threads = False
    allow_reuse_address = True


def claim_pid(path):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError:
        raise SystemExit("order-adapter pid file already exists: " + str(path))
    with os.fdopen(descriptor, "w", encoding="ascii") as handle:
        handle.write(str(os.getpid()) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-dir", required=True, type=pathlib.Path)
    parser.add_argument("--bind", default="10.1.1.2")
    parser.add_argument("--port", type=int, default=8089)
    parser.add_argument("--allow-peer", default="10.1.1.101")
    parser.add_argument("--trader-data-ip", default="20.1.1.2")
    parser.add_argument("--exchange-data-ip", default="20.1.1.1")
    parser.add_argument("--exchange-port", type=int, default=43300)
    parser.add_argument("--socket-timeout", type=float, default=5.0)
    args = parser.parse_args()
    if not RUN_RE.fullmatch(args.run_id):
        raise SystemExit("invalid --run-id")
    for label, port in (
        ("--port", args.port), ("--exchange-port", args.exchange_port)
    ):
        if not 1 <= port <= 65535:
            raise SystemExit(label + " must be from 1 to 65535")
    if not 0.1 <= args.socket_timeout <= 60:
        raise SystemExit("--socket-timeout must be from 0.1 to 60 seconds")
    run_dir = args.run_dir.resolve()
    if run_dir == pathlib.Path("/"):
        raise SystemExit("--run-dir cannot be /")
    adapter_state = AdapterState(args.run_id, run_dir)
    claim_pid(adapter_state.pid_path)
    try:
        server = AdapterServer((args.bind, args.port), AdapterHandler)
    except Exception:
        adapter_state.pid_path.unlink(missing_ok=True)
        raise
    server.run_id = args.run_id
    server.allowed_peer = args.allow_peer
    server.trader_data_ip = args.trader_data_ip
    server.exchange_ip = args.exchange_data_ip
    server.exchange_port = args.exchange_port
    server.socket_timeout = args.socket_timeout
    server.adapter_state = adapter_state
    server.timeout = 0.5
    stop = threading.Event()

    def request_stop(signum, unused_frame):
        print("%s signal=%d action=stop" % (utc_now(), signum), flush=True)
        stop.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    print(
        "%s status=ready bind=%s port=%d allowed_peer=%s "
        "trader_data=%s exchange=%s:%d run_id=%s"
        % (
            utc_now(), args.bind, args.port, args.allow_peer,
            args.trader_data_ip, args.exchange_data_ip,
            args.exchange_port, args.run_id,
        ),
        flush=True,
    )
    try:
        while not stop.is_set():
            server.handle_request()
    finally:
        server.server_close()
        try:
            if (
                adapter_state.pid_path.read_text(encoding="ascii").strip()
                == str(os.getpid())
            ):
                adapter_state.pid_path.unlink()
        except FileNotFoundError:
            pass
        print("%s status=stopped run_id=%s" % (utc_now(), args.run_id), flush=True)


if __name__ == "__main__":
    main()
