import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest


SOURCE = Path(__file__).resolve().parents[1] / "flle_trading/transport_controller.py"
spec = importlib.util.spec_from_file_location("transport_action_log", SOURCE)
controller = importlib.util.module_from_spec(spec)
spec.loader.exec_module(controller)


class ActionLogTest(unittest.TestCase):
    def run_action(self, body, timeout=5):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        script = root / "control.sh"
        script.write_text("#!/bin/bash\n" + body)
        script.chmod(0o700)
        control = controller.Controller(script, "test-run", root / "actions")
        try:
            result = control._run_action("sfc", timeout)
        except subprocess.TimeoutExpired:
            result = None
        directory, = (root / "actions").iterdir()
        return result, json.loads((directory / "result.json").read_text()), directory

    def test_success_keeps_json_and_stderr_separate(self):
        result, record, directory = self.run_action(
            'echo stage=restore >&2\necho \'{"mode":"SFC"}\'\n')
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout), {"mode": "SFC"})
        self.assertEqual(result.stderr, "stage=restore\n")
        self.assertEqual((directory / "stderr.txt").read_text(), result.stderr)
        self.assertEqual(record["result"], "PASS")
        self.assertEqual(record["run_id"], "test-run")

    def test_nonzero_exit_retains_failure(self):
        result, record, directory = self.run_action('echo gate_failed >&2\nexit 17\n')
        self.assertEqual(result.returncode, 17)
        self.assertEqual(record["result"], "FAILED")
        self.assertEqual(record["returncode"], 17)
        self.assertEqual((directory / "stderr.txt").read_text(), "gate_failed\n")

    def test_timeout_keeps_partial_output_and_terminal_status(self):
        result, record, directory = self.run_action(
            'echo waiting_for_device >&2\nsleep 30\n', timeout=0.1)
        self.assertIsNone(result)
        self.assertEqual(record["result"], "TIMEOUT")
        self.assertIn("waiting_for_device", (directory / "stderr.txt").read_text())
        self.assertLess(record["elapsed_seconds"], 5)


if __name__ == "__main__":
    unittest.main()
