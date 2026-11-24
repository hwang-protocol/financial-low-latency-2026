import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
SPEC = importlib.util.spec_from_file_location(
    "analyze_four_transport_raw", SCRIPT_DIR / "analyze_four_transport_raw.py"
)
assert SPEC is not None and SPEC.loader is not None
ANALYZE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ANALYZE)


class BalancedAnalysisTest(unittest.TestCase):
    def test_common_clock_identity_rejects_broken_sample(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "common-clock identity"):
            ANALYZE.validate_common_clock_sample(
                {
                    "queue_to_send_ns": 7,
                    "order_rtt_ns": 11,
                    "submit_to_final_ns": 19,
                },
                Path("raw.json"),
                0,
            )

    def test_common_clock_identity_rejects_boolean_as_integer(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "non-integer clock field"):
            ANALYZE.validate_common_clock_sample(
                {
                    "queue_to_send_ns": False,
                    "order_rtt_ns": 11,
                    "submit_to_final_ns": 11,
                },
                Path("raw.json"),
                0,
            )

    def test_analysis_contract_requires_v13_and_emits_v11(self) -> None:
        self.assertEqual(
            ANALYZE.EXPECTED_SOURCE_SCHEMA,
            "flle.ch06-four-order-paths.v13",
        )
        self.assertEqual(
            ANALYZE.ANALYSIS_SCHEMA,
            "flle.ch06-four-order-paths-balanced-analysis.v11",
        )

    def test_presend_warmup_observation_stays_in_evidence_not_classroom_output(self) -> None:
        source = Path(ANALYZE.__file__).read_text(encoding="utf-8")
        self.assertIn('"tcpdirect_presend_warmup_boundary"', source)
        self.assertIn("OBSERVED_SUBMIT_TO_OUCH_SEND_WINDOW_NOT_CAUSAL_SUBTIMERS", source)
        self.assertNotIn("预热边界：TCPDirect submit→send >=19 ms", source)
        self.assertNotIn("发送前窗口最大值：TCPDirect", source)
        self.assertIn("测量方法：4×4 Williams", source)
        self.assertIn("订单结果：warmup Executed=1600", source)
        self.assertIn("路径验证：16/16 个测试单元", source)
        self.assertNotIn('print("DPDK 端点：', source)
        self.assertNotIn('print("TCPDirect 重传观察：', source)
        self.assertNotIn("lost wake", source.lower())

        rows = []
        for index in range(4):
            rows.append(
                {
                    "transport": "TCPDIRECT",
                    "warmup_raw_samples": [
                        {"queue_to_send_ns": 20_000_000 if index != 1 else 10_000},
                        {"queue_to_send_ns": 12_000},
                    ],
                    "raw_samples": [
                        {"queue_to_send_ns": 90_000},
                        {"queue_to_send_ns": 80_000},
                    ],
                }
            )
        observed = ANALYZE.summarize_tcpdirect_presend_boundary(rows)
        self.assertEqual(observed["warmup_samples"], 8)
        self.assertEqual(observed["warmup_at_or_above_threshold"], 3)
        self.assertEqual(observed["warmup_first_sample_at_or_above_threshold"], 3)
        self.assertEqual(observed["warmup_max_ns"], 20_000_000)
        self.assertEqual(observed["measured_samples"], 8)
        self.assertEqual(observed["measured_at_or_above_threshold"], 0)
        self.assertEqual(observed["measured_max_ns"], 90_000)

    def test_observer_absence_contract_requires_exact_two_endpoints(self) -> None:
        expected = [
            {"host": "10.1.1.101", "port": 8088, "state": "ABSENT"},
            {"host": "10.1.1.2", "port": 48606, "state": "ABSENT"},
        ]
        self.assertEqual(
            ANALYZE.validate_observer_absence_contract(
                {"observer_absence_before_measurement": expected}
            ),
            expected,
        )
        invalid_contracts = (
            {},
            {"observer_absence_before_measurement": expected[:1]},
            {
                "observer_absence_before_measurement": [
                    {**expected[0], "state": "PRESENT"},
                    expected[1],
                ]
            },
            {
                "observer_absence_before_measurement": [
                    expected[0],
                    {**expected[1], "port": 48607},
                ]
            },
        )
        for contract in invalid_contracts:
            with self.subTest(contract=contract), self.assertRaisesRegex(
                RuntimeError, "observer absence contract is not exact"
            ):
                ANALYZE.validate_observer_absence_contract(contract)

    def test_analysis_emits_validated_observer_witness_not_boolean(self) -> None:
        source = Path(ANALYZE.__file__).read_text(encoding="utf-8")
        self.assertNotIn('"gateway_stopped_during_measurement": True', source)
        self.assertIn(
            '"observer_absence_before_measurement": observer_absence', source
        )

    def make_native_fixture(
        self,
        root: Path,
        transport: str,
        *,
        phase: str = "pre",
        orders: int = 7,
        ctpio_packets: int = 11,
        ctpio_fallbacks: int = 0,
        onload_cross_block: bool = False,
        omit_dpdk_ull: bool = False,
        exchange_ss_pid: int = 654,
        exchange_listener_pid: int = 654,
        tcpdirect_retransmits: int = 0,
        tcpdirect_txq_added: int = 19,
        tcpdirect_local_port: int = 45678,
        dpdk_bdf: str = "0000:03:00.0",
        dpdk_decoy_bdf: str | None = None,
        dpdk_peer_ports: tuple[int, ...] = (45678,),
        dpdk_extra_ss_lines: tuple[str, ...] = (),
        dpdk_imissed: int = 0,
        client_exe_path: str | None = None,
        client_cmdline_path: str | None = None,
        client_exe_sha256: str = "d" * 64,
        client_manifest_sha256: str | None = None,
    ) -> tuple[dict, Path]:
        prefix = Path("native-receipts") / f"1-1-{transport.lower()}" / phase
        directory = root / prefix
        directory.mkdir(parents=True)
        pid = 321
        binary = {
            "TCPDIRECT": "flle-trader-tcpdirect",
            "DPDK": "flle-trader-dpdk",
        }.get(transport, "flle-trader")
        if client_exe_path is None:
            client_exe_path = (
                "/var/tmp/flle-trading-lab-unit/transport-runtime/"
                f"flle-ch06-four-path/bin/{binary}"
            )
        if client_manifest_sha256 is None:
            client_manifest_sha256 = client_exe_sha256
        if client_cmdline_path is None:
            client_cmdline_path = client_exe_path
        runtime_archive_sha = "e" * 64
        runtime_manifest_sha = "f" * 64
        checkpoint_sha = "c" * 64
        itch_sha = "9" * 64
        label = {
            "SOCKET": "POSIX_SOCKET",
            "OPENONLOAD": "OPENONLOAD",
            "TCPDIRECT": "TCPDIRECT_ZF",
            "DPDK": "DPDK_FSTACK",
        }[transport]
        management_port = {
            "SOCKET": 48122,
            "OPENONLOAD": 48123,
            "TCPDIRECT": 48124,
            "DPDK": 48125,
        }[transport]
        user_ref_base = {
            "SOCKET": 2100000000,
            "OPENONLOAD": 2500000000,
            "TCPDIRECT": 2900000000,
            "DPDK": 3900000000,
        }[transport]
        user_ref_span = 1000000 if transport == "DPDK" else 100000
        measurement_generation = 1 if phase == "pre" else 2
        measurement_ready = 1 if phase == "pre" else 1000
        order_tid = 777
        management_tid = 778
        bridge_tid = 779
        software = {
            "queue_mode": "DEQUE_CV",
            "queue_locked": True,
            "queue_full_drops": 0,
            "order_thread_tid": order_tid,
            "order_thread_cpu": 2,
            "order_thread_allowed_count": 1,
            "management_thread_tid": management_tid,
            "management_thread_cpu": 3,
            "management_thread_allowed_count": 1,
            "network_engine": {
                "SOCKET": "KERNEL_SOCKET",
                "OPENONLOAD": "ONLOAD_USER_STACK",
                "TCPDIRECT": "ZF_REACTOR_POLL",
            }.get(transport, "FSTACK_POLL"),
        }
        if transport == "DPDK":
            software.update(
                {
                    "bridge_thread_tid": bridge_tid,
                    "bridge_thread_cpu": 3,
                    "bridge_thread_allowed_count": 1,
                }
            )
        state_value = {
                "status": "ONLINE",
                "role": "MANUAL",
                "market_protocol": (
                    "CENTRAL_GATEWAY_BOOK"
                    if transport == "DPDK" else "COMMON_GATEWAY_BOOK"
                ),
                "order_protocol": "OUCH_5.0_OVER_SOUPBINTCP",
                "order_transport": label,
                "paper_epoch": 1,
                "market_receiver_ready": False,
                "user_ref_base": user_ref_base,
                "user_ref_span": user_ref_span,
                "user_ref_end_exclusive": user_ref_base + user_ref_span,
                "user_ref_next": user_ref_base + (1 if phase == "pre" else 1100),
                "tcp_nodelay": None if transport == "TCPDIRECT" else True,
                "nagle_semantics": (
                    "ZF_API_NO_POSIX_TCP_NODELAY"
                    if transport == "TCPDIRECT"
                    else "FSTACK_GETSOCKOPT_VERIFIED"
                    if transport == "DPDK"
                    else "POSIX_CONNECT_GETSOCKOPT_VERIFIED"
                ),
                "stats": {"orders": orders, "fills": orders},
                "measurement_latency": {
                    "generation": measurement_generation,
                    "ready_samples": measurement_ready,
                },
                "software_latency": software,
            }
        if transport == "DPDK":
            state_value["heartbeat_enabled"] = False
            state_value["dpdk_port_stats"] = {
                "port_id": 0,
                "ipackets": orders * 2,
                "opackets": orders * 2 + 1,
                "imissed": dpdk_imissed,
                "ierrors": 0,
                "oerrors": 0,
                "rx_nombuf": 0,
            }
        state = json.dumps(state_value, separators=(",", ":")) + "\n"
        run_dir = Path(client_exe_path).parents[3]
        if transport == "DPDK":
            client_argv = [
                client_cmdline_path,
                "--conf", (run_dir / "dpdk-session/f-stack.effective.ini").as_posix(),
                "--proc-type=primary",
                "--proc-id=0",
            ]
        else:
            clordid_prefix = {
                "SOCKET": "SOCK",
                "OPENONLOAD": "ONLD",
                "TCPDIRECT": "TCPD",
            }[transport]
            client_argv = [
                client_cmdline_path,
                "--role", "MANUAL",
                "--data-ip", "20.1.1.2",
                "--exchange-data-ip", "20.1.1.1",
                "--management-ip", "10.1.1.2",
                "--telemetry-host", "10.1.1.101",
                "--book-checkpoint", (run_dir / "opening-book.checkpoint").as_posix(),
                "--market-receiver", "0",
                "--order-queue", "DEQUE_CV",
                "--lock-order-queue", "1",
                "--order-cpu", "2",
                "--management-cpu", "3",
                "--management-port", str(management_port),
                "--user-ref-base", str(user_ref_base),
                "--user-ref-span", str(user_ref_span),
                "--clordid-prefix", clordid_prefix,
                "--order-transport-label", label,
            ]
        listener = (
            f'LISTEN 0 128 10.1.1.2:{management_port} 0.0.0.0:* '
            f'users:(("client",pid=321,fd=7))'
        )
        process_lines = [
            "pid=321",
            "start_ticks=654",
            "boot_id=boot-unit",
            f"cmdline={' '.join(client_argv)} ",
            f"exe_path={client_exe_path}",
            f"exe_sha256={client_exe_sha256}",
            f"exe_manifest_sha256={client_manifest_sha256}",
            f"checkpoint_sha256={checkpoint_sha}",
            f"measurement_generation={measurement_generation}",
            f"measurement_ready_samples={measurement_ready}",
            "management_listener_count=1",
            f"management_listener_ss_line_1={listener}",
            f"argv_count={len(client_argv)}",
            *(f"argv_{index:02d}={value}"
              for index, value in enumerate(client_argv)),
            f"thread_order_tid={order_tid}",
            (
                "thread_order_name=flle-trader-dpd"
                if transport == "DPDK" else "thread_order_name=flle-order"
            ),
            "thread_order_cpus_allowed_list=2",
            f"thread_management_tid={management_tid}",
            "thread_management_name=flle-mgmt",
            "thread_management_cpus_allowed_list=3",
        ]
        if transport == "DPDK":
            lease_token = "unit-run-0"
            process_lines.extend(
                [
                    f"thread_bridge_tid={bridge_tid}",
                    "thread_bridge_name=flle-bridge",
                    "thread_bridge_cpus_allowed_list=3",
                    f"env_FLLE_DPDK_GATE_PID_FILE={run_dir}/trader-dpdk-gate.pid",
                    f"env_FLLE_DPDK_LEASE_TOKEN={lease_token}",
                    "env_FLLE_DPDK_DEADMAN=1800",
                    f"env_FLLE_DPDK_USER_REF_BASE={user_ref_base}",
                    f"env_FLLE_DPDK_USER_REF_SPAN={user_ref_span}",
                    "env_FLLE_MANAGEMENT_PORT=48125",
                    "env_FLLE_TELEMETRY_HOST=10.1.1.101",
                    "env_FLLE_DPDK_HELPER_CPU=3",
                    "env_FLLE_DPDK_HEARTBEAT=0",
                    "env_FLLE_DPDK_DATA_IP=<ABSENT>",
                    "env_FLLE_EXCHANGE_DATA_IP=<ABSENT>",
                    "env_FLLE_ORDER_PORT=<ABSENT>",
                    "env_FLLE_MANAGEMENT_IP=<ABSENT>",
                    "env_FLLE_TELEMETRY_PORT=<ABSENT>",
                ]
            )
        elif transport == "OPENONLOAD":
            process_lines.extend(
                [
                    "env_EF_POLL_USEC=100000",
                    "env_EF_TCP_FASTSTART_INIT=0",
                    "env_EF_TCP_FASTSTART_IDLE=0",
                ]
            )
        process = "\n".join(process_lines) + "\n"
        input_receipt = (
            f"runtime_sha256={runtime_archive_sha}\n"
            f"runtime_manifest_sha256={runtime_manifest_sha}\n"
            f"opening_book_sha256={checkpoint_sha}\n"
            f"itch_sha256={itch_sha}\n"
        )
        contents = {
            "data-plane-input.receipt": input_receipt,
            "process.txt": process,
            "state.json": state,
        }
        required = [
            *process.splitlines(),
            f"runtime_sha256={runtime_archive_sha}",
            f"runtime_manifest_sha256={runtime_manifest_sha}",
            f"opening_book_sha256={checkpoint_sha}",
            f"itch_sha256={itch_sha}",
        ]
        counter_kind = "trader_orders"
        counter_value = orders
        if transport == "SOCKET":
            endpoint = (
                '0 0 20.1.1.2:45678 20.1.1.1:43120 '
                'users:(("flle-trader",pid=321,fd=6))'
            )
            contents["ss-established.txt"] = endpoint + "\n"
            required.append(endpoint)
        elif transport == "OPENONLOAD":
            header = "  Onload 9.0.2 uid=0 pid=321 ns_flags=a0"
            endpoint = (
                "TCP 2:7 lcl=20.1.1.2:45678 "
                "rmt=20.1.1.1:43120 ESTABLISHED"
            )
            valid = "  snd: sndbuf_pkts=136 Onloaded(Valid) if=4"
            if onload_cross_block:
                dump = "\n".join(
                    [
                        header,
                        endpoint,
                        "  snd: no-valid-marker",
                        "TCP 2:8 lcl=20.1.1.2:1111 rmt=20.1.1.1:2222 ESTABLISHED",
                        valid,
                        "-----",
                        f"ctpio_pkts: {ctpio_packets}",
                        f"ctpio_dma_fallbacks: {ctpio_fallbacks}",
                    ]
                ) + "\n"
            else:
                dump = "\n".join(
                    [
                        header,
                        endpoint,
                        valid,
                        "----- sockets -----",
                        f"ctpio_pkts: {ctpio_packets}",
                        f"ctpio_dma_fallbacks: {ctpio_fallbacks}",
                    ]
                ) + "\n"
            contents["onload-stackdump.txt"] = dump
            required.extend(
                [
                    header,
                    endpoint,
                    valid,
                    f"ctpio_pkts: {ctpio_packets}",
                    f"ctpio_dma_fallbacks: {ctpio_fallbacks}",
                ]
            )
        elif transport == "TCPDIRECT":
            list_line = "flle-tcpdirect id=16    pid=321"
            endpoint = (
                f"TCP flle-tcpdirect:3 lcl=20.1.1.2:{tcpdirect_local_port} "
                f"rmt=20.1.1.1:43120 retransmits={tcpdirect_retransmits} "
                "ESTABLISHED"
            )
            txq = (
                f"  txq: added={tcpdirect_txq_added} "
                f"removed={max(0, tcpdirect_txq_added - 1)}"
            )
            contents.update(
                {
                    "zf-list.txt": list_line + "\n",
                    "zf-attr.txt": "ctpio=3\nctpio_mode=sf-np\n",
                    "zf-dump.txt": endpoint + "\n" + txq + "\n",
                }
            )
            counter_kind = "zf_txq_added"
            counter_value = tcpdirect_txq_added
            required.extend(
                [list_line, "ctpio=3", "ctpio_mode=sf-np", endpoint, txq]
            )
        else:
            fixed_sha = "a" * 64
            generator_sha = "b" * 64
            exchange_exe = (
                "/var/tmp/flle-trading-lab-unit/transport-runtime/"
                "flle-ch06-four-path/bin/flle-exchange"
            )
            exchange_run_dir = Path(exchange_exe).parents[3]
            exchange_argv = [
                exchange_exe,
                "--telemetry-host", "10.1.1.101",
                "--replay-file", (exchange_run_dir / "AAPL_NVDA.itch").as_posix(),
                "--book-checkpoint",
                (exchange_run_dir / "opening-book.checkpoint").as_posix(),
                "--market-date", "2026-06-12",
                "--market-mode", "UNICAST",
                "--replay-speed", "1",
            ]
            exchange_process = (
                "pid=654\nstart_ticks=987\nboot_id=boot-exchange\n"
                f"cmdline={exchange_exe} --unit\n"
                f"exe_path={exchange_exe}\n"
                f"exe_sha256={fixed_sha}\n"
                f"exe_manifest_sha256={fixed_sha}\n"
                f"checkpoint_sha256={checkpoint_sha}\n"
                f"checkpoint_generator_sha256={generator_sha}\n"
                f"checkpoint_generator_manifest_sha256={generator_sha}\n"
                f"itch_sha256={itch_sha}\n"
                "listener_count=1\n"
                "listener_ss_line_1=LISTEN 0 128 20.1.1.1:43120 0.0.0.0:* "
                f'users:(("flle-exchange",pid={exchange_listener_pid},fd=5))\n'
                f"argv_count={len(exchange_argv)}\n"
                + "".join(
                    f"argv_{index:02d}={value}\n"
                    for index, value in enumerate(exchange_argv)
                )
            )
            exchange_endpoints = [
                (
                    f"0 0 20.1.1.1:43120 20.1.1.2:{peer_port} "
                    f'users:(("flle-exchange",pid={exchange_ss_pid},fd={fd}))'
                )
                for fd, peer_port in enumerate(dpdk_peer_ports, start=9)
            ]
            contents["exchange-process.txt"] = exchange_process
            contents["exchange-ss-established.txt"] = (
                "\n".join([*exchange_endpoints, *dpdk_extra_ss_lines]) + "\n"
            )
            log_lines = ["EAL: Using IOMMU type 1 (Type 1)"]
            if dpdk_decoy_bdf is not None:
                log_lines.extend(
                    [
                        "EAL: Probe PCI driver: net_sfc_efx (1924:0b03) "
                        f"device: {dpdk_decoy_bdf} (socket 0)",
                        f"PMD: sfc_efx {dpdk_decoy_bdf} #0: "
                        "running FW variant is ultra-low-latency",
                    ]
                )
            log_lines.append(
                "EAL: Probe PCI driver: net_sfc_efx (1924:0b03) "
                f"device: {dpdk_bdf} (socket 0)"
            )
            if not omit_dpdk_ull:
                log_lines.append(
                    f"PMD: sfc_efx {dpdk_bdf} #0: "
                    "running FW variant is ultra-low-latency"
                )
            contents["fstack.log"] = "\n".join(log_lines) + "\n"
            gate_start = (
                "gate_pid=777\n"
                "gate_cpus_allowed_list=0\n"
                f"runtime_manifest_sha256={runtime_manifest_sha}\n"
                f"wrapper_sha256={'1' * 64}\n"
                f"binary_sha256={client_exe_sha256}\n"
                f"config_sha256={'2' * 64}\n"
                f"lease_token={lease_token}\n"
            )
            contents["gate-start.receipt"] = gate_start
            lease_start = (
                f"lease_unit=flle-x2522-lease-{'3' * 20}\n"
                "lease_seconds=1800\n"
                f"lease_token={lease_token}\n"
                "recovery_executor=systemd_timer_independent_of_wrapper\n"
            )
            contents["lease-start.receipt"] = lease_start
            contents["lease-status.txt"] = (
                f"lease_unit=flle-x2522-lease-{'3' * 20}\n"
                f"lease_token={lease_token}\n"
                "ownership_state=OWNED\n"
                "timer_active=active\n"
                "timer_sub=waiting\n"
                "service_active=inactive\n"
            )
            contents["owner.txt"] = (
                "driver=vfio-pci\niommu_group=7\n"
                "group_device=0000:03:00.0\nunsafe_noiommu=N\n"
            )
            required.extend(
                log_lines
                + [
                    "pid=654",
                    f"exe_path={exchange_exe}",
                    f"exe_sha256={fixed_sha}",
                    f"checkpoint_generator_sha256={generator_sha}",
                    f"checkpoint_sha256={checkpoint_sha}",
                    f"itch_sha256={itch_sha}",
                    "listener_count=1",
                    (
                        "listener_ss_line_1=LISTEN 0 128 20.1.1.1:43120 "
                        f'0.0.0.0:* users:(("flle-exchange",'
                        f'pid={exchange_listener_pid},fd=5))'
                    ),
                    f"argv_count={len(exchange_argv)}",
                    *(
                        f"argv_{index:02d}={value}"
                        for index, value in enumerate(exchange_argv)
                    ),
                    *exchange_endpoints,
                    "driver=vfio-pci",
                    "iommu_group=7",
                    "group_device=0000:03:00.0",
                    "unsafe_noiommu=N",
                    "gate_pid=777",
                    "gate_cpus_allowed_list=0",
                    f"runtime_manifest_sha256={runtime_manifest_sha}",
                    f"wrapper_sha256={'1' * 64}",
                    f"binary_sha256={client_exe_sha256}",
                    f"config_sha256={'2' * 64}",
                    f"lease_token={lease_token}",
                    f"lease_unit=flle-x2522-lease-{'3' * 20}",
                    "lease_seconds=1800",
                    "recovery_executor=systemd_timer_independent_of_wrapper",
                ]
            )
            counter_kind = "dpdk_port_packets"
            counter_value = (
                state_value["dpdk_port_stats"]["ipackets"]
                + state_value["dpdk_port_stats"]["opackets"]
            )

        for name, text in contents.items():
            (directory / name).write_text(text, encoding="utf-8")
        files = []
        for target in sorted(directory.iterdir()):
            payload = target.read_bytes()
            files.append(
                {
                    "path": (prefix / target.name).as_posix(),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "bytes": len(payload),
                }
            )
        excerpt_paths = {}
        for name, text in contents.items():
            for line in text.splitlines():
                excerpt_paths.setdefault(line, (prefix / name).as_posix())
        manifest = {
            "files": files,
            "counter_kind": counter_kind,
            "counter_value": counter_value,
            "matching_excerpts": [
                {"path": excerpt_paths[line], "text": line} for line in required
            ],
        }
        if transport == "DPDK":
            manifest["hardware_counters"] = state_value["dpdk_port_stats"]
        row = {
            "transport": transport,
            "round": 1,
            "position": 1,
            "cell_audit": {"native_receipts": {phase: manifest}},
        }
        return row, directory

    def rewrite_native_original(
        self,
        row: dict,
        directory: Path,
        phase: str,
        name: str,
        transform,
    ) -> None:
        target = directory / name
        old = target.read_text(encoding="utf-8")
        new = transform(old)
        self.assertNotEqual(old, new)
        target.write_text(new, encoding="utf-8")
        manifest = row["cell_audit"]["native_receipts"][phase]
        item = next(
            item for item in manifest["files"] if item["path"].endswith(f"/{name}")
        )
        payload = new.encode("utf-8")
        item["sha256"] = hashlib.sha256(payload).hexdigest()
        item["bytes"] = len(payload)
        replacements = dict(zip(old.splitlines(), new.splitlines()))
        for excerpt in manifest["matching_excerpts"]:
            if excerpt["path"] == item["path"]:
                excerpt["text"] = replacements.get(excerpt["text"], excerpt["text"])

    def test_pooled_summary_uses_all_equal_cells(self) -> None:
        rounds = [
            {
                "raw_samples": [
                    {"order_rtt_ns": value, "queue_to_send_ns": value + 1,
                     "submit_to_final_ns": value + 2}
                    for value in values
                ]
            }
            for values in ([1, 2], [3, 4], [5, 6], [7, 100])
        ]
        result = ANALYZE.pooled_metric_summary(rounds, "order_rtt")
        self.assertEqual(result["samples"], 8)
        self.assertEqual(result["p50_ns"], 4)
        self.assertEqual(result["p95_ns"], 100)
        self.assertEqual(result["cells"], 4)
        self.assertEqual(result["samples_per_cell"], 2)

    def test_pooled_summary_rejects_unequal_cells(self) -> None:
        rounds = [
            {"raw_samples": [{"order_rtt_ns": 1}]},
            {"raw_samples": [{"order_rtt_ns": 2}, {"order_rtt_ns": 3}]},
        ]
        with self.assertRaisesRegex(RuntimeError, "not equally weighted"):
            ANALYZE.pooled_metric_summary(rounds, "order_rtt")

    def test_equal_cell_mean_is_half_up(self) -> None:
        rounds = [
            {
                "order_rtt": {
                    "p50_ns": value,
                    "p95_ns": value,
                    "p99_ns": value,
                    "mean_ns": value,
                    "max_ns": value,
                }
            }
            for value in (10, 20, 21, 40)
        ]
        result = ANALYZE.equal_cell_mean_summary(rounds, "order_rtt")
        self.assertEqual(result["p50_ns"], 23)
        self.assertEqual(result["max_ns"], 40)
        self.assertEqual(
            result["max_aggregation"],
            "GLOBAL_MAX_ACROSS_4_CELLS_NOT_A_CELL_MEAN",
        )

    def test_each_transport_is_rebuilt_from_native_originals(self) -> None:
        for transport, expected_kind, expected_counter in (
            ("SOCKET", "trader_orders", 7),
            ("OPENONLOAD", "trader_orders", 7),
            ("TCPDIRECT", "zf_txq_added", 19),
            ("DPDK", "dpdk_port_packets", 29),
        ):
            with self.subTest(transport=transport), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                row, _ = self.make_native_fixture(root, transport)
                result = ANALYZE.validate_native_receipt_from_originals(
                    root, row, "pre", root / "raw.json"
                )
                self.assertEqual(result["pid"], 321)
                self.assertEqual(result["counter_kind"], expected_kind)
                self.assertEqual(result["counter_value"], expected_counter)
                self.assertTrue(
                    result["runtime_identity"]["exe_path"].endswith(
                        {
                            "TCPDIRECT": "/bin/flle-trader-tcpdirect",
                            "DPDK": "/bin/flle-trader-dpdk",
                        }.get(transport, "/bin/flle-trader")
                    )
                )
                self.assertEqual(
                    result["runtime_identity"]["exe_sha256"], "d" * 64
                )
                self.assertEqual(
                    result["runtime_identity"]["exe_manifest_sha256"],
                    "d" * 64,
                )
                if transport == "DPDK":
                    witness = result["server_endpoint_witness"]
                    self.assertEqual(witness["pid"], 654)
                    self.assertNotEqual(witness["pid"], result["pid"])
                    self.assertEqual(
                        witness["scope"],
                        "EXCHANGE_SERVER_OBSERVED_PEER_ENDPOINT",
                    )
                    self.assertTrue(witness["not_a_client_pid_binding"])
                    self.assertEqual(witness["host"], "10.1.1.1")
                    self.assertEqual(witness["listener_count"], 1)
                    self.assertEqual(witness["endpoint_count"], 1)
                if transport == "TCPDIRECT":
                    self.assertEqual(
                        result["path_health_witness"]["retransmits"], 0
                    )

    def test_each_transport_rejects_client_manifest_sha_mismatch(self) -> None:
        for transport in ("SOCKET", "OPENONLOAD", "TCPDIRECT", "DPDK"):
            with self.subTest(transport=transport), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                row, _ = self.make_native_fixture(
                    root,
                    transport,
                    client_exe_sha256="d" * 64,
                    client_manifest_sha256="e" * 64,
                )
                with self.assertRaisesRegex(
                    RuntimeError, "runtime executable identity is not sealed"
                ):
                    ANALYZE.validate_native_receipt_from_originals(
                        root, row, "pre", root / "raw.json"
                    )

    def test_client_runtime_identity_rejects_wrong_transport_binary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            wrong = (
                "/var/tmp/flle-trading-lab-unit/transport-runtime/"
                "flle-ch06-four-path/bin/flle-trader"
            )
            row, _ = self.make_native_fixture(
                root, "TCPDIRECT", client_exe_path=wrong
            )
            with self.assertRaisesRegex(
                RuntimeError, "runtime executable identity is not sealed"
            ):
                ANALYZE.validate_native_receipt_from_originals(
                    root, row, "pre", root / "raw.json"
                )

    def test_client_runtime_identity_rejects_malformed_sha(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            row, _ = self.make_native_fixture(
                root,
                "SOCKET",
                client_exe_sha256="not-a-sha256",
                client_manifest_sha256="not-a-sha256",
            )
            with self.assertRaisesRegex(
                RuntimeError, "runtime executable identity is not sealed"
            ):
                ANALYZE.validate_native_receipt_from_originals(
                    root, row, "pre", root / "raw.json"
                )

    def test_client_runtime_identity_must_match_nul_argv(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            row, _ = self.make_native_fixture(
                root,
                "SOCKET",
                client_cmdline_path="/opt/decoy/flle-trader",
            )
            with self.assertRaisesRegex(RuntimeError, "argv contract is not exact"):
                ANALYZE.validate_native_receipt_from_originals(
                    root, row, "pre", root / "raw.json"
                )

    def test_client_argv_rejects_changed_role_even_with_rehashed_original(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            row, directory = self.make_native_fixture(root, "SOCKET")
            self.rewrite_native_original(
                row,
                directory,
                "pre",
                "process.txt",
                lambda text: text.replace("argv_02=MANUAL", "argv_02=AUTO"),
            )
            with self.assertRaisesRegex(RuntimeError, "argv contract is not exact"):
                ANALYZE.validate_native_receipt_from_originals(
                    root, row, "pre", root / "raw.json"
                )

    def test_native_state_rejects_unlocked_queue_even_with_rehashed_original(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            row, directory = self.make_native_fixture(root, "TCPDIRECT")

            def unlock(text: str) -> str:
                state = json.loads(text)
                state["software_latency"]["queue_locked"] = False
                return json.dumps(state, separators=(",", ":")) + "\n"

            self.rewrite_native_original(
                row, directory, "pre", "state.json", unlock
            )
            with self.assertRaisesRegex(
                RuntimeError, "queue/network-engine contract failed"
            ):
                ANALYZE.validate_native_receipt_from_originals(
                    root, row, "pre", root / "raw.json"
                )

    def test_dpdk_lease_token_must_match_client_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            row, directory = self.make_native_fixture(root, "DPDK")
            self.rewrite_native_original(
                row,
                directory,
                "pre",
                "lease-start.receipt",
                lambda text: text.replace(
                    "lease_token=unit-run-0", "lease_token=unit-run-decoy"
                ),
            )
            with self.assertRaisesRegex(
                RuntimeError, "ownership gate identity is not sealed"
            ):
                ANALYZE.validate_native_receipt_from_originals(
                    root, row, "pre", root / "raw.json"
                )

    def test_compact_row_generation_and_threads_must_close_native_receipts(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            row, _ = self.make_native_fixture(
                root, "SOCKET", phase="pre", orders=7
            )
            post_row, _ = self.make_native_fixture(
                root, "SOCKET", phase="post", orders=1106
            )
            row.update(
                {
                    "warmup_orders": 100,
                    "measurement_orders": 1000,
                    "warmup_submission_ids": list(
                        range(2100000000, 2100000100)
                    ),
                    "measurement_submission_ids": list(
                        range(2100000100, 2100001100)
                    ),
                    "warmup_generation": 1,
                    "measurement_generation": 2,
                    "contract": {
                        "symbol": "AAPL",
                        "quantity": 1,
                        "order_type": "IOC_LIMIT_CROSSING",
                        "protocol": "OUCH_5.0_OVER_SOUPBINTCP",
                        "queue_mode": "DEQUE_CV",
                        "queue_locked": True,
                        "single_flight": True,
                        "accepted_telemetry_in_timer": False,
                        "clock": "CLOCK_MONOTONIC",
                        "timer_start": "OUCH_ENCODED_BEFORE_SOUP_FRAME",
                        "timer_end": "FINAL_EXECUTED_DECODED",
                        "data_cpu": 2,
                        "management_cpu": 3,
                        "observed_hugepages_2mb": 128,
                        "nagle": {
                            "applicable": True,
                            "tcp_nodelay": True,
                            "verification": "RUNTIME_GETSOCKOPT_NONZERO",
                        },
                    },
                    "network_engine": "KERNEL_SOCKET",
                    "thread_placement": {
                        "order_thread_cpu": 2,
                        "order_thread_allowed_count": 1,
                        "management_thread_cpu": 3,
                        "management_thread_allowed_count": 1,
                    },
                }
            )
            row["cell_audit"].update(
                {
                    "start_monotonic_ns": 100,
                    "end_monotonic_ns": 200,
                    "duration_ns": 100,
                }
            )
            row["cell_audit"]["native_receipts"]["post"] = post_row[
                "cell_audit"
            ]["native_receipts"]["post"]
            native = ANALYZE.validate_cell_audit(
                root, row, root / "socket-r1.json"
            )
            ANALYZE.validate_row_runtime_contract(
                row, native, root / "socket-r1.json"
            )
            row["measurement_generation"] = 3
            with self.assertRaisesRegex(RuntimeError, "generation is not closed"):
                ANALYZE.validate_row_runtime_contract(
                    row, native, root / "socket-r1.json"
                )

    def test_client_runtime_identity_must_be_in_compact_excerpts(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            row, _ = self.make_native_fixture(root, "SOCKET")
            receipt = row["cell_audit"]["native_receipts"]["pre"]
            receipt["matching_excerpts"] = [
                item
                for item in receipt["matching_excerpts"]
                if not item["text"].startswith("exe_manifest_sha256=")
            ]
            with self.assertRaisesRegex(
                RuntimeError, "omit independently required native lines"
            ):
                ANALYZE.validate_native_receipt_from_originals(
                    root, row, "pre", root / "raw.json"
                )

    def test_cell_rejects_client_runtime_executable_change(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            row, _ = self.make_native_fixture(
                root, "SOCKET", phase="pre", orders=7,
                client_exe_sha256="d" * 64,
            )
            post_row, _ = self.make_native_fixture(
                root, "SOCKET", phase="post", orders=1106,
                client_exe_sha256="e" * 64,
            )
            row["cell_audit"].update(
                {
                    "start_monotonic_ns": 100,
                    "end_monotonic_ns": 200,
                    "duration_ns": 100,
                }
            )
            row["cell_audit"]["native_receipts"]["post"] = post_row[
                "cell_audit"
            ]["native_receipts"]["post"]
            with self.assertRaisesRegex(
                RuntimeError, "runtime executable changed inside cell"
            ):
                ANALYZE.validate_cell_audit(
                    root, row, root / "socket-r1.json"
                )

    def test_onload_requires_valid_marker_in_same_tcp_block(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            row, _ = self.make_native_fixture(
                root, "OPENONLOAD", onload_cross_block=True
            )
            with self.assertRaisesRegex(RuntimeError, "Onload endpoint.*TCP block"):
                ANALYZE.validate_native_receipt_from_originals(
                    root, row, "pre", root / "raw.json"
                )

    def test_onload_cell_reports_growing_ctpio_without_dma_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            row, _ = self.make_native_fixture(
                root,
                "OPENONLOAD",
                phase="pre",
                orders=7,
                ctpio_packets=11,
                ctpio_fallbacks=0,
            )
            post_row, _ = self.make_native_fixture(
                root,
                "OPENONLOAD",
                phase="post",
                orders=1106,
                ctpio_packets=1110,
                ctpio_fallbacks=0,
            )
            row["cell_audit"].update(
                {
                    "clock": "CLOCK_MONOTONIC_ON_LOW_LATENCY_OPS",
                    "start_monotonic_ns": 100,
                    "end_monotonic_ns": 200,
                    "duration_ns": 100,
                }
            )
            row["cell_audit"]["native_receipts"]["post"] = post_row[
                "cell_audit"
            ]["native_receipts"]["post"]
            result = ANALYZE.validate_cell_audit(
                root, row, root / "openonload-r1.json"
            )
            self.assertEqual(result["counter_kind"], "trader_orders")
            self.assertEqual(result["hardware_witness"]["ctpio_pkts_delta"], 1099)
            self.assertEqual(
                result["hardware_witness"]["ctpio_dma_fallbacks_delta"], 0
            )

    def test_onload_cell_rejects_dma_fallback_growth(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            row, _ = self.make_native_fixture(
                root, "OPENONLOAD", phase="pre", ctpio_packets=11
            )
            post_row, _ = self.make_native_fixture(
                root,
                "OPENONLOAD",
                phase="post",
                orders=100,
                ctpio_packets=99,
                ctpio_fallbacks=1,
            )
            row["cell_audit"].update(
                {
                    "start_monotonic_ns": 100,
                    "end_monotonic_ns": 200,
                    "duration_ns": 100,
                }
            )
            row["cell_audit"]["native_receipts"]["post"] = post_row[
                "cell_audit"
            ]["native_receipts"]["post"]
            with self.assertRaisesRegex(RuntimeError, "DMA fallback counter grew"):
                ANALYZE.validate_cell_audit(
                    root, row, root / "openonload-r1.json"
                )

    def test_dpdk_requires_ull_firmware_native_line(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            row, _ = self.make_native_fixture(
                root, "DPDK", omit_dpdk_ull=True
            )
            with self.assertRaisesRegex(RuntimeError, "ultra-low-latency"):
                    ANALYZE.validate_native_receipt_from_originals(
                        root, row, "pre", root / "raw.json"
                    )

    def test_dpdk_cell_rejects_port_drop_growth(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            row, _ = self.make_native_fixture(
                root, "DPDK", phase="pre", orders=7, dpdk_imissed=0
            )
            post_row, _ = self.make_native_fixture(
                root, "DPDK", phase="post", orders=1106, dpdk_imissed=1
            )
            row["cell_audit"].update(
                {
                    "start_monotonic_ns": 100,
                    "end_monotonic_ns": 200,
                    "duration_ns": 100,
                }
            )
            row["cell_audit"]["native_receipts"]["post"] = post_row[
                "cell_audit"
            ]["native_receipts"]["post"]
            with self.assertRaisesRegex(
                RuntimeError, "DPDK port drop/error counter grew"
            ):
                ANALYZE.validate_cell_audit(root, row, root / "dpdk-r1.json")

    def test_dpdk_exchange_endpoint_is_server_side_not_client_pid(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            row, _ = self.make_native_fixture(
                root, "DPDK", phase="pre", orders=7
            )
            post_row, _ = self.make_native_fixture(
                root, "DPDK", phase="post", orders=1106
            )
            row["cell_audit"].update(
                {
                    "start_monotonic_ns": 100,
                    "end_monotonic_ns": 200,
                    "duration_ns": 100,
                }
            )
            row["cell_audit"]["native_receipts"]["post"] = post_row[
                "cell_audit"
            ]["native_receipts"]["post"]
            result = ANALYZE.validate_cell_audit(
                root, row, root / "dpdk-r1.json"
            )
            witness = result["server_endpoint_witness"]
            self.assertEqual(witness["exchange_pid"], 654)
            self.assertEqual(witness["pre_endpoint_count"], 1)
            self.assertEqual(witness["post_endpoint_count"], 1)
            self.assertEqual(witness["pre_listener_count"], 1)
            self.assertEqual(witness["post_listener_count"], 1)
            self.assertEqual(
                witness["pre_observed_endpoints"][0]["peer_endpoint"],
                "20.1.1.2:45678",
            )
            self.assertTrue(witness["not_a_client_pid_binding"])
            self.assertEqual(witness["exchange_host"], "10.1.1.1")
            self.assertNotEqual(witness["exchange_pid"], result["pid"])

    def test_dpdk_exchange_observation_allows_multiple_target_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            row, _ = self.make_native_fixture(
                root,
                "DPDK",
                dpdk_peer_ports=(45678, 45679),
                dpdk_extra_ss_lines=(
                    '0 0 10.1.1.1:22 10.1.1.2:50123 '
                    'users:(("sshd",pid=654,fd=8))',
                ),
            )
            result = ANALYZE.validate_native_receipt_from_originals(
                root, row, "pre", root / "raw.json"
            )
            witness = result["server_endpoint_witness"]
            self.assertEqual(witness["endpoint_count"], 2)
            self.assertEqual(
                [item["peer_endpoint"] for item in witness["observed_endpoints"]],
                ["20.1.1.2:45678", "20.1.1.2:45679"],
            )
            self.assertTrue(
                all(
                    item["local_endpoint"] == "20.1.1.1:43120"
                    for item in witness["observed_endpoints"]
                )
            )

    def test_dpdk_exchange_endpoint_sets_may_change_across_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            row, _ = self.make_native_fixture(
                root,
                "DPDK",
                phase="pre",
                orders=7,
                dpdk_peer_ports=(45678, 45679),
            )
            post_row, _ = self.make_native_fixture(
                root,
                "DPDK",
                phase="post",
                orders=1106,
                dpdk_peer_ports=(45680,),
            )
            row["cell_audit"].update(
                {
                    "start_monotonic_ns": 100,
                    "end_monotonic_ns": 200,
                    "duration_ns": 100,
                }
            )
            row["cell_audit"]["native_receipts"]["post"] = post_row[
                "cell_audit"
            ]["native_receipts"]["post"]
            result = ANALYZE.validate_cell_audit(
                root, row, root / "dpdk-r1.json"
            )
            witness = result["server_endpoint_witness"]
            self.assertEqual(witness["pre_endpoint_count"], 2)
            self.assertEqual(witness["post_endpoint_count"], 1)
            self.assertIn("SETS_MAY_DIFFER", witness["observation_semantics"])

    def test_dpdk_exchange_observation_ignores_non_target_connections(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            row, _ = self.make_native_fixture(
                root,
                "DPDK",
                dpdk_peer_ports=(),
                dpdk_extra_ss_lines=(
                    '0 0 10.1.1.1:22 10.1.1.2:50123 '
                    'users:(("sshd",pid=654,fd=8))',
                ),
            )
            with self.assertRaisesRegex(
                RuntimeError, "current PID has no target endpoint"
            ):
                ANALYZE.validate_native_receipt_from_originals(
                    root, row, "pre", root / "raw.json"
                )

    def test_dpdk_exchange_endpoint_must_match_current_exchange_pid(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            row, _ = self.make_native_fixture(
                root, "DPDK", exchange_ss_pid=999
            )
            with self.assertRaisesRegex(
                RuntimeError, "current PID has no target endpoint"
            ):
                ANALYZE.validate_native_receipt_from_originals(
                    root, row, "pre", root / "raw.json"
                )

    def test_dpdk_exchange_listener_must_match_current_exchange_pid(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            row, _ = self.make_native_fixture(
                root, "DPDK", exchange_listener_pid=999
            )
            with self.assertRaisesRegex(
                RuntimeError, "invalid Exchange listener snapshot"
            ):
                ANALYZE.validate_native_receipt_from_originals(
                    root, row, "pre", root / "raw.json"
                )

    def test_dpdk_pmd_and_ull_must_belong_to_the_owned_x2522_bdf(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            row, _ = self.make_native_fixture(
                root, "DPDK", dpdk_bdf="0000:04:00.0"
            )
            with self.assertRaisesRegex(RuntimeError, "X2522 PMD"):
                ANALYZE.validate_native_receipt_from_originals(
                    root, row, "pre", root / "raw.json"
                )

    def test_dpdk_mixed_log_selects_only_the_owned_x2522_bdf(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            row, _ = self.make_native_fixture(
                root,
                "DPDK",
                dpdk_decoy_bdf="0000:04:00.0",
            )
            result = ANALYZE.validate_native_receipt_from_originals(
                root, row, "pre", root / "raw.json"
            )
            log_matches = [
                line
                for line in result["independently_matched"]
                if "net_sfc_efx" in line or "ULL" in line
                or "ultra-low-latency" in line
            ]
            self.assertTrue(log_matches)
            self.assertTrue(all("0000:03:00.0" in line for line in log_matches))

    def test_tcpdirect_retransmit_delta_is_reported_without_failing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            row, _ = self.make_native_fixture(
                root,
                "TCPDIRECT",
                phase="pre",
                tcpdirect_retransmits=3,
            )
            post_row, _ = self.make_native_fixture(
                root,
                "TCPDIRECT",
                phase="post",
                tcpdirect_retransmits=5,
                tcpdirect_txq_added=1118,
            )
            row["cell_audit"].update(
                {
                    "start_monotonic_ns": 100,
                    "end_monotonic_ns": 200,
                    "duration_ns": 100,
                }
            )
            row["cell_audit"]["native_receipts"]["post"] = post_row[
                "cell_audit"
            ]["native_receipts"]["post"]
            result = ANALYZE.validate_cell_audit(
                root, row, root / "tcpdirect-r1.json"
            )
            self.assertEqual(
                result["path_health_witness"],
                {
                    "scope": "ZF_ENDPOINT_CUMULATIVE_RETRANSMITS",
                    "retransmits_before": 3,
                    "retransmits_after": 5,
                    "retransmits_delta": 2,
                    "local_endpoint": "20.1.1.2:45678",
                    "remote_endpoint": "20.1.1.1:43120",
                    "interpretation": (
                        "PATH_HEALTH_CLUE_NOT_MAPPED_TO_LATENCY_SAMPLES"
                    ),
                },
            )

    def test_tcpdirect_retransmit_counter_cannot_move_backward(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            row, _ = self.make_native_fixture(
                root,
                "TCPDIRECT",
                phase="pre",
                tcpdirect_retransmits=5,
            )
            post_row, _ = self.make_native_fixture(
                root,
                "TCPDIRECT",
                phase="post",
                tcpdirect_retransmits=3,
                tcpdirect_txq_added=1118,
            )
            row["cell_audit"].update(
                {
                    "start_monotonic_ns": 100,
                    "end_monotonic_ns": 200,
                    "duration_ns": 100,
                }
            )
            row["cell_audit"]["native_receipts"]["post"] = post_row[
                "cell_audit"
            ]["native_receipts"]["post"]
            with self.assertRaisesRegex(RuntimeError, "moved backward"):
                ANALYZE.validate_cell_audit(
                    root, row, root / "tcpdirect-r1.json"
                )

    def test_tcpdirect_retransmit_delta_requires_one_stable_endpoint(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            row, _ = self.make_native_fixture(
                root,
                "TCPDIRECT",
                phase="pre",
                tcpdirect_local_port=45678,
            )
            post_row, _ = self.make_native_fixture(
                root,
                "TCPDIRECT",
                phase="post",
                tcpdirect_local_port=45679,
                tcpdirect_txq_added=1118,
            )
            row["cell_audit"].update(
                {
                    "start_monotonic_ns": 100,
                    "end_monotonic_ns": 200,
                    "duration_ns": 100,
                }
            )
            row["cell_audit"]["native_receipts"]["post"] = post_row[
                "cell_audit"
            ]["native_receipts"]["post"]
            with self.assertRaisesRegex(RuntimeError, "endpoint changed"):
                ANALYZE.validate_cell_audit(
                    root, row, root / "tcpdirect-r1.json"
                )

    def test_native_original_hash_tamper_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            row, directory = self.make_native_fixture(root, "TCPDIRECT")
            (directory / "zf-attr.txt").write_text(
                "ctpio=0\nctpio_mode=sf-np\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(RuntimeError, "does not match compact manifest"):
                ANALYZE.validate_native_receipt_from_originals(
                    root, row, "pre", root / "raw.json"
                )

    def test_native_counter_manifest_is_independently_checked(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            row, _ = self.make_native_fixture(root, "SOCKET")
            row["cell_audit"]["native_receipts"]["pre"]["counter_value"] = 99
            with self.assertRaisesRegex(RuntimeError, "not independently reproduced"):
                ANALYZE.validate_native_receipt_from_originals(
                    root, row, "pre", root / "raw.json"
                )

    def test_live_measure_module_must_match_formal_sealed_program(self) -> None:
        analyzer_path = Path(ANALYZE.__file__).resolve()
        measure_path = Path(ANALYZE.measure.__file__).resolve()
        original = {
            "execution_provenance": {
                "sealed_programs": [
                    {
                        "path": "provenance/analyze_four_transport_raw.py",
                        "sha256": hashlib.sha256(
                            analyzer_path.read_bytes()
                        ).hexdigest(),
                    },
                    {
                        "path": "provenance/measure_four_transports.py",
                        "sha256": hashlib.sha256(
                            measure_path.read_bytes()
                        ).hexdigest(),
                    },
                ]
            }
        }
        with tempfile.TemporaryDirectory() as temporary:
            mutated = Path(temporary) / "measure_four_transports.py"
            mutated.write_text("# mutated after the formal RUN\n", encoding="utf-8")
            previous = ANALYZE.measure.__file__
            ANALYZE.measure.__file__ = str(mutated)
            try:
                with self.assertRaisesRegex(RuntimeError, "live measure module"):
                    ANALYZE.verify_live_analysis_programs(original)
            finally:
                ANALYZE.measure.__file__ = previous

    def test_formal_manifest_cannot_omit_a_raw_original(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "SHA256SUMS").write_text(
                f"{'a' * 64}  summary.json\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(RuntimeError, "file set is not exact"):
                ANALYZE.require_exact_source_manifest_paths(
                    root, {"summary.json", "raw/socket-r1.json"}
                )

    def test_formal_manifest_rejects_symlinked_originals(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outside = root / "outside.json"
            outside.write_text("{}\n", encoding="utf-8")
            linked = root / "summary.json"
            linked.symlink_to(outside)
            digest = hashlib.sha256(outside.read_bytes()).hexdigest()
            (root / "SHA256SUMS").write_text(
                f"{digest}  summary.json\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(RuntimeError, "must not be a symlink"):
                ANALYZE.verify_source_manifest(root)

    def test_formal_manifest_cannot_change_during_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            entries = []
            for name in ("one.txt", "two.txt"):
                target = root / name
                target.write_text(name + "\n", encoding="utf-8")
                entries.append(
                    f"{hashlib.sha256(target.read_bytes()).hexdigest()}  {name}"
                )
            manifest = root / "SHA256SUMS"
            manifest.write_text("\n".join(entries) + "\n", encoding="utf-8")
            initial = ANALYZE.verify_source_manifest(root)
            manifest.write_text(
                "\n".join(reversed(entries)) + "\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(RuntimeError, "changed during analysis"):
                ANALYZE.require_source_manifest_unchanged(root, initial)

    def test_balanced_analysis_rejects_stale_file_or_subdirectory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "balanced-analysis"
            output.mkdir()
            (output / "stale.txt").write_text("old\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "stale or non-file"):
                ANALYZE.prepare_analysis_output(output)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            real_output = root / "real-output"
            real_output.mkdir()
            linked_output = root / "balanced-analysis"
            linked_output.symlink_to(real_output, target_is_directory=True)
            with self.assertRaisesRegex(RuntimeError, "real directory"):
                ANALYZE.prepare_analysis_output(linked_output)

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "balanced-analysis"
            output.mkdir()
            (output / "nested").mkdir()
            with self.assertRaisesRegex(RuntimeError, "stale or non-file"):
                ANALYZE.prepare_analysis_output(output)

    def test_balanced_analysis_payload_set_is_exactly_two_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            for name in ("README.md", "summary.json"):
                (output / name).write_text("unit\n", encoding="utf-8")
            ANALYZE.verify_analysis_payload_set(output)
            (output / "extra.txt").write_text("extra\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "payload set is not exact"):
                ANALYZE.verify_analysis_payload_set(output)


if __name__ == "__main__":
    unittest.main()
