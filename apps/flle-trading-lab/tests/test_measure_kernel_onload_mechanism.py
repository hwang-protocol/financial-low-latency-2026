from contextlib import redirect_stderr, redirect_stdout
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "measure_kernel_onload_mechanism.py"
)
SPEC = importlib.util.spec_from_file_location(
    "measure_kernel_onload_mechanism", SCRIPT
)
assert SPEC is not None and SPEC.loader is not None
MECHANISM = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MECHANISM)


class KernelOnloadMechanismTest(unittest.TestCase):
    @staticmethod
    def write_snapshot(
        raw_dir: Path,
        key: str,
        phase: str,
        *,
        voluntary: int,
        nonvoluntary: int,
        runtime_ns: int,
        wait_ns: int,
        timeslices: int,
        cpus: str = "2",
    ) -> None:
        identity = (
            "pid=100\n"
            "pid_start_ticks=200\n"
            "tid=101\n"
            "tid_start_ticks=201\n"
            "boot_id=boot-unit\n"
            "comm=flle-order\n"
            f"cpus_allowed_list={cpus}\n"
            "process_cmdline=/opt/flle-trader --unit\n"
            "exe_path=/var/tmp/flle-trading-lab-UNIT/transport-runtime/"
            "flle-ch05-four-path/bin/flle-trader\n"
            f"exe_sha256={'a' * 64}\n"
        )
        status = (
            "Name:\tflle-order\n"
            "Tgid:\t100\n"
            "Pid:\t101\n"
            f"Cpus_allowed_list:\t{cpus}\n"
            f"voluntary_ctxt_switches:\t{voluntary}\n"
            f"nonvoluntary_ctxt_switches:\t{nonvoluntary}\n"
        )
        schedstat = f"{runtime_ns} {wait_ns} {timeslices}\n"
        for name, text in (
            ("identity", identity),
            ("status", status),
            ("schedstat", schedstat),
        ):
            MECHANISM.proc_original_path(raw_dir, key, phase, name).write_text(
                text, encoding="utf-8"
            )

    def test_schema_is_bumped_for_proc_original_contract(self) -> None:
        self.assertEqual(
            MECHANISM.MECHANISM_SCHEMA,
            "flle.ch06-kernel-onload-mechanism.v4",
        )

    @staticmethod
    def sample(client_order_id: int, queue_ns: int = 7, rtt_ns: int = 11) -> dict:
        return {
            "client_order_id": client_order_id,
            "result": "E",
            "queue_to_send_ns": queue_ns,
            "order_rtt_ns": rtt_ns,
            "submit_to_final_ns": queue_ns + rtt_ns,
        }

    def test_submit_batch_binds_generation_ids_results_and_common_clock(self) -> None:
        responses = [
            {"ok": True, "measurement_generation": 7},
            {"ok": True, "client_order_id": 101},
            {"measurement_latency": {"generation": 7, "ready_samples": 1}},
            {"ok": True, "client_order_id": 102},
            {"measurement_latency": {"generation": 7, "ready_samples": 2}},
            {
                "measurement_generation": 7,
                "clock": "CLOCK_MONOTONIC",
                "samples": [self.sample(101), self.sample(102)],
            },
        ]
        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(
            MECHANISM, "management", side_effect=responses
        ):
            receipt = Path(temporary) / "batch.json"
            batch = MECHANISM.submit_batch(48122, 2, receipt)
            persisted = json.loads(receipt.read_text(encoding="utf-8"))
        self.assertEqual(batch, persisted)
        self.assertEqual(batch["measurement_generation"], 7)
        self.assertEqual(batch["submitted_client_order_ids"], [101, 102])
        self.assertEqual(
            batch["validation"]["submission_to_sample_order_and_set"], "EXACT"
        )
        identity = MECHANISM.batch_identity_summary(batch)
        self.assertEqual(identity["orders"], 2)
        self.assertEqual(identity["result"], "ALL_EXECUTED")

    def test_submit_batch_rejects_generation_change_while_waiting(self) -> None:
        responses = [
            {"ok": True, "measurement_generation": 7},
            {"ok": True, "client_order_id": 101},
            {"measurement_latency": {"generation": 8, "ready_samples": 1}},
        ]
        with mock.patch.object(MECHANISM, "management", side_effect=responses):
            with self.assertRaisesRegex(RuntimeError, "generation changed"):
                MECHANISM.submit_batch(48122, 1)

    def test_submit_batch_rejects_returned_id_order_mismatch(self) -> None:
        responses = [
            {"ok": True, "measurement_generation": 7},
            {"ok": True, "client_order_id": 101},
            {"measurement_latency": {"generation": 7, "ready_samples": 1}},
            {"ok": True, "client_order_id": 102},
            {"measurement_latency": {"generation": 7, "ready_samples": 2}},
            {
                "measurement_generation": 7,
                "clock": "CLOCK_MONOTONIC",
                "samples": [self.sample(102), self.sample(101)],
            },
        ]
        with mock.patch.object(MECHANISM, "management", side_effect=responses):
            with self.assertRaisesRegex(RuntimeError, "ID order mismatch"):
                MECHANISM.submit_batch(48122, 2)

    def test_submit_batch_rejects_returned_id_set_mismatch(self) -> None:
        responses = [
            {"ok": True, "measurement_generation": 7},
            {"ok": True, "client_order_id": 101},
            {"measurement_latency": {"generation": 7, "ready_samples": 1}},
            {
                "measurement_generation": 7,
                "clock": "CLOCK_MONOTONIC",
                "samples": [self.sample(999)],
            },
        ]
        with mock.patch.object(MECHANISM, "management", side_effect=responses):
            with self.assertRaisesRegex(RuntimeError, "ID set mismatch"):
                MECHANISM.submit_batch(48122, 1)

    def test_submit_batch_rejects_raw_generation_or_nonexecuted_result(self) -> None:
        generation_mismatch = [
            {"ok": True, "measurement_generation": 7},
            {"ok": True, "client_order_id": 101},
            {"measurement_latency": {"generation": 7, "ready_samples": 1}},
            {
                "measurement_generation": 8,
                "clock": "CLOCK_MONOTONIC",
                "samples": [self.sample(101)],
            },
        ]
        with mock.patch.object(
            MECHANISM, "management", side_effect=generation_mismatch
        ):
            with self.assertRaisesRegex(RuntimeError, "generation mismatch"):
                MECHANISM.submit_batch(48122, 1)

        rejected = self.sample(101)
        rejected["result"] = "R"
        nonexecuted = [
            {"ok": True, "measurement_generation": 7},
            {"ok": True, "client_order_id": 101},
            {"measurement_latency": {"generation": 7, "ready_samples": 1}},
            {
                "measurement_generation": 7,
                "clock": "CLOCK_MONOTONIC",
                "samples": [rejected],
            },
        ]
        with mock.patch.object(MECHANISM, "management", side_effect=nonexecuted):
            with self.assertRaisesRegex(RuntimeError, "not Executed"):
                MECHANISM.submit_batch(48122, 1)

    def test_submit_batch_rejects_broken_common_clock_identity(self) -> None:
        broken = self.sample(101)
        broken["submit_to_final_ns"] += 1
        responses = [
            {"ok": True, "measurement_generation": 7},
            {"ok": True, "client_order_id": 101},
            {"measurement_latency": {"generation": 7, "ready_samples": 1}},
            {
                "measurement_generation": 7,
                "clock": "CLOCK_MONOTONIC",
                "samples": [broken],
            },
        ]
        with mock.patch.object(MECHANISM, "management", side_effect=responses):
            with self.assertRaisesRegex(RuntimeError, "common-clock identity"):
                MECHANISM.submit_batch(48122, 1)

    def test_run_id_shell_metacharacters_are_rejected_before_remote_use(self) -> None:
        argv = [
            str(SCRIPT),
            "--run-id",
            "UNIT;touch-injected",
            "--output",
            "/never-created",
        ]
        with mock.patch.object(sys, "argv", argv), redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as raised:
                MECHANISM.main()
        self.assertEqual(raised.exception.code, 2)

    def test_proc_snapshot_is_parsed_only_from_persisted_originals(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            raw = Path(temporary) / "raw"
            raw.mkdir()
            self.write_snapshot(
                raw,
                "SOCKET",
                "pre",
                voluntary=10,
                nonvoluntary=2,
                runtime_ns=1000,
                wait_ns=30,
                timeslices=7,
            )
            parsed = MECHANISM.parse_proc_snapshot(raw, "SOCKET", "pre")
            self.assertEqual(parsed["identity"]["pid"], 100)
            self.assertEqual(parsed["identity"]["tid"], 101)
            self.assertEqual(parsed["identity"]["cpus_allowed_list"], "2")
            self.assertEqual(parsed["counters"]["voluntary"], 10)
            self.assertEqual(parsed["counters"]["runtime_ns"], 1000)
            self.assertEqual(
                set(parsed["originals"]), {"identity", "status", "schedstat"}
            )

    def test_proc_snapshot_rejects_cpu_binding_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            raw = Path(temporary) / "raw"
            raw.mkdir()
            self.write_snapshot(
                raw,
                "OPENONLOAD",
                "post",
                voluntary=10,
                nonvoluntary=2,
                runtime_ns=1000,
                wait_ns=30,
                timeslices=7,
                cpus="2-3",
            )
            with self.assertRaisesRegex(RuntimeError, "identity values"):
                MECHANISM.parse_proc_snapshot(raw, "OPENONLOAD", "post")

    def test_proc_snapshot_rejects_noncanonical_or_unhashed_executable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            raw = Path(temporary) / "raw"
            raw.mkdir()
            self.write_snapshot(
                raw,
                "SOCKET",
                "pre",
                voluntary=10,
                nonvoluntary=2,
                runtime_ns=1000,
                wait_ns=30,
                timeslices=7,
            )
            identity = MECHANISM.proc_original_path(
                raw, "SOCKET", "pre", "identity"
            )
            identity.write_text(
                identity.read_text().replace(f"exe_sha256={'a' * 64}", "exe_sha256=bad"),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(RuntimeError, "identity values"):
                MECHANISM.parse_proc_snapshot(raw, "SOCKET", "pre")

    def test_report_manifest_requires_the_exact_twenty_one_evidence_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            expected = MECHANISM.expected_report_paths()
            self.assertEqual(len(expected), 21)
            for relative in expected:
                target = output / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("unit\n", encoding="utf-8")
            self.assertEqual(MECHANISM.verify_exact_report_paths(output), 21)
            (output / "raw/unexpected.txt").write_text("extra\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "file set is not exact"):
                MECHANISM.verify_exact_report_paths(output)

    def test_strace_cleanup_is_attempted_when_order_submission_fails(self) -> None:
        commands = []

        def record_ssh(command):
            commands.append(command)
            return ""

        with (
            mock.patch.object(MECHANISM, "ssh", side_effect=record_ssh),
            mock.patch.object(
                MECHANISM,
                "submit_batch",
                side_effect=RuntimeError("unit submit failure"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "unit submit failure"):
                MECHANISM.trace_orders(
                    "SOCKET",
                    "/var/tmp/flle-trading-lab-UNIT",
                    100,
                    101,
                    48122,
                    2,
                    Path("/unused"),
                )
        self.assertEqual(len(commands), 2)
        self.assertIn('test "$observed" = "$tracer"', commands[0])
        self.assertIn('test "$observed" = "$tracer"', commands[1])
        self.assertIn('kill -INT "$tracer"', commands[1])
        self.assertIn('test ! -e /proc/$tracer', commands[1])
        self.assertIn("sync -f", commands[1])

    def test_main_rebuilds_deltas_and_sha_from_twelve_proc_originals(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "mechanism"

            def capture(key, phase, run_dir, pidfile, pid, tid):
                del run_dir, pidfile, pid, tid
                return f"/remote/{key.lower()}-{phase}"

            def fetch(key, phase, remote, raw_dir):
                self.assertEqual(remote, f"/remote/{key.lower()}-{phase}")
                if phase == "pre":
                    values = (10, 2, 1000, 30, 7)
                else:
                    values = (14, 3, 5000, 90, 12)
                self.write_snapshot(
                    raw_dir,
                    key,
                    phase,
                    voluntary=values[0],
                    nonvoluntary=values[1],
                    runtime_ns=values[2],
                    wait_ns=values[3],
                    timeslices=values[4],
                )
                return MECHANISM.parse_proc_snapshot(raw_dir, key, phase)

            def trace(key, run_dir, pid, tid, port, samples, raw_dir):
                del run_dir, pid, tid, port
                (raw_dir / f"{key.lower()}-order-network.strace").write_text(
                    "native trace\n", encoding="utf-8"
                )
                traced = {
                    "measurement_generation": 2,
                    "clock": "CLOCK_MONOTONIC",
                    "submitted_client_order_ids": list(range(100, 100 + samples)),
                    "samples": [
                        self.sample(client_order_id)
                        for client_order_id in range(100, 100 + samples)
                    ],
                    "validation": {
                        "count": samples,
                        "unique_submission_ids": samples,
                        "submission_to_sample_order_and_set": "EXACT",
                        "results": "ALL_EXECUTED",
                        "common_clock_identity": "ALL_SAMPLES_VERIFIED",
                    },
                }
                (raw_dir / f"{key.lower()}-traced-orders.batch.json").write_text(
                    json.dumps(traced) + "\n", encoding="utf-8"
                )
                return {
                    "orders_executed": samples,
                    "batch_identity": MECHANISM.batch_identity_summary(traced),
                    "order_peer": MECHANISM.ORDER_PEER,
                    "order_tcp_syscalls": 6 if key == "SOCKET" else 0,
                    "order_tcp_calls": {"sendto": 1} if key == "SOCKET" else {},
                    "excluded_telemetry_peer": MECHANISM.TELEMETRY_PEER,
                    "excluded_telemetry_syscalls": 0,
                }

            generation = 10

            def submit(port, samples, receipt_path=None):
                nonlocal generation
                generation += 1
                first = port * 1000 + generation * 10
                ids = list(range(first, first + samples))
                batch = {
                    "measurement_generation": generation,
                    "clock": "CLOCK_MONOTONIC",
                    "submitted_client_order_ids": ids,
                    "samples": [self.sample(client_order_id) for client_order_id in ids],
                    "validation": {
                        "count": samples,
                        "unique_submission_ids": samples,
                        "submission_to_sample_order_and_set": "EXACT",
                        "results": "ALL_EXECUTED",
                        "common_clock_identity": "ALL_SAMPLES_VERIFIED",
                    },
                }
                if receipt_path is not None:
                    receipt_path.write_text(json.dumps(batch) + "\n", encoding="utf-8")
                return batch

            argv = [
                str(SCRIPT),
                "--run-id",
                "UNIT",
                "--trace-orders",
                "2",
                "--schedule-orders",
                "3",
                "--output",
                str(output),
            ]
            with (
                mock.patch.object(sys, "argv", argv),
                mock.patch.object(
                    MECHANISM, "thread_identity", return_value=(100, 101)
                ),
                mock.patch.object(MECHANISM, "capture_proc_snapshot", side_effect=capture),
                mock.patch.object(MECHANISM, "fetch_proc_snapshot", side_effect=fetch),
                mock.patch.object(MECHANISM, "trace_orders", side_effect=trace),
                mock.patch.object(MECHANISM, "submit_batch", side_effect=submit),
                mock.patch.object(MECHANISM, "management", return_value={
                    "stats": {"transport_retries": 0}
                }),
                mock.patch.object(MECHANISM.time, "sleep"),
            ):
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(MECHANISM.main(), 0)

            summary = json.loads((output / "summary.json").read_text())
            self.assertEqual(summary["schema"], MECHANISM.MECHANISM_SCHEMA)
            sealed = summary["execution_provenance"]["sealed_program"]
            self.assertEqual(
                sealed["path"],
                "provenance/measure_kernel_onload_mechanism.py",
            )
            sealed_payload = (output / sealed["path"]).read_bytes()
            self.assertEqual(sealed_payload, SCRIPT.read_bytes())
            self.assertEqual(
                sealed["sha256"], hashlib.sha256(sealed_payload).hexdigest()
            )
            self.assertEqual(sealed["bytes"], len(sealed_payload))
            self.assertEqual(summary["program_sha256"], sealed["sha256"])
            for key in MECHANISM.TRANSPORTS:
                probe = summary["transports"][key]["schedule_probe"]
                self.assertEqual(probe["order_thread_delta"]["voluntary"], 4)
                self.assertEqual(probe["order_thread_delta"]["runtime_ns"], 4000)
                self.assertEqual(probe["order_thread_delta"]["runqueue_wait_ns"], 60)
                self.assertEqual(
                    set(probe["proc_originals"]), {"pre", "post"}
                )

            manifest = (output / "SHA256SUMS").read_text().splitlines()
            self.assertEqual(len(manifest), 21)
            self.assertEqual(summary["artifact_gate"]["sha256_entries"], 21)
            proc_lines = [line for line in manifest if "-order-thread-" in line]
            self.assertEqual(len(proc_lines), 12)
            for line in manifest:
                digest, relative = line.split("  ", 1)
                self.assertEqual(
                    hashlib.sha256((output / relative).read_bytes()).hexdigest(),
                    digest,
                )
            readme = (output / "README.md").read_text()
            self.assertIn("独立的 3 笔无跟踪真单", readme)
            self.assertIn("status` / `schedstat` pre/post 原文复算", readme)
            self.assertIn("探针本身的执行字节保存在 `provenance/`", readme)


if __name__ == "__main__":
    unittest.main()
