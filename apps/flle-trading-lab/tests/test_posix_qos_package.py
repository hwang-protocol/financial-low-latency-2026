"""Check additive package identity and snapshot-compatible selection."""
import importlib.util
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest

APP=Path(__file__).resolve().parents[1]
CHECKOUT=(APP.parents[1]/'apps/flle-trading-lab').resolve() == APP
sys.path.insert(0,str(APP))
from flle_trading.posix_qos import NAME, ARCHIVE_SHA, digest, runtime_root, verify_root
ARCHIVE=APP.parents[1]/'artifacts/blobs/x2522/ch05-four-path/posix-qos-v1/flle-posix-qos-v1-x86_64-jammy.tgz'

class PackageTest(unittest.TestCase):
    def test_old_snapshot_without_marker_keeps_original_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            self.assertEqual(runtime_root(root),root/'transport-runtime/flle-ch05-four-path')

    @unittest.skipUnless(CHECKOUT, 'pinned archive is verified in the management checkout')
    def test_pinned_package_and_reject_changed_binary(self):
        self.assertEqual(digest(ARCHIVE),ARCHIVE_SHA)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/'posix-runtime').mkdir()
            with tarfile.open(ARCHIVE) as tar: tar.extractall(root/'posix-runtime',filter='data')
            (root/'posix-qos.enabled').write_text('POSIX_QOS_V1\n')
            selected=root/'posix-runtime'/NAME
            self.assertEqual(runtime_root(root),selected)
            (selected/'bin/flle-trader').write_bytes(b'wrong image')
            with self.assertRaises(ValueError): runtime_root(root)

    def test_selected_but_missing_package_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/'posix-qos.enabled').write_text('POSIX_QOS_V1\n')
            with self.assertRaises(OSError): runtime_root(root)

if __name__=='__main__': unittest.main()
