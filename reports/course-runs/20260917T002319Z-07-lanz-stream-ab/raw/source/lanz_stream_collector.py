#!/usr/bin/env python3
"""调用 Arista 官方 LANZ 客户端读取事件，给 8088 页面提供只读 JSON。"""

import json
import os
import signal
import subprocess
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
READER_PATH = "/opt/flle/lanz-reader-v1/flle-lanz-reader"
STATE_PATH = "/run/flle-lanz-stream/latest.json"

_lock = threading.Lock()
_state = {
    "schema": "flle.lanz-stream.v1",
    "decoder": "arista-goarista-lanz",
    "connected": False,
    "switch": f"{SWITCH_HOST}:{SWITCH_PORT}",
    "listen": f"{LISTEN_HOST}:{LISTEN_PORT}",
    "error": "",
    "config": None,
    "events": [],
    "counts": {"START": 0, "UPDATE": 0, "END": 0, "POLLING": 0, "OTHER": 0},
    "counts_by_queue": {},
    "updated_unix_ns": 0,
}


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
            key = f"{record.get('intf_name')}/TC{record.get('traffic_class')}"
            counts = _state["counts_by_queue"].setdefault(key, dict.fromkeys(_state["counts"], 0))
            counts[entry] += 1
            _state["events"] = (_state["events"] + [record])[-MAX_EVENTS:]
    persist()


def set_connected(connected, error=""):
    """更新连接灯。"""
    with _lock:
        _state["connected"] = bool(connected)
        _state["error"] = error
        _state["updated_unix_ns"] = time.time_ns()
    persist()


_reader_lock = threading.Lock()
_reader = None


def stop_reader():
    """结束官方客户端子进程，避免网页采集器重启后留下旧连接。"""
    with _reader_lock:
        process = _reader
    if process is not None and process.poll() is None:
        process.terminate()


def stream_once(stop_event):
    """官方 Go 客户端完成 TCP 接收与 Protobuf 解码；这里只读取 JSON。"""
    global _reader
    with subprocess.Popen(
        [READER_PATH, "-addr", f"{SWITCH_HOST}:{SWITCH_PORT}", "-json"],
        stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, text=True,
    ) as process:
        with _reader_lock:
            _reader = process
        try:
            if stop_event.is_set():
                process.terminate()
            for line in process.stdout:
                record = json.loads(line)
                if record.get("kind") == "connection":
                    set_connected(record["connected"], record.get("error", ""))
                elif record.get("kind") == "error":
                    set_connected(True, record.get("message", ""))
                else:
                    apply_record(record)
            raise ConnectionError(f"官方 LANZ 客户端已退出：{process.wait()}")
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=6)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            with _reader_lock:
                _reader = None


def stream_loop(stop_event):
    """断线后自动重连，直到进程退出。"""
    while not stop_event.is_set():
        try:
            stream_once(stop_event)
        except Exception as exc:
            set_connected(False, str(exc))
        if stop_event.wait(RECONNECT_SEC):
            return


def reset_history():
    """清空本轮观测历史，保留连接和交换机配置。"""
    with _lock:
        _state["events"].clear()
        _state["counts"] = dict.fromkeys(_state["counts"], 0)
        _state["counts_by_queue"].clear()
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
    if not os.access(READER_PATH, os.X_OK):
        raise SystemExit(f"官方 LANZ 客户端不存在或不可执行：{READER_PATH}")
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    persist()
    stop_event = threading.Event()
    worker = threading.Thread(target=stream_loop, args=(stop_event,), daemon=True)
    def interrupted(signum, frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    server = ThreadingHTTPServer((LISTEN_HOST, LISTEN_PORT), LanzHandler)
    worker.start()
    print(f"lanz_stream listen={LISTEN_HOST}:{LISTEN_PORT} switch={SWITCH_HOST}:{SWITCH_PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        stop_reader()
        worker.join(timeout=7)
        server.server_close()


if __name__ == "__main__":
    print("~~~~~~~~~~~~~~~~~~~~~LANZ 接收器~~~~~~~~~~~~~~~~~~~~~")
    serve()
