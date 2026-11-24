import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "flle_trading"
    / "transport_controller.py"
)
LAB_CONTROL = SCRIPT.parents[1] / "scripts" / "transport_labctl.sh"
BASE_LAB_CONTROL = SCRIPT.parents[1] / "scripts" / "labctl.sh"
CHECKOUT_CANDIDATE = Path(__file__).resolve().parents[3]
CHECKOUT_ROOT = CHECKOUT_CANDIDATE if (
    (CHECKOUT_CANDIDATE / "AGENTS.md").is_file()
    and (CHECKOUT_CANDIDATE / "Documents").is_dir()
    and (CHECKOUT_CANDIDATE / "apps/flle-trading-lab").resolve()
    == SCRIPT.parents[1].resolve()
) else None
CH06_CODE_CONTRACT = None if CHECKOUT_ROOT is None else (
    CHECKOUT_ROOT / "Documents"
    / "newDoc"
    / "assets"
    / "06-kernel-bypass"
    / "four-path-build-contract-audit.sh"
)
CH06_PREFLIGHT = None if CH06_CODE_CONTRACT is None else (
    CH06_CODE_CONTRACT.with_name("02-four-path-preflight.sh")
)
SPEC = importlib.util.spec_from_file_location("transport_controller", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
CONTROLLER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTROLLER)
SFC_READY = (
    '{"mode":"SFC","transition":"READY","owner":"sfc",'
    '"hugepages_2mb":128,"data_ip_present":true}\n'
)


class TrackingLock:
    def __init__(self) -> None:
        self.held = False

    def __enter__(self) -> None:
        if self.held:
            raise AssertionError("lock entered twice")
        self.held = True

    def __exit__(self, *_args: object) -> None:
        self.held = False


