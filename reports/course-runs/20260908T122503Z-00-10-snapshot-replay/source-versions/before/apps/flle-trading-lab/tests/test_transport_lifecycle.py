"""Execute production shell assertions and transitions with controlled host operations."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
TRANSPORT = (SCRIPTS / 'transport_labctl.sh').read_text()
CONTROL = (SCRIPTS / 'control-host.sh').read_text()


class RemoteAssertionTest(unittest.TestCase):
    def test_unit_and_port_must_both_be_absent(self):
        commands = []
        for source, marker in ((TRANSPORT, 'lab_is_quiescent() {'),
                               (CONTROL, 'controller_stop() {')):
            commands.append(next(line.strip() for line in source.split(marker, 1)[1].splitlines()
                                 if '"! systemctl is-active' in line))
        for command in commands:
            for active, listening in ((0, 0), (1, 0), (0, 1), (1, 1)):
                with self.subTest(command=command, active=active, listening=listening):
                    script = '''
unit=unit; CONTROLLER_UNIT=unit; TRADER_HOST=trader
systemctl() { test "$ACTIVE" = 1; }
ss() { if test "$LISTENING" = 1; then echo listener; fi; }
export -f systemctl ss
remote() { shift; bash -c "$*"; }
SSH=(remote)
assert_stopped() {
''' + command + '\n}\nassert_stopped\n'
                    result = subprocess.run(['bash', '-c', script], env=dict(os.environ,
                        ACTIVE=str(active), LISTENING=str(listening)), capture_output=True)
                    self.assertEqual(result.returncode == 0, not (active or listening))


class TransitionTest(unittest.TestCase):
    def run_transition(self, action, *, profile='TRANSPORT', feed=False,
                       fail='', current='STALE', recovery_fail=False):
        end = {'sfc': 'dpdk', 'dpdk': 'reset-paper'}[action]
        body = TRANSPORT.split('\n  ' + action + ')\n', 1)[1].split('\n  ' + end + ')', 1)[0]
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / 'profile').write_text(profile)
            harness = root / 'ctl'
            harness.write_text('''#!/bin/bash
set -Eeuo pipefail
RUN_ID=test; RUN_DIR=/test; TRADER_HOST=trader
record() { echo "$1" >>"$WORK/events"; test "$FAIL" != "$1"; }
platform_is_software() { test "$(cat "$WORK/profile")" = SOFTWARE; }
platform_process_running() { test "$FEED" = 1; }
platform_stop_software_clients() { record stop_feed_consumers; }
verify_exchange_rss() { record verify_exchange_rss; }
collect_status() { printf '{"mode":"%s","transition":"READY"}' "$CURRENT"; }
require_mode_ready() { record require_mode_ready; }
stop_sfc_clients() { record stop_sfc_clients; }
stop_feed_receiver() { record stop_feed_receiver; }
stop_dpdk_client() { record stop_dpdk_client; }
wait_hugepages_zero() { record wait_hugepages_zero; }
start_dpdk_client() { record start_dpdk_client; }
start_sfc_clients() { record start_sfc_clients; }
remote() { record remote; }
SSH=(remote)
case "$1" in
baseline) record recovery_baseline; test "$RECOVERY_FAIL" != 1;;
start) record prepare_start; echo TRANSPORT >"$WORK/profile";;
''' + ('sfc) record recovery_sfc; test "$RECOVERY_FAIL" != 1;;\n' if action == 'dpdk' else '') +
                action + ')\n' + body + '\nesac\n')
            harness.chmod(0o755)
            result = subprocess.run([str(harness), action], env=dict(os.environ,
                WORK=raw, FEED=str(int(feed)), FAIL=fail, CURRENT=current,
                RECOVERY_FAIL=str(int(recovery_fail))), capture_output=True, text=True)
            return result, (root / 'events').read_text().splitlines()

    def test_ready_sfc_still_removes_guardian_and_receiver(self):
        result, events = self.run_transition('sfc', feed=True, current='SFC')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLess(events.index('stop_feed_consumers'), events.index('stop_feed_receiver'))
        self.assertNotIn('start_sfc_clients', events)

    def test_sfc_receiver_failure_stops_transition(self):
        result, events = self.run_transition('sfc', fail='stop_feed_receiver')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('SFC_ACTION_FAILED stage=stop_feed_receiver', result.stderr)
        self.assertNotIn('start_sfc_clients', events)

    def test_dpdk_stops_consumers_before_receiver(self):
        result, events = self.run_transition('dpdk', feed=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLess(events.index('stop_feed_consumers'), events.index('stop_sfc_clients'))
        self.assertLess(events.index('stop_sfc_clients'), events.index('stop_feed_receiver'))
        self.assertLess(events.index('stop_feed_receiver'), events.index('start_dpdk_client'))

    def test_each_dpdk_failure_reports_stage_and_recovers(self):
        for stage in ('stop_feed_consumers', 'stop_sfc_clients', 'stop_feed_receiver',
                      'stop_dpdk_client', 'wait_hugepages_zero', 'start_dpdk_client',
                      'require_mode_ready'):
            with self.subTest(stage=stage):
                result, events = self.run_transition('dpdk', feed=True, fail=stage)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn('DPDK_ACTION_FAILED stage=' + stage, result.stderr)
                self.assertEqual(events.count('recovery_baseline'), 1)
                if stage == 'stop_sfc_clients':
                    self.assertNotIn('stop_feed_receiver', events)

    def test_software_origin_is_remembered_before_start(self):
        result, events = self.run_transition('dpdk', profile='SOFTWARE', fail='start_dpdk_client')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('prepare_start', events)
        self.assertIn('recovery_baseline', events)

    def test_order_only_origin_recovers_without_starting_feed(self):
        result, events = self.run_transition('dpdk', fail='start_dpdk_client')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('recovery_sfc', events)
        self.assertNotIn('recovery_baseline', events)

    def test_recovery_failure_is_not_reported_as_success(self):
        result, events = self.run_transition('dpdk', fail='start_dpdk_client', recovery_fail=True)
        self.assertEqual(result.returncode, 125)
        self.assertIn('DPDK_RECOVERY_FAILED', result.stderr)
