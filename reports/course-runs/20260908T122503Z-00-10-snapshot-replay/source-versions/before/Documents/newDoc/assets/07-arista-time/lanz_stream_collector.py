#!/usr/bin/env python3
"""在 .101 上接收 7150 推过来的 LANZ protobuf 流，并给 8088 页面提供只读 JSON。"""

import json
import os
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ----- 模块级配置：改这里即可重跑 -----
SWITCH_HOST = "10.1.1.253"
SWITCH_PORT = 50001
LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 8089
MAX_EVENTS = 80
RECONNECT_SEC = 1.0
CONNECT_TIMEOUT_SEC = 5.0
STATE_PATH = "/run/flle-lanz-stream/latest.json"

# goarista LANZ proto：CongestionRecord.EntryType
ENTRY_NAME = {1: "START", 2: "UPDATE", 3: "END", 4: "POLLING"}

_lock = threading.Lock()
_state = {
    "schema": "flle.lanz-stream.v1",
    "connected": False,
    "switch": f"{SWITCH_HOST}:{SWITCH_PORT}",
    "listen": f"{LISTEN_HOST}:{LISTEN_PORT}",
    "error": "",
    "config": None,
    "events": [],
    "counts": {"START": 0, "UPDATE": 0, "END": 0, "POLLING": 0, "OTHER": 0},
    "updated_unix_ns": 0,
}


