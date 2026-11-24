#!/usr/bin/env python3
"""Local ownership/watchdog tests; no NIC, SSH or live program is touched."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("xdp_session", Path(__file__).with_name("xdp-session.py"))
session = importlib.util.module_from_spec(spec)
spec.loader.exec_module(session)


class OwnershipTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        session.STATE = Path(self.temp.name) / "attachment.json"
        session.STATE.write_text(json.dumps({"interface": "test0", "ifindex": 10, "program_id": 123}))

    def info(self, index=10, pid=123):
        return {"ifindex": index, "xdp": {"prog": {"id": pid}}}

    def test_detach_own_program(self):
        with patch.object(session, "link", return_value=self.info()), patch.object(session.subprocess, "check_call") as call:
            session.detach()
            call.assert_called_once_with(["ip", "link", "set", "dev", "test0", "xdpdrv", "off"])
        self.assertFalse(session.STATE.exists())

    def test_refuse_foreign_program(self):
        with patch.object(session, "link", return_value=self.info(pid=124)), patch.object(session.subprocess, "check_call") as call:
            with self.assertRaises(SystemExit):
                session.detach()
            call.assert_not_called()
        self.assertTrue(session.STATE.exists())

    def test_refuse_replaced_interface(self):
        with patch.object(session, "link", return_value=self.info(index=11)), patch.object(session.subprocess, "check_call") as call:
            with self.assertRaises(SystemExit):
                session.detach()
            call.assert_not_called()

    def test_already_detached(self):
        with patch.object(session, "link", return_value=self.info(pid=0)), patch.object(session.subprocess, "check_call") as call:
            session.detach()
            call.assert_not_called()
        self.assertFalse(session.STATE.exists())

    def test_expired_watchdog(self):
        with patch.object(session.sys, "argv", ["xdp-session.py", "watch"]), patch.object(session.time, "monotonic", side_effect=[0, 181]), patch.object(session, "detach") as detach:
            session.main()
            detach.assert_called_once_with()

    def test_program_id_formats(self):
        self.assertEqual(session.program_id({"xdp": {"prog_id": 9}}), 9)
        self.assertEqual(session.program_id(self.info()), 123)
        self.assertEqual(session.program_id({}), 0)


if __name__ == "__main__":
    unittest.main()
