#!/usr/bin/env python3
"""FLLE Market Day management-plane event gateway and static terminal server."""

import argparse
import collections
import datetime
import http.server
import json
import os
import pathlib
import queue
import re
import secrets
import shlex
import signal
import threading
import time
import urllib.error
import urllib.parse
import urllib.request


EVENT_SCHEMA = "flle.market-event.v1"
COMMAND_SCHEMA = "flle.terminal-command.v1"
ORDER_SCHEMA = "flle.order-command.v1"
ADAPTER_SCHEMA = "flle.order-adapter-result.v1"
PHASES = {"OPEN", "CALM", "BURST", "FAULT", "RECOVER", "CLOSE", "UNSPECIFIED"}
MODES = {"live", "replay", "fault-demo"}
RUN_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,63}$")
CORRELATION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
MAX_BODY = 1024 * 1024


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


def validate_name(value, label):
    text = str(value)
    if not NAME_RE.fullmatch(text):
        raise ValueError("%s has an invalid value" % label)
    return text


def validate_phase(value):
    phase = str(value or "UNSPECIFIED").upper()
    if phase not in PHASES:
        raise ValueError("phase must be one of " + ",".join(sorted(PHASES)))
    return phase


class UpstreamError(Exception):
    def __init__(self, message, result=None):
        super().__init__(message)
        self.result = result


def parse_native_line(line, source):
    raw_line = line.rstrip("\r\n")
    if not raw_line.strip():
        return None
    if len(raw_line.encode("utf-8")) > 8192:
        raise ValueError("native event line exceeds 8192 bytes")
    values = {}
    for token in shlex.split(raw_line):
        if "=" not in token:
            raise ValueError("native event token lacks '=': " + token)
        key, value = token.split("=", 1)
        validate_name(key, "native event key")
        if key in values:
            raise ValueError("duplicate native event key: " + key)
        values[key] = value
    if "event" not in values:
        raise ValueError("native event line requires event=<kind>")
    kind = validate_name(values.pop("event"), "event")
    phase = validate_phase(values.pop("phase", "UNSPECIFIED"))
    embedded_run = values.pop("run_id", None)
    return {
        "source": source,
        "phase": phase,
        "kind": kind,
        "fields": values,
        "raw_line": raw_line,
        "embedded_run_id": embedded_run,
    }


def parse_json_event(item, default_source):
    if not isinstance(item, dict):
        raise ValueError("each JSON event must be an object")
    if item.get("schema") not in (None, EVENT_SCHEMA):
        raise ValueError("JSON event schema must be " + EVENT_SCHEMA)
    if item.get("simulated") is False:
        raise ValueError("this course gateway accepts SIMULATED events only")
    if "raw_line" in item and "event" not in item and "kind" not in item:
        parsed = parse_native_line(str(item["raw_line"]), item.get("source", default_source))
        parsed["embedded_run_id"] = item.get("run_id", parsed["embedded_run_id"])
        return parsed
    kind = validate_name(item.get("kind", item.get("event", "")), "event")
    source = validate_name(item.get("source", default_source), "source")
    phase = validate_phase(item.get("phase", "UNSPECIFIED"))
    fields = item.get("fields", {})
    if not isinstance(fields, dict):
        raise ValueError("fields must be an object")
    reserved = {
        "schema", "event_id", "sequence", "run_id", "ingested_at", "source",
        "phase", "kind", "event", "simulated", "delivery", "fields", "raw_line",
    }
    merged = dict(fields)
    for key, value in item.items():
        if key not in reserved:
            validate_name(key, "JSON event field")
            if key in merged:
                raise ValueError("duplicate JSON event field: " + key)
            merged[key] = value
    compact_json(merged)
    return {
        "source": source,
        "phase": phase,
        "kind": kind,
        "fields": merged,
        "raw_line": item.get("raw_line"),
        "embedded_run_id": item.get("run_id"),
    }


