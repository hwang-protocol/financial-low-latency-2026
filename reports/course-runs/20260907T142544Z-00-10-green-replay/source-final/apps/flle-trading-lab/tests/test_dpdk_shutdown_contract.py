from pathlib import Path
import tempfile
import os
import subprocess
import unittest


APP_ROOT = Path(__file__).resolve().parents[1]
TRADER_SOURCE = APP_ROOT / "src" / "dpdk_trader.cpp"
POSIX_TRADER_SOURCE = APP_ROOT / "src" / "trader.cpp"
EXCHANGE_SOURCE = APP_ROOT / "src" / "exchange.cpp"
REMOTE_GUARD = APP_ROOT / "scripts" / "x2522-dpdk-trader-remote.sh"
LAB_CONTROL = APP_ROOT / "scripts" / "transport_labctl.sh"
BASE_CONTROL = APP_ROOT / "scripts" / "labctl.sh"


def find_checkout_root(app_root: Path) -> Path | None:
    for candidate in (app_root, *app_root.parents):
        if (candidate / "AGENTS.md").is_file() and (
            candidate / "Documents"
        ).is_dir() and (
            candidate / "apps/flle-trading-lab"
        ).resolve() == app_root.resolve():
            return candidate
    return None


CHECKOUT_ROOT = find_checkout_root(APP_ROOT)
RUN04_WRAPPER = None if CHECKOUT_ROOT is None else (
    CHECKOUT_ROOT
    / "Documents/newDoc/assets/06-kernel-bypass/07-dpdk-real-order.sh"
)
PREP_D_WRAPPER = None if CHECKOUT_ROOT is None else (
    CHECKOUT_ROOT
    / "Documents/newDoc/assets/06-kernel-bypass/03-four-path-lab-ready.sh"
)


