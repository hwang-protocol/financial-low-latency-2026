"""Execute production shell assertions and transitions with controlled host operations."""
import os
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
TRANSPORT = (SCRIPTS / 'transport_labctl.sh').read_text()
CONTROL = (SCRIPTS / 'control-host.sh').read_text()


class BookFeedHealthTest(unittest.TestCase):
    def check(self, payload, later=None):
        if later is None:
            sample = json.loads(payload)
            sample['next_expected'] = sample.get('next_expected', 0) + 1
            later = json.dumps(sample)
        body = CONTROL.split('book_feed_healthy() {', 1)[1].split('\n}', 1)[0]
        script = '''
management_command() { printf '%s' "$STATE"; }
sleep() { STATE="$LATER"; }
book_feed_healthy() {
''' + body + '\n}\nbook_feed_healthy\n'
        return subprocess.run(['bash', '-c', script], env=dict(os.environ, STATE=payload, LATER=later),
                              capture_output=True, text=True)

    def test_accepts_open_book_guardian(self):
        result = self.check(
            '{"integrity":"HEALTHY","trading_gate":"OPEN","next_expected":2,'
            '"session":"0612260002","strategy":{"enabled":false}}')
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_rejects_mid_session_gap_and_strategy(self):
        gap = self.check(
            '{"integrity":"GAP","trading_gate":"INHIBITED_FEED_GAP","next_expected":1,'
            '"session":"0612260002","strategy":{"enabled":false}}')
        trading = self.check(
            '{"integrity":"HEALTHY","trading_gate":"OPEN","next_expected":2,'
            '"session":"0612260002","strategy":{"enabled":true}}')
        self.assertNotEqual(gap.returncode, 0)
        self.assertNotEqual(trading.returncode, 0)

    def test_rejects_frozen_healthy_state(self):
        state = '{"integrity":"HEALTHY","trading_gate":"OPEN","next_expected":100,"session":"S1","strategy":{"enabled":false}}'
        self.assertNotEqual(self.check(state, state).returncode, 0)

    def test_rejects_session_change_between_samples(self):
        state = '{"integrity":"HEALTHY","trading_gate":"OPEN","next_expected":100,"session":"S1","strategy":{"enabled":false}}'
        later = json.loads(state)
        later.update(session='S2', next_expected=101)
        self.assertNotEqual(self.check(state, json.dumps(later)).returncode, 0)


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
                       fail='', current='STALE', recovery_fail=False, clients_current=True,
                       target=''):
        end = {'sfc': 'dpdk', 'dpdk': 'reset-paper'}[action]
        body = TRANSPORT.split('\n  ' + action + ')\n', 1)[1].split('\n  ' + end + ')', 1)[0]
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / 'profile').write_text(profile)
            harness = root / 'ctl'
            harness.write_text('''#!/bin/bash
set -Eeuo pipefail
RUN_ID=test; RUN_DIR=/test; TRADER_HOST=trader
TARGET="${3:-}"
record() { echo "$1" >>"$WORK/events"; test "$FAIL" != "$1"; }
platform_is_software() { test "$(cat "$WORK/profile")" = SOFTWARE; }
platform_process_running() { test "$FEED" = 1; }
platform_stop_software_clients() { record stop_feed_consumers; }
verify_exchange_rss() { record verify_exchange_rss; }
collect_status() { printf '{"mode":"%s","transition":"READY"}' "$CURRENT"; }
posix_clients_current() { test "$CLIENTS_CURRENT" = 1; }
require_mode_ready() { record require_mode_ready; }
stop_sfc_clients() { record stop_sfc_clients; }
stop_feed_receiver() { record stop_feed_receiver; }
stop_dpdk_client() { record stop_dpdk_client; }
wait_hugepages_zero() { record wait_hugepages_zero; }
start_dpdk_client() { record start_dpdk_client; }
start_sfc_clients() { record start_sfc_clients; }
start_feed_receiver() { record start_feed_receiver; }
start_feed_book_guardian() { record start_feed_book_guardian; }
resync_book_feed() { record resync_book_feed; }
remote() { record remote; }
SSH=(remote)
case "$1" in
baseline) record recovery_baseline; test "$RECOVERY_FAIL" != 1;;
start) record prepare_start; echo TRANSPORT >"$WORK/profile";;
''' + ('sfc) record recovery_sfc; record "recovery_target=$TARGET"; test "$RECOVERY_FAIL" != 1;;\n' if action == 'dpdk' else '') +
                action + ')\n' + body + '\nesac\n')
            restore = 'restore_book_feed() {' + CONTROL.split('restore_book_feed() {', 1)[1].split('\n}', 1)[0] + '\n}\n'
            harness.write_text(harness.read_text().replace('case "$1" in', restore + 'case "$1" in'))
            harness.chmod(0o755)
            result = subprocess.run([str(harness), action, 'test', target], env=dict(os.environ,
                WORK=raw, FEED=str(int(feed)), FAIL=fail, CURRENT=current,
                RECOVERY_FAIL=str(int(recovery_fail)),
                CLIENTS_CURRENT=str(int(clients_current))), capture_output=True, text=True)
            return result, (root / 'events').read_text().splitlines()

    def test_ready_sfc_restores_receiver_and_book_guardian(self):
        result, events = self.run_transition('sfc', feed=True, current='SFC')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLess(events.index('stop_feed_consumers'), events.index('stop_feed_receiver'))
        self.assertLess(events.index('stop_feed_receiver'), events.index('start_feed_receiver'))
        self.assertLess(events.index('start_feed_receiver'), events.index('start_feed_book_guardian'))
        self.assertLess(events.index('start_feed_book_guardian'), events.index('resync_book_feed'))
        self.assertNotIn('start_sfc_clients', events)

    def test_ready_sfc_restarts_clients_when_their_image_is_stale(self):
        result, events = self.run_transition('sfc', current='SFC', clients_current=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLess(events.index('stop_sfc_clients'), events.index('start_sfc_clients'))
        self.assertEqual(events.count('start_sfc_clients'), 1)
        self.assertLess(events.index('start_sfc_clients'), events.index('start_feed_receiver'))
        self.assertEqual(events[-1], 'resync_book_feed')

    def test_sfc_receiver_failure_stops_transition(self):
        result, events = self.run_transition('sfc', fail='stop_feed_receiver')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('SFC_ACTION_FAILED stage=stop_feed_receiver', result.stderr)
        self.assertNotIn('start_sfc_clients', events)

    def test_ready_sfc_resync_failure_stops_transition(self):
        result, events = self.run_transition('sfc', current='SFC', fail='resync_book_feed')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('SFC_ACTION_FAILED stage=resync_book_feed', result.stderr)
        self.assertIn('start_feed_book_guardian', events)

    def test_formal_sfc_does_not_restart_paused_replay(self):
        for current in ('SFC', 'STALE'):
            with self.subTest(current=current):
                result, events = self.run_transition('sfc', current=current, target='order-only')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('stop_feed_receiver', events)
                self.assertNotIn('start_feed_book_guardian', events)
                self.assertNotIn('resync_book_feed', events)

    def test_formal_dpdk_failure_preserves_order_only_recovery(self):
        result, events = self.run_transition('dpdk', fail='start_dpdk_client', target='order-only')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('recovery_target=order-only', events)

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
                self.assertEqual(events.count('recovery_sfc'), 1)
                self.assertNotIn('recovery_baseline', events)
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

    def test_transport_with_live_receiver_still_recovers_to_sfc(self):
        result, events = self.run_transition('dpdk', feed=True, fail='start_dpdk_client')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('recovery_sfc', events)
        self.assertNotIn('recovery_baseline', events)

    def test_recovery_failure_is_not_reported_as_success(self):
        result, events = self.run_transition('dpdk', fail='start_dpdk_client', recovery_fail=True)
        self.assertEqual(result.returncode, 125)
        self.assertIn('DPDK_RECOVERY_FAILED', result.stderr)