class EventStore:
    def __init__(self, run_id, run_dir, adapter_url, adapter_timeout):
        self.run_id = run_id
        self.adapter_url = adapter_url
        self.adapter_timeout = adapter_timeout
        self.http = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        self.root = run_dir / "gateway"
        self.root.mkdir(parents=True, exist_ok=True, mode=0o750)
        self.events_path = self.root / "events.ndjson"
        self.commands_path = self.root / "commands.ndjson"
        self.state_path = self.root / "state.json"
        self.pid_path = self.root / "gateway.pid"
        self.lock = threading.RLock()
        self.command_lock = threading.Lock()
        self.events = []
        self.event_counts = collections.Counter()
        self.phase_counts = collections.Counter()
        self.command_sequence = 0
        self.mode = "live"
        self.phase = "OPEN"
        self.subscribers = {}
        self.subscriber_number = 0
        self.stream_drops = 0
        self.started_at = utc_now()
        self._load()
        with self.lock:
            self._persist_state_unlocked()

    def _load(self):
        if self.events_path.exists():
            with self.events_path.open(encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, 1):
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError as error:
                        raise RuntimeError(
                            "corrupt events.ndjson line %d: %s" % (line_number, error)
                        )
                    if event.get("schema") != EVENT_SCHEMA:
                        raise RuntimeError("event schema drift at line %d" % line_number)
                    if event.get("run_id") != self.run_id:
                        raise RuntimeError("event RUN_ID drift at line %d" % line_number)
                    expected = len(self.events) + 1
                    if event.get("sequence") != expected:
                        raise RuntimeError("event sequence drift at line %d" % line_number)
                    self.events.append(event)
                    self.event_counts[event["kind"]] += 1
                    self.phase_counts[event["phase"]] += 1
                    self.phase = event["phase"]
        if self.commands_path.exists():
            with self.commands_path.open(encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, 1):
                    try:
                        command = json.loads(line)
                    except json.JSONDecodeError as error:
                        raise RuntimeError(
                            "corrupt commands.ndjson line %d: %s"
                            % (line_number, error)
                        )
                    if command.get("schema") != COMMAND_SCHEMA:
                        raise RuntimeError("command schema drift at line %d" % line_number)
                    if command.get("run_id") != self.run_id:
                        raise RuntimeError("command RUN_ID drift at line %d" % line_number)
                    expected = self.command_sequence + 1
                    if command.get("sequence") != expected:
                        raise RuntimeError(
                            "command sequence drift at line %d" % line_number
                        )
                    self.command_sequence = expected
                    if command.get("mode"):
                        self.mode = command["mode"]
                    if command.get("phase"):
                        self.phase = command["phase"]
        if self.state_path.exists():
            try:
                state = json.loads(self.state_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as error:
                raise RuntimeError("corrupt gateway state.json: %s" % error)
            if state.get("schema") != "flle.terminal-state.v1":
                raise RuntimeError("gateway state schema drift")
            if state.get("run_id") != self.run_id:
                raise RuntimeError("gateway state RUN_ID drift")
            state_events = state.get("last_sequence")
            state_commands = state.get("command_sequence")
            if (
                state_events == len(self.events)
                and state_commands == self.command_sequence
            ):
                self.mode = state.get("mode", self.mode)
                self.phase = validate_phase(state.get("phase", self.phase))
                self.started_at = state.get("started_at", self.started_at)
                self.stream_drops = int(state.get("stream_queue_drops", 0))
            elif (
                not isinstance(state_events, int)
                or not isinstance(state_commands, int)
                or state_events > len(self.events)
                or state_commands > self.command_sequence
            ):
                raise RuntimeError("gateway state is ahead of its journals")

    def _state_unlocked(self):
        last_event = self.events[-1] if self.events else None
        return {
            "schema": "flle.terminal-state.v1",
            "event_contract": EVENT_SCHEMA,
            "run_id": self.run_id,
            "simulated": True,
            "mode": self.mode,
            "phase": self.phase,
            "last_sequence": len(self.events),
            "last_event": last_event,
            "event_counts": dict(sorted(self.event_counts.items())),
            "phase_counts": dict(sorted(self.phase_counts.items())),
            "command_sequence": self.command_sequence,
            "stream_clients": len(self.subscribers),
            "stream_queue_drops": self.stream_drops,
            "order_path": "GATEWAY_TO_TRADER_ADAPTER_TO_EXCHANGE_TCP",
            "adapter_url": self.adapter_url,
            "data_plane_coupling": "MARKET_DATA_INDEPENDENT_FROM_UI",
            "started_at": self.started_at,
            "updated_at": utc_now(),
        }

    def snapshot(self):
        with self.lock:
            return self._state_unlocked()

    def _persist_state_unlocked(self):
        atomic_json(self.state_path, self._state_unlocked())

    def append_events(self, candidates):
        published = []
        with self.lock:
            for candidate in candidates:
                embedded = candidate.pop("embedded_run_id", None)
                if embedded not in (None, "", self.run_id):
                    raise ValueError("event RUN_ID does not match gateway RUN_ID")
                sequence = len(self.events) + len(published) + 1
                event = {
                    "schema": EVENT_SCHEMA,
                    "event_id": "%s:%08d" % (self.run_id, sequence),
                    "sequence": sequence,
                    "run_id": self.run_id,
                    "ingested_at": utc_now(),
                    "source": validate_name(candidate["source"], "source"),
                    "phase": validate_phase(candidate["phase"]),
                    "kind": validate_name(candidate["kind"], "event"),
                    "simulated": True,
                    "delivery": "live",
                    "fields": candidate.get("fields", {}),
                }
                if candidate.get("raw_line") is not None:
                    event["raw_line"] = str(candidate["raw_line"])
                published.append(event)
            if not published:
                raise ValueError("request contains no event lines")
            with self.events_path.open("a", encoding="utf-8") as handle:
                for event in published:
                    handle.write(compact_json(event) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            for event in published:
                self.events.append(event)
                self.event_counts[event["kind"]] += 1
                self.phase_counts[event["phase"]] += 1
                self.phase = event["phase"]
            self._persist_state_unlocked()
            subscribers = list(self.subscribers.values())
        for event in published:
            self._publish(event, subscribers)
        return published

    def _publish(self, event, subscribers=None):
        if subscribers is None:
            with self.lock:
                subscribers = list(self.subscribers.values())
        for stream_queue in subscribers:
            try:
                stream_queue.put_nowait(event)
            except queue.Full:
                try:
                    stream_queue.get_nowait()
                    stream_queue.put_nowait(event)
                except (queue.Empty, queue.Full):
                    pass
                with self.lock:
                    self.stream_drops += 1

    def recent(self, limit=250, after=0):
        with self.lock:
            selected = self.events[after:]
            return selected[-limit:]

    def subscribe(self, after):
        with self.lock:
            self.subscriber_number += 1
            token = self.subscriber_number
            stream_queue = queue.Queue(maxsize=512)
            self.subscribers[token] = stream_queue
            backlog = list(self.events[after:])
            self._persist_state_unlocked()
        return token, stream_queue, backlog

    def unsubscribe(self, token):
        with self.lock:
            self.subscribers.pop(token, None)
            self._persist_state_unlocked()

    def _persist_command(self, fields, status):
        with self.lock:
            self.command_sequence += 1
            command = {
                "schema": COMMAND_SCHEMA,
                "command_id": "%s:cmd:%08d" % (
                    self.run_id, self.command_sequence
                ),
                "sequence": self.command_sequence,
                "run_id": self.run_id,
                "accepted_at": utc_now(),
                "status": status,
                "simulated": True,
                **fields,
            }
            with self.commands_path.open("a", encoding="utf-8") as handle:
                handle.write(compact_json(command) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            self._persist_state_unlocked()
        return command

    def _command_event(self, command, kind):
        return self.append_events(
            [
                {
                    "source": "terminal-gateway",
                    "phase": command.get("phase", self.phase),
                    "kind": kind,
                    "fields": command,
                    "raw_line": None,
                    "embedded_run_id": self.run_id,
                }
            ]
        )[0]

    def _call_adapter(self, order):
        request = urllib.request.Request(
            self.adapter_url,
            data=compact_json(order).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        status = 200
        try:
            with self.http.open(request, timeout=self.adapter_timeout) as response:
                status = response.status
                body = response.read(MAX_BODY + 1)
        except urllib.error.HTTPError as error:
            status = error.code
            body = error.read(MAX_BODY + 1)
            if status != 409:
                try:
                    detail = json.loads(body.decode("utf-8")).get("error")
                except (AttributeError, UnicodeDecodeError, json.JSONDecodeError):
                    detail = None
                raise UpstreamError(
                    "Trader order adapter returned HTTP %d%s"
                    % (status, ": " + detail if detail else "")
                )
        except (OSError, urllib.error.URLError) as error:
            raise UpstreamError("Trader order adapter is unavailable: " + str(error))
        if len(body) > MAX_BODY:
            raise UpstreamError("Trader order adapter response exceeds 1 MiB")
        try:
            result = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise UpstreamError("Trader order adapter returned invalid JSON: " + str(error))
        if not isinstance(result, dict) or result.get("schema") != ADAPTER_SCHEMA:
            raise UpstreamError("Trader order adapter contract drift")
        if result.get("run_id") != self.run_id:
            raise UpstreamError("Trader order adapter RUN_ID drift")
        if result.get("correlation") != order["correlation"]:
            raise UpstreamError("Trader order adapter correlation drift")
        if result.get("origin") != order["origin"]:
            raise UpstreamError("Trader order adapter origin drift")
        if result.get("simulated") is not True:
            raise UpstreamError("Trader order adapter lost simulated=true")
        disposition = result.get("disposition")
        expected_status = 409 if disposition == "CONFLICT" else 200
        if status != expected_status or disposition not in {
            "APPLIED", "REPLAY", "CONFLICT"
        }:
            raise UpstreamError("Trader order adapter disposition drift")
        events = result.get("events")
        if not isinstance(events, list) or not events:
            raise UpstreamError("Trader order adapter returned no market events")
        responses = result.get("responses")
        if not isinstance(responses, list):
            raise UpstreamError("Trader order adapter responses drift")
        response_types = [item.get("type") for item in responses if isinstance(item, dict)]
        expected_types = (
            ["REJECT"] if disposition == "CONFLICT" else ["ACK", "EXECUTION"]
        )
        if response_types != expected_types or len(response_types) != len(responses):
            raise UpstreamError("Trader order adapter response sequence drift")
        if (
            not isinstance(result.get("action_count"), int)
            or isinstance(result.get("action_count"), bool)
            or result["action_count"] < 0
        ):
            raise UpstreamError("Trader order adapter action_count drift")
        if (
            not isinstance(result.get("elapsed_ns"), int)
            or isinstance(result.get("elapsed_ns"), bool)
            or result["elapsed_ns"] < 0
        ):
            raise UpstreamError("Trader order adapter elapsed_ns drift")
        receipt = result.get("onload_receipt")
        if (
            not isinstance(receipt, str)
            or not re.fullmatch(r"onload-request-[A-Za-z0-9._-]+-[0-9]+\.txt", receipt)
        ):
            raise UpstreamError("Trader order adapter Onload receipt drift")
        return result

    def _submit_order(self, payload, origin):
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
        correlation = str(
            payload.get("correlation") or ("ord-" + secrets.token_hex(12))
        )
        if not CORRELATION_RE.fullmatch(correlation):
            raise ValueError("correlation has an invalid value")
        with self.lock:
            phase = self.phase
        order = {
            "schema": ORDER_SCHEMA,
            "run_id": self.run_id,
            "correlation": correlation,
            "phase": phase,
            "origin": origin,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "simulated": True,
        }
        try:
            adapter_result = self._call_adapter(order)
        except UpstreamError as error:
            command = self._persist_command(
                {
                    "action": "submit_order",
                    "origin": origin,
                    "phase": phase,
                    "symbol": symbol,
                    "side": side,
                    "quantity": quantity,
                    "correlation": correlation,
                    "disposition": "UPSTREAM_FAILED",
                    "error": str(error),
                },
                "failed",
            )
            event = self._command_event(command, "command_failed")
            raise UpstreamError(
                str(error),
                {
                    "status": "failed",
                    "error": str(error),
                    "command": command,
                    "event": event,
                },
            )
        try:
            candidates = [
                parse_json_event(item, "trader-order-adapter")
                for item in adapter_result["events"]
            ]
            market_events = self.append_events(candidates)
        except ValueError as error:
            command = self._persist_command(
                {
                    "action": "submit_order",
                    "origin": origin,
                    "phase": phase,
                    "symbol": symbol,
                    "side": side,
                    "quantity": quantity,
                    "correlation": correlation,
                    "disposition": "EVENT_CONTRACT_FAILED",
                    "error": str(error),
                },
                "failed",
            )
            event = self._command_event(command, "command_failed")
            raise UpstreamError(
                "Trader order adapter event contract failed: " + str(error),
                {
                    "status": "failed",
                    "error": str(error),
                    "command": command,
                    "event": event,
                },
            )
        disposition = adapter_result["disposition"]
        command = self._persist_command(
            {
                "action": "submit_order",
                "origin": origin,
                "phase": phase,
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "correlation": correlation,
                "disposition": disposition,
                "action_count": adapter_result["action_count"],
            },
            "rejected" if disposition == "CONFLICT" else "accepted",
        )
        command_event = self._command_event(
            command,
            "command_rejected" if disposition == "CONFLICT" else "command_accepted",
        )
        return {
            "http_status": 409 if disposition == "CONFLICT" else 200,
            "status": "rejected" if disposition == "CONFLICT" else "accepted",
            "command": command,
            "event": command_event,
            "market_events": market_events,
            "adapter": {
                key: adapter_result[key]
                for key in (
                    "schema", "status", "run_id", "correlation", "origin",
                    "disposition", "action_count", "responses", "elapsed_ns",
                    "onload_receipt", "simulated",
                )
            },
        }

    def accept_command(self, payload):
        if not isinstance(payload, dict):
            raise ValueError("command body must be a JSON object")
        action = payload.get("action")
        if action not in {"set_mode", "set_phase", "submit_order", "replay"}:
            raise ValueError("unsupported command action")
        origin = str(payload.get("origin", "api")).lower()
        if origin not in {"ui", "api"}:
            raise ValueError("origin must be ui or api")
        with self.command_lock:
            if action == "submit_order":
                return self._submit_order(payload, origin)
            command_fields = {"action": action, "origin": origin}
            replay_events = []
            if action == "set_mode":
                mode = str(payload.get("mode", ""))
                if mode not in MODES:
                    raise ValueError("mode must be live, replay, or fault-demo")
                with self.lock:
                    self.mode = mode
                command_fields["mode"] = mode
            elif action == "set_phase":
                phase = validate_phase(payload.get("phase"))
                with self.lock:
                    self.phase = phase
                command_fields["phase"] = phase
            else:
                limit = payload.get("limit", 250)
                interval_ms = payload.get("interval_ms", 20)
                if not isinstance(limit, int) or not 1 <= limit <= 1000:
                    raise ValueError("replay limit must be from 1 to 1000")
                if not isinstance(interval_ms, int) or not 0 <= interval_ms <= 1000:
                    raise ValueError("interval_ms must be from 0 to 1000")
                with self.lock:
                    self.mode = "replay"
                    replay_events = list(self.events[-limit:])
                command_fields.update(
                    mode="replay", limit=limit, interval_ms=interval_ms
                )
            command = self._persist_command(command_fields, "accepted")
            accepted_event = self._command_event(command, "command_accepted")
            if action == "replay":
                thread = threading.Thread(
                    target=self._replay,
                    args=(replay_events, payload.get("interval_ms", 20)),
                    daemon=True,
                )
                thread.start()
            return {
                "http_status": 202,
                "status": "accepted",
                "command": command,
                "event": accepted_event,
            }

    def _replay(self, events, interval_ms):
        for original in events:
            replayed = dict(original)
            replayed["delivery"] = "replay"
            self._publish(replayed)
            if interval_ms:
                time.sleep(interval_ms / 1000.0)


class GatewayHandler(http.server.BaseHTTPRequestHandler):
    server_version = "FLLETerminalGateway/1"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        print(
            "%s peer=%s %s" % (utc_now(), self.client_address[0], fmt % args),
            flush=True,
        )

    @property
    def store(self):
        return self.server.event_store

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
            {"error": message, "status": status, "run_id": self.store.run_id},
        )

    def parsed_path(self):
        return urllib.parse.urlparse(self.path)

    def do_GET(self):
        parsed = self.parsed_path()
        if parsed.path == "/healthz":
            self.send_json(
                200,
                {
                    "status": "ready", "run_id": self.store.run_id,
                    "event_contract": EVENT_SCHEMA,
                },
            )
        elif parsed.path == "/api/v1/state":
            self.send_json(200, self.store.snapshot())
        elif parsed.path == "/api/v1/contract":
            self.send_json(
                200,
                {
                    "schema": EVENT_SCHEMA,
                    "required": [
                        "event_id", "sequence", "run_id", "ingested_at",
                        "source", "phase", "kind", "simulated", "delivery",
                        "fields",
                    ],
                    "phases": sorted(PHASES),
                    "modes": sorted(MODES),
                },
            )
        elif parsed.path == "/api/v1/events":
            try:
                query = urllib.parse.parse_qs(parsed.query)
                limit = int(query.get("limit", ["250"])[0])
                after = int(query.get("after", ["0"])[0])
                if not 1 <= limit <= 1000 or after < 0:
                    raise ValueError
            except ValueError:
                self.send_error_json(400, "limit=1..1000 and after>=0 are required")
                return
            self.send_json(
                200,
                {
                    "schema": EVENT_SCHEMA, "run_id": self.store.run_id,
                    "events": self.store.recent(limit, after),
                },
            )
        elif parsed.path == "/api/v1/events/stream":
            self.serve_stream(parsed)
        elif parsed.path == "/":
            self.send_asset("index.html", "text/html; charset=utf-8")
        elif parsed.path == "/assets/terminal.css":
            self.send_asset("terminal.css", "text/css; charset=utf-8")
        elif parsed.path == "/assets/terminal.js":
            self.send_asset("terminal.js", "text/javascript; charset=utf-8")
        elif parsed.path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
        else:
            self.send_error_json(404, "route not found")

    def send_asset(self, name, content_type):
        path = self.server.asset_root / name
        try:
            body = path.read_bytes()
        except FileNotFoundError:
            self.send_error_json(404, "terminal asset missing: " + name)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; connect-src 'self'; img-src 'self' data:; "
            "style-src 'self'; script-src 'self'; frame-ancestors 'none'",
        )
        self.end_headers()
        self.wfile.write(body)

    def serve_stream(self, parsed):
        query = urllib.parse.parse_qs(parsed.query)
        after_text = query.get("after", [None])[0]
        if after_text is None:
            last_id = self.headers.get("Last-Event-ID", "")
            after_text = last_id.rsplit(":", 1)[-1] if last_id else "0"
        try:
            after = int(after_text)
            if after < 0:
                raise ValueError
        except ValueError:
            self.send_error_json(400, "after must be a non-negative sequence")
            return
        token, stream_queue, backlog = self.store.subscribe(after)
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        try:
            self.wfile.write(b"retry: 2000\n\n")
            self.wfile.flush()
            for event in backlog:
                self.write_sse(event)
            while True:
                try:
                    event = stream_queue.get(timeout=10)
                    self.write_sse(event)
                except queue.Empty:
                    heartbeat = ": gateway heartbeat %s\n\n" % utc_now()
                    self.wfile.write(heartbeat.encode("utf-8"))
                    self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            pass
        finally:
            self.store.unsubscribe(token)

    def write_sse(self, event):
        payload = compact_json(event)
        block = "id: %s\nevent: market\ndata: %s\n\n" % (
            event["sequence"], payload
        )
        self.wfile.write(block.encode("utf-8"))
        self.wfile.flush()

    def read_body(self):
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            raise ValueError("Content-Length is required")
        if not 1 <= length <= MAX_BODY:
            raise ValueError("request body must be from 1 byte to 1 MiB")
        return self.rfile.read(length)

    def do_POST(self):
        parsed = self.parsed_path()
        try:
            body = self.read_body()
            content_type = self.headers.get("Content-Type", "").split(";", 1)[0]
            if parsed.path == "/api/v1/events":
                source = validate_name(
                    self.headers.get("X-FLLE-Source", "market_day.py"), "source"
                )
                if content_type == "text/plain":
                    text = body.decode("utf-8")
                    candidates = [
                        parsed_line for line in text.splitlines()
                        if (parsed_line := parse_native_line(line, source)) is not None
                    ]
                elif content_type == "application/json":
                    payload = json.loads(body)
                    items = payload.get("events", []) if isinstance(payload, dict) and "events" in payload else payload
                    if isinstance(items, dict):
                        items = [items]
                    if not isinstance(items, list):
                        raise ValueError("JSON body must be an event, list, or events list")
                    candidates = [parse_json_event(item, source) for item in items]
                else:
                    raise ValueError("use Content-Type text/plain or application/json")
                events = self.store.append_events(candidates)
                self.send_json(
                    202,
                    {
                        "accepted": len(events), "run_id": self.store.run_id,
                        "first_sequence": events[0]["sequence"],
                        "last_sequence": events[-1]["sequence"],
                        "event_contract": EVENT_SCHEMA,
                    },
                )
            elif parsed.path == "/api/v1/commands":
                if content_type != "application/json":
                    raise ValueError("commands require Content-Type application/json")
                payload = json.loads(body)
                result = self.store.accept_command(payload)
                status = result.pop("http_status")
                self.send_json(status, result)
            else:
                self.send_error_json(404, "route not found")
        except UpstreamError as error:
            result = error.result or {
                "status": "failed",
                "error": str(error),
                "run_id": self.store.run_id,
            }
            self.send_json(502, result)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
            self.send_error_json(400, str(error))


class GatewayServer(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def claim_pid(path):
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError:
        raise SystemExit("gateway pid file already exists: " + str(path))
    with os.fdopen(descriptor, "w", encoding="ascii") as handle:
        handle.write(str(os.getpid()) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--run-dir", required=True, type=pathlib.Path)
    parser.add_argument("--asset-root", type=pathlib.Path)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8088)
    parser.add_argument(
        "--adapter-url", default="http://10.1.1.2:8089/v1/orders"
    )
    parser.add_argument("--adapter-timeout", type=float, default=5.0)
    args = parser.parse_args()
    if not RUN_RE.fullmatch(args.run_id):
        raise SystemExit("invalid --run-id")
    run_dir = args.run_dir.resolve()
    if run_dir == pathlib.Path("/"):
        raise SystemExit("--run-dir cannot be /")
    adapter = urllib.parse.urlparse(args.adapter_url)
    if adapter.scheme != "http" or not adapter.hostname or adapter.path != "/v1/orders":
        raise SystemExit("--adapter-url must be an http:// URL ending in /v1/orders")
    if not 0.1 <= args.adapter_timeout <= 60:
        raise SystemExit("--adapter-timeout must be from 0.1 to 60 seconds")
    asset_root = (
        args.asset_root.resolve() if args.asset_root
        else (pathlib.Path(__file__).resolve().parent / "terminal")
    )
    for required in ("index.html", "terminal.css", "terminal.js"):
        if not (asset_root / required).is_file():
            raise SystemExit("missing terminal asset: " + required)
    store = EventStore(
        args.run_id, run_dir, args.adapter_url, args.adapter_timeout
    )
    claim_pid(store.pid_path)
    try:
        server = GatewayServer((args.bind, args.port), GatewayHandler)
    except Exception:
        store.pid_path.unlink(missing_ok=True)
        raise
    server.event_store = store
    server.asset_root = asset_root
    stop = threading.Event()

    def request_stop(signum, unused_frame):
        print("%s signal=%d action=stop" % (utc_now(), signum), flush=True)
        stop.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    server.timeout = 0.5
    print(
        "%s status=ready bind=%s port=%d run_id=%s contract=%s adapter=%s" % (
            utc_now(), args.bind, args.port, args.run_id, EVENT_SCHEMA,
            args.adapter_url,
        ),
        flush=True,
    )
    try:
        while not stop.is_set():
            server.handle_request()
    finally:
        server.server_close()
        try:
            if store.pid_path.read_text(encoding="ascii").strip() == str(os.getpid()):
                store.pid_path.unlink()
        except FileNotFoundError:
            pass
        print("%s status=stopped run_id=%s" % (utc_now(), args.run_id), flush=True)


if __name__ == "__main__":
    main()
