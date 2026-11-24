import hashlib
import importlib.util
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "measure_four_transports.py"
SPEC = importlib.util.spec_from_file_location("measure_four_transports", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MEASURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MEASURE)


def leased_paused(state: dict) -> dict:
    return {
        **state,
        "replay_status": "PAUSED",
        "replay_pause_lease_ms": MEASURE.FORMAL_PAUSE_LEASE_MS,
        "replay_pause_lease_remaining_ms": MEASURE.FORMAL_PAUSE_LEASE_MS - 1,
    }


class FourTransportStatisticsTest(unittest.TestCase):
    def test_formal_receipt_contract_uses_v13_schema(self) -> None:
        self.assertEqual(
            MEASURE.SOURCE_SCHEMA, "flle.ch06-four-order-paths.v13"
        )
        self.assertEqual(
            MEASURE.NATIVE_RECEIPT_FILES["DPDK"],
            {
                "data-plane-input.receipt",
                "exchange-process.txt",
                "exchange-ss-established.txt",
                "fstack.log",
                "gate-start.receipt",
                "lease-start.receipt",
                "lease-status.txt",
                "owner.txt",
                "process.txt",
                "state.json",
            },
        )

    def test_pause_gate_proves_book_driving_fields_stable(self) -> None:
        playing = {
            "replay_status": "PLAYING", "session": "S1", "replay_loop": 3,
            "source_timestamp_ns": 10, "replay_messages": 20,
            "market_sequence": 21,
        }
        paused = leased_paused(playing)
        with (
            mock.patch.object(
                MEASURE,
                "management_command",
                side_effect=[playing, {"ok": True}, paused, paused],
            ) as command,
            mock.patch.object(MEASURE.time, "sleep"),
        ):
            gate = MEASURE.pause_exchange_at_fixed_book("10.1.1.1", 48120)
        self.assertEqual(gate["paused_stable"], paused)
        self.assertEqual(
            gate["stable_fields"],
            [
                "session", "replay_loop", "source_timestamp_ns",
                "replay_messages", "market_sequence",
            ],
        )
        self.assertEqual(
            command.call_args_list[1].args[2],
            f"REPLAY|PAUSE_LEASE_MS|{MEASURE.FORMAL_PAUSE_LEASE_MS}",
        )
        self.assertEqual(gate["pause_lease_ms"], MEASURE.FORMAL_PAUSE_LEASE_MS)
        self.assertEqual(gate["lease_renewals"], [])

    def test_pause_gate_compensates_if_stability_proof_fails(self) -> None:
        playing = {
            "replay_status": "PLAYING", "session": "S1", "replay_loop": 3,
            "source_timestamp_ns": 10, "replay_messages": 20,
            "market_sequence": 21,
        }
        paused = leased_paused(playing)
        changed = {**paused, "replay_messages": 21}
        with (
            mock.patch.object(
                MEASURE,
                "management_command",
                side_effect=[
                    playing, {"ok": True}, paused, changed,
                    paused, {"ok": True}, playing,
                ],
            ) as command,
            mock.patch.object(MEASURE.time, "sleep"),
        ):
            with self.assertRaisesRegex(RuntimeError, "was not stable"):
                MEASURE.pause_exchange_at_fixed_book("10.1.1.1", 48120)
        self.assertIn(
            "REPLAY|RESUME", [call.args[2] for call in command.call_args_list]
        )

    def test_pause_gate_reconciles_a_lost_pause_response(self) -> None:
        playing = {
            "replay_status": "PLAYING", "session": "S1", "replay_loop": 3,
            "source_timestamp_ns": 10, "replay_messages": 20,
            "market_sequence": 21,
        }
        paused = leased_paused(playing)
        with (
            mock.patch.object(
                MEASURE,
                "management_command",
                side_effect=[
                    playing, TimeoutError("response lost"), paused, paused,
                ],
            ),
            mock.patch.object(MEASURE.time, "sleep"),
        ):
            gate = MEASURE.pause_exchange_at_fixed_book("10.1.1.1", 48120)
        self.assertEqual(gate["paused_stable"], paused)

    def test_pause_lease_renewal_rejects_a_moved_book(self) -> None:
        baseline = leased_paused({
            "session": "S1", "replay_loop": 3, "source_timestamp_ns": 10,
            "replay_messages": 20, "market_sequence": 21,
        })
        moved = {**baseline, "source_timestamp_ns": 11}
        contract = {"paused_stable": baseline, "lease_renewals": []}
        with mock.patch.object(
            MEASURE,
            "management_command",
            side_effect=[{"ok": True}, moved],
        ):
            with self.assertRaisesRegex(RuntimeError, "fixed book moved"):
                MEASURE.renew_exchange_pause_lease(
                    "10.1.1.1", 48120, contract, "before-r1-p1-socket"
                )
        self.assertEqual(contract["lease_renewals"], [])

    def test_pause_lease_renewal_records_a_stable_book(self) -> None:
        baseline = leased_paused({
            "session": "S1", "replay_loop": 3, "source_timestamp_ns": 10,
            "replay_messages": 20, "market_sequence": 21,
        })
        contract = {"paused_stable": baseline, "lease_renewals": []}
        renewed = {
            **baseline,
            "replay_pause_lease_remaining_ms":
                MEASURE.FORMAL_PAUSE_LEASE_MS - 2,
        }
        with mock.patch.object(
            MEASURE,
            "management_command",
            side_effect=[{"ok": True}, renewed],
        ) as command:
            receipt = MEASURE.renew_exchange_pause_lease(
                "10.1.1.1", 48120, contract, "before-r1-p1-socket"
            )
        self.assertEqual(contract["lease_renewals"], [receipt])
        self.assertEqual(receipt["checkpoint"], "before-r1-p1-socket")
        self.assertEqual(
            command.call_args_list[0].args[2],
            f"REPLAY|PAUSE_LEASE_MS|{MEASURE.FORMAL_PAUSE_LEASE_MS}",
        )

    def test_formal_pause_renewal_plan_covers_all_cells_and_mode_switches(self) -> None:
        checkpoints = MEASURE.expected_pause_renewal_checkpoints()
        self.assertEqual(len(checkpoints), 26)
        self.assertEqual(checkpoints[0], "before-initial-sfc")
        self.assertEqual(checkpoints[-1], "before-final-ledger")
        self.assertEqual(
            sum(item.startswith("before-r") for item in checkpoints), 16
        )
        self.assertEqual(
            sum(item.startswith("after-switch-r") for item in checkpoints), 8
        )
        self.assertEqual(len(checkpoints), len(set(checkpoints)))

    def test_resume_reconciles_a_lost_resume_response(self) -> None:
        paused = {"replay_status": "PAUSED", "session": "S1"}
        playing = {"replay_status": "PLAYING", "session": "S1"}
        with (
            mock.patch.object(
                MEASURE,
                "management_command",
                side_effect=[paused, TimeoutError("response lost"), playing],
            ),
            mock.patch.object(MEASURE.time, "sleep"),
        ):
            self.assertEqual(
                MEASURE.reconcile_exchange_playing("10.1.1.1", 48120, "S1"),
                playing,
            )

    def test_hugepage_reader_uses_read_only_root_ssh(self) -> None:
        completed = MEASURE.subprocess.CompletedProcess(
            args=[], returncode=0, stdout="128\n", stderr=""
        )
        with mock.patch.object(MEASURE.subprocess, "run", return_value=completed) as run:
            self.assertEqual(MEASURE.read_hugepages_2mb("10.1.1.2"), 128)
        self.assertEqual(
            run.call_args.args[0],
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "StrictHostKeyChecking=yes",
                "root@10.1.1.2",
                "cat",
                MEASURE.HUGEPAGES_2MB_PATH,
            ],
        )
        self.assertFalse(run.call_args.kwargs["check"])

    def test_hugepage_contract_accepts_sfc_and_dpdk_profiles(self) -> None:
        with mock.patch.object(
            MEASURE, "read_hugepages_2mb", side_effect=[128, 256]
        ):
            self.assertEqual(MEASURE.require_hugepages_2mb("10.1.1.2", "SOCKET"), 128)
            self.assertEqual(MEASURE.require_hugepages_2mb("10.1.1.2", "DPDK"), 256)

    def test_hugepage_contract_rejects_wrong_active_pool(self) -> None:
        with mock.patch.object(MEASURE, "read_hugepages_2mb", return_value=128):
            with self.assertRaisesRegex(
                RuntimeError,
                r"DPDK 2 MiB hugepage contract failed on root@10\.1\.1\.2: "
                r"expected=256 observed=128",
            ):
                MEASURE.require_hugepages_2mb("10.1.1.2", "DPDK")

    def test_observer_absence_gate_records_both_exact_endpoints(self) -> None:
        with mock.patch.object(
            MEASURE.socket,
            "create_connection",
            side_effect=[ConnectionRefusedError(), TimeoutError()],
        ) as connect:
            self.assertEqual(
                MEASURE.require_observer_endpoints_absent(),
                [
                    {"host": "10.1.1.101", "port": 8088, "state": "ABSENT"},
                    {"host": "10.1.1.111", "port": 48606, "state": "ABSENT"},
                ],
            )
        self.assertEqual(
            connect.call_args_list,
            [
                mock.call(("10.1.1.101", 8088), timeout=1.0),
                mock.call(("10.1.1.111", 48606), timeout=1.0),
            ],
        )

    def test_observer_absence_gate_rejects_either_connectable_port(self) -> None:
        endpoints = (("10.1.1.101", 8088), ("10.1.1.111", 48606))
        for index, (host, port) in enumerate(endpoints):
            with self.subTest(host=host, port=port):
                connection = mock.Mock()
                outcomes = [ConnectionRefusedError(), ConnectionRefusedError()]
                outcomes[index] = connection
                with mock.patch.object(
                    MEASURE.socket,
                    "create_connection",
                    side_effect=outcomes,
                ) as connect:
                    with self.assertRaisesRegex(
                        RuntimeError,
                        rf"connectable: {re.escape(host)}:{port}",
                    ):
                        MEASURE.require_observer_endpoints_absent()
                self.assertEqual(connect.call_count, 2)
                connection.close.assert_called_once_with()

    def test_observer_absence_gate_precedes_any_formal_state_change(self) -> None:
        source = Path(MEASURE.__file__).read_text(encoding="utf-8")
        body = source.split("def main() -> int:", 1)[1]
        absence = body.index(
            "observer_absence = require_observer_endpoints_absent()"
        )
        pause = body.index("pause_contract = pause_exchange_at_fixed_book(")
        switch = body.index("switch_data_plane_mode(control_script, args.run_id")
        self.assertLess(absence, pause)
        self.assertLess(absence, switch)
        self.assertIn(
            '"observer_absence_before_measurement": observer_absence', body
        )

    def test_nearest_rank_summary_includes_p95(self) -> None:
        values = list(range(1, 1001))
        summary = MEASURE.summarize(values)
        self.assertEqual(summary["p50_ns"], 500)
        self.assertEqual(summary["p95_ns"], 950)
        self.assertEqual(summary["p99_ns"], 990)

    def test_single_flight_returns_the_submitted_client_order_id(self) -> None:
        with (
            mock.patch.object(
                MEASURE,
                "management_command",
                side_effect=[
                    {"ok": True, "client_order_id": 12345},
                    {"measurement_generation": 7, "ready_samples": 1},
                ],
            ),
        ):
            client_order_id = MEASURE.submit_single_flight(
                "10.1.1.2",
                48122,
                "MEASUREMENT_ORDER",
                "BUY",
                "measurement_latency",
                1,
                7,
            )
        self.assertEqual(client_order_id, 12345)

    def test_measurement_single_flight_waits_for_post_work_ready_marker(self) -> None:
        replies = iter(
            [
                {"ok": True, "client_order_id": 12345},
                {"measurement_generation": 7, "ready_samples": 0},
                {"measurement_generation": 7, "ready_samples": 1},
            ]
        )

        with (
            mock.patch.object(
                MEASURE,
                "management_command",
                side_effect=lambda *_args: next(replies),
            ),
            mock.patch.object(MEASURE.time, "sleep"),
        ):
            MEASURE.submit_single_flight(
                "10.1.1.2", 48122, "MEASUREMENT_ORDER", "BUY",
                "measurement_latency", 1, 7,
            )

    def test_round_summary_uses_median_of_round_percentiles(self) -> None:
        rounds = [
            {"latency": {"p50_ns": 10, "p95_ns": 30, "p99_ns": 50,
                         "mean_ns": 20, "max_ns": 90}},
            {"latency": {"p50_ns": 20, "p95_ns": 40, "p99_ns": 60,
                         "mean_ns": 30, "max_ns": 100}},
            {"latency": {"p50_ns": 30, "p95_ns": 50, "p99_ns": 70,
                         "mean_ns": 40, "max_ns": 110}},
        ]
        summary = MEASURE.median_round_summary(rounds, "latency")
        self.assertEqual(summary["p50_ns"], 20)
        self.assertEqual(summary["p95_ns"], 40)
        self.assertEqual(summary["p99_ns"], 60)
        self.assertEqual(summary["max_ns"], 110)

    def test_four_round_summary_rounds_half_nanosecond_up(self) -> None:
        rounds = [
            {
                "latency": {
                    "p50_ns": value,
                    "p95_ns": value,
                    "p99_ns": value,
                    "mean_ns": value,
                    "max_ns": value,
                }
            }
            for value in (10, 20, 21, 40)
        ]
        summary = MEASURE.median_round_summary(rounds, "latency")
        self.assertEqual(summary["p50_ns"], 21)
        self.assertEqual(summary["p95_ns"], 21)
        self.assertEqual(summary["p99_ns"], 21)
        self.assertEqual(summary["mean_ns"], 21)

    def test_sample_identity_success_reports_counts_and_ranges(self) -> None:
        rounds = [
            {
                "transport": "DPDK",
                "round": 2,
                "measurement_submission_ids": [402, 401],
                "raw_samples": [
                    {"client_order_id": 402},
                    {"client_order_id": 401},
                ],
            },
            {
                "transport": "SOCKET",
                "round": 1,
                "measurement_submission_ids": [102, 101],
                "raw_samples": [
                    {"client_order_id": 102},
                    {"client_order_id": 101},
                ],
            },
            {
                "transport": "DPDK",
                "round": 1,
                "measurement_submission_ids": [302, 301],
                "raw_samples": [
                    {"client_order_id": 302},
                    {"client_order_id": 301},
                ],
            },
        ]

        identity = MEASURE.validate_and_summarize_sample_identity(rounds)

        self.assertEqual(identity["total"], 6)
        self.assertEqual(identity["unique"], 6)
        by_transport = {
            item["transport"]: item for item in identity["per_transport"]
        }
        self.assertEqual(by_transport["SOCKET"]["total"], 2)
        self.assertEqual(by_transport["SOCKET"]["unique"], 2)
        self.assertEqual(by_transport["SOCKET"]["min_client_order_id"], 101)
        self.assertEqual(by_transport["SOCKET"]["max_client_order_id"], 102)
        self.assertEqual(by_transport["DPDK"]["total"], 4)
        self.assertEqual(by_transport["DPDK"]["unique"], 4)
        self.assertEqual(
            [
                (item["transport"], item["round"], item["min_client_order_id"],
                 item["max_client_order_id"])
                for item in identity["per_round_ranges"]
                if item["transport"] in {"SOCKET", "DPDK"}
            ],
            [
                ("SOCKET", 1, 101, 102),
                ("DPDK", 1, 301, 302),
                ("DPDK", 2, 401, 402),
            ],
        )

    def test_sample_identity_rejects_duplicate_with_both_locations(self) -> None:
        rounds = [
            {
                "transport": "SOCKET",
                "round": 1,
                "measurement_submission_ids": [42],
                "raw_samples": [{"client_order_id": 42}],
            },
            {
                "transport": "TCPDIRECT",
                "round": 3,
                "measurement_submission_ids": [99, 42],
                "raw_samples": [
                    {"client_order_id": 99},
                    {"client_order_id": 42},
                ],
            },
        ]

        with self.assertRaisesRegex(
            RuntimeError,
            r"duplicate client_order_id=42 across raw files: "
            r"current=tcpdirect-r3\.json phase=measurement sample=2; "
            r"first=socket-r1\.json phase=measurement sample=1",
        ):
            MEASURE.validate_and_summarize_sample_identity(rounds)

    def test_sample_identity_rejects_duplicate_within_raw_file(self) -> None:
        rounds = [
            {
                "transport": "OPENONLOAD",
                "round": 4,
                "measurement_submission_ids": [77, 77],
                "raw_samples": [
                    {"client_order_id": 77},
                    {"client_order_id": 77},
                ],
            }
        ]

        with self.assertRaisesRegex(
            RuntimeError,
            r"duplicate client_order_id=77 within raw file: "
            r"current=openonload-r4\.json phase=measurement sample=2; "
            r"first=openonload-r4\.json phase=measurement sample=1",
        ):
            MEASURE.validate_and_summarize_sample_identity(rounds)

    def test_submission_identity_rejects_warmup_measurement_collision(self) -> None:
        rounds = [
            {
                "transport": "SOCKET",
                "round": 1,
                "warmup_orders": 1,
                "measurement_orders": 1,
                "warmup_submission_ids": [42],
                "measurement_submission_ids": [42],
            }
        ]
        with self.assertRaisesRegex(
            RuntimeError,
            r"duplicate client_order_id=42 within submission file: "
            r"current=socket-r1\.json phase=measurement submission=1; "
            r"first=socket-r1\.json phase=warmup submission=1",
        ):
            MEASURE.validate_and_summarize_submission_identity(rounds)

    def test_submission_identity_rejects_cross_file_collision(self) -> None:
        rounds = [
            {
                "transport": "SOCKET",
                "round": 1,
                "warmup_orders": 1,
                "measurement_orders": 1,
                "warmup_submission_ids": [42],
                "measurement_submission_ids": [43],
            },
            {
                "transport": "DPDK",
                "round": 2,
                "warmup_orders": 1,
                "measurement_orders": 1,
                "warmup_submission_ids": [44],
                "measurement_submission_ids": [42],
            },
        ]
        with self.assertRaisesRegex(
            RuntimeError,
            r"duplicate client_order_id=42 across submission files: "
            r"current=dpdk-r2\.json phase=measurement submission=1; "
            r"first=socket-r1\.json phase=warmup submission=1",
        ):
            MEASURE.validate_and_summarize_submission_identity(rounds)

    def test_measurement_mapping_rejects_response_set_mismatch(self) -> None:
        with self.assertRaisesRegex(
            RuntimeError,
            r"SOCKET round 1 measurement submission/raw set mismatch: "
            r"missing_from_raw=\[102\] unexpected_in_raw=\[103\]",
        ):
            MEASURE.validate_measurement_submission_mapping(
                "SOCKET",
                1,
                [101, 102],
                [
                    {"client_order_id": 101},
                    {"client_order_id": 103},
                ],
            )

    def test_measurement_mapping_rejects_response_order_mismatch(self) -> None:
        with self.assertRaisesRegex(
            RuntimeError,
            r"TCPDIRECT round 3 measurement submission/raw order mismatch "
            r"at index=1: submitted=201 raw=202",
        ):
            MEASURE.validate_measurement_submission_mapping(
                "TCPDIRECT",
                3,
                [201, 202],
                [
                    {"client_order_id": 202},
                    {"client_order_id": 201},
                ],
            )

    def test_default_identity_gates_cover_all_17600_submissions(self) -> None:
        rounds = []
        next_client_order_id = 1
        for round_number, order in enumerate(
            MEASURE.BALANCED_PHASE_ORDER, start=1
        ):
            for transport in order:
                warmup_ids = list(
                    range(next_client_order_id, next_client_order_id + 100)
                )
                next_client_order_id += 100
                measurement_ids = list(
                    range(next_client_order_id, next_client_order_id + 1000)
                )
                next_client_order_id += 1000
                rounds.append(
                    {
                        "transport": transport,
                        "round": round_number,
                        "warmup_orders": 100,
                        "measurement_orders": 1000,
                        "warmup_submission_ids": warmup_ids,
                        "warmup_raw_samples": [
                            {"client_order_id": value}
                            for value in warmup_ids
                        ],
                        "measurement_submission_ids": measurement_ids,
                        "raw_samples": [
                            {"client_order_id": value}
                            for value in measurement_ids
                        ],
                    }
                )
        submission_identity, warmup_identity, sample_identity = (
            MEASURE.validate_final_identity_gates(rounds, 100, 1000)
        )
        self.assertEqual(submission_identity["total"], 17600)
        self.assertEqual(submission_identity["unique"], 17600)
        self.assertEqual(warmup_identity["total"], 1600)
        self.assertEqual(warmup_identity["unique"], 1600)
        self.assertEqual(sample_identity["total"], 16000)
        self.assertEqual(sample_identity["unique"], 16000)
        self.assertEqual(len(submission_identity["per_round_ranges"]), 16)

    def test_exchange_ledger_gate_rejects_too_few_entries(self) -> None:
        with mock.patch.object(
            MEASURE,
            "management_command",
            return_value={
                "paper_ledger_entries": 109,
                "replay_loop": 7,
                "session": "SESSION007",
            },
        ) as command:
            with self.assertRaisesRegex(
                RuntimeError,
                r"before=10 after=109 delta=99 expected=100 "
                r"diagnosis=too_few_cached_or_missing",
            ):
                MEASURE.capture_exchange_ledger_growth(
                    "10.1.1.1",
                    48120,
                    before={"entries": 10, "replay_loop": 7, "session": "SESSION007"},
                    expected=100,
                )
        command.assert_called_once_with("10.1.1.1", 48120, "STATE")

    def test_exchange_ledger_gate_rejects_too_many_entries(self) -> None:
        with mock.patch.object(
            MEASURE,
            "management_command",
            return_value={
                "paper_ledger_entries": 111,
                "replay_loop": 7,
                "session": "SESSION007",
            },
        ) as command:
            with self.assertRaisesRegex(
                RuntimeError,
                r"before=10 after=111 delta=101 expected=100 "
                r"diagnosis=too_many_external",
            ):
                MEASURE.capture_exchange_ledger_growth(
                    "10.1.1.1",
                    48120,
                    before={"entries": 10, "replay_loop": 7, "session": "SESSION007"},
                    expected=100,
                )
        command.assert_called_once_with("10.1.1.1", 48120, "STATE")

    def test_exchange_ledger_gate_rejects_replay_change(self) -> None:
        with mock.patch.object(
            MEASURE,
            "management_command",
            return_value={
                "paper_ledger_entries": 110,
                "replay_loop": 8,
                "session": "SESSION008",
            },
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                r"exchange replay identity changed during measurement",
            ):
                MEASURE.capture_exchange_ledger_growth(
                    "10.1.1.1",
                    48120,
                    before={"entries": 10, "replay_loop": 7, "session": "SESSION007"},
                    expected=100,
                )

    def test_order_balances_positions_and_within_round_predecessors(self) -> None:
        self.assertEqual(
            MEASURE.BALANCED_PHASE_ORDER,
            (
                ("SOCKET", "OPENONLOAD", "DPDK", "TCPDIRECT"),
                ("OPENONLOAD", "TCPDIRECT", "SOCKET", "DPDK"),
                ("TCPDIRECT", "DPDK", "OPENONLOAD", "SOCKET"),
                ("DPDK", "SOCKET", "TCPDIRECT", "OPENONLOAD"),
            ),
        )
        balance = MEASURE.validate_position_and_predecessor_balance()
        for item in balance["position_balance"]:
            self.assertEqual(
                item["position_counts"],
                {"1": 1, "2": 1, "3": 1, "4": 1},
                item["transport"],
            )
        predecessor_rows = balance[
            "within_round_first_order_predecessor_balance"
        ]
        self.assertEqual(len(predecessor_rows), 12)
        self.assertTrue(all(item["count"] == 1 for item in predecessor_rows))
        self.assertEqual(len(balance["cross_round_boundaries"]), 3)
        complete_counts = sorted(
            item["count"]
            for item in balance["complete_sequence_predecessor_coverage"]
        )
        self.assertEqual(complete_counts, [1] * 9 + [2] * 3)

    def test_cyclic_position_only_order_fails_predecessor_hard_gate(self) -> None:
        cyclic_order = (
            ("SOCKET", "OPENONLOAD", "TCPDIRECT", "DPDK"),
            ("OPENONLOAD", "TCPDIRECT", "DPDK", "SOCKET"),
            ("TCPDIRECT", "DPDK", "SOCKET", "OPENONLOAD"),
            ("DPDK", "SOCKET", "OPENONLOAD", "TCPDIRECT"),
        )
        with self.assertRaisesRegex(
            RuntimeError,
            r"order design first-order predecessor balance failed",
        ):
            MEASURE.validate_position_and_predecessor_balance(cyclic_order)

    def test_report_persists_identity_summary_and_total_equals_unique(self) -> None:
        rounds = [
            {
                "transport": transport,
                "round": 1,
                "warmup_orders": 1,
                "measurement_orders": 1,
                "warmup_submission_ids": [10 + index],
                "warmup_raw_samples": [{"client_order_id": 10 + index}],
                "measurement_submission_ids": [100 + index],
                "raw_samples": [{"client_order_id": 100 + index}],
            }
            for index, transport in enumerate(MEASURE.TRANSPORT_ORDER)
        ]
        identity = MEASURE.validate_and_summarize_sample_identity(rounds)
        warmup_identity = (
            MEASURE.validate_and_summarize_warmup_sample_identity(rounds)
        )
        submission_identity = (
            MEASURE.validate_and_summarize_submission_identity(rounds)
        )
        metric = {"p50_ns": 1, "p95_ns": 2, "p99_ns": 3}
        summary = {
            transport: {
                "order_rtt": metric,
                "submit_to_final": metric,
            }
            for transport in reversed(MEASURE.TRANSPORT_ORDER)
        }
        result = {
            "run_id": "unit-test",
            "parameters": {"warmup_per_round": 1},
            "exchange_ledger_gate": {
                "before": 5,
                "after": 13,
                "delta": 8,
                "expected": 8,
                "before_state": {
                    "paper_ledger_entries": 5,
                    "replay_loop": 1,
                    "session": "UNIT",
                },
                "after_state": {
                    "paper_ledger_entries": 13,
                    "replay_loop": 1,
                    "session": "UNIT",
                },
            },
            "submission_identity": submission_identity,
            "warmup_sample_identity": warmup_identity,
            "sample_identity": identity,
            "summary": summary,
            "rounds": rounds,
        }

        with tempfile.TemporaryDirectory() as temporary:
            temporary_path = Path(temporary)
            output = Path(temporary) / "report"
            payloads = {}
            for name in (
                "transport_labctl.sh",
                "measure_four_transports.py",
                "analyze_four_transport_raw.py",
            ):
                source = temporary_path / f"source-{name}"
                source.write_text(f"sealed {name}\n", encoding="utf-8")
                payloads[name] = source.read_bytes()
            MEASURE.write_report(
                output, result, sealed_program_payloads=payloads
            )
            persisted = json.loads((output / "summary.json").read_text())
            self.assertEqual(persisted["submission_identity"]["total"], 8)
            self.assertEqual(persisted["submission_identity"]["unique"], 8)
            self.assertEqual(persisted["warmup_sample_identity"]["total"], 4)
            self.assertEqual(persisted["warmup_sample_identity"]["unique"], 4)
            self.assertEqual(persisted["sample_identity"]["total"], 4)
            self.assertEqual(persisted["sample_identity"]["unique"], 4)
            self.assertEqual(
                len(persisted["sample_identity"]["per_transport"]), 4
            )
            self.assertEqual(
                len(persisted["sample_identity"]["per_round_ranges"]), 4
            )
            readme = (output / "README.md").read_text()
            self.assertIn("submitted total=unique=8", readme)
            self.assertIn("warmup total=unique=4", readme)
            self.assertIn("measured total=unique=4", readme)
            self.assertIn("delta=expected=8", readme)
            self.assertIn("P50 / P95 / P99", readme)
            self.assertTrue((output / "raw/exchange-ledger-before.json").is_file())
            self.assertTrue((output / "raw/exchange-ledger-after.json").is_file())
            self.assertEqual(
                {
                    row["path"]
                    for row in persisted["execution_provenance"]["sealed_programs"]
                },
                {
                    "provenance/transport_labctl.sh",
                    "provenance/measure_four_transports.py",
                    "provenance/analyze_four_transport_raw.py",
                },
            )
            self.assertEqual(
                persisted["execution_provenance"]["capture_contract"],
                "START_SNAPSHOT_END_BYTES_UNCHANGED",
            )
            manifest_text = (output / "SHA256SUMS").read_text()
            self.assertIn("provenance/transport_labctl.sh", manifest_text)

    def test_path_receipt_distinguishes_launch_from_current_path(self) -> None:
        receipt = {
            "launch_verified": True,
            "verified": False,
            "pid": 101,
            "start_ticks": 202,
            "boot_id": "boot-a",
            "generation": "onload-101-202",
            "attested_monotonic_ns": 303,
            "path_counter": 0,
            "verification": "LAUNCH_ONLOAD_CURRENT_PID",
        }
        state = {
            "mode": "SFC",
            "transition": "READY",
            "owner": "sfc",
            "hardware_receipts": {"onload": receipt},
        }
        observed = MEASURE.require_path_receipt(
            state, "OPENONLOAD", require_path=False
        )
        self.assertEqual(observed["receipt"]["pid"], 101)
        with self.assertRaisesRegex(RuntimeError, "no path witness"):
            MEASURE.require_path_receipt(
                state, "OPENONLOAD", require_path=True
            )

    def test_formal_program_drift_after_start_snapshot_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = {}
            payloads = {}
            for name in (
                "transport_labctl.sh",
                "measure_four_transports.py",
                "analyze_four_transport_raw.py",
            ):
                path = root / name
                path.write_text(f"start {name}\n", encoding="utf-8")
                paths[name] = path
                payloads[name] = path.read_bytes()
            MEASURE.verify_program_sources_unchanged(paths, payloads)
            paths["transport_labctl.sh"].write_text(
                "changed during formal run\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(
                RuntimeError, "changed after the start snapshot"
            ):
                MEASURE.verify_program_sources_unchanged(paths, payloads)

    def test_native_manifest_is_compact_and_counter_kind_is_explicit(self) -> None:
        prefix = "native-receipts/1-3-tcpdirect/pre"
        files = [
            {
                "path": f"{prefix}/{name}",
                "sha256": "a" * 64,
                "bytes": 1,
            }
            for name in sorted(MEASURE.NATIVE_RECEIPT_FILES["TCPDIRECT"])
        ]
        manifest = {
            "files": files,
            "counter_kind": "zf_txq_added",
            "counter_value": 19,
            "matching_excerpts": [
                {"path": f"{prefix}/zf-attr.txt", "text": "ctpio=3"}
            ],
        }
        observed = MEASURE.validate_native_receipt_manifest(
            manifest, "TCPDIRECT", 1, 3, "pre"
        )
        self.assertIs(observed, manifest)
        self.assertEqual(
            set(observed),
            {"files", "counter_kind", "counter_value", "matching_excerpts"},
        )

    def test_native_manifest_rejects_controller_verified_boolean(self) -> None:
        prefix = "native-receipts/1-1-socket/pre"
        manifest = {
            "files": [
                {
                    "path": f"{prefix}/{name}",
                    "sha256": "b" * 64,
                    "bytes": 1,
                }
                for name in sorted(MEASURE.NATIVE_RECEIPT_FILES["SOCKET"])
            ],
            "counter_kind": "trader_orders",
            "counter_value": 7,
            "matching_excerpts": [
                {"path": f"{prefix}/process.txt", "text": "pid=321"}
            ],
            "verified": True,
        }
        with self.assertRaisesRegex(RuntimeError, "unexpected fields"):
            MEASURE.validate_native_receipt_manifest(
                manifest, "SOCKET", 1, 1, "pre"
            )

    def test_onload_hardware_witness_is_separate_from_order_counter(self) -> None:
        manifest = {
            "counter_kind": "trader_orders",
            "counter_value": 1100,
            "matching_excerpts": [
                {"path": "native", "text": "ctpio_pkts: 1099"},
                {"path": "native", "text": "ctpio_dma_fallbacks: 0"},
            ],
        }
        self.assertEqual(
            MEASURE.onload_ctpio_counters_from_manifest(manifest),
            {"ctpio_pkts": 1099, "ctpio_dma_fallbacks": 0},
        )
        self.assertEqual(manifest["counter_kind"], "trader_orders")

    def test_dpdk_exchange_manifest_allows_multiple_target_endpoints(self) -> None:
        prefix = "native-receipts/1-4-dpdk/pre"
        endpoints = [
            (
                f"0 0 20.1.1.1:43120 20.1.1.2:{port} "
                f'users:(("flle-exchange",pid=654,fd={fd}))'
            )
            for fd, port in ((9, 45678), (10, 45679))
        ]
        manifest = {
            "matching_excerpts": [
                {
                    "path": f"{prefix}/exchange-process.txt",
                    "text": "pid=654",
                },
                {
                    "path": f"{prefix}/exchange-process.txt",
                    "text": "listener_count=1",
                },
                {
                    "path": f"{prefix}/exchange-process.txt",
                    "text": (
                        "listener_ss_line_1=LISTEN 0 128 20.1.1.1:43120 "
                        '0.0.0.0:* users:(("flle-exchange",pid=654,fd=5))'
                    ),
                },
                *[
                    {
                        "path": f"{prefix}/exchange-ss-established.txt",
                        "text": endpoint,
                    }
                    for endpoint in endpoints
                ],
                {
                    "path": f"{prefix}/exchange-ss-established.txt",
                    "text": (
                        '0 0 10.1.1.1:22 10.1.1.2:50123 '
                        'users:(("sshd",pid=654,fd=8))'
                    ),
                },
            ]
        }
        result = MEASURE.dpdk_exchange_server_observations_from_manifest(
            manifest
        )
        self.assertEqual(result["endpoint_count"], 2)
        self.assertEqual(result["listener_count"], 1)
        self.assertEqual(
            [item["peer_endpoint"] for item in result["observed_endpoints"]],
            ["20.1.1.2:45678", "20.1.1.2:45679"],
        )
        self.assertTrue(result["not_a_client_pid_binding"])

    def test_dpdk_exchange_manifest_requires_current_pid_target_endpoint(self) -> None:
        prefix = "native-receipts/1-4-dpdk/pre"
        manifest = {
            "matching_excerpts": [
                {
                    "path": f"{prefix}/exchange-process.txt",
                    "text": "pid=654",
                },
                {
                    "path": f"{prefix}/exchange-process.txt",
                    "text": "listener_count=1",
                },
                {
                    "path": f"{prefix}/exchange-process.txt",
                    "text": (
                        "listener_ss_line_1=LISTEN 0 128 20.1.1.1:43120 "
                        '0.0.0.0:* users:(("flle-exchange",pid=654,fd=5))'
                    ),
                },
                {
                    "path": f"{prefix}/exchange-ss-established.txt",
                    "text": (
                        "0 0 20.1.1.1:43120 20.1.1.2:45678 "
                        'users:(("flle-exchange",pid=999,fd=9))'
                    ),
                },
            ]
        }
        with self.assertRaisesRegex(
            RuntimeError, "current Exchange PID has no target endpoint"
        ):
            MEASURE.dpdk_exchange_server_observations_from_manifest(manifest)

    def test_native_fetch_uses_fixed_scp_argv_and_requires_tree(self) -> None:
        def fake_run(command, **kwargs):
            destination = Path(command[-1])
            (destination / "native-receipts").mkdir()
            return MEASURE.subprocess.CompletedProcess(
                args=command, returncode=0, stdout="", stderr=""
            )

        with tempfile.TemporaryDirectory() as temporary, mock.patch.object(
            MEASURE.subprocess, "run", side_effect=fake_run
        ) as run:
            destination = Path(temporary) / "fetch"
            observed = MEASURE.fetch_native_receipt_tree(
                "10.1.1.2", "RUN-UNIT", destination
            )
            self.assertEqual(observed, destination / "native-receipts")
        command = run.call_args.args[0]
        self.assertEqual(command[0], "scp")
        self.assertIn(
            "root@10.1.1.2:/var/tmp/flle-trading-lab-RUN-UNIT/native-receipts",
            command,
        )
        self.assertNotIsInstance(command, str)

    def test_formal_native_tree_requires_exactly_32_pre_post_sets(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            receipt_root = root / "native-receipts"
            rounds = []
            for round_number, order in enumerate(
                MEASURE.BALANCED_PHASE_ORDER, start=1
            ):
                for position, transport in enumerate(order, start=1):
                    manifests = {}
                    for phase in ("pre", "post"):
                        prefix = MEASURE.native_receipt_prefix(
                            transport, round_number, position, phase
                        )
                        directory = root / prefix
                        directory.mkdir(parents=True)
                        files = []
                        for name in sorted(
                            MEASURE.NATIVE_RECEIPT_FILES[transport]
                        ):
                            payload = f"{transport}-{phase}-{name}\n".encode()
                            target = directory / name
                            target.write_bytes(payload)
                            files.append(
                                {
                                    "path": f"{prefix}/{name}",
                                    "sha256": hashlib.sha256(payload).hexdigest(),
                                    "bytes": len(payload),
                                }
                            )
                        process_path = f"{prefix}/process.txt"
                        manifests[phase] = {
                            "files": files,
                            "counter_kind": MEASURE.NATIVE_COUNTER_KIND[transport],
                            "counter_value": 1 if phase == "pre" else 2,
                            "matching_excerpts": [
                                {
                                    "path": process_path,
                                    "text": f"{transport}-{phase}-process.txt",
                                }
                            ],
                        }
                        if transport == "DPDK":
                            manifests[phase]["hardware_counters"] = {
                                "port_id": 0,
                                "ipackets": 1 if phase == "pre" else 2,
                                "opackets": 1 if phase == "pre" else 2,
                                "imissed": 0,
                                "ierrors": 0,
                                "oerrors": 0,
                                "rx_nombuf": 0,
                            }
                    rounds.append(
                        {
                            "transport": transport,
                            "round": round_number,
                            "position": position,
                            "cell_audit": {"native_receipts": manifests},
                        }
                    )

            self.assertEqual(
                MEASURE.validate_downloaded_native_receipts(
                    rounds, receipt_root
                ),
                {
                    "cells": 16,
                    "pre_post_manifests": 32,
                    "original_files": 192,
                },
            )
            (receipt_root / "unexpected.txt").write_text("not sealed\n")
            with self.assertRaisesRegex(RuntimeError, "file set mismatch"):
                MEASURE.validate_downloaded_native_receipts(
                    rounds, receipt_root
                )

    def test_status_collector_has_no_heavy_stack_probe_or_receipt_write(self) -> None:
        script_path = (
            Path(__file__).resolve().parents[1] / "scripts/transport_labctl.sh"
        )
        if not script_path.is_file():
            self.skipTest("Chapter 06 controller is not part of the base app bundle")
        script = script_path.read_text()
        body = script.split("collect_status() {", 1)[1].split(
            '\ncase "$ACTION" in', 1
        )[0]
        self.assertNotIn("stackdump", body)
        self.assertNotIn("ethtool", body)
        self.assertNotIn("touch ", body)
        self.assertNotIn("mv ", body)

    def test_formal_measurement_rechecks_mode_and_rss_at_every_cell(self) -> None:
        source = Path(MEASURE.__file__).read_text(encoding="utf-8")
        main = source.split("def main() -> int:", 1)[1]
        loop = main.split(
            "for position, key in enumerate(order, start=1):", 1
        )[1].split("measured = measure_round(", 1)[0]
        self.assertIn("switch_data_plane_mode(", loop)
        self.assertNotIn("if required_mode != current_mode:", loop)
        self.assertIn("if mode_changed:", loop)

    def test_formal_measurement_stops_gateway_polling(self) -> None:
        script_path = (
            Path(__file__).resolve().parents[1] / "scripts/transport_labctl.sh"
        )
        if not script_path.is_file():
            self.skipTest("Chapter 06 controller is not part of the base app bundle")
        script = script_path.read_text()
        measure_case = script.split("  measure)\n", 1)[1].split("    ;;", 1)[0]
        self.assertIn(
            'stop_remote_process "$OBSERVER_HOST" gateway flle_trading.gateway',
            measure_case,
        )
        self.assertIn("start_gateway", measure_case)

    def test_native_receipt_seals_client_executable_against_runtime_manifest(
        self,
    ) -> None:
        script_path = (
            Path(__file__).resolve().parents[1] / "scripts/transport_labctl.sh"
        )
        if not script_path.is_file():
            self.skipTest("Chapter 06 controller is not part of the base app bundle")
        script = script_path.read_text()
        body = script.split("capture_native_receipt() {", 1)[1].split(
            "\nallocate_sfc_user_ref_slot() {", 1
        )[0]
        self.assertIn('exe_path="$(readlink -f "/proc/$pid/exe")"', body)
        self.assertIn(
            'expected_exe_path="$(readlink -f "$runtime_root/bin/$expected")"',
            body,
        )
        self.assertIn('test "$exe_path" = "$expected_exe_path"', body)
        self.assertIn(
            'mapfile -d \'\' -t observed_argv <"/proc/$pid/cmdline"', body
        )
        self.assertIn('test "${observed_argv[0]}" = "$exe_path"', body)
        self.assertIn(
            'test "${#observed_argv[@]}" -eq "${#expected_argv[@]}"', body
        )
        self.assertIn(
            'test "${observed_argv[$index]}" = "${expected_argv[$index]}"',
            body,
        )
        self.assertIn(
            'exe_sha256="$(sha256sum -- "/proc/$pid/exe"', body
        )
        self.assertIn('test "$exe_sha256" = "$exe_manifest_sha256"', body)
        self.assertIn("awk -v expected=\"bin/$expected\"", body)
        self.assertIn("exe_path=%s", body)
        self.assertIn("exe_sha256=%s", body)
        self.assertIn("exe_manifest_sha256=%s", body)
        self.assertIn("argv_count=%s", body)
        self.assertIn("argv_%02d=%s", body)
        self.assertIn(
            'runtime_manifest_matches != [exe_manifest_sha256]', body
        )

    def test_controller_exposes_native_formal_and_standalone_copy_contracts(self) -> None:
        script_path = (
            Path(__file__).resolve().parents[1] / "scripts/transport_labctl.sh"
        )
        if not script_path.is_file():
            self.skipTest("Chapter 06 controller is not part of the base app bundle")
        script = script_path.read_text()
        self.assertIn('final="$root/$cell/$phase"', script)
        self.assertIn("standalone-native-receipts", script)
        self.assertIn('"local_directory": str(output)', script)
        self.assertIn('"manifest_file": str(manifest_path)', script)
        self.assertIn('"sha256sums_file": str(sha_path)', script)
        self.assertIn('manifest_path = output / "manifest.json"', script)
        self.assertIn('sha_path = output / "SHA256SUMS"', script)
        self.assertIn("standalone native file set mismatch", script)
        self.assertIn('"zf-attr.txt"', script)
        self.assertIn('"zf-dump.txt"', script)
        self.assertIn('"$EXCHANGE_HOST:$exchange_final/exchange-process.txt"', script)
        self.assertIn(
            '"$EXCHANGE_HOST:$exchange_final/exchange-ss-established.txt"',
            script,
        )
        self.assertIn('"${SCP[@]}" -3', script)
        self.assertIn("END { exit(matches >= 1 ? 0 : 1) }", script)
        self.assertNotIn("END { exit(matches == 1 ? 0 : 1) }", script)
        self.assertIn(
            '"DPDK Exchange-side current PID has no target endpoint"',
            script,
        )
        self.assertIn("attest export path must be absolute", script)
        self.assertNotIn("assert ", script)

    def test_standalone_export_is_self_contained_and_rejects_extra_file(self) -> None:
        script_path = (
            Path(__file__).resolve().parents[1] / "scripts/transport_labctl.sh"
        )
        if not script_path.is_file():
            self.skipTest("Chapter 06 controller is not part of the base app bundle")
        script = script_path.read_text()
        marker = 'python3 - "$manifest" "$EXPORT_DIR" <<\'PY\'\n'
        embedded = script.split(marker, 1)[1].split("\nPY\n", 1)[0]

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "native"
            output.mkdir()
            files = []
            for name, payload in (
                ("zf-attr.txt", b"ctpio=3\nctpio_mode=sf-np\n"),
                ("zf-dump.txt", b"  txq: added=11 removed=10\n"),
            ):
                relative = Path(
                    f"standalone-native-receipts/unit/evidence/{name}"
                )
                (output / relative).parent.mkdir(parents=True, exist_ok=True)
                (output / relative).write_bytes(payload)
                files.append(
                    {
                        "path": relative.as_posix(),
                        "sha256": hashlib.sha256(payload).hexdigest(),
                        "bytes": len(payload),
                    }
                )
            manifest = {
                "files": files,
                "counter_kind": "zf_txq_added",
                "counter_value": 11,
                "matching_excerpts": [
                    {"path": files[0]["path"], "text": "ctpio=3"}
                ],
            }
            completed = MEASURE.subprocess.run(
                ["python3", "-", json.dumps(manifest), str(output)],
                input=embedded,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            response = json.loads(completed.stdout)
            self.assertEqual(response["native_receipt"], manifest)
            self.assertEqual(
                json.loads((output / "manifest.json").read_text()), manifest
            )
            sha_entries = (output / "SHA256SUMS").read_text().splitlines()
            self.assertEqual(len(sha_entries), 3)
            self.assertTrue(any(line.endswith("  manifest.json") for line in sha_entries))
            self.assertTrue(
                any(line.endswith("  " + files[0]["path"]) for line in sha_entries)
            )
            self.assertFalse(any(line.endswith("  SHA256SUMS") for line in sha_entries))

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "native"
            output.mkdir()
            for item in manifest["files"]:
                target = output / item["path"]
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(
                    b"ctpio=3\nctpio_mode=sf-np\n"
                    if item["path"].endswith("zf-attr.txt")
                    else b"  txq: added=11 removed=10\n"
                )
            (output / "unexpected.txt").write_text("not sealed\n")
            rejected = MEASURE.subprocess.run(
                ["python3", "-", json.dumps(manifest), str(output)],
                input=embedded,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("standalone native file set mismatch", rejected.stderr)


if __name__ == "__main__":
    unittest.main()