class DpdkShutdownContractTest(unittest.TestCase):
    def test_formal_samples_skip_synchronous_ui_telemetry_and_publish_ready(self) -> None:
        posix = POSIX_TRADER_SOURCE.read_text(encoding="utf-8")
        dpdk = TRADER_SOURCE.read_text(encoding="utf-8")
        exchange = EXCHANGE_SOURCE.read_text(encoding="utf-8")
        self.assertIn("if (!measurement_sample) {", posix)
        self.assertIn("if (!work.measurement_sample) {", posix)
        self.assertIn("++measurement_ready_samples_", posix)
        self.assertIn('\\"ready_samples\\":', posix)
        self.assertIn("if (!measurement) {", dpdk)
        self.assertIn("if (!work.measurement) {", dpdk)
        self.assertIn("++measurement_ready_samples_", dpdk)
        self.assertIn('\\"ready_samples\\":', dpdk)
        self.assertIn('parts[0] == "MEASUREMENT_PROGRESS"', posix)
        self.assertIn('parts[0] == "MEASUREMENT_PROGRESS"', dpdk)
        self.assertIn('measurement ? "MDPK" : "DPDK"', dpdk)
        self.assertIn("order.clordid.front() == 'M'", exchange)
        self.assertIn("if (!formal_measurement)", exchange)
        self.assertIn("rte_eth_stats_get(0, &port_stats)", dpdk)
        for field in ("ipackets", "opackets", "imissed", "ierrors", "oerrors", "rx_nombuf"):
            self.assertIn(f"port_stats.{field}", dpdk)

    def test_runtime_only_tree_does_not_invent_a_checkout_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            misleading_root = Path(temporary)
            (misleading_root / "AGENTS.md").touch()
            (misleading_root / "Documents").mkdir()
            runtime_root = misleading_root / "runtime/flle-trading-lab"
            runtime_root.mkdir(parents=True)
            self.assertIsNone(find_checkout_root(runtime_root))

    def test_base_deployment_includes_shell_contracts_used_by_tests(self) -> None:
        control = BASE_CONTROL.read_text(encoding="utf-8")
        self.assertIn(
            'scp "$APP_DIR"/scripts/*.py "$APP_DIR"/scripts/*.sh', control
        )

    def test_fstack_shutdown_bypasses_incomplete_post_loop_cleanup(self) -> None:
        source = TRADER_SOURCE.read_text(encoding="utf-8")
        shutdown = source.index("void begin_reactor_shutdown()")
        half_close = source.index("ff_shutdown(order_fd_, SHUT_WR)", shutdown)
        process_exit = source.index("std::_Exit(")
        self.assertLess(process_exit, shutdown)
        self.assertLess(shutdown, half_close)
        self.assertNotIn("ff_stop_run(", source)
        self.assertNotIn("ff_close(", source)

    def test_reactor_requires_idle_work_and_peer_eof_before_clean_exit(self) -> None:
        source = TRADER_SOURCE.read_text(encoding="utf-8")
        shutdown = source[source.index("void begin_reactor_shutdown()") :]
        self.assertIn("active_.has_value()", shutdown)
        self.assertIn("mailbox_.has_value()", shutdown)
        self.assertIn("!tx_buffer_.empty()", shutdown)
        self.assertIn("queue_.depth() != 0", shutdown)
        self.assertIn(
            "std::lock_guard<std::mutex> submission_lock(submission_mutex_)",
            shutdown,
        )
        self.assertIn(
            "std::chrono::steady_clock::now() + std::chrono::seconds(2)",
            source,
        )
        self.assertIn("if (peer_eof_)", source)
        self.assertIn(
            "std::chrono::steady_clock::now() >= reactor_shutdown_deadline_",
            source,
        )

    def test_shutdown_receipt_is_flushed_before_process_exit(self) -> None:
        source = TRADER_SOURCE.read_text(encoding="utf-8")
        finish = source[
            source.index("[[noreturn]] void finish_reactor_shutdown(") :
            source.index("void begin_reactor_shutdown()")
        ]
        receipt = (
            "cleanup_mode=PROCESS_EXIT_BYPASS_INCOMPLETE_FSTACK_CLEANUP"
        )
        self.assertIn(receipt, finish)
        self.assertIn('<< " shutdown_rc=" << shutdown_rc_', finish)
        self.assertIn('<< " peer_eof=" << (peer_eof_ ? 1 : 0)', finish)
        self.assertLess(finish.index("std::cout.flush()"), finish.index("::write("))
        self.assertLess(finish.index("std::cerr.flush()"), finish.index("::write("))
        self.assertIn("while (written < text.size())", finish)
        self.assertLess(finish.index("::write("), finish.index("std::_Exit("))
        self.assertLess(finish.index("::fsync("), finish.index("std::_Exit("))

    def test_shutdown_eof_is_not_reported_as_a_transport_failure(self) -> None:
        source = TRADER_SOURCE.read_text(encoding="utf-8")
        drain = source[source.index("void drain_rx()") : source.index(
            "void process_soup(")
        ]
        self.assertIn("if (reactor_shutdown_started_)", drain)
        self.assertIn("peer_eof_ = true", drain)
        self.assertIn('fail("SOUP_EOF")', drain)
        self.assertLess(
            drain.index("if (reactor_shutdown_started_)"),
            drain.index('fail("SOUP_EOF")'),
        )

    def test_new_orders_are_rejected_once_shutdown_starts(self) -> None:
        source = TRADER_SOURCE.read_text(encoding="utf-8")
        command = source[source.index("std::string command(") : source.index(
            "void management_loop()"
        )]
        order_branch = command.index('parts[0] == "ORDER"')
        submit_lock = command.index(
            "std::lock_guard<std::mutex> submission_lock(submission_mutex_)",
            order_branch,
        )
        stop_guard = command.index("if (g_stop.load())", submit_lock)
        queue_call = command.index("queue_order(", stop_guard)
        self.assertLess(submit_lock, stop_guard)
        self.assertLess(stop_guard, queue_call)

    def test_remote_guard_records_and_propagates_trader_exit(self) -> None:
        guard = REMOTE_GUARD.read_text(encoding="utf-8")
        self.assertIn('echo "trader_exit_status=$trader_exit_status"', guard)
        self.assertIn('echo "cleanup_mode=$trader_cleanup_mode"', guard)
        self.assertIn('echo "shutdown_rc=$trader_shutdown_rc"', guard)
        self.assertIn('echo "peer_eof=$trader_peer_eof"', guard)
        self.assertIn(
            "grep -Fxc \"$cleanup_line\" \"$SESSION_DIR/fstack.log\"",
            guard,
        )
        self.assertIn('echo "wrapper_exit_status=$final_rc"', guard)
        self.assertIn("if wait_for_trader_exit 1; then", guard)
        self.assertIn('exit "$trader_rc"', guard)
        self.assertNotIn('wait "$trader_pid" 2>/dev/null || true', guard)

    def test_remote_guard_restores_hugetlbfs_baseline_and_hard_gates_state(
        self,
    ) -> None:
        guard = REMOTE_GUARD.read_text(encoding="utf-8")
        self.assertIn("HUGETLBFS_BASELINE=", guard)
        self.assertIn('hugetlbfs_mounted_by_wrapper=1', guard)
        self.assertIn('umount "$HUGETLBFS"', guard)
        self.assertIn(
            '[[ "$hugetlbfs_current" = "$HUGETLBFS_BASELINE" ]]', guard
        )
        self.assertIn('DPDK_FILE_PREFIX="flle06_', guard)
        self.assertIn('file_prefix=$DPDK_FILE_PREFIX', guard)
        self.assertIn('cmp -s "$HUGETLBFS_FILES_BASELINE"', guard)
        self.assertIn('-name "${DPDK_FILE_PREFIX}map_*"', guard)
        self.assertIn('-name "container-${DPDK_FILE_PREFIX}map_*"', guard)
        self.assertIn("remove_owned_hugefiles", guard)
        self.assertNotIn("-name 'rtemap_*' -delete", guard)
        self.assertIn('echo "restore_state=', guard)
        self.assertIn('echo "wrapper_exit_status=$final_rc"', guard)
        self.assertIn('return "$final_rc"', guard)

    def test_remote_gate_cannot_erase_a_lost_launcher_stop_request(self) -> None:
        guard = REMOTE_GUARD.read_text(encoding="utf-8")
        controller = LAB_CONTROL.read_text(encoding="utf-8")
        self.assertNotIn('rm -f "$STOP_FILE"', guard)
        self.assertIn("FLLE_DPDK_GATE_PID_FILE is required", guard)
        self.assertLess(
            guard.index('mv -- "$gate_tmp" "$GATE_PID_FILE"'),
            guard.index("=== acquire X2522 with safe VFIO ==="),
        )
        self.assertIn("taskset -c 0", controller)
        self.assertIn("find_gate_pid()", controller)
        self.assertIn("multiple exact DPDK ownership wrappers found", controller)

    def test_independent_systemd_lease_can_recover_a_killed_wrapper(self) -> None:
        guard = REMOTE_GUARD.read_text(encoding="utf-8")
        controller = LAB_CONTROL.read_text(encoding="utf-8")
        self.assertIn('if [[ "${1:-}" == --recover-only ]]', guard)
        self.assertIn('systemd-run --quiet --unit="$LEASE_UNIT"', guard)
        self.assertIn(
            'recovery_executor=systemd_timer_independent_of_wrapper', guard
        )
        self.assertIn('REMOTE_LOCK=/run/lock/flle-x2522-0000_03_00_0.lock', guard)
        self.assertIn('if ! flock -w 180 9; then', guard)
        self.assertIn('flock -w 120 9', guard)
        self.assertIn('flock -n 9', guard)
        before_mutation = guard.index("=== acquire X2522 with safe VFIO ===")
        self.assertLess(guard.index("systemd-run --quiet"), before_mutation)
        self.assertLess(guard.index('lease_token=$LEASE_TOKEN'), before_mutation)
        recovery = guard[guard.index("recover_only() {") : guard.index(
            'if [[ "${1:-}" == --recover-only ]]'
        )]
        self.assertGreaterEqual(recovery.count('"$token_file"'), 4)
        self.assertIn("stale_after_lock=1 action=NONE", recovery)
        self.assertIn('kill -KILL "$pid"', recovery)
        self.assertIn('"$devbind" --bind="$baseline_driver" "$BDF"', recovery)
        self.assertIn('mv -- "$token_file" "$consumed_token_file"', recovery)
        self.assertIn(
            'systemctl stop "$LEASE_UNIT.timer" "$LEASE_UNIT.service"',
            guard,
        )
        self.assertIn('state=CONSUMED', controller)
        self.assertIn('lease.token.consumed', controller)
        self.assertIn('lease-recovery.receipt', controller)

    def test_sfc_only_stop_does_not_require_zero_hugepages_too_early(self) -> None:
        controller = LAB_CONTROL.read_text(encoding="utf-8")
        no_dpdk_session = controller.index(
            'test ! -s "$session_dir/lease-start.receipt"'
        )
        early_exit = controller.index("exit 0", no_dpdk_session)
        zero_hugepages = controller.index(
            'test "$(cat /sys/kernel/mm/hugepages/hugepages-2048kB/nr_hugepages)" = 0',
            early_exit,
        )
        self.assertLess(early_exit, zero_hugepages)

    def test_lease_preflight_and_partial_mutation_are_fail_closed(self) -> None:
        guard = REMOTE_GUARD.read_text(encoding="utf-8")
        controller = LAB_CONTROL.read_text(encoding="utf-8")
        preflight = guard.index("echo '=== preflight ==='")
        trap_install = guard.index("trap finish EXIT")
        mutation_state = guard.index("write_ownership_state MUTATING gate")
        first_hardware_write = guard.index("sysctl -w vm.nr_hugepages=256")
        self.assertLess(preflight, trap_install)
        self.assertLess(trap_install, mutation_state)
        self.assertLess(mutation_state, first_hardware_write)
        self.assertIn('if test -s "$session_dir/lease.token"; then', controller)
        self.assertIn('lease.token.consumed', controller)
        self.assertIn('timer_state" = inactive', controller)
        self.assertIn('service_state" = inactive', controller)

    def test_recovery_identity_checks_do_not_depend_on_errexit(self) -> None:
        guard = REMOTE_GUARD.read_text(encoding="utf-8")
        recovery = guard[guard.index("validate_identity() {") : guard.index(
            'exec 9>"$REMOTE_LOCK"'
        )]
        for contract in (
            'IFS= read -r line <"$identity" || return 1',
            'test -z "${extra:-}" || return 1',
            'test "$token_field" = "lease_token=$expected_token" || return 1',
            'test "$start" = "$expected_start" || return 1',
            'test "$boot" = "$expected_boot" || return 1',
        ):
            self.assertIn(contract, recovery)

    def test_live_path_receipts_are_bound_to_process_generations_and_lease(
        self,
    ) -> None:
        control = LAB_CONTROL.read_text(encoding="utf-8")
        sfc = control[
            control.index("attest_sfc_receipts() {") :
            control.index("attest_dpdk_receipt() {")
        ]
        self.assertIn('identity="$run_dir/$name.identity"', sfc)
        self.assertIn('test "$start_ticks" = "$expected_start" || return 1', sfc)
        self.assertIn('test "$current_boot" = "$expected_boot" || return 1', sfc)
        self.assertIn(
            'socket_identity="$(process_identity trader-socket', sfc
        )
        self.assertNotIn(
            '< <(process_identity trader-socket', sfc
        )

        dpdk = control[
            control.index("attest_dpdk_receipt() {") :
            control.index("capture_native_receipt() {")
        ]
        self.assertIn('test -s "$session_dir/trader.identity"', dpdk)
        self.assertIn('test "$(<"$session_dir/lease.token")" = "$lease_token"', dpdk)
        self.assertIn("grep -Fxq 'state=OWNED'", dpdk)
        self.assertIn('test "$boot_id" = "$expected_boot"', dpdk)
        self.assertIn('expected_argv=(', dpdk)
        self.assertIn(
            'test "${#observed_argv[@]}" -eq "${#expected_argv[@]}"',
            dpdk,
        )

    def test_foreign_listener_signal_revalidates_pid_generation(self) -> None:
        control = LAB_CONTROL.read_text(encoding="utf-8")
        cleanup = control[
            control.index("stop_foreign_course_listener() {") :
            control.index("wait_hugepages_zero() {")
        ]
        signal = cleanup.index('kill -INT "$pid"')
        self.assertLess(
            cleanup.index('start_ticks="$(awk'), signal
        )
        self.assertLess(
            cleanup.index('test "$(awk'), signal
        )
        self.assertLess(
            cleanup.index('test "$(tr'), signal
        )
        self.assertIn('case "$current_listener" in *"pid=$pid,"*)', cleanup)

    def test_dpdk_prime_helper_has_generation_identity_and_all_path_cleanup(self) -> None:
        controller = LAB_CONTROL.read_text(encoding="utf-8")
        start = controller[controller.index("start_dpdk_prime() {") :]
        stop = start[start.index("stop_dpdk_prime() {") : start.index(
            "start_dpdk_client() {"
        )]
        self.assertIn("dpdk-prime.identity", start)
        self.assertIn("start_ticks=%s boot_id=%s", start)
        self.assertIn("flle-dpdk-prime", start)
        self.assertIn("deadline=$((SECONDS + 180))", start)
        self.assertIn("multiple", stop.lower())
        self.assertIn('kill -TERM "$pid"', stop)
        self.assertIn('kill -KILL "$pid"', stop)
        self.assertIn("DPDK prime helper survived cleanup", stop)
        launch = controller[controller.index("start_dpdk_client() {") :
                            controller.index("start_exchange() {")]
        self.assertIn("trap dpdk_start_failure ERR", launch)
        self.assertGreaterEqual(launch.count("stop_dpdk_prime"), 2)

    def test_preparation_d_reuses_platform_and_checks_identity_before_ready(self) -> None:
        if PREP_D_WRAPPER is None:
            self.skipTest("runtime-only deployment has no Documents tree")
        script = PREP_D_WRAPPER.read_text(encoding="utf-8")
        self.assertIn("source Documents/reports/run-state/02-trading-baseline.env", script)
        self.assertNotIn('"$CTL" deploy', script)
        self.assertNotIn('>"$STATE"', script)
        report = script.index("result=READY")
        self.assertLess(script.index('cmp "$OUT/raw/before.txt" "$OUT/raw/after.txt"'), report)
        self.assertLess(script.index('test "$ready" -eq 1'), report)
        self.assertIn("/api/transport-lab", script)
        self.assertIn("exchange_and_gui=UNCHANGED", script)
        self.assertNotIn("/api/order", script)

    def test_four_classroom_order_cards_each_submit_once_and_hide_raw_json(self) -> None:
        if CHECKOUT_ROOT is None:
            self.skipTest("runtime-only deployment has no Documents tree")
        asset_root = CHECKOUT_ROOT / "Documents/newDoc/assets/06-kernel-bypass"
        names = (
            "04-socket-real-order.sh",
            "05-onload-real-order.sh",
            "06-tcpdirect-real-order.sh",
            "07-dpdk-real-order.sh",
        )
        for name in names:
            with self.subTest(asset=name):
                script = (asset_root / name).read_text(encoding="utf-8")
                self.assertLessEqual(len(script.splitlines()), 50)
                self.assertEqual(script.count("/api/order"), 1)
                self.assertIn('print("task=', script)
                self.assertIn('print("result="+row["result"])', script)
                self.assertIn('print("order_rtt_ns="', script)
                self.assertIn('print("engine="', script)
                self.assertIn('print("scope=单笔路径验证；正式延迟比较看运行 ⑤")', script)
                self.assertNotIn('print("queue_to_send_ns="', script)
                self.assertNotIn('print("submit_to_final_ns="', script)
                self.assertNotIn('线程唤醒冷启动', script)
                self.assertIn('executed=0', script)
                self.assertIn('test "$executed" -eq 1', script)
                self.assertIn("tee -a \"$RAW/result.txt\"", script)
                self.assertNotIn('tee "$RAW/order-reply.json"', script)
                self.assertNotIn('tee "$RAW/order-state.json"', script)
                self.assertNotIn('tee "$RAW/transport-lab.json"', script)

    def test_experiment_finish_keeps_reusable_sfc_gui_online(self) -> None:
        if CHECKOUT_ROOT is None:
            self.skipTest("runtime-only deployment has no Documents tree")
        script = (
            CHECKOUT_ROOT
            / "Documents/newDoc/assets/06-kernel-bypass/09-four-path-handoff.sh"
        ).read_text(encoding="utf-8")
        self.assertLessEqual(len(script.splitlines()), 50)
        self.assertNotIn(
            "sha256sum raw/* kernel-onload-mechanism/SHA256SUMS",
            script,
        )
        self.assertIn('bash "$CTL" sfc "$RUN_ID"', script)
        self.assertIn('reuse-state "$RUN_ID"', script)
        self.assertNotIn('transport_labctl.sh stop', script)
        self.assertNotIn('01-restore-trading-lab.sh', script)
        self.assertIn("http://10.1.1.101:8088/api/transport-lab", script)
        self.assertIn('== "WAITING"', script)
        self.assertIn('clients=Socket, Onload, TCPDirect ONLINE', script)
        self.assertIn('dpdk=WAITING', script)
        self.assertIn('next=第 07 章', script)

    def test_run_five_only_measures_and_formats_the_four_path_comparison(self) -> None:
        if CHECKOUT_ROOT is None:
            self.skipTest("runtime-only deployment has no Documents tree")
        script = (
            CHECKOUT_ROOT
            / "Documents/newDoc/assets/06-kernel-bypass/08-four-path-compare.sh"
        ).read_text(encoding="utf-8")
        self.assertEqual(script.count("transport_labctl.sh measure"), 1)
        self.assertEqual(script.count("analyze_four_transport_raw.py"), 1)
        self.assertNotIn("measure_kernel_onload_mechanism.py", script)
        self.assertNotIn("/api/order", script)

    def test_course_manifests_cover_nested_platform_evidence(self) -> None:
        if CHECKOUT_ROOT is None:
            self.skipTest("runtime-only deployment has no Documents tree")
        for name in ("08-four-path-compare.sh", "09-four-path-handoff.sh"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                for name_ in ("raw/plain.txt", "raw/code-contract/with space.txt",
                              "run.env", "four-path-comparison/SHA256SUMS",
                              "four-path-comparison/balanced-analysis/SHA256SUMS"):
                    path = root / name_
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("evidence\n")
                script = (CHECKOUT_ROOT / "Documents/newDoc/assets/06-kernel-bypass" / name).read_text()
                seal = script.strip().splitlines()[-1]
                subprocess.run(["bash", "-ec", seal], env={**os.environ, "OUT": tmp}, check=True)
                subprocess.run(["sha256sum", "-c", "SHA256SUMS"], cwd=root, check=True, stdout=subprocess.DEVNULL)
                manifest = (root / "SHA256SUMS").read_text()
                self.assertIn("raw/code-contract/with space.txt", manifest)
                self.assertIn("run.env", manifest)

    def test_formal_remeasurement_preserves_prior_native_receipts(self) -> None:
        script = LAB_CONTROL.read_text().split("  measure)\n", 1)[1]
        remote = script.split("<<'REMOTE'\n", 1)[1].split("\nREMOTE", 1)[0]
        self.assertIn('for receipt_host in "$EXCHANGE_HOST" "$TRADER_HOST"', script)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            trees = ("native-receipts", "native-exchange-receipts", "native-exchange-staging")
            for attempt in ("first", "second"):
                for tree in trees:
                    receipts = root / tree
                    receipts.mkdir()
                    (receipts / "pre.txt").write_text(attempt)
                subprocess.run(["bash", "-s", "--", tmp, attempt], input=remote, text=True, check=True)
                self.assertTrue(all(not (root / tree).exists() for tree in trees))
            for attempt in ("first", "second"):
                for tree in trees:
                    self.assertEqual((root / "native-receipts-history" / attempt / tree / "pre.txt").read_text(), attempt)

    def test_controller_requires_terminal_dpdk_shutdown_receipts(self) -> None:
        control = LAB_CONTROL.read_text(encoding="utf-8")
        self.assertIn("live four-path RUN $live_run still holds an incomplete lab", control)
        self.assertIn('case "$command" in *flle-trading-lab-*)', control)
        self.assertIn('case "$command" in *"$expected"*)', control)
        self.assertNotIn('*flle-trading-lab-*"$expected"*', control)
        self.assertIn("gate-exit.receipt", control)
        self.assertIn("trader-exit.receipt", control)
        self.assertIn('wrapper_status="$(sed -n', control)
        self.assertIn('if test "$wrapper_status" -eq 0; then', control)
        self.assertIn("grep -Fxq 'trader_exit_status=0'", control)
        self.assertIn("grep -Fxq 'trader_termination=SIGINT'", control)

    def test_dpdk_stop_retries_management_listener_close_with_diagnostic(self) -> None:
        control = LAB_CONTROL.read_text(encoding="utf-8")
        stop = control[
            control.index("stop_dpdk_client() {") :
            control.index("attest_sfc_receipts() {")
        ]
        listener_wait = (
            "for _ in \\$(seq 1 40); do listener=\\$(ss -ltnpH "
            "'( sport = :48125 )'"
        )
        self.assertIn(listener_wait, stop)
        self.assertIn("sleep 0.1; done", stop)
        self.assertIn(
            "DPDK management listener remained LISTEN after client stop:",
            stop,
        )
        self.assertIn("DPDK_MANAGEMENT_LISTENER_CLOSED listen=0", stop)
        self.assertLess(stop.index(listener_wait), stop.index("stop_dpdk_prime"))
        self.assertIn(
            "grep -Fxq 'cleanup_mode="
            "PROCESS_EXIT_BYPASS_INCOMPLETE_FSTACK_CLEANUP'",
            control,
        )
        self.assertIn("grep -Fxq 'shutdown_rc=0'", control)
        self.assertIn("grep -Fxq 'peer_eof=1'", control)
        self.assertIn("grep -Fxq 'restore_state=PASS'", control)
        self.assertIn("grep -Fxq 'ownership_state=CONSUMED'", control)
        self.assertIn(
            "DPDK_EXCHANGE_ENDPOINT_CLOSED established=0", control
        )
        sfc_action = control[control.index("  sfc)\n"):control.index("  dpdk)\n")]
        self.assertLess(
            sfc_action.index('current="$(collect_status)"'),
            sfc_action.index("stop_sfc_clients"),
        )
        self.assertLess(
            sfc_action.index("stop_sfc_clients"),
            sfc_action.index("stop_dpdk_client"),
        )

    def test_dpdk_stop_tolerates_proc_exit_while_finding_gate_pid(self) -> None:
        control = LAB_CONTROL.read_text(encoding="utf-8")
        finder = control[
            control.index("find_gate_pid() {") :
            control.index("verify_gate_identity() {")
        ]
        guarded_read = (
            'command="$(tr \'\\0\' \' \' 2>/dev/null '
            '<"$proc/cmdline" || true)"'
        )
        self.assertIn(guarded_read, finder)
        self.assertIn('test -n "$command" || continue', finder)
        self.assertNotIn(
            'command="$(tr \'\\0\' \' \' <"$proc/cmdline")"',
            finder,
        )

    def test_dpdk_stop_retries_hugepage_release_and_reports_late_gate(self) -> None:
        control = LAB_CONTROL.read_text(encoding="utf-8")
        stop = control[
            control.index("stop_dpdk_client() {") :
            control.index("attest_sfc_receipts() {")
        ]
        self.assertIn("DPDK_STOP_HARD_GATE_FAILED", stop)
        self.assertIn("for _ in $(seq 1 400); do", stop)
        self.assertIn("sysctl -w vm.nr_hugepages=0", stop)
        self.assertIn('test "$pages" = 0 && break', stop)
        self.assertIn("DPDK hugepages remained allocated after client stop:", stop)
        self.assertIn("surplus_pages", stop)
        self.assertIn("flock -w 30 8", stop)
        self.assertIn(
            "timed out waiting for the DPDK wrapper to release the X2522 lock",
            stop,
        )

    def test_exchange_x2522_rss_is_fixed_verified_and_restored(self) -> None:
        control = LAB_CONTROL.read_text(encoding="utf-8")
        configure = control[
            control.index("configure_exchange_rss() {") :
            control.index("verify_exchange_rss() {")
        ]
        verify = control[
            control.index("verify_exchange_rss() {") :
            control.index("restore_exchange_rss() {")
        ]
        restore = control[
            control.index("restore_exchange_rss() {") :
            control.index("start_exchange() {")
        ]
        self.assertIn('ethtool -X "$iface" weight 0 1 0 0', configure)
        self.assertIn('test "$applied_entries" -eq 128', configure)
        self.assertIn('test "$applied_bad" -eq 0', configure)
        self.assertIn('effective_affinity_list', configure)
        self.assertIn('systemctl stop irqbalance', configure)
        self.assertIn('>"/proc/irq/$irq/smp_affinity_list"', configure)
        self.assertIn('irqbalance_during_run=inactive', configure)
        self.assertIn('exchange_cpu=2', configure)
        self.assertIn('current="$(ethtool -x "$iface")"', verify)
        self.assertIn('test "$current_sha" = "$expected_sha"', verify)
        self.assertIn('test "$requested_cpu" = 2', verify)
        self.assertIn('test "$effective_cpu" = 2', verify)
        self.assertIn('test "$irqbalance_state" = inactive', verify)
        self.assertIn('ethtool -X "$iface" equal 4', restore)
        self.assertIn('cmp -s "$current" "$applied"', restore)
        self.assertIn('cmp -s "$current" "$baseline"', restore)
        self.assertIn('systemctl start irqbalance', restore)
        self.assertIn('X2522_EXCHANGE_IRQ_RESTORED', restore)
        self.assertIn('irqbalance_current" = "$irqbalance_baseline"', restore)
        self.assertIn('already=1', restore)
        self.assertIn(
            'X2522 Exchange IRQ changed outside the owned course transition',
            restore,
        )
        start = control[control.index("  start)\n") : control.index("  sfc)\n")]
        self.assertLess(
            start.index("configure_exchange_rss"),
            start.index("start_exchange"),
        )
        self.assertIn("restore_exchange_rss || recovery_failed=1", start)
        stop_start = control.index("  stop)\n")
        stop = control[stop_start : control.index("  *)\n", stop_start)]
        self.assertIn("restore_exchange_rss", stop)
        self.assertIn('"exchange_rss"', control)
        self.assertIn("X2522_RSS_ALL_BUCKETS_TO_EXCHANGE_CPU_QUEUE", control)
        sfc_start = control.index("  sfc)\n")
        sfc = control[sfc_start : control.index("  dpdk)\n", sfc_start)]
        dpdk_start = control.index("  dpdk)\n")
        dpdk = control[dpdk_start : control.index("  measure)\n", dpdk_start)]
        self.assertGreaterEqual(sfc.count("verify_exchange_rss"), 2)
        self.assertGreaterEqual(dpdk.count("verify_exchange_rss"), 2)

    def test_run04_restore_is_hard_gated_and_exit_fallback_keeps_rc(self) -> None:
        if RUN04_WRAPPER is None:
            self.skipTest("runtime-only deployment has no Documents tree")
        self.assertTrue(
            RUN04_WRAPPER.is_file(),
            f"full checkout lacks the Chapter 06 Run 04 asset: {RUN04_WRAPPER}",
        )
        script = RUN04_WRAPPER.read_text(encoding="utf-8")
        self.assertIn("post_mode(){ curl --max-time 620 -fsS", script)
        fallback = script[
            script.index("restore(){") : script.index("trap restore EXIT")
        ]
        self.assertIn("rc=$?; trap - EXIT", fallback)
        self.assertIn('if test "$rc" -ne 0', fallback)
        self.assertIn("transport_labctl.sh sfc", fallback)
        self.assertIn("|| exit 125", fallback)
        self.assertNotIn("|| true", fallback)
        self.assertIn('exit "$rc"', fallback)

        explicit = script[script.index('restored="$(post_mode SFC)"') :]
        self.assertNotIn("|| true", explicit)
        self.assertIn('x.get("mode")=="SFC"', explicit)
        self.assertIn('x.get("transition")=="READY"', explicit)
        self.assertIn('x.get("owner")=="sfc"', explicit)
        self.assertLess(
            explicit.index('printf \'%s\\n\' "$restored"'),
            explicit.index("trap - EXIT"),
        )

    def test_run04_reads_engine_from_attested_native_schema(self) -> None:
        if RUN04_WRAPPER is None:
            self.skipTest("runtime-only deployment has no Documents tree")
        script = RUN04_WRAPPER.read_text(encoding="utf-8")
        self.assertIn('receipt=json.load(open(sys.argv[3]))', script)
        self.assertIn('Path(receipt["local_directory"])', script)
        self.assertIn(
            'software.get("network_engine", software.get("network_reactor"))',
            script,
        )
        self.assertIn('if engine != "FSTACK_POLL"', script)
        self.assertNotIn(
            'lab["clients"]["trader_dpdk"]["software"]', script
        )
        self.assertNotIn('$API/api/transport-lab', script)

if __name__ == "__main__":
    unittest.main()
