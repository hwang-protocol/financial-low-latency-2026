"""Local harness with real OpenFDK CSV parsing and a fake hardware backend.

Usage: python3 test_eos_control.py /path/to/openfdk
This does not execute EOSSDK, program a PDI or validate the board adapter.
"""
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
FDK = Path(sys.argv.pop(1)).resolve()
spec = importlib.util.spec_from_file_location("upstream_register_file", FDK / "resources/libapp/register_file.py")
register_file = importlib.util.module_from_spec(spec)
spec.loader.exec_module(register_file)
sys.path.insert(0, str(ROOT / "eos"))
from filter_control import APP_ID, FilterControl
from filter_rpc import FilterRpc


class FakeHardware:
    board_standard, image_type = "bvl", "pdi"

    def __init__(self):
        self.communicator = self
        self.state, self.writes = "applying", []
        self.words = dict.fromkeys(range(9), 0)
        self.words[0] = APP_ID
        self.words[7], self.words[8] = 2, 647
        self.fail_write, self.loads, self.unloads = False, [], 0
        self.changing_sequence = False

    def read_reg(self, address):
        if self.changing_sequence and address == 8:
            self.words[5] += 1
        return self.words[address]

    def write_reg(self, address, value):
        self.writes.append((address, value))
        self.words[2] = 1 if value == 1 else 0
        if self.fail_write:
            raise OSError("Simulated write applied but reply lost")

    def load_image(self, image, **kwargs):
        self.loads.append((image, kwargs))

    def profile_state(self):
        return self.state

    def unload_image(self):
        self.state = None
        self.unloads += 1


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.fpga = FakeHardware()
        self.now = 0
        self.control = FilterControl(self.fpga, register_file.RegisterFile,
                                     str(ROOT / "flle_filter_registers.csv"), lambda: self.now)
        # Test port metadata only; not an actual BVL FDK port definition.
        self.control.start("/test/flle_filter-bvl.pdi", {"test": {}})

    def ready(self):
        self.fpga.state = "applied"
        self.control.poll()

    def test_waits_without_writes_until_profile_applied(self):
        self.control.poll()
        self.assertFalse(self.control.ready)
        self.assertEqual(self.fpga.writes, [])
        self.assertFalse(self.fpga.loads[0][1]["blocking"])
        with self.assertRaises(RuntimeError):
            self.control.execute("arm-once")

    def test_start_disarms_and_explicit_command_arms(self):
        self.ready()
        self.assertEqual(self.fpga.writes, [(1, 2)])
        self.control.execute("arm-once")
        self.assertEqual(self.fpga.writes[-1], (1, 1))
        with self.assertRaises(RuntimeError):
            self.control.execute("arm-once")
        self.control.execute("disarm")
        self.assertEqual(self.fpga.writes[-1], (1, 2))

    def test_wrong_application_id_cannot_write(self):
        self.fpga.words[0] = 123
        with self.assertRaises(RuntimeError):
            self.ready()
        self.assertEqual(self.fpga.writes, [])

    def test_id_is_checked_again_before_each_command(self):
        self.ready()
        self.fpga.words[0] = 123
        with self.assertRaises(RuntimeError):
            self.control.execute("arm-once")
        self.assertEqual(self.fpga.writes, [(1, 2)])

    def test_ambiguous_write_is_never_retried(self):
        self.ready()
        self.fpga.fail_write = True
        with self.assertRaisesRegex(RuntimeError, "outcome unknown"):
            self.control.execute("arm-once")
        self.assertEqual(self.fpga.writes, [(1, 2), (1, 1)])
        self.assertFalse(self.control.ready)

    def test_sequence_only_published_when_disarmed_and_stable(self):
        self.ready()
        self.assertEqual(self.control.execute("show")["last_sequence"], (2 << 32) | 647)
        self.control.execute("arm-once")
        self.assertIsNone(self.control.execute("show")["last_sequence"])
        self.control.execute("disarm")
        self.fpga.changing_sequence = True
        self.assertIsNone(self.control.execute("show")["last_sequence"])

    def test_timeout_refuses_ready(self):
        self.now = 121
        with self.assertRaisesRegex(RuntimeError, "timed out"):
            self.control.poll()
        self.assertEqual(self.fpga.writes, [])

    def test_unrecognized_profile_state_waits_until_deadline(self):
        self.fpga.state = "another intermediate state"
        self.control.poll()
        self.assertFalse(self.control.ready)
        self.assertEqual(self.fpga.writes, [])

    def test_stop_without_started_image_does_not_unload(self):
        fresh = FilterControl(self.fpga, register_file.RegisterFile,
                              str(ROOT / "flle_filter_registers.csv"))
        fresh.stop()
        self.assertEqual(self.fpga.unloads, 0)

    def test_stop_disarms_then_unloads_and_restart_does_not_arm(self):
        self.ready()
        self.control.execute("arm-once")
        self.control.stop()
        self.assertEqual(self.fpga.writes[-1], (1, 2))
        self.assertEqual(self.fpga.unloads, 1)
        self.control.start("/test/flle_filter-bvl.pdi", {"test": {}})
        self.ready()
        self.assertEqual(self.fpga.writes, [(1, 2), (1, 1), (1, 2), (1, 2)])

    def test_duplicate_rpc_is_not_executed_twice(self):
        self.ready()
        rpc = FilterRpc(self.control, lambda: self.now)
        command = json.dumps({"operation": "arm-once", "id": "first", "session": rpc.session, "deadline": 5})
        first = rpc.handle(command)
        self.fpga.words[2] = 0  # Hardware has consumed the first quota.
        second = rpc.handle(command)
        self.assertEqual(first, second)
        self.assertTrue(json.loads(first)["ok"])
        self.assertEqual(self.fpga.writes, [(1, 2), (1, 1)])

    def test_expired_rpc_is_not_executed(self):
        self.ready()
        rpc = FilterRpc(self.control, lambda: self.now)
        reply = rpc.handle(json.dumps({"operation": "arm-once", "id": "first", "session": rpc.session, "deadline": 0}))
        self.assertFalse(json.loads(reply)["ok"])
        self.assertEqual(self.fpga.writes, [(1, 2)])

    def test_rpc_from_previous_daemon_session_is_rejected(self):
        self.ready()
        rpc = FilterRpc(self.control, lambda: self.now)
        reply = rpc.handle(json.dumps({"operation": "arm-once", "id": "first", "session": "old-session", "deadline": 5}))
        self.assertFalse(json.loads(reply)["ok"])
        self.assertEqual(self.fpga.writes, [(1, 2)])


