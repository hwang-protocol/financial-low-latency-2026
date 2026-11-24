"""CLI checks finish before sysfs access; these are NOT hardware MMIO tests."""
import subprocess
import sys
import unittest

BINARY = sys.argv.pop(1)

class Guards(unittest.TestCase):
    def reject(self, args, text):
        result = subprocess.run([BINARY, *args], text=True, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(text, result.stderr)

    def test_requires_full_pf1_bdf(self):
        for bdf in ("65:00.1", "0000:65:00.0", "0000:65:ff.1", "../../etc.1"):
            with self.subTest(bdf=bdf):
                self.reject(["--device", bdf, "show"], "Usage:")

    def test_write_is_explicit(self):
        for command in ("arm", "disarm", "submit"):
            args = ["--device", "0000:65:00.1", command]
            if command == "submit":
                args.append("647")
            self.reject(args, "require --write")

    def test_sequence_validation(self):
        for seq in ("-1", "0x100", "18446744073709551616", ""):
            with self.subTest(seq=seq):
                self.reject(["--device", "0000:65:00.1", "--write", "submit", seq], "ERROR:")

    def test_unknown_command(self):
        self.reject(["--device", "0000:65:00.1", "--write", "flash"], "Unknown command")

    def test_extra_sequence_rejected(self):
        self.reject(["--device", "0000:65:00.1", "show", "647"], "Only submit")

if __name__ == "__main__":
    unittest.main(verbosity=2)
