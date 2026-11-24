#!/usr/bin/env python3
"""Management-plane gateway for the FLLE browser trading terminal.

The gateway is deliberately outside the measured trading path.  C++ exchange
and trader processes emit best-effort UDP telemetry; browser disconnects,
rendering, or this process stopping cannot block market data or order entry.
"""

from __future__ import annotations

import argparse
import http.client
import json
import mimetypes
import socket
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen


BASE_TRADER_CLIENTS = ("trader_auto", "trader_manual")
TRANSPORT_TRADER_CLIENTS = ("trader_onload", "trader_tcpdirect", "trader_dpdk")


class StateStore:
    def __init__(self, transport_lab_enabled: bool = False) -> None:
        self.lock = threading.RLock()
        self.condition = threading.Condition(self.lock)
        self.sequence = 0
        self.events: deque[dict[str, Any]] = deque(maxlen=2_000)
        self.instruments: dict[str, dict[str, Any]] = {}
        self.trader_books: dict[str, dict[str, Any]] = {}
        # Keep the complete current replay epoch in the observer.  The epoch is
        # cleared at replay_started/paper_reset, so this cannot grow across days.
        # A shared fixed-size deque let frequent AUTO orders evict the latest
        # MANUAL order from the classroom blotter within minutes.
        self.orders: deque[dict[str, Any]] = deque()
        self.fills: deque[dict[str, Any]] = deque()
        self.chart: dict[str, deque[list[int]]] = {}
        self.transport_lab_enabled = transport_lab_enabled
        self.experiment_profile = "TRANSPORT"
        self.data_plane_mode = "SFC"
        self.data_plane_transition = "READY"
        self.data_plane_owner = "sfc"
        # Populated only by the fixed Ch06 controller after it has collected
        # a path-specific receipt.  Capability labels in the browser describe
        # the contract; this map is what is allowed to mark that contract as
        # verified on the current machine.
        self.hardware_receipts: dict[str, dict[str, Any]] = {}
        self.health: dict[str, dict[str, Any]] = {
            "exchange": {"status": "WAITING", "last_event_ns": 0},
            "trader_auto": {"status": "WAITING", "last_event_ns": 0},
            "trader_manual": {"status": "WAITING", "last_event_ns": 0},
            "gateway": {"status": "ONLINE", "last_event_ns": time.time_ns()},
        }
        if transport_lab_enabled:
            self.health.update(
                {
                    client: {"status": "WAITING", "last_event_ns": 0}
                    for client in TRANSPORT_TRADER_CLIENTS
                }
            )
        self.market_mode = "—"
        self.market_network: dict[str, Any] = {}
        self.session = "—"
        self.replay = {
            "source": "NASDAQ_PUBLIC_ITCH_SAMPLE",
            "market_date": "2026-06-12",
            "status": "WAITING",
            "speed": 1.0,
            "loop": 0,
            "source_timestamp_ns": 0,
            "source_clock": "--:--:--.---------",
            "first_source_timestamp_ns": 34_200_000_000_000,
            "last_source_timestamp_ns": 57_600_000_000_000,
            "first_source_clock": "09:30:00.000000000",
            "last_source_clock": "16:00:00.000000000",
            "window": "REGULAR_SESSION",
            "progress": 0.0,
            "remaining_source_ns": 23_400_000_000_000,
            "estimated_remaining_wall_ns": 23_400_000_000_000,
            "messages": 0,
        }
        self.feed = self.empty_feed()
        self.feed_receiver: dict[str, Any] = {}
        self.strategy = {"enabled": True, "imbalance_threshold": 0.35, "quantity": 25, "max_position": 200, "cooldown_ms": 5000}
        self.positions = {symbol: 0 for symbol in ("AAPL", "NVDA")}
        trader_clients = BASE_TRADER_CLIENTS + (
            TRANSPORT_TRADER_CLIENTS if transport_lab_enabled else ()
        )
        self.client_positions = {
            client: {symbol: 0 for symbol in ("AAPL", "NVDA")}
            for client in trader_clients
        }
        self.client_pnl_x10000 = {client: 0 for client in self.client_positions}
        self.client_stats = {client: {} for client in self.client_positions}
        self.client_latency = {
            client: {"samples": 0, "p50_ns": 0, "p99_ns": 0, "max_ns": 0}
            for client in self.client_positions
        }
        self.client_measurement_latency = {
            client: {"samples": 0, "p50_ns": 0, "p99_ns": 0, "max_ns": 0, "generation": 0}
            for client in self.client_positions
        }
        self.client_software_latency = {
            client: {
                "samples": 0,
                "queue_mode": "DEQUE_CV",
                "queue_capacity": 1023,
                "queue_depth": 0,
                "queue_full_drops": 0,
                "order_thread_tid": -1,
                "order_thread_cpu": -1,
                "order_thread_allowed_count": 0,
                "order_rx_cpu": -1,
                "queue_to_send": {"p50_ns": 0, "p99_ns": 0, "max_ns": 0},
                "submit_to_final": {"p50_ns": 0, "p99_ns": 0, "max_ns": 0},
            }
            for client in self.client_positions
        }
        self.client_reaction_latency = {
            client: {"samples": 0, "p50_ns": 0, "p99_ns": 0, "max_ns": 0}
            for client in self.client_positions
        }
        self.gui_reset_ns = 0
        self.paper_epoch = 0
        self.exchange_ledger_entries = 0
        self.exchange_ledger: list[dict[str, Any]] = []
        self.pnl_x10000 = 0
        self.stats = {
            "orders": 0,
            "fills": 0,
            "rejects": 0,
            "transport_retries": 0,
            "received": 0,
            "delivered": 0,
        }
        self.latency = {"samples": 0, "p50_ns": 0, "p99_ns": 0, "max_ns": 0}
        self.reaction_latency = {"samples": 0, "p50_ns": 0, "p99_ns": 0, "max_ns": 0}

    def clear_paper_state(self) -> None:
        self.orders.clear()
        self.fills.clear()
        self.exchange_ledger_entries = 0
        self.exchange_ledger.clear()
        self.positions = {symbol: 0 for symbol in ("AAPL", "NVDA")}
        for positions in self.client_positions.values():
            positions.update({symbol: 0 for symbol in ("AAPL", "NVDA")})
        self.client_pnl_x10000 = {client: 0 for client in self.client_positions}
        self.client_stats = {client: {} for client in self.client_positions}
        for values in self.client_latency.values():
            values.update({"samples": 0, "p50_ns": 0, "p99_ns": 0, "max_ns": 0})
        for values in self.client_measurement_latency.values():
            values.update({"samples": 0, "p50_ns": 0, "p99_ns": 0, "max_ns": 0, "generation": 0})
        for values in self.client_software_latency.values():
            values.update(
                {
                    "samples": 0,
                    "queue_depth": 0,
                    "queue_full_drops": 0,
                    "queue_to_send": {"p50_ns": 0, "p99_ns": 0, "max_ns": 0},
                    "submit_to_final": {"p50_ns": 0, "p99_ns": 0, "max_ns": 0},
                }
            )
        for values in self.client_reaction_latency.values():
            values.update({"samples": 0, "p50_ns": 0, "p99_ns": 0, "max_ns": 0})
        self.pnl_x10000 = 0
        for key in self.stats:
            self.stats[key] = 0
        for values in (self.latency, self.reaction_latency):
            for key in values:
                values[key] = 0
        self.feed = self.empty_feed()

    def clear_gui_state(self) -> None:
        with self.condition:
            fresh = StateStore(self.transport_lab_enabled)
            preserved = {"lock", "condition", "sequence", "transport_lab_enabled",
                         "data_plane_mode", "data_plane_transition", "data_plane_owner",
                         "hardware_receipts", "strategy", "experiment_profile"}
            for key, value in vars(fresh).items():
                if key not in preserved:
                    setattr(self, key, value)
            self.gui_reset_ns = time.time_ns()
            self.condition.notify_all()

    @staticmethod
    def empty_feed() -> dict[str, Any]:
        return {
            "session": "",
            "next_expected": 0,
            "last_delivered": 0,
            "first_pending": 0,
            "highest_received": 0,
            "pending": 0,
            "duplicates": 0,
            "gaps": 0,
            "gap_messages": 0,
            "resync_required": False,
            "resync_reason": "",
            "pending_bytes": 0,
            "pending_limit": 32768,
            "discarded_after_gap": 0,
            "gap_size": 0,
            "gap_age_ms": 0,
            "path": "—",
            "integrity": "HEALTHY",
            "trading_gate": "OPEN",
        }

    def merge_feed(self, fields: dict[str, Any]) -> None:
        """用 Trader 状态或事件刷新 Feed 视图。"""
        aliases = {
            "session": ("session",),
            "next_expected": ("next_expected",),
            "last_delivered": ("last_delivered",),
            "first_pending": ("first_pending",),
            "highest_received": ("highest_received",),
            "pending": ("pending",),
            "duplicates": ("duplicates",),
            "gaps": ("gaps",),
            "gap_messages": ("gap_messages",),
            "resync_required": ("resync_required",),
            "resync_reason": ("resync_reason",),
            "pending_bytes": ("pending_bytes",),
            "pending_limit": ("pending_limit",),
            "discarded_after_gap": ("discarded_after_gap",),
            "gap_size": ("gap_size",),
            "gap_age_ms": ("gap_age_ms",),
            "path": ("path", "market_path"),
            "integrity": ("integrity",),
            "trading_gate": ("trading_gate",),
        }
        for dest, sources in aliases.items():
            for source in sources:
                if source in fields:
                    self.feed[dest] = fields[source]
                    break
        pending = int(self.feed.get("pending") or 0)
        gaps = int(self.feed.get("gaps") or 0)
        integrity = str(self.feed.get("integrity") or "")
        if not integrity:
            integrity = "GAP" if pending or gaps else "HEALTHY"
        self.feed["integrity"] = integrity
        self.feed["trading_gate"] = (
            "OPEN" if integrity == "HEALTHY" else
            "INHIBITED_FEED_GAP" if integrity == "GAP" else
            "INHIBITED_FEED_RECOVERING"
        )

    def ingest(self, event: dict[str, Any]) -> None:
        if event.get("schema") != "flle.trading-event.v1" or not isinstance(event.get("fields"), dict):
            return
        with self.condition:
            self.sequence += 1
            event = dict(event)
            event["gateway_sequence"] = self.sequence
            event["gateway_ns"] = time.time_ns()
            self.events.append(event)
            source = str(event.get("source", "unknown"))
            if source in self.health:
                self.health[source] = {"status": "ONLINE", "last_event_ns": event["gateway_ns"]}
            self.apply_event(event)
            self.condition.notify_all()

    def apply_event(self, event: dict[str, Any]) -> None:
        kind = str(event.get("kind"))
        fields = event["fields"]
        if fields.get("session"):
            self.session = str(fields["session"])
        if fields.get("market_mode"):
            self.market_mode = str(fields["market_mode"])
        if kind == "market_update":
            symbol = str(fields.get("symbol", ""))
            if symbol:
                self.instruments[symbol] = dict(fields)
                points = self.chart.setdefault(symbol, deque(maxlen=360))
                points.append([int(fields.get("source_timestamp_ns", 0)), int(fields.get("last_x10000", 0))])
            self.replay.update(
                {
                    "market_date": fields.get("market_date", self.replay["market_date"]),
                    "source_timestamp_ns": fields.get("source_timestamp_ns", self.replay["source_timestamp_ns"]),
                    "source_clock": fields.get("source_clock", self.replay["source_clock"]),
                    "loop": fields.get("replay_loop", self.replay["loop"]),
                    "speed": fields.get("replay_speed", self.replay["speed"]),
                    "status": "PLAYING",
                }
            )
        elif kind == "replay_started":
            self.replay.update({"status": "PLAYING", "loop": fields.get("loop", self.replay["loop"])})
            self.instruments.clear()
            self.trader_books.clear()
            self.chart.clear()
            self.clear_paper_state()
            self.feed["integrity"] = "RECOVERING"
            self.feed["trading_gate"] = "INHIBITED_FEED_RECOVERING"
            self.events.clear()
            self.events.append(event)
        elif kind == "replay_completed":
            self.replay.update({"status": "COMPLETE", "progress": 1.0})
        elif kind == "paper_reset":
            epoch = int(fields.get("paper_epoch", self.paper_epoch))
            if epoch != self.paper_epoch:
                self.clear_paper_state()
                self.paper_epoch = epoch
        elif kind == "book_applied":
            symbol = str(fields.get("symbol", ""))
            if symbol:
                self.trader_books[symbol] = dict(fields)
            self.merge_feed(fields)
        elif kind == "feed_receiver_status" and event.get("source") == "feed_receiver":
            self.feed_receiver = dict(fields)
            self.feed_receiver["last_event_ns"] = event["gateway_ns"]
        elif kind == "feed_gap":
            self.merge_feed(fields)
            self.feed["integrity"] = str(fields.get("integrity") or "GAP")
            self.feed["trading_gate"] = str(
                fields.get("trading_gate") or "INHIBITED_FEED_GAP"
            )
            self.feed["gap_size"] = fields.get("gap_size", 1)
            self.feed["pending"] = int(fields.get("pending", self.feed.get("pending", 0)))
        elif kind == "strategy_config":
            self.strategy.update(fields)
        elif kind == "order_queued":
            order = dict(fields)
            order.update(
                {
                    "state": "QUEUED",
                    "event_ns": event["gateway_ns"],
                    "market_date": self.replay["market_date"],
                    "source_clock": self.replay["source_clock"],
                    "replay_loop": self.replay["loop"],
                    "session": self.session,
                }
            )
            self.orders.append(order)
        elif kind == "order_complete":
            completed = dict(fields)
            completed.update({"state": fields.get("result", "COMPLETE"), "event_ns": event["gateway_ns"]})
            client_order_id = completed.get("client_order_id")
            for index in range(len(self.orders) - 1, -1, -1):
                if self.orders[index].get("client_order_id") == client_order_id:
                    merged = dict(self.orders[index])
                    merged.update(completed)
                    self.orders[index] = merged
                    completed = merged
                    break
            else:
                self.orders.append(completed)
            if fields.get("result") == "ORDER_EXECUTED":
                self.fills.append(completed)
            symbol = str(fields.get("symbol", ""))
            source = str(event.get("source", ""))
            if symbol and source in self.client_positions:
                self.client_positions[source][symbol] = int(fields.get("position", self.client_positions[source][symbol]))
                self.positions[symbol] = sum(values[symbol] for values in self.client_positions.values())
                self.client_pnl_x10000[source] = int(fields.get("pnl_x10000", self.client_pnl_x10000[source]))
                self.pnl_x10000 = sum(self.client_pnl_x10000.values())
        elif kind == "component_heartbeat" and event.get("source") in self.client_stats:
            source = str(event["source"])
            self.client_stats[source].update({key: fields[key] for key in self.stats if key in fields})
            for key in self.stats:
                self.stats[key] = sum(int(values.get(key, 0)) for values in self.client_stats.values())
            if source == "trader_auto":
                self.merge_feed(fields)
        elif kind == "component_stop" and event.get("source") in self.health:
            self.health[event["source"]]["status"] = "OFFLINE"

    def merge_component_state(self, component: str, state: dict[str, Any]) -> None:
        with self.condition:
            self.health[component] = {"status": state.get("status", "ONLINE"), "last_event_ns": time.time_ns()}
            if component == "exchange":
                self.session = state.get("session", self.session)
                self.market_mode = state.get("market_mode", self.market_mode)
                self.market_network = {key: state[key] for key in (
                    "market_schema", "market_group_a", "market_group_b",
                    "market_port_a", "market_port_b") if key in state}
                self.replay.update(
                    {
                        "source": state.get("source", self.replay["source"]),
                        "market_date": state.get("market_date", self.replay["market_date"]),
                        "status": state.get("replay_status", self.replay["status"]),
                        "speed": state.get("replay_speed", self.replay["speed"]),
                        "loop": state.get("replay_loop", self.replay["loop"]),
                        "source_timestamp_ns": state.get("source_timestamp_ns", self.replay["source_timestamp_ns"]),
                        "source_clock": state.get("source_clock", self.replay["source_clock"]),
                        "first_source_timestamp_ns": state.get("first_source_timestamp_ns", self.replay["first_source_timestamp_ns"]),
                        "last_source_timestamp_ns": state.get("last_source_timestamp_ns", self.replay["last_source_timestamp_ns"]),
                        "first_source_clock": state.get("first_source_clock", self.replay["first_source_clock"]),
                        "last_source_clock": state.get("last_source_clock", self.replay["last_source_clock"]),
                        "window": state.get("replay_window", self.replay["window"]),
                        "progress": state.get("replay_progress", self.replay["progress"]),
                        "remaining_source_ns": state.get("remaining_source_ns", self.replay["remaining_source_ns"]),
                        "estimated_remaining_wall_ns": state.get("estimated_remaining_wall_ns", self.replay["estimated_remaining_wall_ns"]),
                        "messages": state.get("replay_messages", self.replay["messages"]),
                    }
                )
                self.exchange_ledger_entries = int(state.get("paper_ledger_entries", self.exchange_ledger_entries))
                self.exchange_ledger = list(state.get("paper_ledger", self.exchange_ledger))
            if component in self.client_positions:
                if state.get("session") and state.get("session") != self.session:
                    self.condition.notify_all()
                    return
                if component == "trader_auto":
                    self.strategy.update(state.get("strategy", {}))
                self.paper_epoch = int(state.get("paper_epoch", self.paper_epoch))
                self.client_positions[component].update(state.get("positions", {}))
                self.client_pnl_x10000[component] = int(state.get("pnl_x10000", self.client_pnl_x10000[component]))
                self.client_stats[component].update(state.get("stats", {}))
                self.client_latency[component].update(state.get("latency", {}))
                self.client_measurement_latency[component].update(state.get("measurement_latency", {}))
                self.client_software_latency[component].update(state.get("software_latency", {}))
                self.client_reaction_latency[component].update(state.get("reaction_latency", {}))
                for symbol in self.positions:
                    self.positions[symbol] = sum(int(values.get(symbol, 0)) for values in self.client_positions.values())
                self.pnl_x10000 = sum(self.client_pnl_x10000.values())
                for key in self.stats:
                    self.stats[key] = sum(int(values.get(key, 0)) for values in self.client_stats.values())
                if component == "trader_auto":
                    self.latency.update(state.get("latency", {}))
                    self.reaction_latency.update(state.get("reaction_latency", {}))
                    self.merge_feed(state)
                elif (
                    self.transport_lab_enabled
                    and self.experiment_profile == "TRANSPORT"
                    and component in TRANSPORT_TRADER_CLIENTS + ("trader_manual",)
                    and state.get("market_protocol") == "COMMON_GATEWAY_BOOK"
                    and not self.health["trader_auto"].get("last_event_ns")
                    and not self.feed_receiver
                    and not self.feed.get("session")
                    and self.feed.get("integrity") != "GAP"
                ):
                    # Order-only clients use an explicit price from the gateway.
                    # After replay_started there is no Guardian to clear its
                    # RECOVERING flag. Use the client's actual gate in this
                    # profile; never overwrite an observed feed/Guardian gate.
                    self.merge_feed({**state, "path": "COMMON_GATEWAY_BOOK"})
            self.condition.notify_all()

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            now = time.time_ns()
            health = {name: dict(value) for name, value in self.health.items()}
            health["gateway"] = {"status": "ONLINE", "last_event_ns": now}
            for value in health.values():
                if value["status"] == "ONLINE" and now - int(value["last_event_ns"]) > 4_000_000_000:
                    value["status"] = "STALE"
            # A verified mode deliberately stops the other clients. Preserve
            # their last statistics, but display them as waiting for activation.
            inactive: tuple[str, ...] = ()
            if self.transport_lab_enabled and self.data_plane_transition == "READY":
                if self.data_plane_mode == "SFC" and self.data_plane_owner == "sfc":
                    inactive = ("trader_dpdk",)
                elif self.data_plane_mode == "DPDK" and self.data_plane_owner == "vfio-pci":
                    inactive = ("trader_manual", "trader_onload", "trader_tcpdirect")
            for name in inactive:
                health[name]["status"] = "WAITING"
            receiver = dict(self.feed_receiver)
            if receiver and now - int(receiver.get("last_event_ns", 0)) > 4_000_000_000:
                receiver["status"] = "STALE"
            feed = dict(self.feed)
            # Integrity describes the sequence already consumed. A vanished
            # consumer cannot report a new GAP; expire its liveness separately.
            # DPDK deliberately releases the shared receiver and Guardian.
            feed["availability"] = "UNKNOWN"
            if self.transport_lab_enabled and self.data_plane_mode == "DPDK":
                feed["availability"] = "INACTIVE"
            elif self.feed_receiver or self.health["trader_auto"].get("last_event_ns"):
                feed["availability"] = (
                    "ACTIVE" if receiver.get("status") == "ONLINE"
                    and health["trader_auto"]["status"] == "ONLINE" else "STALE"
                )
            return {
                "schema": "flle.terminal-state.v1",
                "historical_market": True,
                "paper_execution": True,
                "features": {"transport_lab": self.transport_lab_enabled},
                "experiment_profile": self.experiment_profile,
                "data_plane_mode": self.data_plane_mode,
                "data_plane_transition": self.data_plane_transition,
                "data_plane_owner": self.data_plane_owner,
                "hardware_receipts": {
                    name: dict(receipt)
                    for name, receipt in self.hardware_receipts.items()
                },
                "gateway_sequence": self.sequence,
                "session": self.session,
                "market_mode": self.market_mode,
                "market_network": dict(self.market_network),
                "replay": dict(self.replay),
                "instruments": self.instruments,
                "trader_books": self.trader_books,
                "chart": {symbol: list(points) for symbol, points in self.chart.items()},
                "orders": self.visible_history(self.orders),
                "fills": self.visible_history(self.fills),
                "health": health,
                "feed": feed,
                "feed_receiver": receiver,
                "strategy": dict(self.strategy),
                "positions": dict(self.positions),
                "client_positions": {name: dict(values) for name, values in self.client_positions.items()},
                "client_stats": {name: dict(values) for name, values in self.client_stats.items()},
                "client_latency": {name: dict(values) for name, values in self.client_latency.items()},
                "client_measurement_latency": {
                    name: dict(values) for name, values in self.client_measurement_latency.items()
                },
                "client_software_latency": {
                    name: dict(values) for name, values in self.client_software_latency.items()
                },
                "client_reaction_latency": {name: dict(values) for name, values in self.client_reaction_latency.items()},
                "paper_epoch": self.paper_epoch,
                "gui_reset_ns": self.gui_reset_ns,
                "exchange_ledger_entries": self.exchange_ledger_entries,
                "exchange_ledger": list(self.exchange_ledger),
                "pnl_x10000": self.pnl_x10000,
                "stats": dict(self.stats),
                "latency": dict(self.latency),
                "reaction_latency": dict(self.reaction_latency),
                "server_ns": now,
            }

    def merge_data_plane(self, state: dict[str, Any]) -> None:
        with self.condition:
            self.experiment_profile = str(state.get("experiment_profile", "TRANSPORT"))
            mode = str(state.get("mode", self.data_plane_mode)).upper()
            if mode in {"SFC", "DPDK"}:
                self.data_plane_mode = mode
            self.data_plane_transition = str(
                state.get("transition", self.data_plane_transition)
            ).upper()
            self.data_plane_owner = str(
                state.get("owner", self.data_plane_owner)
            )
            receipts = state.get("hardware_receipts")
            if isinstance(receipts, dict):
                self.hardware_receipts = {
                    str(name): dict(receipt)
                    for name, receipt in receipts.items()
                    if isinstance(receipt, dict)
                }
            self.condition.notify_all()

    @staticmethod
    def visible_history(records: deque[dict[str, Any]], per_origin: int = 40) -> list[dict[str, Any]]:
        """Return a bounded, chronological view without one origin evicting the other."""
        values = list(records)
        manual = [value for value in values if value.get("origin") == "MANUAL_GUI"][-per_origin:]
        automatic = [value for value in values if value.get("origin") == "AUTO_STRATEGY"][-per_origin:]
        other = [value for value in values if value.get("origin") not in ("MANUAL_GUI", "AUTO_STRATEGY")][-per_origin:]
        return sorted(manual + automatic + other, key=lambda value: int(value.get("event_ns", 0)))

    def after(self, sequence: int, limit: int = 500) -> list[dict[str, Any]]:
        with self.lock:
            return [event for event in self.events if event["gateway_sequence"] > sequence][:limit]


