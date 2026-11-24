#!/usr/bin/env python3
"""Trader-host control service: browser gateway to local device ownership gate.

The service accepts GET /state, POST /mode with SFC or DPDK, and POST /reset-paper.  It does
not accept shell text from the network; every subprocess argument is fixed by
the local launch configuration.
"""

from __future__ import annotations

import argparse
from contextlib import ExitStack
import json
import os
import signal
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


class Controller:
    def __init__(self, script: Path, run_id: str, log_dir: Path | None = None) -> None:
        self.script = script.resolve(strict=True)
        self.run_id = run_id
        self.lock = threading.Lock()
        self.log_dir = log_dir

    def _run_action(self, action: str, timeout: int) -> subprocess.CompletedProcess[str]:
        if self.log_dir is None or action == "status":
            return self._execute_action(action, timeout)
        directory = self.log_dir / f"{time.time_ns()}-{action}"
        directory.mkdir(parents=True, exist_ok=False)
        started = time.monotonic()
        record = {"action": action, "run_id": self.run_id,
                  "timeout_seconds": timeout, "result": "RUNNING"}

        def save() -> None:
            temporary = directory / "result.json.tmp"
            temporary.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
            temporary.replace(directory / "result.json")

        save()
        print(f"MODE_ACTION_START action={action} evidence={directory}", flush=True)
        try:
            with ExitStack() as files:
                stdout = files.enter_context((directory / "stdout.txt").open("w+"))
                stderr = files.enter_context((directory / "stderr.txt").open("w+"))
                completed = self._execute_action(action, timeout, stdout, stderr)
            record.update(result="PASS" if completed.returncode == 0 else "FAILED",
                          returncode=completed.returncode)
            return completed
        except subprocess.TimeoutExpired:
            record["result"] = "TIMEOUT"
            raise
        except Exception as error:
            record.update(result="ERROR", error=str(error))
            raise
        finally:
            record["elapsed_seconds"] = round(time.monotonic() - started, 3)
            save()
            print(f"MODE_ACTION_END action={action} result={record['result']} "
                  f"elapsed={record['elapsed_seconds']} evidence={directory}", flush=True)

    def _execute_action(self, action: str, timeout: int,
                        stdout_file: Any = None, stderr_file: Any = None
                        ) -> subprocess.CompletedProcess[str]:
        command = [str(self.script), action, self.run_id]
        process = subprocess.Popen(
            command,
            stdout=stdout_file if stdout_file is not None else subprocess.PIPE,
            stderr=stderr_file if stderr_file is not None else subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.communicate()
            raise
        if stdout_file is not None:
            stdout_file.seek(0)
            stdout = stdout_file.read()
        if stderr_file is not None:
            stderr_file.seek(0)
            stderr = stderr_file.read()
        return subprocess.CompletedProcess(
            command, process.returncode, stdout, stderr
        )

    @staticmethod
    def _parse_state(stdout: str) -> dict[str, Any] | None:
        for line in reversed(stdout.splitlines()):
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                return value
        return None

    @staticmethod
    def _mode_state_is_ready(state: dict[str, Any], action: str) -> bool:
        if state.get("experiment_profile") == "SOFTWARE":
            return (action == "baseline"
                    and state.get("mode") == "SFC"
                    and state.get("owner") == "sfc"
                    and state.get("transition") == "READY"
                    and state.get("hugepages_2mb") == 128
                    and state.get("data_ip_present") is True
                    and state.get("software_clients_ready") is True)
        if action not in {"sfc", "dpdk"}:
            return False
        expected = {
            "sfc": ("SFC", "sfc", 128, True),
            "dpdk": ("DPDK", "vfio-pci", 256, False),
        }[action]
        mode, owner, hugepages, ip_present = expected
        return (
            state.get("mode") == mode
            and state.get("transition") == "READY"
            and state.get("owner") == owner
            and state.get("hugepages_2mb") == hugepages
            and state.get("data_ip_present") is ip_present
        )

    def invoke(self, action: str, timeout: int) -> dict[str, Any]:
        if action not in {"status", "baseline", "sfc", "dpdk", "reset-paper"}:
            raise ValueError("unsupported controller action")

        def recover_sfc(reason: str, cause: Exception | None = None) -> None:
            try:
                recovery = self._run_action("sfc", 300)
            except subprocess.TimeoutExpired as recovery_timeout:
                raise RuntimeError(
                    f"{reason} and direct SFC recovery timed out"
                ) from recovery_timeout
            if recovery.returncode != 0:
                detail = recovery.stderr.strip() or recovery.stdout.strip()
                raise RuntimeError(
                    f"{reason} and direct SFC recovery failed: "
                    + detail[-2000:]
                ) from cause
            recovery_state = self._parse_state(recovery.stdout)
            if recovery_state is None or not self._mode_state_is_ready(
                recovery_state, "sfc"
            ):
                raise RuntimeError(
                    f"{reason} and direct SFC recovery returned no verified "
                    "SFC/READY hard-gate state"
                ) from cause
            raise RuntimeError(
                f"{reason}; direct SFC recovery reached its hard gates"
            ) from cause

        with self.lock:
            try:
                completed = self._run_action(action, timeout)
            except subprocess.TimeoutExpired as timeout_error:
                if action in {"baseline", "sfc", "dpdk"}:
                    recover_sfc("mode action timed out", timeout_error)
                raise RuntimeError("status action timed out") from timeout_error
            if completed.returncode != 0:
                detail = completed.stderr.strip() or completed.stdout.strip()
                # The DPDK shell transaction may already have restored the
                # feed-dependent SOFTWARE profile. Verify it before keeping it;
                # unconditional SFC recovery would immediately stop its receiver.
                if action == "dpdk":
                    for profile in ("baseline", "sfc"):
                        if f"DPDK_RECOVERY_OK profile={profile}" not in completed.stderr.splitlines():
                            continue
                        try:
                            checked = self._run_action("status", 10)
                            restored = self._parse_state(checked.stdout)
                        except subprocess.TimeoutExpired:
                            break
                        if (checked.returncode == 0 and restored is not None
                                and self._mode_state_is_ready(restored, profile)):
                            raise RuntimeError(
                                f"mode action failed; verified {profile} recovery retained: "
                                + detail[-2000:]
                            )
                if action in {"baseline", "sfc", "dpdk"}:
                    recover_sfc(
                        "mode action failed: " + (detail[-2000:] or "no detail")
                    )
                raise RuntimeError(detail[-2000:] or "controller action failed")
            state = self._parse_state(completed.stdout)
            if state is None:
                if action in {"baseline", "sfc", "dpdk"}:
                    recover_sfc("mode action returned no JSON state")
                raise RuntimeError("controller action returned no JSON state")
            if action in {"baseline", "sfc", "dpdk"} and not self._mode_state_is_ready(
                state, action
            ):
                recover_sfc(
                    "mode action returned an unverified terminal state"
                )
            if action == "reset-paper" and (
                state.get("paper_reset") is not True
                or state.get("mode") not in {"SFC", "DPDK"}
                or not self._mode_state_is_ready(state, "baseline" if state.get("experiment_profile") == "SOFTWARE" else state["mode"].lower())
            ):
                raise RuntimeError("paper reset returned no verified zero-position/READY receipt")
            return state


def handler(controller: Controller, allowed_peer: str) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def respond(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload, separators=(",", ":")).encode("ascii")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def authorized(self) -> bool:
            if self.client_address[0] == allowed_peer:
                return True
            self.respond(403, {"error": "controller peer is not allowed"})
            return False

        def do_GET(self) -> None:  # noqa: N802
            if not self.authorized():
                return
            if self.path != "/state":
                self.respond(404, {"error": "not found"})
                return
            try:
                self.respond(200, controller.invoke("status", 10))
            except (RuntimeError, subprocess.TimeoutExpired) as error:
                self.respond(503, {"error": str(error)})

        def do_POST(self) -> None:  # noqa: N802
            if not self.authorized():
                return
            if self.path not in {"/mode", "/reset-paper"}:
                self.respond(404, {"error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 2 or length > 1024:
                    raise ValueError("invalid request size")
                request = json.loads(self.rfile.read(length))
                if self.path == "/reset-paper":
                    self.respond(200, controller.invoke("reset-paper", 300))
                    return
                mode = str(request.get("mode", "")).upper()
                if mode not in {"BASELINE", "SFC", "DPDK"}:
                    raise ValueError("mode must be BASELINE, SFC or DPDK")
                self.respond(200, controller.invoke(mode.lower(), 300))
            except (ValueError, json.JSONDecodeError) as error:
                self.respond(400, {"error": str(error)})
            except (RuntimeError, subprocess.TimeoutExpired) as error:
                self.respond(503, {"error": str(error)})

        def log_message(self, _format: str, *_args: Any) -> None:
            return

    return Handler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bind-ip", default="10.1.1.2")
    parser.add_argument("--port", type=int, default=48606)
    parser.add_argument("--allowed-peer", default="10.1.1.101")
    parser.add_argument("--control-script", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--log-dir", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    controller = Controller(Path(args.control_script), args.run_id, args.log_dir)
    ThreadingHTTPServer(
        (args.bind_ip, args.port), handler(controller, args.allowed_peer)
    ).serve_forever(poll_interval=0.5)


if __name__ == "__main__":
    main()
