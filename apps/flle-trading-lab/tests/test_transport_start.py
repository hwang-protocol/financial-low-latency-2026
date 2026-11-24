"""Exercise restart contracts without touching a network device or live VM."""
import os
import socket
from pathlib import Path
import subprocess
import tempfile
import unittest


SOURCE = (Path(__file__).resolve().parents[1] / "scripts/transport_labctl.sh").read_text()


def section(first, following):
    return SOURCE[SOURCE.index(first + "() {"):SOURCE.index(following + "() {")]


class TransportStartTest(unittest.TestCase):
    def shell(self, script, **env):
        return subprocess.run(["bash", "-c", "set -Eeuo pipefail\n" + script],
                              env=dict(os.environ, **env), capture_output=True,
                              text=True, timeout=10)

    def test_start_handles_previous_boot_pid_without_claiming_or_signalling_it(self):
        script = section('start_remote_process', 'wait_remote_listener') + """
SSH=(local_ssh)
local_ssh(){
  shift
  if test "$1" = python3; then "$@"; else echo LAUNCH; fi
}
start_remote_process fixture receiver 'sleep 30'
"""
        with subprocess.Popen(['sleep', '30']) as process:
            try:
                stat = Path(f'/proc/{process.pid}/stat').read_text().rsplit(')', 1)[1].split()[19]
                boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
                for kind in ('old-boot', 'current', 'reused', 'no-identity'):
                    with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                        root = Path(directory)
                        (root / 'receiver.pid').write_text(str(process.pid))
                        if kind != 'no-identity':
                            (root / 'receiver.identity').write_text(
                                f'pid={process.pid} start_ticks={"0" if kind == "reused" else stat} '
                                f'boot_id={"old-boot" if kind == "old-boot" else boot}\n')
                        result = self.shell(script, RUN_DIR=directory)
                        self.assertEqual(result.returncode == 0, kind in ('old-boot', 'current'), result.stderr)
                        self.assertEqual('LAUNCH' in result.stdout, kind == 'old-boot')
                        self.assertIsNone(process.poll())
            finally:
                process.terminate()

    def test_stop_does_not_signal_reused_pid_from_previous_boot(self):
        script = section('stop_remote_process', 'start_remote_process') + """
SSH=(local_ssh)
local_ssh(){ shift; "$@"; }
ss(){ :; }; export -f ss
stop_remote_process fixture receiver /not-this-process 48121
"""
        with subprocess.Popen(['sleep', '30']) as process:
            try:
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    (root / 'receiver.pid').write_text(str(process.pid))
                    (root / 'receiver.identity').write_text(f'pid={process.pid} start_ticks=0 boot_id=old-boot\n')
                    result = self.shell(script, RUN_DIR=directory)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertFalse((root / 'receiver.pid').exists())
                    self.assertIsNone(process.poll())
            finally:
                process.terminate()

    def test_receiver_cleanup_after_shutdown_keeps_live_or_unexpected_paths(self):
        source = (Path(__file__).resolve().parents[1] / 'scripts/control-host.sh').read_text()
        function = source.split('stop_feed_receiver() {', 1)[1].split('\nstart_feed_book_guardian()', 1)[0]
        script = "stop_feed_receiver() {" + function + """
TRADER_HOST=fixture
SSH=(local_ssh)
local_ssh(){ shift; "$@"; }
stop_remote_process(){ :; }
stop_feed_receiver
"""
        for case in ('absent', 'stale', 'live', 'file', 'symlink'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'feed.sock'
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                    if case in ('stale', 'live'):
                        sock.bind(str(path))
                        if case == 'stale':
                            sock.close()
                    elif case == 'file':
                        path.write_text('keep')
                    elif case == 'symlink':
                        path.symlink_to(Path(directory) / 'missing')
                    result = self.shell(script, RUN_DIR=directory)
                    if case in ('absent', 'stale'):
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertFalse(path.exists())
                    else:
                        self.assertNotEqual(result.returncode, 0)
                        self.assertTrue(path.exists() or path.is_symlink())

    def test_rss_receipt_reuse_reapply_and_drift_rejection(self):
        script = section("configure_exchange_rss", "verify_exchange_rss") + r'''
EXCHANGE_HOST=fixture
SSH=(fake_ssh)
verify_exchange_rss(){ test "$CASE" = active; }
restore_exchange_rss(){ test "$CASE" = restored; }
fake_ssh(){
  shift
  if [[ "$1" != bash ]]; then return 0; fi
  local body
  body="$(cat)"
  if [[ "$body" == *'archive='* ]]; then
    command bash -s -- "$RUN_DIR" <<<"$body"
  else
    echo APPLY_NEW_RSS
  fi
}
configure_exchange_rss
'''
        for case in ("active", "restored", "drift"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                names = ["exchange-rss" + x for x in
                         (".receipt", "-baseline.txt", "-applied.txt", "-restored.txt")]
                for name in names:
                    (root / name).write_text("retained evidence " + name)
                result = self.shell(script, CASE=case, RUN_DIR=directory)
                self.assertEqual(result.returncode, 1 if case == "drift" else 0, result.stderr)
                archives = list(root.glob("exchange-rss-history.*"))
                self.assertEqual(len(archives), int(case == "restored"))
                self.assertEqual("APPLY_NEW_RSS" in result.stdout, case == "restored")
                for name in names:
                    saved = archives[0] / name if archives else root / name
                    self.assertEqual(saved.read_text(), "retained evidence " + name)

    def test_reuse_native_exchange_and_verify_manifest_before_start(self):
        script = section("select_exchange_runtime", "verify_exchange_runtime") + r'''
RUN_DIR=/var/tmp/current
RUNTIME_ROOT=$RUN_DIR/transport-runtime/flle-ch05-four-path
EXCHANGE_HOST=fixture; TELEMETRY_HOST=10.1.1.101; SSH=(fake_ssh)
fake_ssh(){
  if [[ "$2" == *'test -f'* ]]; then test "$NATIVE" = 1
  else test "$CORRUPT" = 0; fi
}
platform_process_running(){ test "$RUNNING" = 1 && test "$3" = "$RUN_DIR/flle-exchange"; }
start_remote_process(){ printf 'START %s\n' "$3"; }
wait_remote_listener(){ :; }
verify_exchange_runtime(){ echo VERIFIED; }
start_exchange
'''
        for native, running, corrupt in (("1", "1", "0"), ("1", "0", "0"),
                                         ("1", "0", "1"), ("0", "0", "0")):
            with self.subTest(native=native, running=running, corrupt=corrupt):
                result = self.shell(script, NATIVE=native, RUNNING=running, CORRUPT=corrupt)
                if corrupt == "1":
                    self.assertNotEqual(result.returncode, 0)
                    self.assertNotIn("START", result.stdout)
                    continue
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("VERIFIED", result.stdout)
                if running == "1":
                    self.assertNotIn("START", result.stdout)
                elif native == "1":
                    self.assertIn("'/var/tmp/current/flle-exchange'", result.stdout)
                    self.assertIn("--market-mode 'MULTICAST_A'", result.stdout)
                else:
                    self.assertIn("/transport-runtime/flle-ch05-four-path/bin/flle-exchange", result.stdout)
                    self.assertIn("--market-mode 'UNICAST'", result.stdout)

    def test_failed_start_keeps_preexisting_exchange_and_gateway(self):
        rollback = SOURCE.split("    start_rollback() {", 1)[1].split("    trap start_rollback ERR", 1)[0]
        script = "start_rollback() {" + rollback + r'''
EXCHANGE_HOST=exchange; OBSERVER_HOST=observer; TRADER_HOST=trader
CONTROLLER_UNIT=fixture; start_stage=start_sfc_clients
SSH=(fake_ssh)
fake_ssh(){ :; }
systemctl(){ return 1; }
ss(){ :; }
stop_remote_process(){ printf 'STOP %s %s\n' "$1" "$2"; }
stop_sfc_clients(){ :; }
stop_dpdk_client(){ :; }
stop_feed_receiver(){ :; }
wait_hugepages_zero(){ :; }
restore_exchange_rss(){ :; }
trap start_rollback ERR
false
'''
        for keep in ("0", "1"):
            with self.subTest(keep=keep):
                result = self.shell(script, keep_exchange=keep, keep_gateway=keep)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn("TRANSPORT_START_FAILED stage=start_sfc_clients rc=1", result.stderr)
                self.assertEqual("STOP exchange exchange" in result.stdout, keep == "0")
                self.assertEqual("STOP observer gateway" in result.stdout, keep == "0")
                self.assertIn("STOP trader trader-auto", result.stdout)


if __name__ == "__main__":
    unittest.main()
