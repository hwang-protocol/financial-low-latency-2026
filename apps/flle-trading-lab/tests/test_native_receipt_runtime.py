"""Exercise the actual receipt producer, including additive client runtimes."""
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("native_fixture", HERE / "test_analyze_four_transport_raw.py")
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
SCRIPT = HERE.parent / "scripts/transport_labctl.sh"


class NativeReceiptRuntimeTest(unittest.TestCase):
    def run_receipt(self, target="SOCKET", additive=True, tamper=None):
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary).resolve()
            base = run / "transport-runtime/flle-ch05-four-path"
            client = run / "posix-runtime/flle-posix-qos-v1" if additive else base
            binary = "flle-trader-tcpdirect" if target == "TCPDIRECT" else "flle-trader"
            base.mkdir(parents=True)
            client.mkdir(parents=True, exist_ok=True)
            (base / "MANIFEST.sha256").write_text("e" * 64 + "  bin/flle-exchange\n")
            with (client / "MANIFEST.sha256").open("a") as manifest:
                manifest.write("d" * 64 + f"  bin/{binary}\n")
            manifest_sha = hashlib.sha256((base / "MANIFEST.sha256").read_bytes()).hexdigest()
            _, directory = fixtures.BalancedAnalysisTest().make_native_fixture(
                run, target, client_exe_path=str(client / "bin" / binary))
            receipt = directory / "data-plane-input.receipt"
            receipt.write_text(receipt.read_text().replace("f" * 64, manifest_sha))
            if additive:
                state_file = directory / "state.json"
                state = json.loads(state_file.read_text())
                state.update(order_dscp_control="POSIX_QOS_V1", order_dscp=0)
                state_file.write_text(json.dumps(state))
            if tamper == "base":
                with (base / "MANIFEST.sha256").open("a") as manifest:
                    manifest.write("0" * 64 + "  unexpected\n")
            elif tamper == "client":
                (client / "MANIFEST.sha256").write_text("0" * 64 + f"  bin/{binary}\n")
            elif tamper == "checkpoint":
                receipt.write_text(receipt.read_text().replace("c" * 64, "0" * 64))
            source = SCRIPT.read_text().split('manifest="$(python3 - "$run_dir" "$tmp" "$final" "$target"', 1)[1]
            producer = source.split("<<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
            return subprocess.run([sys.executable, "-", str(run), str(directory),
                                   str(directory), target, str(client), str(base)],
                                  input=producer, text=True, capture_output=True)

    def test_additive_socket_and_onload_use_base_input_manifest(self):
        for target in ("SOCKET", "OPENONLOAD"):
            with self.subTest(target=target):
                result = self.run_receipt(target)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(json.loads(result.stdout)["files"])

    def test_original_runtime_clients_still_pass(self):
        for target in ("SOCKET", "TCPDIRECT"):
            with self.subTest(target=target):
                result = self.run_receipt(target, additive=False)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_changed_base_manifest_or_checkpoint_is_rejected(self):
        for tamper in ("base", "checkpoint"):
            with self.subTest(tamper=tamper):
                result = self.run_receipt(tamper=tamper)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("base-runtime/checkpoint input identity is invalid", result.stderr)

    def test_changed_client_manifest_is_rejected(self):
        result = self.run_receipt(tamper="client")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("client executable/runtime manifest identity is invalid", result.stderr)


if __name__ == "__main__":
    unittest.main()