def read_varint(buf, pos):
    """读取 protobuf / 流帧使用的无符号 varint。"""
    result = 0
    shift = 0
    while True:
        if pos >= len(buf):
            raise ValueError("varint 被截断")
        byte = buf[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if byte < 0x80:
            return result, pos
        shift += 7
        if shift > 70:
            raise ValueError("varint 过长")


def decode_fields(buf):
    """把一段 proto2 字节解成 {field_no: value 或 [value, ...]}。"""
    fields = {}
    pos = 0
    while pos < len(buf):
        tag, pos = read_varint(buf, pos)
        field_no = tag >> 3
        wire = tag & 7
        if wire == 0:
            value, pos = read_varint(buf, pos)
        elif wire == 2:
            length, pos = read_varint(buf, pos)
            value = buf[pos : pos + length]
            pos += length
            if pos > len(buf):
                raise ValueError("length-delimited 字段被截断")
        elif wire == 1:
            value = buf[pos : pos + 8]
            pos += 8
        elif wire == 5:
            value = buf[pos : pos + 4]
            pos += 4
        else:
            raise ValueError(f"不支持的 wire type {wire}")
        if field_no in fields:
            previous = fields[field_no]
            if isinstance(previous, list):
                previous.append(value)
            else:
                fields[field_no] = [previous, value]
        else:
            fields[field_no] = value
    return fields


def field_u(fields, number, default=0):
    """读取单个 varint 字段。"""
    value = fields.get(number, default)
    if isinstance(value, list):
        value = value[-1]
    return int(value or 0)


def field_s(fields, number, default=""):
    """读取单个字符串字段。"""
    value = fields.get(number, default)
    if isinstance(value, list):
        value = value[-1]
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return value or ""


def decode_congestion(raw):
    """解 CongestionRecord。字段号与 goarista lanz.proto 一致。"""
    fields = decode_fields(raw)
    entry = field_u(fields, 6)
    return {
        "kind": "congestion",
        "timestamp_us": field_u(fields, 1),
        "intf_name": field_s(fields, 2),
        "switch_id": field_u(fields, 3),
        "port_id": field_u(fields, 4),
        "queue_size": field_u(fields, 5),
        "entry_type": ENTRY_NAME.get(entry, str(entry) or "OTHER"),
        "traffic_class": field_u(fields, 7),
        "time_of_max_qlen": field_u(fields, 8),
        "tx_latency": field_u(fields, 9),
        "q_drop_count": field_u(fields, 10),
    }


def decode_config(raw):
    """解 ConfigRecord，只留课堂要用的格子大小。"""
    fields = decode_fields(raw)
    return {
        "kind": "config",
        "timestamp_us": field_u(fields, 1),
        "lanz_version": field_u(fields, 2),
        "num_of_ports": field_u(fields, 3),
        "segment_size": field_u(fields, 4),
        "max_queue_size": field_u(fields, 5),
    }


def decode_lanz_record(raw):
    """解最外层 LanzRecord。"""
    fields = decode_fields(raw)
    if 2 in fields:
        nested = fields[2][-1] if isinstance(fields[2], list) else fields[2]
        return decode_congestion(nested)
    if 1 in fields:
        nested = fields[1][-1] if isinstance(fields[1], list) else fields[1]
        return decode_config(nested)
    if 3 in fields:
        nested = fields[3][-1] if isinstance(fields[3], list) else fields[3]
        error_fields = decode_fields(nested)
        return {"kind": "error", "message": field_s(error_fields, 2)}
    return {"kind": "other"}


def encode_varint(value):
    """编码无符号 varint，给自检造一条最小报文。"""
    chunks = []
    while value > 0x7F:
        chunks.append((value & 0x7F) | 0x80)
        value >>= 7
    chunks.append(value)
    return bytes(chunks)


def encode_key(field_no, wire):
    """编码 protobuf tag。"""
    return encode_varint((field_no << 3) | wire)


def encode_string(field_no, text):
    """编码 length-delimited 字符串。"""
    payload = text.encode("utf-8")
    return encode_key(field_no, 2) + encode_varint(len(payload)) + payload


def encode_varint_field(field_no, value):
    """编码 varint 字段。"""
    return encode_key(field_no, 0) + encode_varint(value)


def encode_message(field_no, payload):
    """把一段已编码消息嵌进外层字段。"""
    return encode_key(field_no, 2) + encode_varint(len(payload)) + payload


def self_test_decoder():
    """造一条 Et2 START，确认解码与官方字段号对齐。"""
    congestion = b"".join(
        [
            encode_varint_field(1, 123456),
            encode_string(2, "Ethernet2"),
            encode_varint_field(3, 0),
            encode_varint_field(4, 2),
            encode_varint_field(5, 64),
            encode_varint_field(6, 1),
            encode_varint_field(7, 1),
        ]
    )
    record = encode_message(2, congestion)
    decoded = decode_lanz_record(record)
    assert decoded["kind"] == "congestion"
    assert decoded["intf_name"] == "Ethernet2"
    assert decoded["entry_type"] == "START"
    assert decoded["queue_size"] == 64
    assert decoded["traffic_class"] == 1


def snapshot():
    """复制当前接收器状态。"""
    with _lock:
        return json.loads(json.dumps(_state, ensure_ascii=False))


def persist():
    """把最新快照写到 /run，供脚本验收。"""
    blob = json.dumps(snapshot(), ensure_ascii=False, indent=2)
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as handle:
            handle.write(blob + "\n")
    except OSError:
        return


def apply_record(record):
    """把一条已解码记录写进内存状态。"""
    with _lock:
        _state["updated_unix_ns"] = time.time_ns()
        _state["error"] = ""
        if record.get("kind") == "config":
            _state["config"] = record
        elif record.get("kind") == "congestion":
            entry = record.get("entry_type") or "OTHER"
            if entry not in _state["counts"]:
                entry = "OTHER"
            _state["counts"][entry] += 1
            _state["events"] = (_state["events"] + [record])[-MAX_EVENTS:]
    persist()


def set_connected(connected, error=""):
    """更新连接灯。"""
    with _lock:
        _state["connected"] = bool(connected)
        _state["error"] = error
        _state["updated_unix_ns"] = time.time_ns()
    persist()


def recv_exact(conn, size):
    """从 TCP 连接读满 size 字节。"""
    chunks = []
    remain = size
    while remain:
        piece = conn.recv(remain)
        if not piece:
            raise ConnectionError("交换机断开 LANZ 流")
        chunks.append(piece)
        remain -= len(piece)
    return b"".join(chunks)


def recv_uvarint(conn):
    """按 goarista 客户端读一帧长度：TCP 上的 uvarint。"""
    raw = b""
    for _ in range(10):
        byte = conn.recv(1)
        if not byte:
            raise ConnectionError("交换机断开 LANZ 流")
        raw += byte
        if byte[0] < 0x80:
            length, _ = read_varint(raw, 0)
            return length
    raise ValueError("帧长度 varint 过长")


def stream_once():
    """连上 7150:50001，循环解 LanzRecord。"""
    conn = socket.create_connection((SWITCH_HOST, SWITCH_PORT), CONNECT_TIMEOUT_SEC)
    conn.settimeout(30)
    set_connected(True)
    try:
        while True:
            length = recv_uvarint(conn)
            if length <= 0 or length > 1_000_000:
                raise ValueError(f"非法帧长度 {length}")
            raw = recv_exact(conn, length)
            apply_record(decode_lanz_record(raw))
    finally:
        conn.close()


def stream_loop(stop_event):
    """断线后自动重连，直到进程退出。"""
    while not stop_event.is_set():
        try:
            stream_once()
        except Exception as exc:
            set_connected(False, str(exc))
        if stop_event.wait(RECONNECT_SEC):
            return


def reset_history():
    """清空本轮观测历史，保留连接和交换机配置。"""
    with _lock:
        _state["events"].clear()
        _state["counts"] = dict.fromkeys(_state["counts"], 0)
        _state["updated_unix_ns"] = time.time_ns()
    persist()
    return {"ok": True, "cleared": True}


class LanzHandler(BaseHTTPRequestHandler):
    """给 8088 页面和教师脚本提供只读 JSON。"""

    def log_message(self, format, *args):
        return

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.end_headers()

    def do_POST(self):
        # Only the co-located gateway may reset; browser access remains read-only.
        if self.client_address[0] not in ("127.0.0.1", "::1"):
            self.send_error(403)
            return
        if self.path != "/api/lanz/reset":
            self.send_error(404)
            return
        body = json.dumps(reset_history()).encode("ascii")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.split("?", 1)[0] not in ("/api/lanz", "/"):
            self.send_error(404)
            return
        body = json.dumps(snapshot(), ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def serve():
    """启动 HTTP 和交换机接收线程。"""
    self_test_decoder()
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    persist()
    stop_event = threading.Event()
    worker = threading.Thread(target=stream_loop, args=(stop_event,), daemon=True)
    worker.start()
    server = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), LanzHandler)
    print(f"lanz_stream listen={LISTEN_HOST}:{LISTEN_PORT} switch={SWITCH_HOST}:{SWITCH_PORT}")
    try:
        server.serve_forever()
    finally:
        stop_event.set()
        server.server_close()


if __name__ == "__main__":
    print("~~~~~~~~~~~~~~~~~~~~~LANZ 接收器~~~~~~~~~~~~~~~~~~~~~")
    serve()
