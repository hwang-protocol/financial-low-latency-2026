#!/usr/bin/env python3
"""Prove the true-order Kernel/Onload mechanism without treating strace as a timer."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import socket
import subprocess
import time
from pathlib import Path
from typing import Any


TRADER_HOST = "10.1.1.2"
ORDER_PEER = "20.1.1.1:43120"
TELEMETRY_PEER = "10.1.1.101:46120"
PROBE_SETTLE_SECONDS = 0.2
COUNTER_TAIL_SECONDS = 0.2
TRANSPORTS = {
    "SOCKET": {"port": 48122, "pidfile": "trader-socket.pid"},
    "OPENONLOAD": {"port": 48123, "pidfile": "trader-onload.pid"},
}
MECHANISM_SCHEMA = "flle.ch06-kernel-onload-mechanism.v3"
PROC_PHASES = ("pre", "post")
PROC_FILES = ("identity", "status", "schedstat")
EXECUTION_PROGRAM_BYTES = Path(__file__).resolve().read_bytes()


def management(port: int, line: str) -> dict[str, Any]:
    with socket.create_connection((TRADER_HOST, port), timeout=3) as connection:
        connection.sendall((line + "\n").encode("ascii"))
        raw = connection.makefile("rb").readline()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise RuntimeError(f"management response is not an object: {line}")
    return value


def wait_samples(port: int, expected: int) -> dict[str, Any]:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        state = management(port, "STATE")
        if int(state["measurement_latency"]["samples"]) >= expected:
            return state
        time.sleep(0.002)
    raise TimeoutError(f"port {port} did not reach {expected} samples")


def submit_batch(port: int, samples: int) -> dict[str, Any]:
    reset = management(port, "MEASUREMENT_RESET")
    if reset.get("ok") is not True:
        raise RuntimeError(f"measurement reset failed: {reset}")
    side = "BUY"
    for index in range(samples):
        price = 999_999_999_999 if side == "BUY" else 1
        reply = management(
            port, f"MEASUREMENT_ORDER|AAPL|{side}|1|{price}"
        )
        if reply.get("ok") is not True:
            raise RuntimeError(f"order rejected before enqueue: {reply}")
        wait_samples(port, index + 1)
        side = "SELL" if side == "BUY" else "BUY"
    raw = management(port, "MEASUREMENT_SAMPLES")
    rows = raw.get("samples", [])
    if len(rows) != samples or any(row.get("result") != "E" for row in rows):
        raise RuntimeError(f"expected {samples} executed orders, got {rows!r}")
    return raw


def ssh(command: str) -> str:
    return subprocess.run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=yes",
            f"root@{TRADER_HOST}",
            command,
        ],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    ).stdout


def scp(remote: str, local: Path) -> None:
    subprocess.run(
        [
            "scp",
            "-q",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=yes",
            f"root@{TRADER_HOST}:{remote}",
            str(local),
        ],
        check=True,
    )


def thread_identity(run_dir: str, pidfile: str, port: int) -> tuple[int, int]:
    state = management(port, "STATE")
    tid = int(state["software_latency"]["order_thread_tid"])
    pid = int(ssh(f"cat '{run_dir}/{pidfile}'").strip())
    identity = ssh(
        f"set -eu; test -d /proc/{pid}/task/{tid}; "
        f"expected=$(readlink -f '{run_dir}/transport-runtime/"
        f"flle-ch06-four-path/bin/flle-trader'); "
        f"observed=$(readlink -f /proc/{pid}/exe); "
        f"test \"$observed\" = \"$expected\"; "
        f"digest=$(sha256sum \"$observed\" | awk '{{print $1}}'); "
        f"case \"$digest\" in ''|*[!0-9a-f]*) exit 1;; esac; "
        f"test \"${{#digest}}\" -eq 64; "
        f"printf '%s ' \"$(cat /proc/{tid}/comm)\"; "
        f"awk '/Cpus_allowed_list/ {{print $2}}' /proc/{tid}/status"
    ).strip()
    if identity != "flle-order 2":
        raise RuntimeError(f"unexpected order thread identity: {identity}")
    return pid, tid


def proc_original_path(raw_dir: Path, key: str, phase: str, name: str) -> Path:
    if key not in TRANSPORTS or phase not in PROC_PHASES or name not in PROC_FILES:
        raise RuntimeError(
            f"invalid /proc original identity: key={key} phase={phase} name={name}"
        )
    return raw_dir / f"{key.lower()}-order-thread-{phase}.{name}"


def capture_proc_snapshot(
    key: str,
    phase: str,
    run_dir: str,
    pidfile: str,
    pid: int,
    tid: int,
) -> str:
    """Publish one generation-checked /proc snapshot directory on the trader."""

    if key not in TRANSPORTS or phase not in PROC_PHASES:
        raise RuntimeError(f"invalid /proc snapshot target: {key}/{phase}")
    remote = f"{run_dir}/mechanism-proc/{key.lower()}-{phase}"
    ssh(
        f"set -Eeuo pipefail; final='{remote}'; tmp=\"$final.tmp.$$\"; "
        f"test ! -e \"$final\"; mkdir -p \"$(dirname \"$final\")\" \"$tmp\"; "
        f"trap 'test ! -e \"$tmp\" || find \"$tmp\" -depth -delete' EXIT; "
        f"current_pid=$(cat '{run_dir}/{pidfile}'); test \"$current_pid\" = '{pid}'; "
        f"test -d /proc/{pid}/task/{tid}; "
        f"pid_start=$(awk '{{print $22}}' /proc/{pid}/stat); "
        f"tid_start=$(awk '{{print $22}}' /proc/{tid}/stat); "
        f"boot_id=$(cat /proc/sys/kernel/random/boot_id); "
        f"comm=$(cat /proc/{tid}/comm); "
        f"cpus=$(awk '/^Cpus_allowed_list:/ {{print $2}}' /proc/{tid}/status); "
        f"expected_exe=$(readlink -f '{run_dir}/transport-runtime/"
        f"flle-ch06-four-path/bin/flle-trader'); "
        f"exe_path=$(readlink -f /proc/{pid}/exe); "
        f"test \"$exe_path\" = \"$expected_exe\"; "
        f"exe_sha256=$(sha256sum \"$exe_path\" | awk '{{print $1}}'); "
        f"case \"$exe_sha256\" in ''|*[!0-9a-f]*) exit 1;; esac; "
        f"test \"${{#exe_sha256}}\" -eq 64; "
        f"cmdline=$(tr '\\0' ' ' </proc/{pid}/cmdline); "
        f"test \"$comm\" = flle-order; test \"$cpus\" = 2; "
        f"case \"$cmdline\" in *flle-trader*) ;; *) exit 1;; esac; "
        f"cp /proc/{tid}/status \"$tmp/status\"; "
        f"cp /proc/{tid}/schedstat \"$tmp/schedstat\"; "
        f"printf 'pid=%s\\npid_start_ticks=%s\\ntid=%s\\ntid_start_ticks=%s\\n"
        f"boot_id=%s\\ncomm=%s\\ncpus_allowed_list=%s\\nprocess_cmdline=%s\\n"
        f"exe_path=%s\\nexe_sha256=%s\\n' "
        f"'{pid}' \"$pid_start\" '{tid}' \"$tid_start\" \"$boot_id\" "
        f"\"$comm\" \"$cpus\" \"$cmdline\" \"$exe_path\" \"$exe_sha256\" "
        f">\"$tmp/identity\"; "
        f"test \"$(awk '{{print $22}}' /proc/{pid}/stat)\" = \"$pid_start\"; "
        f"test \"$(awk '{{print $22}}' /proc/{tid}/stat)\" = \"$tid_start\"; "
        f"mv \"$tmp\" \"$final\"; trap - EXIT"
    )
    return remote


def fetch_proc_snapshot(
    key: str, phase: str, remote: str, raw_dir: Path
) -> dict[str, Any]:
    """Copy one already-published remote snapshot and reparse its originals."""

    for name in PROC_FILES:
        scp(f"{remote}/{name}", proc_original_path(raw_dir, key, phase, name))
    return parse_proc_snapshot(raw_dir, key, phase)


def parse_proc_snapshot(
    raw_dir: Path, key: str, phase: str
) -> dict[str, Any]:
    """Rebuild identity and counters strictly from the persisted originals."""

    identity_text = proc_original_path(raw_dir, key, phase, "identity").read_text()
    identity: dict[str, str] = {}
    for line in identity_text.splitlines():
        if "=" not in line:
            raise RuntimeError(f"invalid {key}/{phase} identity line: {line!r}")
        name, value = line.split("=", 1)
        if not name or name in identity:
            raise RuntimeError(f"duplicate {key}/{phase} identity key: {name!r}")
        identity[name] = value
    expected_identity = {
        "pid",
        "pid_start_ticks",
        "tid",
        "tid_start_ticks",
        "boot_id",
        "comm",
        "cpus_allowed_list",
        "process_cmdline",
        "exe_path",
        "exe_sha256",
    }
    if set(identity) != expected_identity:
        raise RuntimeError(f"incomplete {key}/{phase} identity original: {identity}")
    try:
        pid = int(identity["pid"])
        pid_start = int(identity["pid_start_ticks"])
        tid = int(identity["tid"])
        tid_start = int(identity["tid_start_ticks"])
    except ValueError as error:
        raise RuntimeError(f"non-integer {key}/{phase} identity original") from error
    if (
        min(pid, pid_start, tid, tid_start) < 1
        or not identity["boot_id"]
        or identity["comm"] != "flle-order"
        or identity["cpus_allowed_list"] != "2"
        or "flle-trader" not in identity["process_cmdline"]
        or re.fullmatch(
            r"/var/tmp/flle-trading-lab-[A-Za-z0-9._-]+/transport-runtime/"
            r"flle-ch06-four-path/bin/flle-trader",
            identity["exe_path"],
        ) is None
        or re.fullmatch(r"[0-9a-f]{64}", identity["exe_sha256"]) is None
    ):
        raise RuntimeError(f"invalid {key}/{phase} identity values: {identity}")

    status: dict[str, str] = {}
    for line in proc_original_path(raw_dir, key, phase, "status").read_text().splitlines():
        if ":" not in line:
            continue
        name, value = line.split(":", 1)
        status[name] = value.strip()
    try:
        status_pid = int(status["Pid"])
        status_tgid = int(status["Tgid"])
        voluntary = int(status["voluntary_ctxt_switches"])
        nonvoluntary = int(status["nonvoluntary_ctxt_switches"])
    except (KeyError, ValueError) as error:
        raise RuntimeError(f"incomplete {key}/{phase} status original") from error
    if (
        status.get("Name") != "flle-order"
        or status.get("Cpus_allowed_list") != "2"
        or status_pid != tid
        or status_tgid != pid
    ):
        raise RuntimeError(f"status/identity mismatch for {key}/{phase}")

    sched_fields = proc_original_path(
        raw_dir, key, phase, "schedstat"
    ).read_text().split()
    if len(sched_fields) != 3 or any(
        re.fullmatch(r"[0-9]+", value) is None for value in sched_fields
    ):
        raise RuntimeError(f"invalid {key}/{phase} schedstat original")
    runtime_ns, wait_ns, timeslices = (int(value) for value in sched_fields)
    return {
        "identity": {
            "pid": pid,
            "pid_start_ticks": pid_start,
            "tid": tid,
            "tid_start_ticks": tid_start,
            "boot_id": identity["boot_id"],
            "comm": identity["comm"],
            "cpus_allowed_list": identity["cpus_allowed_list"],
            "exe_path": identity["exe_path"],
            "exe_sha256": identity["exe_sha256"],
        },
        "counters": {
            "voluntary": voluntary,
            "nonvoluntary": nonvoluntary,
            "runtime_ns": runtime_ns,
            "runqueue_wait_ns": wait_ns,
            "timeslices": timeslices,
        },
        "originals": {
            name: proc_original_path(raw_dir, key, phase, name).relative_to(
                raw_dir.parent
            ).as_posix()
            for name in PROC_FILES
        },
    }


def seal_execution_program(output: Path) -> dict[str, Any]:
    """Persist the exact probe bytes used by this process before collecting data."""

    payload = EXECUTION_PROGRAM_BYTES
    relative = Path("provenance/measure_kernel_onload_mechanism.py")
    target = output / relative
    target.parent.mkdir()
    target.write_bytes(payload)
    return {
        "path": relative.as_posix(),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
    }


def expected_report_paths() -> set[str]:
    paths = {
        "README.md",
        "summary.json",
        "provenance/measure_kernel_onload_mechanism.py",
    }
    for key in TRANSPORTS:
        paths.add(f"raw/{key.lower()}-order-network.strace")
        for phase in PROC_PHASES:
            for name in PROC_FILES:
                paths.add(
                    proc_original_path(Path("raw"), key, phase, name).as_posix()
                )
    return paths


def verify_exact_report_paths(output: Path) -> int:
    expected_paths = expected_report_paths()
    actual_paths = {
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_file()
    }
    if actual_paths != expected_paths:
        raise RuntimeError(
            "mechanism report file set is not exact: "
            f"missing={sorted(expected_paths - actual_paths)} "
            f"unexpected={sorted(actual_paths - expected_paths)}"
        )
    return len(actual_paths)


def delta(after: dict[str, int], before: dict[str, int]) -> dict[str, int]:
    return {key: after[key] - before[key] for key in before}


def trace_orders(
    key: str, run_dir: str, pid: int, tid: int, port: int,
    samples: int, raw_dir: Path,
) -> dict[str, Any]:
    remote_trace = f"{run_dir}/{key.lower()}-order-network.strace"
    remote_pid = f"{run_dir}/{key.lower()}-strace.pid"
    ssh(
        f"set -eu; test -d /proc/{pid}/task/{tid}; "
        f"rm -f '{remote_trace}' '{remote_pid}'; "
        f"nohup strace -qq -ttt -yy -e trace=network -p {tid} "
        f"-o '{remote_trace}' </dev/null >/dev/null 2>&1 & tracer=$!; "
        f"trap 'kill -INT \"$tracer\" 2>/dev/null || true' EXIT; "
        f"echo \"$tracer\" >'{remote_pid}'; "
        f"for n in $(seq 1 40); do observed=$(awk '/^TracerPid:/ {{print $2}}' "
        f"/proc/{tid}/status); if test \"$observed\" = \"$tracer\"; then "
        f"trap - EXIT; exit 0; fi; "
        f"sleep .05; done; exit 1"
    )
    try:
        rows = submit_batch(port, samples)
    finally:
        ssh(
            f"set -eu; tracer=$(cat '{remote_pid}'); "
            f"case \"$tracer\" in ''|*[!0-9]*) exit 1;; esac; "
            f"test -r /proc/$tracer/cmdline; "
            f"command=$(tr '\\0' ' ' </proc/$tracer/cmdline); "
            f"case \"$command\" in *strace*'-p {tid}'*) ;; *) exit 1;; esac; "
            f"observed=$(awk '/^TracerPid:/ {{print $2}}' /proc/{tid}/status); "
            f"test \"$observed\" = \"$tracer\"; kill -INT \"$tracer\"; "
            f"for n in $(seq 1 40); do "
            f"observed=$(awk '/^TracerPid:/ {{print $2}}' /proc/{tid}/status); "
            f"test \"$observed\" = 0 && exit 0; sleep .05; done; exit 1"
        )
    local_trace = raw_dir / f"{key.lower()}-order-network.strace"
    scp(remote_trace, local_trace)
    text = local_trace.read_text()
    order_lines = [line for line in text.splitlines() if ORDER_PEER in line]
    telemetry_ip, telemetry_port = TELEMETRY_PEER.split(":", 1)
    telemetry_lines = [
        line
        for line in text.splitlines()
        if telemetry_ip in line and telemetry_port in line
    ]
    calls: dict[str, int] = {}
    for line in order_lines:
        match = re.search(r"\b([a-z_]+)\(", line)
        if match:
            calls[match.group(1)] = calls.get(match.group(1), 0) + 1
    return {
        "orders_executed": len(rows["samples"]),
        "order_peer": ORDER_PEER,
        "order_tcp_syscalls": len(order_lines),
        "order_tcp_calls": calls,
        "excluded_telemetry_peer": TELEMETRY_PEER,
        "excluded_telemetry_syscalls": len(telemetry_lines),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--trace-orders", type=int, default=32)
    parser.add_argument("--schedule-orders", type=int, default=1000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.trace_orders < 1 or args.schedule_orders < 1:
        parser.error("sample counts must be positive")
    if re.fullmatch(r"[A-Za-z0-9._-]+", args.run_id) is None:
        parser.error("--run-id must match [A-Za-z0-9._-]+")

    output = args.output
    output.mkdir(parents=True, exist_ok=False)
    raw_dir = output / "raw"
    raw_dir.mkdir()
    sealed_program = seal_execution_program(output)
    run_dir = f"/var/tmp/flle-trading-lab-{args.run_id}"
    result: dict[str, Any] = {
        "schema": MECHANISM_SCHEMA,
        "run_id": args.run_id,
        "scope": "established SoupBinTCP true-order hot path; strace is not a timer",
        "execution_provenance": {"sealed_program": sealed_program},
        "program_sha256": sealed_program["sha256"],
        "artifact_gate": {
            "sha256_entries": len(expected_report_paths()),
            "exact_path_set": True,
        },
        "transports": {},
    }
    for key, config in TRANSPORTS.items():
        port = int(config["port"])
        pid, tid = thread_identity(run_dir, str(config["pidfile"]), port)
        submit_batch(port, 1)  # establish and warm the persistent order session
        trace = trace_orders(
            key, run_dir, pid, tid, port, args.trace_orders, raw_dir
        )
        time.sleep(PROBE_SETTLE_SECONDS)
        pre_remote = capture_proc_snapshot(
            key,
            "pre",
            run_dir,
            str(config["pidfile"]),
            pid,
            tid,
        )
        start_ns = time.monotonic_ns()
        schedule_rows = submit_batch(port, args.schedule_orders)
        wall_ns = time.monotonic_ns() - start_ns
        time.sleep(COUNTER_TAIL_SECONDS)
        post_remote = capture_proc_snapshot(
            key,
            "post",
            run_dir,
            str(config["pidfile"]),
            pid,
            tid,
        )
        before = fetch_proc_snapshot(key, "pre", pre_remote, raw_dir)
        after = fetch_proc_snapshot(key, "post", post_remote, raw_dir)
        if before["identity"] != after["identity"]:
            raise RuntimeError(
                f"{key} order-thread identity changed across the schedule probe"
            )
        counter_delta = delta(after["counters"], before["counters"])
        if any(value < 0 for value in counter_delta.values()):
            raise RuntimeError(f"{key} /proc counters moved backward: {counter_delta}")
        state = management(port, "STATE")
        result["transports"][key] = {
            "pid": pid,
            "order_tid": tid,
            "trace": trace,
            "schedule_probe": {
                "orders_executed": len(schedule_rows["samples"]),
                "wall_ns": wall_ns,
                "wall_scope": "submit_batch management orchestration only",
                "counter_scope": (
                    "persisted remote pre snapshot through persisted remote post "
                    "snapshot; excludes original transfer/parsing; includes "
                    "submit_batch orchestration and post-batch observation tail"
                ),
                "counter_tail_ms": int(COUNTER_TAIL_SECONDS * 1000),
                "order_thread_identity": before["identity"],
                "proc_originals": {
                    "pre": before["originals"],
                    "post": after["originals"],
                },
                "order_thread_delta": counter_delta,
            },
            "transport_retries": int(state["stats"]["transport_retries"]),
        }

    kernel_calls = result["transports"]["SOCKET"]["trace"][
        "order_tcp_syscalls"
    ]
    onload_calls = result["transports"]["OPENONLOAD"]["trace"][
        "order_tcp_syscalls"
    ]
    if kernel_calls <= 0 or onload_calls != 0:
        raise RuntimeError(
            f"unexpected hot-path syscall result: Kernel={kernel_calls}, "
            f"Onload={onload_calls}"
        )
    (output / "summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    )
    lines = [
        "# Kernel / OpenOnload true-order mechanism probe",
        "",
        "`strace` 只作路径收据，不读取被跟踪订单的延迟。",
        "",
        (
            f"第一表来自 {args.trace_orders} 笔 `strace` 跟踪真单；"
            f"第二表来自独立的 {args.schedule_orders} 笔无跟踪真单"
            f"及随后 {int(COUNTER_TAIL_SECONDS * 1000)} ms 观察窗。"
        ),
        "第二表的线程身份、CPU 绑定与计数差全部从已落盘的 "
        "`status` / `schedstat` pre/post 原文复算。",
        "计数窗口从远端 pre 原件到远端 post 原件；原件传输与解析在 post 之后，"
        "不进入这段差值。",
        "探针本身的执行字节保存在 `provenance/`；其 SHA 同时写入 `summary.json`。",
        "`schedule_probe.wall_ns` 包含管理口提交、查询与短连接编排，不作订单延迟。",
        "",
        f"| Path | traced orders ({args.trace_orders}) | order TCP syscalls |",
        "| --- | ---: | ---: |",
    ]
    for key in TRANSPORTS:
        row = result["transports"][key]
        lines.append(
            f"| {key} | {row['trace']['orders_executed']} | "
            f"{row['trace']['order_tcp_syscalls']} |"
        )
    lines.extend(
        [
            "",
            (
                f"| Path | untraced orders ({args.schedule_orders}) | "
                "voluntary switches | CPU runtime | runqueue wait |"
            ),
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for key in TRANSPORTS:
        row = result["transports"][key]
        lines.append(
            f"| {key} | {row['schedule_probe']['orders_executed']} | "
            f"{row['schedule_probe']['order_thread_delta']['voluntary']} | "
            f"{row['schedule_probe']['order_thread_delta']['runtime_ns']} ns | "
            f"{row['schedule_probe']['order_thread_delta']['runqueue_wait_ns']} ns |"
        )
    (output / "README.md").write_text("\n".join(lines) + "\n")
    verify_exact_report_paths(output)
    manifest = []
    for target in sorted(path for path in output.rglob("*") if path.is_file()):
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        manifest.append(f"{digest}  {target.relative_to(output)}")
    (output / "SHA256SUMS").write_text("\n".join(manifest) + "\n")
    print(
        f"mechanism Kernel_syscalls={kernel_calls} "
        f"Onload_syscalls={onload_calls} "
        "proc_originals=12 "
        f"evidence={output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
