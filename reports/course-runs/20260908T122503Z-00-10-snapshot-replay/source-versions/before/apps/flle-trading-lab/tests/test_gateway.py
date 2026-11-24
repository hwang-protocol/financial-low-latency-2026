import json
import socket
import sys
import threading
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from flle_trading.gateway import StateStore, render_prometheus, send_command  # noqa: E402


class StateStoreTest(unittest.TestCase):
    def test_transport_lab_is_an_explicit_chapter_six_feature(self) -> None:
        baseline = StateStore().snapshot()
        self.assertFalse(baseline["features"]["transport_lab"])
        self.assertNotIn("trader_onload", baseline["health"])
        self.assertNotIn("trader_tcpdirect", baseline["health"])
        self.assertNotIn("trader_dpdk", baseline["health"])

        transport_lab = StateStore(transport_lab_enabled=True).snapshot()
        self.assertTrue(transport_lab["features"]["transport_lab"])
        self.assertEqual(transport_lab["data_plane_mode"], "SFC")
        self.assertEqual(transport_lab["health"]["trader_onload"]["status"], "WAITING")
        self.assertEqual(transport_lab["health"]["trader_tcpdirect"]["status"], "WAITING")
        self.assertEqual(transport_lab["health"]["trader_dpdk"]["status"], "WAITING")

    def test_market_and_fill_projection(self) -> None:
        store = StateStore()
        store.ingest(
            {
                "schema": "flle.trading-event.v1",
                "event_id": "exchange:1",
                "source": "exchange",
                "kind": "market_update",
                "event_ns": 1,
                "sequence": 1,
                "simulated": True,
                "fields": {
                    "session": "SESSION001",
                    "market_mode": "MULTICAST",
                    "market_date": "2026-06-12",
                    "source_timestamp_ns": 34200000000000,
                    "source_clock": "09:30:00.000000000",
                    "replay_loop": 1,
                    "symbol": "AAPL",
                    "last_x10000": 2374200,
                    "bids": [[2374100, 100]],
                    "asks": [[2374300, 100]],
                },
            }
        )
        store.ingest(
            {
                "schema": "flle.trading-event.v1",
                "event_id": "trader_manual:1",
                "source": "trader_manual",
                "kind": "order_complete",
                "event_ns": 2,
                "sequence": 1,
                "simulated": True,
                "fields": {
                    "result": "ORDER_EXECUTED",
                    "symbol": "AAPL",
                    "position": 25,
                    "pnl_x10000": 1000,
                },
            }
        )
        snapshot = store.snapshot()
        self.assertEqual(snapshot["session"], "SESSION001")
        self.assertEqual(snapshot["market_mode"], "MULTICAST")
        self.assertEqual(snapshot["replay"]["market_date"], "2026-06-12")
        self.assertEqual(snapshot["replay"]["source_clock"], "09:30:00.000000000")
        self.assertTrue(snapshot["historical_market"])
        self.assertTrue(snapshot["paper_execution"])
        self.assertEqual(snapshot["positions"]["AAPL"], 25)
        self.assertEqual(len(snapshot["fills"]), 1)
        self.assertEqual(snapshot["health"]["exchange"]["status"], "ONLINE")

    def test_completed_order_updates_queued_row(self) -> None:
        store = StateStore()
        base = {
            "schema": "flle.trading-event.v1",
            "source": "trader_manual",
            "event_ns": 1,
            "simulated": True,
        }
        store.ingest(
            {
                **base,
                "event_id": "trader:1",
                "sequence": 1,
                "kind": "order_queued",
                "fields": {
                    "client_order_id": 42,
                    "symbol": "AAPL",
                    "limit_price_x10000": 1234500,
                },
            }
        )
        store.ingest(
            {
                **base,
                "event_id": "trader:2",
                "sequence": 2,
                "kind": "order_complete",
                "fields": {
                    "client_order_id": 42,
                    "symbol": "AAPL",
                    "result": "ORDER_EXECUTED",
                    "filled_quantity": 10,
                    "position": 10,
                },
            }
        )
        snapshot = store.snapshot()
        self.assertEqual(len(snapshot["orders"]), 1)
        self.assertEqual(snapshot["orders"][0]["limit_price_x10000"], 1234500)
        self.assertEqual(snapshot["orders"][0]["result"], "ORDER_EXECUTED")
        self.assertEqual(len(snapshot["fills"]), 1)

    def test_new_replay_loop_clears_all_paper_state(self) -> None:
        store = StateStore()
        store.orders.append({"client_order_id": 7})
        store.fills.append({"client_order_id": 7})
        store.positions["AAPL"] = 10
        store.pnl_x10000 = 1234
        store.stats.update({"orders": 1, "fills": 1})
        store.latency.update({"samples": 1, "p50_ns": 99, "p99_ns": 99, "max_ns": 99})
        store.exchange_ledger_entries = 1
        store.exchange_ledger.append({"client_order_id": 7})
        store.ingest(
            {
                "schema": "flle.trading-event.v1",
                "event_id": "exchange:2",
                "source": "exchange",
                "kind": "replay_started",
                "event_ns": 2,
                "sequence": 2,
                "fields": {"loop": 2, "session": "SESSION002"},
            }
        )
        snapshot = store.snapshot()
        self.assertEqual(snapshot["orders"], [])
        self.assertEqual(snapshot["fills"], [])
        self.assertEqual(snapshot["positions"], {"AAPL": 0, "NVDA": 0})
        self.assertEqual(snapshot["pnl_x10000"], 0)
        self.assertEqual(snapshot["stats"]["orders"], 0)
        self.assertEqual(snapshot["latency"]["samples"], 0)
        self.assertEqual(snapshot["exchange_ledger_entries"], 0)
        self.assertEqual(snapshot["exchange_ledger"], [])
        self.assertEqual(snapshot["replay"]["loop"], 2)
        self.assertEqual(snapshot["feed"]["integrity"], "RECOVERING")
        self.assertEqual(
            snapshot["feed"]["trading_gate"], "INHIBITED_FEED_RECOVERING"
        )

    def test_feed_gap_and_recovery_drive_one_common_gate(self) -> None:
        store = StateStore()
        store.ingest(
            {
                "schema": "flle.trading-event.v1",
                "event_id": "trader_auto:1",
                "source": "trader_auto",
                "kind": "feed_gap",
                "event_ns": 1,
                "sequence": 1,
                "fields": {
                    "session": "SESSION001",
                    "next_expected": 41,
                    "first_pending": 42,
                    "highest_received": 44,
                    "pending": 3,
                    "gap_size": 1,
                    "gap_age_ms": 7,
                    "integrity": "GAP",
                    "trading_gate": "INHIBITED_FEED_GAP",
                },
            }
        )
        gap = store.snapshot()["feed"]
        self.assertEqual(gap["integrity"], "GAP")
        self.assertEqual(gap["trading_gate"], "INHIBITED_FEED_GAP")
        self.assertEqual(gap["gap_age_ms"], 7)

        store.ingest(
            {
                "schema": "flle.trading-event.v1",
                "event_id": "trader_auto:2",
                "source": "trader_auto",
                "kind": "component_heartbeat",
                "event_ns": 2,
                "sequence": 2,
                "fields": {
                    "status": "ONLINE",
                    "session": "SESSION002",
                    "next_expected": 101,
                    "last_delivered": 100,
                    "first_pending": 0,
                    "highest_received": 100,
                    "pending": 0,
                    "gaps": 0,
                    "gap_age_ms": 0,
                    "integrity": "HEALTHY",
                    "trading_gate": "OPEN",
                },
            }
        )
        healthy = store.snapshot()["feed"]
        self.assertEqual(healthy["integrity"], "HEALTHY")
        self.assertEqual(healthy["trading_gate"], "OPEN")
        self.assertEqual(healthy["pending"], 0)

    def test_automatic_flow_does_not_evict_manual_history(self) -> None:
        store = StateStore()
        store.orders.append({"client_order_id": 2_100_000_001, "origin": "MANUAL_GUI", "event_ns": 1})
        for index in range(300):
            store.orders.append(
                {"client_order_id": index + 1, "origin": "AUTO_STRATEGY", "event_ns": index + 2}
            )
        snapshot = store.snapshot()
        self.assertEqual(len(snapshot["orders"]), 41)
        self.assertTrue(any(order["origin"] == "MANUAL_GUI" for order in snapshot["orders"]))
        self.assertEqual(sum(order["origin"] == "AUTO_STRATEGY" for order in snapshot["orders"]), 40)

    def test_management_line_roundtrip(self) -> None:
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]

        def server() -> None:
            client, _ = listener.accept()
            command = client.recv(128)
            self.assertEqual(command, b"STATE\n")
            client.sendall(json.dumps({"status": "ONLINE"}).encode() + b"\n")
            client.close()
            listener.close()

        thread = threading.Thread(target=server)
        thread.start()
        self.assertEqual(send_command("127.0.0.1", port, "STATE")["status"], "ONLINE")
        thread.join()

    def test_prometheus_metrics_keep_identity_low_cardinality(self) -> None:
        store = StateStore()
        store.health["exchange"] = {"status": "ONLINE", "last_event_ns": time.time_ns()}
        store.replay.update({"messages": 1234, "progress": 0.25, "source_timestamp_ns": 36_000_000_000_000})
        store.client_latency["trader_auto"].update(
            {"samples": 7, "p50_ns": 100_000, "p99_ns": 200_000, "max_ns": 300_000}
        )
        store.client_measurement_latency["trader_manual"].update(
            {"samples": 200, "p50_ns": 110_000, "p99_ns": 220_000, "max_ns": 330_000,
             "generation": 2}
        )
        store.client_software_latency["trader_manual"].update(
            {
                "samples": 200,
                "queue_mode": "SPSC_SPIN",
                "order_thread_allowed_count": 1,
                "order_thread_cpu": 2,
                "order_rx_cpu": 2,
                "queue_to_send": {"p50_ns": 10_000, "p99_ns": 20_000, "max_ns": 30_000},
                "submit_to_final": {"p50_ns": 120_000, "p99_ns": 240_000, "max_ns": 360_000},
            }
        )
        store.client_stats["trader_auto"].update({"orders": 9, "fills": 8, "rejects": 1})
        metrics = render_prometheus(store.snapshot())
        self.assertIn('flle_component_up{component="exchange"} 1', metrics)
        self.assertIn("flle_market_messages_total 1234", metrics)
        self.assertIn('flle_order_rtt_seconds{client="auto",stat="p99"} 0.000200000', metrics)
        self.assertIn('flle_baseline_order_rtt_samples{client="manual"} 200', metrics)
        self.assertIn(
            'flle_baseline_order_rtt_seconds{client="manual",stat="p99"} 0.000220000',
            metrics,
        )
        self.assertIn(
            'flle_software_queue_to_send_seconds{client="manual",mode="SPSC_SPIN",placement="pinned",stat="p99"} 0.000020000',
            metrics,
        )
        self.assertIn('flle_order_thread_cpu{client="manual"} 2', metrics)
        self.assertIn('flle_paper_orders_total{client="auto"} 9', metrics)
        self.assertNotIn("SESSION", metrics)
        self.assertNotIn("client_order_id", metrics)


if __name__ == "__main__":
    unittest.main()
