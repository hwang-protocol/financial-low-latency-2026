from pathlib import Path
import subprocess
import sys
import unittest


APP_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_ROOT))

from flle_trading.transport_reuse import classify_reuse  # noqa: E402


def ready_control() -> dict[str, object]:
    return {"mode": "SFC", "transition": "READY", "owner": "sfc"}


def ready_api() -> dict[str, object]:
    return {
        "mode": "SFC",
        "transition": "READY",
        "owner": "sfc",
        "clients": {
            name: {"health": {"status": "ONLINE"}}
            for name in ("trader_manual", "trader_onload", "trader_tcpdirect")
        },
    }


class TransportReusePolicyTest(unittest.TestCase):
    def test_complete_same_run_is_reusable(self) -> None:
        self.assertEqual(
            classify_reuse(
                controller_ok=True,
                gateway_ok=True,
                quiescent=False,
                control=ready_control(),
                api=ready_api(),
            ),
            "REUSABLE",
        )

    def test_dead_controller_makes_otherwise_ready_stack_incomplete(self) -> None:
        self.assertEqual(
            classify_reuse(
                controller_ok=False,
                gateway_ok=True,
                quiescent=False,
                control=ready_control(),
                api=ready_api(),
            ),
            "INCOMPLETE",
        )

    def test_wrong_gateway_identity_is_not_reusable(self) -> None:
        self.assertEqual(
            classify_reuse(
                controller_ok=True,
                gateway_ok=False,
                quiescent=False,
                control=ready_control(),
                api=ready_api(),
            ),
            "INCOMPLETE",
        )

    def test_offline_client_is_not_reusable(self) -> None:
        api = ready_api()
        api["clients"]["trader_tcpdirect"]["health"]["status"] = "WAITING"
        self.assertEqual(
            classify_reuse(
                controller_ok=True,
                gateway_ok=True,
                quiescent=False,
                control=ready_control(),
                api=api,
            ),
            "INCOMPLETE",
        )

    def test_only_verified_quiescent_state_allows_fresh_run(self) -> None:
        self.assertEqual(
            classify_reuse(
                controller_ok=False,
                gateway_ok=False,
                quiescent=True,
                control=None,
                api=None,
            ),
            "CLEAN",
        )

    def test_invalid_json_cannot_become_clean_without_quiescent_gate(self) -> None:
        script = APP_ROOT / "flle_trading" / "transport_reuse.py"
        result = subprocess.run(
            [sys.executable, str(script), "1", "1", "0", "not-json", "{}"],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.stdout.strip(), "INCOMPLETE")


if __name__ == "__main__":
    unittest.main()