class CliContractTests(unittest.TestCase):
    """Real upstream CLI helpers; only EOS-owned objects are test doubles."""

    def setUp(self):
        extension = types.ModuleType("CliExtension")
        extension.CliCommandClass = type("CliCommandClass", (), {})
        extension.ShowCommandClass = type("ShowCommandClass", (), {})
        self.extension = extension
        libapp = types.ModuleType("_course_checked_libapp")
        libapp.__path__ = [str(FDK / "resources/libapp")]
        libapp.IS_EOS = False
        libapp.device = types.ModuleType("_unused_device")
        package = types.ModuleType("flle_filter")
        package.libapp = libapp
        self.modules = patch.dict(sys.modules, {
            "CliExtension": extension,
            "CliExtensionLib": types.ModuleType("CliExtensionLib"),
            "_course_checked_libapp": libapp,
            "flle_filter": package,
        })
        self.modules.start()
        self.addCleanup(self.modules.stop)
        # Source modules themselves are not mocked.
        for name in ("serial", "cli"):
            fullname = "_course_checked_libapp." + name
            spec = importlib.util.spec_from_file_location(fullname, FDK / ("resources/libapp/" + name + ".py"))
            module = importlib.util.module_from_spec(spec)
            sys.modules[fullname] = module
            spec.loader.exec_module(module)
            setattr(libapp, name, module)
        spec = importlib.util.spec_from_file_location("course_cli", ROOT / "eos/FlleFilterCli.py")
        self.cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.cli)
        self.raw = {"running": "true", "session": '"test-session"', "image_state": '"applied"'}
        status = types.SimpleNamespace(statusIter=lambda: iter(self.raw.items()),
                                       status=lambda key: self.raw.get(key))
        config = types.SimpleNamespace(isEnabled=lambda: True)
        daemon = types.SimpleNamespace(status=status, config=config)
        self.ctx = types.SimpleNamespace(getDaemon=lambda name: daemon)

    def test_show_status_uses_real_upstream_status_wrapper(self):
        values = self.cli.ShowStatus().handler(self.ctx)
        self.assertTrue(values["enabled"])
        self.assertTrue(values["running"])
        self.assertEqual(values["detail"], {"running": True, "session": "test-session", "image_state": "applied"})
        # A dictionary is not the object expected by the actual upstream API.
        with self.assertRaises(AttributeError):
            self.cli.libapp.cli.status_as_dict(self.raw)

    def test_not_ready_can_show_status_but_cannot_request_hardware(self):
        self.raw["running"] = "false"
        values = self.cli.ShowStatus().handler(self.ctx)
        self.assertFalse(values["running"])
        with self.assertRaisesRegex(RuntimeError, "not ready"):
            self.cli.request(self.ctx, "show")

    def test_rpc_transport_failure_makes_one_call_and_gives_workable_recovery(self):
        calls = []

        def failed_rpc(ctx, daemon_name, command):
            calls.append((ctx, daemon_name, json.loads(command)))
            raise TimeoutError("Simulated EOS RPC reply lost")

        self.extension.agentRpc = failed_rpc
        with self.assertRaisesRegex(RuntimeError, "restore external bypass"):
            self.cli.request(self.ctx, "arm-once")
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1], "FlleFilterDaemon")
        self.assertEqual(calls[0][2]["session"], "test-session")


if __name__ == "__main__":
    unittest.main(verbosity=2)
