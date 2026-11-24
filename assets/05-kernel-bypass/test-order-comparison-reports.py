#!/usr/bin/env python3
"""Exercise classroom output code with order receipts and invalid inputs."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('comparison_report', ROOT / 'format-comparison-report.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class OrderReports(unittest.TestCase):
    cases = (
        ('04-socket-real-order.sh', 'trader_manual', 'KERNEL_SOCKET'),
        ('05-onload-real-order.sh', 'trader_onload', 'ONLOAD_USER_STACK'),
        ('06-tcpdirect-real-order.sh', 'trader_tcpdirect', 'ZF_REACTOR_POLL'),
        ('07-dpdk-real-order.sh', None, 'FSTACK_POLL'),
    )

    def invoke(self, filename, client, engine, *, result='ORDER_EXECUTED', rtt=12345):
        script = (ROOT / filename).read_text()
        code = script.split("<<'PY' | tee", 1)[1].split('\n', 1)[1].split('\nPY\n', 1)[0]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            order = root / 'order.json'
            order.write_text(json.dumps({'orders': [{'client_order_id': 42, 'result': result, 'order_rtt_ns': rtt}]}))
            receipt = root / 'receipt.json'
            if client:
                receipt.write_text(json.dumps({'clients': {client: {'software': {'network_engine': engine}}}}))
            else:
                state = root / 'standalone-native-receipts/standalone-test/evidence/state.json'
                state.parent.mkdir(parents=True)
                state.write_text(json.dumps({'software_latency': {'network_engine': engine}}))
                receipt.write_text(json.dumps({'local_directory': tmp}))
            return subprocess.run(['python3', '-', '42', str(order), str(receipt)], input=code, text=True, capture_output=True)

    def test_real_inline_output_reads_receipt_values_and_explains_each_group(self):
        for filename, client, engine in self.cases:
            with self.subTest(filename=filename):
                result = self.invoke(filename, client, engine)
                self.assertEqual(result.returncode, 0, result.stderr)
                for value in ('result=ORDER_EXECUTED', 'client_order_id=42', 'order_rtt_ns=12345', f'engine={engine}', '[1/3 成交结果]', '[2/3 实际收发路径]', '[3/3 订单往返耗时]', '12.345 µs', '本步通过'):
                    self.assertIn(value, result.stdout)
                if client is None:
                    self.assertIn('restored=SFC/READY/sfc', result.stdout)

    def test_invalid_order_or_engine_never_prints_success(self):
        for filename, client, engine in self.cases:
            for overrides in ({'result': 'ORDER_REJECTED'}, {'rtt': 0}, {'engine': 'WRONG_PATH'}):
                with self.subTest(filename=filename, overrides=overrides):
                    args = {'engine': engine, **overrides}
                    result = self.invoke(filename, client, **args)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, '')


class ComparisonReports(unittest.TestCase):
    def fixture(self):
        stats = {'p50_ns': 12345, 'p95_ns': 23456, 'p99_ns': 34567, 'cells': 4}
        return {
            'exchange_ledger_gate': {'delta': 17600, 'expected': 17600},
            'warmup_sample_identity': {'total': 1600, 'unique': 1600},
            'sample_identity': {'total': 16000, 'unique': 16000},
            'submission_identity': {'total': 17600, 'unique': 17600},
            'runtime_acceptance': {'cell_native_path_receipts': 16, 'expected_cell_native_path_receipts': 16},
            'analysis_matches_sealed_program': True,
            'measurement_module_matches_sealed_program': True,
            'method': {'primary': 'EQUAL_CELL_MEAN_OF_4_ROUND_NEAREST_RANK_STATISTICS'},
            'summary': {key: {'balanced_equal_cell_mean': {name: copy.deepcopy(stats) for name in ('order_rtt', 'submit_to_final', 'queue_to_send')}} for key in ('SOCKET', 'OPENONLOAD', 'TCPDIRECT', 'DPDK')},
        }

    def test_table_uses_actual_statistics_and_converts_ns_to_us(self):
        text = module.report(self.fixture(), Path('verified/analysis'))
        self.assertEqual(text.count('12.345'), 12)
        self.assertIn('单位为 µs（微秒）', text)
        self.assertIn('measured_executed=16000', text)
        self.assertIn('evidence=verified/analysis', text)

    def test_one_row_per_path_keeps_each_metric_in_its_own_column(self):
        result = self.fixture()
        stats = result['summary']['DPDK']['balanced_equal_cell_mean']
        stats['queue_to_send'].update(p50_ns=5275, p99_ns=25963)
        stats['order_rtt'].update(p50_ns=24171, p95_ns=29385, p99_ns=32551)
        stats['submit_to_final'].update(p50_ns=29724, p99_ns=53322)
        text = module.report(result, Path('verified/analysis'))
        for label in ('Kernel Socket', 'Onload', 'TCPDirect', 'DPDK + F-Stack'):
            self.assertEqual(sum(line.startswith(label + ' ') for line in text.splitlines()), 1)
        row = next(line for line in text.splitlines() if line.startswith('DPDK + F-Stack '))
        self.assertEqual([group.split() for group in row.split('|')[1:]],
                         [['5.275', '25.963'], ['24.171', '29.385', '32.551'], ['29.724', '53.322']])
        self.assertIn('先看右侧“整体”', text)

    def test_incomplete_counts_receipts_or_source_checks_fail(self):
        for key, field, value in (
            ('exchange_ledger_gate', 'delta', 17599),
            ('sample_identity', 'unique', 15999),
            ('runtime_acceptance', 'cell_native_path_receipts', 15),
            ('method', 'primary', 'POOLED'),
        ):
            with self.subTest(key=key):
                result = self.fixture()
                result[key][field] = value
                with self.assertRaises(ValueError):
                    module.report(result, Path('bad'))
        result = self.fixture()
        result['analysis_matches_sealed_program'] = False
        with self.assertRaises(ValueError):
            module.report(result, Path('bad'))

    def test_missing_cells_or_invalid_latency_fail(self):
        for metric in ('queue_to_send', 'order_rtt', 'submit_to_final'):
            for key, value in (('cells', 3), ('p50_ns', 0), ('p99_ns', -1)):
                with self.subTest(metric=metric, key=key):
                    result = self.fixture()
                    result['summary']['DPDK']['balanced_equal_cell_mean'][metric][key] = value
                    with self.assertRaises(ValueError):
                        module.report(result, Path('bad'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