def render_prometheus(state: dict[str, Any]) -> str:
    """Render low-cardinality DISPLAY metrics without entering the C++ hot path."""
    lines = [
        "# HELP flle_component_up Whether the latest component state is ONLINE.",
        "# TYPE flle_component_up gauge",
    ]
    component_names = ["exchange", "trader_auto", "trader_manual"]
    component_names.extend(
        name
        for name in TRANSPORT_TRADER_CLIENTS
        if name in state.get("health", {})
    )
    component_names.append("gateway")
    for component in component_names:
        online = 1 if state.get("health", {}).get(component, {}).get("status") == "ONLINE" else 0
        lines.append(f'flle_component_up{{component="{component}"}} {online}')

    replay = state.get("replay", {})
    feed = state.get("feed", {})
    lines.extend(
        [
            "# HELP flle_replay_progress_ratio Current regular-session replay progress from 0 to 1.",
            "# TYPE flle_replay_progress_ratio gauge",
            f'flle_replay_progress_ratio {float(replay.get("progress", 0.0)):.9f}',
            "# HELP flle_replay_source_time_seconds Historical market time since midnight.",
            "# TYPE flle_replay_source_time_seconds gauge",
            f'flle_replay_source_time_seconds {int(replay.get("source_timestamp_ns", 0)) / 1_000_000_000:.9f}',
            "# HELP flle_market_messages_total ITCH messages replayed in the current paper epoch.",
            "# TYPE flle_market_messages_total counter",
            f'flle_market_messages_total {int(replay.get("messages", 0))}',
            "# HELP flle_feed_pending_messages Messages waiting behind a sequence gap.",
            "# TYPE flle_feed_pending_messages gauge",
            f'flle_feed_pending_messages {int(feed.get("pending", 0))}',
            "# HELP flle_feed_gap_messages Missing sequence count currently blocking delivery.",
            "# TYPE flle_feed_gap_messages gauge",
            f'flle_feed_gap_messages {int(feed.get("gaps", 0))}',
            "# HELP flle_feed_duplicates Duplicate market-data copies seen in the current epoch.",
            "# TYPE flle_feed_duplicates gauge",
            f'flle_feed_duplicates {int(feed.get("duplicates", 0))}',
            "# HELP flle_order_rtt_samples C++ order RTT samples retained in the current epoch.",
            "# TYPE flle_order_rtt_samples gauge",
            "# HELP flle_order_rtt_seconds C++ OUCH send to final response RTT summary.",
            "# TYPE flle_order_rtt_seconds gauge",
            "# HELP flle_baseline_order_rtt_samples C++ samples in the current fixed measurement generation.",
            "# TYPE flle_baseline_order_rtt_samples gauge",
            "# HELP flle_baseline_order_rtt_seconds C++ fixed-profile OUCH RTT summary.",
            "# TYPE flle_baseline_order_rtt_seconds gauge",
            "# HELP flle_software_measurement_samples C++ samples in the current software profile.",
            "# TYPE flle_software_measurement_samples gauge",
            "# HELP flle_software_queue_to_send_seconds C++ queue ingress to OUCH send summary.",
            "# TYPE flle_software_queue_to_send_seconds gauge",
            "# HELP flle_software_submit_to_final_seconds C++ queue ingress to final response summary.",
            "# TYPE flle_software_submit_to_final_seconds gauge",
            "# HELP flle_order_queue_depth Current C++ order queue depth.",
            "# TYPE flle_order_queue_depth gauge",
            "# HELP flle_order_thread_cpu Last CPU observed by the C++ order thread.",
            "# TYPE flle_order_thread_cpu gauge",
            "# HELP flle_order_rx_cpu Last incoming CPU reported by the order socket.",
            "# TYPE flle_order_rx_cpu gauge",
            "# HELP flle_paper_orders_total Paper orders submitted in the current epoch.",
            "# TYPE flle_paper_orders_total counter",
            "# HELP flle_paper_fills_total Paper fills received in the current epoch.",
            "# TYPE flle_paper_fills_total counter",
            "# HELP flle_paper_rejects_total Paper rejects received in the current epoch.",
            "# TYPE flle_paper_rejects_total counter",
        ]
    )
    metric_clients = [
        ("trader_auto", "auto"),
        # Keep the established Ch02--04 Prometheus identity stable.  The
        # transport console names this path Socket in the UI, but changing
        # the time-series label would break the earlier dashboards.
        ("trader_manual", "manual"),
        ("trader_onload", "onload"),
        ("trader_tcpdirect", "tcpdirect"),
        ("trader_dpdk", "dpdk"),
    ]
    for source, client in metric_clients:
        if source not in state.get("client_latency", {}):
            continue
        latency = state.get("client_latency", {}).get(source, {})
        measurement = state.get("client_measurement_latency", {}).get(source, {})
        software = state.get("client_software_latency", {}).get(source, {})
        stats = state.get("client_stats", {}).get(source, {})
        lines.append(f'flle_order_rtt_samples{{client="{client}"}} {int(latency.get("samples", 0))}')
        for key, statistic in (("p50_ns", "p50"), ("p99_ns", "p99"), ("max_ns", "max")):
            value = int(latency.get(key, 0)) / 1_000_000_000
            lines.append(f'flle_order_rtt_seconds{{client="{client}",stat="{statistic}"}} {value:.9f}')
        lines.append(
            f'flle_baseline_order_rtt_samples{{client="{client}"}} '
            f'{int(measurement.get("samples", 0))}'
        )
        for key, statistic in (("p50_ns", "p50"), ("p99_ns", "p99"), ("max_ns", "max")):
            value = int(measurement.get(key, 0)) / 1_000_000_000
            lines.append(
                f'flle_baseline_order_rtt_seconds{{client="{client}",stat="{statistic}"}} '
                f'{value:.9f}'
            )
        mode = str(software.get("queue_mode", "DEQUE_CV"))
        placement = "pinned" if int(software.get("order_thread_allowed_count", 0)) == 1 else "floating"
        software_labels = f'client="{client}",mode="{mode}",placement="{placement}"'
        lines.append(
            f'flle_software_measurement_samples{{{software_labels}}} '
            f'{int(software.get("samples", 0))}'
        )
        for family, metric in (
            ("queue_to_send", "flle_software_queue_to_send_seconds"),
            ("submit_to_final", "flle_software_submit_to_final_seconds"),
        ):
            values = software.get(family, {})
            for key, statistic in (("p50_ns", "p50"), ("p99_ns", "p99"), ("max_ns", "max")):
                value = int(values.get(key, 0)) / 1_000_000_000
                lines.append(
                    f'{metric}{{{software_labels},stat="{statistic}"}} {value:.9f}'
                )
        lines.append(f'flle_order_queue_depth{{client="{client}",mode="{mode}"}} {int(software.get("queue_depth", 0))}')
        lines.append(f'flle_order_thread_cpu{{client="{client}"}} {int(software.get("order_thread_cpu", -1))}')
        lines.append(f'flle_order_rx_cpu{{client="{client}"}} {int(software.get("order_rx_cpu", -1))}')
        lines.append(f'flle_paper_orders_total{{client="{client}"}} {int(stats.get("orders", 0))}')
        lines.append(f'flle_paper_fills_total{{client="{client}"}} {int(stats.get("fills", 0))}')
        lines.append(f'flle_paper_rejects_total{{client="{client}"}} {int(stats.get("rejects", 0))}')
    return "\n".join(lines) + "\n"


