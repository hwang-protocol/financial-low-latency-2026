from pathlib import Path
import os
import subprocess
import tempfile
import unittest

APP = Path(__file__).resolve().parents[1]

class SnapshotRetirement(unittest.TestCase):
    def run_fixture(self, *, remote_ok=True, identity_ok=True, listener=False, active=True):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            if active:(root/'active').touch()
            env=dict(os.environ, FIXTURE=str(root), REMOTE_OK=str(int(remote_ok)), IDENTITY_OK=str(int(identity_ok)), LISTENER=str(int(listener)))
            script=r'''
set -Eeuo pipefail
source "$1/scripts/platform-baseline.sh"
EXCHANGE_HOST=one; TRADER_HOST=two; OBSERVER_HOST=monitor
RUN_ID=TEST; CONTROLLER_UNIT=owned-controller
fake_ssh(){ cat >/dev/null; test "$REMOTE_OK" = 1; }
SSH=(fake_ssh)
verify_controller_identity(){ test "$IDENTITY_OK" = 1; }
systemctl(){
 case "$1" in
  is-active) test -f "$FIXTURE/active" ;;
  stop) printf '%s\n' "$2" >>"$FIXTURE/stopped"; rm "$FIXTURE/active" ;;
  *) return 2 ;;
 esac
}
ss(){ if test "$LISTENER" = 1; then echo 'foreign listener'; fi; }
lab_is_quiescent(){ test ! -f "$FIXTURE/active"; }
platform_retire_snapshot_controller
'''
            result=subprocess.run(['bash','-s','--',str(APP)],input=script,env=env,text=True,capture_output=True)
            stopped=(root/'stopped').read_text() if (root/'stopped').exists() else ''
            return result,stopped
    def test_empty_restored_guests_retire_only_owned_controller(self):
        result,stopped=self.run_fixture()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(stopped,'owned-controller\n')
        self.assertIn('snapshot_retirement=PASS',result.stdout)
    def test_partial_guests_or_wrong_identity_never_stop(self):
        for args in [dict(remote_ok=False),dict(identity_ok=False)]:
            result,stopped=self.run_fixture(**args)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(stopped,'')
    def test_unknown_listener_not_marked_clean(self):
        result,stopped=self.run_fixture(listener=True,active=False)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(stopped,'')
    def test_already_quiet_is_idempotent(self):
        result,stopped=self.run_fixture(active=False)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(stopped,'')
