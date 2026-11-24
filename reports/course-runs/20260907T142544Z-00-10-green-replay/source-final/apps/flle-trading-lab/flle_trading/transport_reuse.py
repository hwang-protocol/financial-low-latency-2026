#!/usr/bin/env python3
"""Classify whether Chapter 06 run 01 may reuse the current live run."""

from __future__ import annotations

import json
import sys
from typing import Any


SFC_CLIENTS = ("trader_manual", "trader_onload", "trader_tcpdirect")


def _load_object(raw: str) -> dict[str, Any] | None:
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    return value if isinstance(value, dict) else None


def classify_reuse(
    *,
    controller_ok: bool,
    gateway_ok: bool,
    quiescent: bool,
    control: dict[str, Any] | None,
    api: dict[str, Any] | None,
) -> str:
    """Return REUSABLE, CLEAN, or INCOMPLETE for the observed lab state."""
    control_ready = bool(
        control
        and control.get("mode") == "SFC"
        and control.get("transition") == "READY"
        and control.get("owner") == "sfc"
    )
    clients = api.get("clients") if api else None
    api_ready = bool(
        api
        and api.get("mode") == "SFC"
        and api.get("transition") == "READY"
        and api.get("owner") == "sfc"
        and isinstance(clients, dict)
        and all(
            isinstance(clients.get(name), dict)
            and isinstance(clients[name].get("health"), dict)
            and clients[name]["health"].get("status") == "ONLINE"
            for name in SFC_CLIENTS
        )
    )
    if controller_ok and gateway_ok and control_ready and api_ready:
        return "REUSABLE"
    if quiescent:
        return "CLEAN"
    return "INCOMPLETE"


def main(argv: list[str]) -> int:
    if len(argv) != 6 or any(value not in {"0", "1"} for value in argv[1:4]):
        print(
            "usage: transport_reuse.py CONTROLLER_OK GATEWAY_OK QUIESCENT "
            "CONTROL_JSON API_JSON",
            file=sys.stderr,
        )
        return 2
    print(
        classify_reuse(
            controller_ok=argv[1] == "1",
            gateway_ok=argv[2] == "1",
            quiescent=argv[3] == "1",
            control=_load_object(argv[4]),
            api=_load_object(argv[5]),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