def send_command(host: str, port: int, command: str, timeout: float = 2.0) -> dict[str, Any]:
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.sendall(command.encode("ascii") + b"\n")
        sock.shutdown(socket.SHUT_WR)
        chunks: list[bytes] = []
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
            if b"\n" in chunk:
                break
    response = json.loads(b"".join(chunks).splitlines()[0])
    if response.get("error"):
        raise ValueError(str(response["error"]))
    return response


def controller_request(
    base_url: str, path: str, payload: dict[str, Any] | None = None
) -> dict[str, Any]:
    if not base_url:
        raise ValueError("data-plane controller is not configured")
    body = None if payload is None else json.dumps(payload).encode("ascii")
    request = Request(
        base_url.rstrip("/") + path,
        data=body,
        method="GET" if payload is None else "POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        # A failed mode change may consume the controller's 300 s action
        # window and then its independent 300 s direct-SFC recovery window.
        with urlopen(request, timeout=610) as response:
            result = json.loads(response.read())
    except HTTPError as error:
        try:
            detail = json.loads(error.read()).get("error", str(error))
        except (json.JSONDecodeError, AttributeError):
            detail = str(error)
        raise ValueError(str(detail)) from error
    except (URLError, TimeoutError, OSError, http.client.HTTPException) as error:
        raise ValueError(f"data-plane controller unavailable: {error}") from error
    if not isinstance(result, dict):
        raise ValueError("data-plane controller returned invalid state")
    if result.get("error"):
        raise ValueError(str(result["error"]))
    return result


class Gateway:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.store = StateStore(args.transport_lab)
        self.stop_event = threading.Event()
        self.action_lock = threading.RLock()
        self.resetting = threading.Event()
        self.web_root = Path(args.web_root).resolve()
        self.telemetry_sources = {
            "exchange": socket.gethostbyname(args.exchange_host),
            "trader_auto": socket.gethostbyname(args.trader_host),
            "trader_manual": socket.gethostbyname(args.trader_host),
            "feed_receiver": socket.gethostbyname(args.trader_host),
        }
        if args.transport_lab:
            self.telemetry_sources.update(
                {
                    source: socket.gethostbyname(args.trader_host)
                    for source in TRANSPORT_TRADER_CLIENTS
                }
            )

    def telemetry_loop(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.args.bind_ip, self.args.telemetry_port))
        sock.settimeout(0.5)
        while not self.stop_event.is_set():
            try:
                payload, peer = sock.recvfrom(16_384)
                event = json.loads(payload.decode("utf-8"))
                if (
                    isinstance(event, dict)
                    and self.telemetry_sources.get(str(event.get("source"))) == peer[0]
                ):
                    with self.store.condition:
                        if not self.resetting.is_set():
                            self.store.ingest(event)
            except socket.timeout:
                continue
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
        sock.close()

    def component_targets(self) -> dict[str, tuple[str, int]]:
        targets = {
            "exchange": (self.args.exchange_host, self.args.exchange_management_port),
            "trader_auto": (self.args.trader_host, self.args.trader_management_port),
            "trader_manual": (self.args.trader_host, self.args.manual_trader_management_port),
        }
        if self.args.transport_lab:
            targets.update(
                {
                    "trader_onload": (
                        self.args.trader_host,
                        self.args.onload_trader_management_port,
                    ),
                    "trader_tcpdirect": (
                        self.args.trader_host,
                        self.args.tcpdirect_trader_management_port,
                    ),
                    "trader_dpdk": (
                        self.args.trader_host,
                        self.args.dpdk_trader_management_port,
                    ),
                }
            )
        return targets

    def state_poll_loop(self) -> None:
        while not self.stop_event.wait(1.0):
            for component, (host, port) in self.component_targets().items():
                try:
                    with self.action_lock:
                        self.store.merge_component_state(component, send_command(host, port, "STATE", timeout=0.5))
                except (OSError, ValueError, json.JSONDecodeError):
                    continue
            if self.args.transport_lab and self.args.data_plane_controller_url:
                try:
                    self.store.merge_data_plane(
                        controller_request(
                            self.args.data_plane_controller_url, "/state"
                        )
                    )
                except ValueError:
                    with self.store.condition:
                        self.store.data_plane_transition = "CONTROLLER_OFFLINE"
                        self.store.condition.notify_all()

    def restart_and_clear(self) -> dict[str, Any]:
        """The browser reset clears real clients; ordinary replay keeps its contract."""
        with self.action_lock:
            self.resetting.set()
            try:
                before = send_command(self.args.exchange_host, self.args.exchange_management_port, "STATE")
                if self.args.transport_lab:
                    receipt = controller_request(self.args.data_plane_controller_url, "/reset-paper", {})
                    if receipt.get("paper_reset") is not True:
                        raise ValueError("未收到客户端清零确认，交易重置未完成")
                    self.store.merge_data_plane(receipt)
                response = send_command(self.args.exchange_host, self.args.exchange_management_port, "REPLAY|RESTART")
                if response.get("error"):
                    raise ValueError(str(response["error"]))
                deadline = time.monotonic() + 15
                while True:
                    exchange = send_command(self.args.exchange_host, self.args.exchange_management_port, "STATE")
                    if exchange.get("session") and exchange["session"] != before.get("session"):
                        break
                    if time.monotonic() >= deadline:
                        raise ValueError("行情未进入新 Session，交易重置未完成")
                    time.sleep(0.1)
                # Market-receiving clients reset asynchronously on the new session.
                while True:
                    auto = send_command(self.args.trader_host, self.args.trader_management_port, "STATE")
                    if auto.get("session") == exchange["session"]:
                        break
                    if time.monotonic() >= deadline:
                        raise ValueError("行情接收器未确认新 Session，重置未完成")
                    time.sleep(0.1)
                # The queue panel has its own collector; clear its authoritative history.
                try:
                    with urlopen(Request("http://127.0.0.1:8089/api/lanz/reset", data=b"", method="POST"), timeout=5) as reply:
                        if json.loads(reply.read()).get("cleared") is not True:
                            raise ValueError("交换机队列事件未确认清空")
                except URLError as error:
                    # Some chapters have no collector. Other failures must be visible.
                    if not isinstance(error.reason, ConnectionRefusedError):
                        raise ValueError(f"交换机队列事件清空失败: {error}") from error
                self.store.clear_gui_state()
                for component, (host, port) in self.component_targets().items():
                    try:
                        state = send_command(host, port, "STATE", timeout=1)
                    except OSError:
                        inactive = {"trader_dpdk"} if self.store.data_plane_mode == "SFC" else {"trader_manual", "trader_onload", "trader_tcpdirect"}
                        if component in inactive:
                            continue
                        raise
                    self.store.merge_component_state(component, state)
                return {"ok": True, "cleared_trades": True, "session": exchange["session"]}
            finally:
                self.resetting.clear()

    def handler(self) -> type[BaseHTTPRequestHandler]:
        gateway = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def json_response(self, status: int, payload: Any) -> None:
                body = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("ascii")
                self.send_response(status)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def text_response(self, status: int, body: str, content_type: str) -> None:
                encoded = body.encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

            def request_json(self) -> dict[str, Any]:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 0 or length > 65_536:
                    raise ValueError("request body too large")
                value = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(value, dict):
                    raise ValueError("request body must be an object")
                return value

            def do_GET(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                if parsed.path == "/api/state":
                    self.json_response(200, gateway.store.snapshot())
                    return
                if parsed.path == "/api/transport-lab":
                    state = gateway.store.snapshot()
                    clients = [
                        "trader_manual",
                        "trader_onload",
                        "trader_tcpdirect",
                        "trader_dpdk",
                    ]
                    self.json_response(
                        200,
                        {
                            "schema": "flle.transport-lab-state.v1",
                            "mode": state["data_plane_mode"],
                            "transition": state["data_plane_transition"],
                            "owner": state["data_plane_owner"],
                            "hardware_receipts": state["hardware_receipts"],
                            "clients": {
                                name: {
                                    "health": state["health"].get(name, {}),
                                    "stats": state["client_stats"].get(name, {}),
                                    "latency": state["client_latency"].get(name, {}),
                                    "measurement_latency": state[
                                        "client_measurement_latency"
                                    ].get(name, {}),
                                    "software": state[
                                        "client_software_latency"
                                    ].get(name, {}),
                                }
                                for name in clients
                            },
                        },
                    )
                    return
                if parsed.path == "/metrics":
                    self.text_response(
                        200,
                        render_prometheus(gateway.store.snapshot()),
                        "text/plain; version=0.0.4; charset=utf-8",
                    )
                    return
                if parsed.path == "/api/health":
                    state = gateway.store.snapshot()
                    self.json_response(
                        200,
                        {
                            "schema": "flle.terminal-health.v1",
                            "session": state["session"],
                            "market_mode": state["market_mode"],
                            "replay": state["replay"],
                            "health": state["health"],
                            "feed": state["feed"],
                            "stats": state["stats"],
                            "latency": state["latency"],
                        },
                    )
                    return
                if parsed.path == "/api/events":
                    query = parse_qs(parsed.query)
                    after = int(query.get("after", ["0"])[0])
                    self.json_response(200, {"events": gateway.store.after(after)})
                    return
                if parsed.path == "/api/stream":
                    self.stream_events(parsed)
                    return
                relative = "index.html" if parsed.path == "/" else parsed.path.lstrip("/")
                target = (gateway.web_root / relative).resolve()
                if gateway.web_root not in target.parents and target != gateway.web_root:
                    self.send_error(403)
                    return
                if not target.is_file():
                    self.send_error(404)
                    return
                body = target.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def stream_events(self, parsed: Any) -> None:
                after = int(parse_qs(parsed.query).get("after", ["0"])[0])
                if self.headers.get("Last-Event-ID"):
                    after = max(after, int(self.headers["Last-Event-ID"]))
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.end_headers()
                try:
                    while not gateway.stop_event.is_set():
                        with gateway.store.condition:
                            events = gateway.store.after(after)
                            if not events:
                                gateway.store.condition.wait(timeout=10)
                                events = gateway.store.after(after)
                        if not events:
                            self.wfile.write(b": heartbeat\n\n")
                            self.wfile.flush()
                            continue
                        for event in events:
                            after = event["gateway_sequence"]
                            body = json.dumps(event, separators=(",", ":"), ensure_ascii=True)
                            self.wfile.write(f"id: {after}\nevent: trading\ndata: {body}\n\n".encode("ascii"))
                        self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    return

            def do_POST(self) -> None:  # noqa: N802
                if gateway.resetting.is_set():
                    self.json_response(409, {"error": "正在重置交易，请稍候"})
                    return
                with gateway.action_lock:
                    self.handle_post()

            def handle_post(self) -> None:
                try:
                    request = self.request_json()
                    if self.path == "/api/order":
                        feed = gateway.store.snapshot().get("feed", {})
                        if feed.get("availability") == "STALE":
                            raise ValueError("FEED_NOT_LIVE")
                        if str(feed.get("integrity") or "HEALTHY") != "HEALTHY":
                            raise ValueError("FEED_NOT_HEALTHY")
                        symbol = str(request.get("symbol", "AAPL")).upper()
                        side = str(request.get("side", "BUY")).upper()
                        quantity = int(request.get("quantity", 10))
                        price = int(request.get("limit_price_x10000", 0) or 0)
                        transport = str(request.get("transport", "SOCKET")).upper()
                        # Resolve an empty GUI price once in the common control
                        # plane.  Every Chapter 06 client therefore receives
                        # the same explicit limit price instead of consulting
                        # four books at slightly different instants.
                        if not price:
                            state = gateway.store.snapshot()
                            book = state.get("instruments", {}).get(symbol, {})
                            if not book.get("bids") or not book.get("asks"):
                                book = state.get("trader_books", {}).get(symbol, {})
                            levels = book.get("asks" if side == "BUY" else "bids", [])
                            if not levels or not levels[0] or int(levels[0][0]) <= 0:
                                raise ValueError("book is not ready")
                            price = int(levels[0][0])
                        routes = {
                            "SOCKET": (
                                "trader_manual",
                                gateway.args.manual_trader_management_port,
                            )
                        }
                        if gateway.args.transport_lab:
                            routes.update(
                                {
                                    "OPENONLOAD": (
                                        "trader_onload",
                                        gateway.args.onload_trader_management_port,
                                    ),
                                    "TCPDIRECT": (
                                        "trader_tcpdirect",
                                        gateway.args.tcpdirect_trader_management_port,
                                    ),
                                    "DPDK": (
                                        "trader_dpdk",
                                        gateway.args.dpdk_trader_management_port,
                                    ),
                                }
                            )
                        if transport not in routes:
                            raise ValueError("transport is not enabled")
                        required_mode = "DPDK" if transport == "DPDK" else "SFC"
                        plane = gateway.store.snapshot()
                        if plane.get("data_plane_transition") != "READY":
                            raise ValueError("data plane is switching; wait for READY")
                        if plane.get("data_plane_mode") != required_mode:
                            raise ValueError(
                                f"{transport} requires {required_mode}_ACTIVE"
                            )
                        component, management_port = routes[transport]
                        status = gateway.store.snapshot()["health"].get(
                            component, {}
                        ).get("status")
                        if status != "ONLINE":
                            raise ValueError(f"{transport} client is not ONLINE")
                        response = send_command(
                            gateway.args.trader_host,
                            management_port,
                            f"ORDER|{symbol}|{side}|{quantity}|{price}",
                        )
                        response["transport"] = transport
                        self.json_response(202, response)
                    elif self.path == "/api/data-plane":
                        if not gateway.args.transport_lab:
                            raise ValueError("transport lab is not enabled")
                        mode = str(request.get("mode", "")).upper()
                        if mode not in {"BASELINE", "SFC", "DPDK"}:
                            raise ValueError("mode must be BASELINE, SFC or DPDK")
                        with gateway.store.condition:
                            gateway.store.data_plane_transition = "SWITCHING"
                            gateway.store.condition.notify_all()
                        result = controller_request(
                            gateway.args.data_plane_controller_url,
                            "/mode",
                            {"mode": mode},
                        )
                        gateway.store.merge_data_plane(result)
                        self.json_response(200, result)
                    elif self.path == "/api/strategy":
                        current = gateway.store.snapshot()["strategy"]
                        current.update(request)
                        response = send_command(
                            gateway.args.trader_host,
                            gateway.args.trader_management_port,
                            "STRATEGY|{}|{}|{}|{}|{}".format(
                                1 if current["enabled"] else 0,
                                float(current["imbalance_threshold"]),
                                int(current["quantity"]),
                                int(current["max_position"]),
                                int(current["cooldown_ms"]),
                            ),
                        )
                        self.json_response(200, response)
                    elif self.path == "/api/market":
                        response = send_command(
                            gateway.args.exchange_host,
                            gateway.args.exchange_management_port,
                            "MARKET|{}".format(str(request.get("market_mode", gateway.store.market_mode)).upper()),
                        )
                        self.json_response(200, response)
                    elif self.path == "/api/replay":
                        action = str(request.get("action", "")).upper()
                        clear = request.get("clear_trades", False)
                        if not isinstance(clear, bool):
                            raise ValueError("clear_trades must be a boolean")
                        if clear:
                            if action != "RESTART":
                                raise ValueError("clear_trades requires RESTART")
                            self.json_response(200, gateway.restart_and_clear())
                            return
                        if action in {"PAUSE", "RESUME", "RESTART"}:
                            command = f"REPLAY|{action}"
                        elif action == "SPEED":
                            command = f"REPLAY|SPEED|{float(request.get('speed', 1.0))}"
                        else:
                            raise ValueError("invalid replay action")
                        response = send_command(
                            gateway.args.exchange_host,
                            gateway.args.exchange_management_port,
                            command,
                        )
                        self.json_response(200, response)
                    else:
                        self.json_response(404, {"error": "not found"})
                except (ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
                    self.json_response(400, {"error": str(exc)})

            def log_message(self, _format: str, *_args: Any) -> None:
                return

        return Handler

    def run(self) -> None:
        telemetry = threading.Thread(target=self.telemetry_loop, name="telemetry", daemon=True)
        poller = threading.Thread(target=self.state_poll_loop, name="state-poller", daemon=True)
        telemetry.start()
        poller.start()
        server = ThreadingHTTPServer((self.args.bind_ip, self.args.http_port), self.handler())
        try:
            server.serve_forever(poll_interval=0.5)
        finally:
            self.stop_event.set()
            server.server_close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bind-ip", default="10.1.1.101")
    parser.add_argument("--http-port", type=int, default=8088)
    parser.add_argument("--telemetry-port", type=int, default=46120)
    parser.add_argument("--exchange-host", default="10.1.1.1")
    parser.add_argument("--exchange-management-port", type=int, default=48120)
    parser.add_argument("--trader-host", default="10.1.1.2")
    parser.add_argument("--trader-management-port", type=int, default=48121)
    parser.add_argument("--manual-trader-management-port", type=int, default=48122)
    parser.add_argument("--onload-trader-management-port", type=int, default=48123)
    parser.add_argument("--tcpdirect-trader-management-port", type=int, default=48124)
    parser.add_argument("--dpdk-trader-management-port", type=int, default=48125)
    parser.add_argument("--transport-lab", action="store_true")
    parser.add_argument("--data-plane-controller-url", default="")
    parser.add_argument("--web-root", default=str(Path(__file__).resolve().parents[1] / "web"))
    return parser.parse_args()


if __name__ == "__main__":
    Gateway(parse_args()).run()