class TransportControllerRecoveryTest(unittest.TestCase):
    def test_software_profile_cannot_satisfy_transport_ready_gate(self):
        state = dict(mode="SFC", transition="READY", owner="sfc",
                     experiment_profile="SOFTWARE", hugepages_2mb=128,
                     data_ip_present=True, software_clients_ready=True)
        ready = CONTROLLER.Controller._mode_state_is_ready
        self.assertTrue(ready(state, "baseline"))
        self.assertFalse(ready(state, "sfc"))
        self.assertFalse(ready(state, "dpdk"))
        for key, value in (("software_clients_ready", False),
                           ("data_ip_present", False), ("hugepages_2mb", 0)):
            self.assertFalse(ready(dict(state, **{key: value}), "baseline"))
        self.assertFalse(ready(dict(mode="SFC", transition="READY"), "baseline"))

    def test_ch06_code_contract_does_not_require_optional_ripgrep(self) -> None:
        if CH06_CODE_CONTRACT is None:
            self.skipTest("runtime-only deployment has no Documents tree")
        contract = CH06_CODE_CONTRACT.read_text(encoding="utf-8")
        self.assertNotIn("rg -n", contract)
        self.assertIn("grep -En --", contract)

    def test_ch06_prep_c_does_not_repeat_prep_a_or_b_checks(self) -> None:
        if CH06_PREFLIGHT is None:
            self.skipTest("runtime-only deployment has no Documents tree")
        prep_c = CH06_PREFLIGHT.read_text(encoding="utf-8")
        for repeated_check in (
            "onload --version",
            "/dev/onload",
            "/proc/cmdline",
            "iommu_group",
            "查 Exchange 数据口",
            "查 Trader 数据口",
        ):
            self.assertNotIn(repeated_check, prep_c)

        transport = LAB_CONTROL.read_text(encoding="utf-8")
        preflight = transport.split("  preflight)", 1)[1].split("    ;;", 1)[0]
        self.assertIn('"$BASE_CTL" preflight "$RUN_ID" stage-c', preflight)
        self.assertNotIn('"$TRADER_HOST"', preflight)
        self.assertNotIn("/proc/cmdline", preflight)

        base = BASE_LAB_CONTROL.read_text(encoding="utf-8")
        self.assertIn("stage-c) remote_builder_preflight", base)

    def test_gate_mutations_have_a_bdf_scoped_interprocess_lock(self) -> None:
        control = LAB_CONTROL.read_text(encoding="utf-8")
        lock_case = control.split('case "$ACTION" in', 1)[1].split("esac", 1)[0]
        self.assertIn('reset-paper|baseline|start|sfc|dpdk|measure|stop|retire-snapshot-controller|feed-profile)', lock_case)
        for action in ("reset-paper", "baseline", "sfc", "dpdk", "measure", "stop"):
            self.assertIn(action, lock_case)
        self.assertIn(
            'exec 8>"/run/lock/flle-transport-0000_03_00_0.lock"', control
        )
        self.assertNotIn('flle-transport-${RUN_ID}.lock', control)
        self.assertIn("flock -w 620 8", control)

    def test_timed_out_mode_action_runs_direct_sfc_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            script = Path(temporary) / "control.sh"
            script.write_text("#!/bin/sh\n", encoding="utf-8")
            controller = CONTROLLER.Controller(script, "run-1")
            recovery = subprocess.CompletedProcess(
                args=[], returncode=0, stdout=SFC_READY, stderr=""
            )
            with mock.patch.object(
                controller,
                "_run_action",
                side_effect=[subprocess.TimeoutExpired([], 300), recovery],
            ) as run_action:
                with self.assertRaisesRegex(
                    RuntimeError, "direct SFC recovery reached its hard gates"
                ):
                    controller.invoke("dpdk", 300)
        self.assertEqual(run_action.call_args_list[1].args, ("sfc", 300))

    def test_timed_out_mode_action_surfaces_recovery_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            script = Path(temporary) / "control.sh"
            script.write_text("#!/bin/sh\n", encoding="utf-8")
            controller = CONTROLLER.Controller(script, "run-1")
            recovery = subprocess.CompletedProcess(
                args=[], returncode=9, stdout="", stderr="restore failed"
            )
            with mock.patch.object(
                controller,
                "_run_action",
                side_effect=[subprocess.TimeoutExpired([], 300), recovery],
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "mode action timed out and direct SFC recovery failed",
                ):
                    controller.invoke("dpdk", 300)

    def test_failed_mode_action_recovers_while_lock_is_held(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            script = Path(temporary) / "control.sh"
            script.write_text("#!/bin/sh\n", encoding="utf-8")
            controller = CONTROLLER.Controller(script, "run-1")
            lock = TrackingLock()
            controller.lock = lock
            replies = iter(
                [
                    subprocess.CompletedProcess(
                        args=[], returncode=7, stdout="", stderr="switch failed"
                    ),
                    subprocess.CompletedProcess(
                        args=[], returncode=0, stdout=SFC_READY, stderr=""
                    ),
                ]
            )
            lock_states: list[bool] = []

            def run_locked(*_args: object, **_kwargs: object) -> object:
                lock_states.append(lock.held)
                return next(replies)

            with mock.patch.object(
                controller, "_run_action", side_effect=run_locked
            ) as run_action:
                with self.assertRaisesRegex(
                    RuntimeError,
                    "mode action failed: switch failed; direct SFC recovery reached",
                ):
                    controller.invoke("dpdk", 300)

        self.assertEqual(lock_states, [True, True])
        self.assertEqual(run_action.call_args_list[1].args, ("sfc", 300))

    def test_failed_mode_action_keeps_original_error_when_recovery_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            script = Path(temporary) / "control.sh"
            script.write_text("#!/bin/sh\n", encoding="utf-8")
            controller = CONTROLLER.Controller(script, "run-1")
            failure = subprocess.CompletedProcess(
                args=[], returncode=7, stdout="", stderr="original switch failure"
            )
            recovery = subprocess.CompletedProcess(
                args=[], returncode=9, stdout="", stderr="restore failure"
            )
            with mock.patch.object(
                controller, "_run_action", side_effect=[failure, recovery]
            ) as run_action:
                with self.assertRaises(RuntimeError) as raised:
                    controller.invoke("dpdk", 300)

        message = str(raised.exception)
        self.assertIn("mode action failed: original switch failure", message)
        self.assertIn("direct SFC recovery failed: restore failure", message)
        self.assertEqual(run_action.call_args_list[1].args, ("sfc", 300))

    def test_timed_out_status_is_read_only_and_does_not_recover(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            script = Path(temporary) / "control.sh"
            script.write_text("#!/bin/sh\n", encoding="utf-8")
            controller = CONTROLLER.Controller(script, "run-1")
            with mock.patch.object(
                controller,
                "_run_action",
                side_effect=subprocess.TimeoutExpired([], 10),
            ) as run_action:
                with self.assertRaisesRegex(RuntimeError, "status action timed out"):
                    controller.invoke("status", 10)
        run_action.assert_called_once_with("status", 10)

    def test_unverified_mode_result_recovers_before_releasing_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            script = Path(temporary) / "control.sh"
            script.write_text("#!/bin/sh\n", encoding="utf-8")
            controller = CONTROLLER.Controller(script, "run-1")
            lock = TrackingLock()
            controller.lock = lock
            replies = iter(
                [
                    subprocess.CompletedProcess(
                        args=[],
                        returncode=0,
                        stdout='{"mode":"DPDK","transition":"DEGRADED"}\n',
                        stderr="",
                    ),
                    subprocess.CompletedProcess(
                        args=[], returncode=0, stdout=SFC_READY, stderr=""
                    ),
                ]
            )
            lock_states: list[bool] = []

            def run_locked(*_args: object, **_kwargs: object) -> object:
                lock_states.append(lock.held)
                return next(replies)

            with mock.patch.object(
                controller, "_run_action", side_effect=run_locked
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "unverified terminal state"
                ):
                    controller.invoke("dpdk", 300)
        self.assertEqual(lock_states, [True, True])

    def test_recovery_success_requires_all_sfc_hard_gate_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            script = Path(temporary) / "control.sh"
            script.write_text("#!/bin/sh\n", encoding="utf-8")
            controller = CONTROLLER.Controller(script, "run-1")
            failure = subprocess.CompletedProcess(
                args=[], returncode=7, stdout="", stderr="switch failed"
            )
            incomplete = subprocess.CompletedProcess(
                args=[], returncode=0, stdout='{"mode":"SFC"}\n', stderr=""
            )
            with mock.patch.object(
                controller, "_run_action", side_effect=[failure, incomplete]
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "no verified SFC/READY hard-gate state"
                ):
                    controller.invoke("dpdk", 300)

    def test_timeout_terminates_the_action_process_group(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            script = Path(temporary) / "control.sh"
            script.write_text("#!/bin/sh\n", encoding="utf-8")
            controller = CONTROLLER.Controller(script, "run-1")
            process = mock.Mock()
            process.pid = 4321
            process.communicate.side_effect = [
                subprocess.TimeoutExpired([], 10),
                ("", ""),
            ]
            with mock.patch.object(
                CONTROLLER.subprocess, "Popen", return_value=process
            ) as popen, mock.patch.object(CONTROLLER.os, "killpg") as killpg:
                with self.assertRaises(subprocess.TimeoutExpired):
                    controller._run_action("dpdk", 10)
        self.assertTrue(popen.call_args.kwargs["start_new_session"])
        killpg.assert_called_once_with(4321, CONTROLLER.signal.SIGTERM)


if __name__ == "__main__":
    unittest.main()

class ShellRecoveryRetentionTest(unittest.TestCase):
    def test_verified_software_rollback_is_not_replaced_by_order_only_sfc(self):
        with tempfile.TemporaryDirectory() as raw:
            script = Path(raw) / 'ctl'; script.touch()
            controller = CONTROLLER.Controller(script, 'run')
            failed = subprocess.CompletedProcess([], 1, '', 'DPDK_ACTION_FAILED stage=start_dpdk_client\nDPDK_RECOVERY_OK profile=baseline\n')
            restored = subprocess.CompletedProcess([], 0,
                '{"mode":"SFC","transition":"READY","owner":"sfc","experiment_profile":"SOFTWARE","hugepages_2mb":128,"data_ip_present":true,"software_clients_ready":true}', '')
            with mock.patch.object(controller, '_run_action', side_effect=[failed, restored]) as run:
                with self.assertRaisesRegex(RuntimeError, 'verified baseline recovery retained'):
                    controller.invoke('dpdk', 300)
                self.assertEqual([c.args for c in run.call_args_list], [('dpdk', 300), ('status', 10)])

    def test_unverified_shell_rollback_still_uses_direct_recovery(self):
        with tempfile.TemporaryDirectory() as raw:
            script = Path(raw) / 'ctl'; script.touch()
            controller = CONTROLLER.Controller(script, 'run')
            failed = subprocess.CompletedProcess([], 1, '', 'DPDK_RECOVERY_OK profile=baseline\n')
            bad = subprocess.CompletedProcess([], 0, '{"mode":"SFC","transition":"READY"}', '')
            sfc = subprocess.CompletedProcess([], 0, SFC_READY, '')
            with mock.patch.object(controller, '_run_action', side_effect=[failed, bad, sfc]) as run:
                with self.assertRaisesRegex(RuntimeError, 'direct SFC recovery reached'):
                    controller.invoke('dpdk', 300)
                self.assertEqual([c.args for c in run.call_args_list], [('dpdk', 300), ('status', 10), ('sfc', 300)])
