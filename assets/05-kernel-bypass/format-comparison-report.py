#!/usr/bin/env python3
"""Classroom view of the analyzer's verified result; never recompute statistics."""
import argparse
import json
from pathlib import Path
import unicodedata


def cell(text: str, width: int, *, center: bool = False) -> str:
    """Pad Chinese headers by terminal columns, not Python character count."""
    used = sum(2 if unicodedata.east_asian_width(char) in 'WF' else 1 for char in text)
    padding = max(0, width - used)
    left = padding // 2 if center else 0
    return ' ' * left + text + ' ' * (padding - left)


def report(result: dict, evidence: Path) -> str:
    ledger = result['exchange_ledger_gate']
    warmup = result['warmup_sample_identity']
    measured = result['sample_identity']
    submitted = result['submission_identity']
    native = result['runtime_acceptance']
    if not (warmup['total'] == warmup['unique'] == 1600
            and measured['total'] == measured['unique'] == 16000
            and submitted['total'] == submitted['unique'] == ledger['delta'] == ledger['expected'] == 17600
            and native['cell_native_path_receipts'] == native['expected_cell_native_path_receipts'] == 16
            and result['analysis_matches_sealed_program']
            and result['measurement_module_matches_sealed_program']
            and result['method']['primary'] == 'EQUAL_CELL_MEAN_OF_4_ROUND_NEAREST_RANK_STATISTICS'):
        raise ValueError('正式比较的样本、总账、路径或封存程序检查未通过')
    lines = [
        '===== 运行 ⑤ · 四条路径正式比较 =====',
        '# 1. 样本检查：预热单不计入延迟统计，正式样本无重复订单。',
        f"warmup_executed={warmup['total']}  # 预热成交笔数",
        f"measured_executed={measured['total']}  # 正式成交笔数，四路各 4000 笔",
        f"path_checks={native['cell_native_path_receipts']}/16  # 每个测试单元均通过实际路径检查",
        f"exchange_executed_delta={ledger['delta']}  # Exchange 新增成交数与全部提交订单数相等",
        '',
        '# 2. 延迟总表：单位为 µs（微秒），1 µs = 1000 ns；数值越小，耗时越短。',
        '# 每个测试单元先求 P50 / P95 / P99，再将同一路径四个测试单元的对应值取平均。',
        ' | '.join((cell('路径', 16), cell('发送前', 19, center=True),
                    cell('订单往返 / RTT', 29, center=True), cell('整体【重点】', 19, center=True))),
        ' | '.join((cell('', 16), cell('queue→send', 19, center=True),
                    cell('send→final', 29, center=True), cell('queue→final', 19, center=True))),
        ' | '.join((cell('', 16), '  '.join(f'{key:>8}' for key in ('P50', 'P99')).center(19),
                    '  '.join(f'{key:>8}' for key in ('P50', 'P95', 'P99')).center(29),
                    '  '.join(f'{key:>8}' for key in ('P50', 'P99')).center(19))),
        '-+-'.join('-' * width for width in (16, 19, 29, 19)),
    ]
    for transport in ('SOCKET', 'OPENONLOAD', 'TCPDIRECT', 'DPDK'):
        stats = result['summary'][transport]['balanced_equal_cell_mean']
        groups = []
        for key, quantiles, width in (
            ('queue_to_send', ('p50_ns', 'p99_ns'), 19),
            ('order_rtt', ('p50_ns', 'p95_ns', 'p99_ns'), 29),
            ('submit_to_final', ('p50_ns', 'p99_ns'), 19),
        ):
            item = stats[key]
            if item['cells'] != 4:
                raise ValueError('延迟总表缺少完整的四个测试单元统计')
            values = [item[k] for k in quantiles]
            if any(v <= 0 for v in values):
                raise ValueError('延迟总表包含无效延迟')
            groups.append('  '.join(f'{v / 1000:8.3f}' for v in values).center(width))
        label = {'SOCKET': 'Kernel Socket', 'OPENONLOAD': 'Onload', 'TCPDIRECT': 'TCPDirect', 'DPDK': 'DPDK + F-Stack'}[transport]
        lines.append(' | '.join((cell(label, 16), *groups)))
    lines += [
        '',
        '# 3. 怎么读：先看整体，再找时间花在哪里。',
        '# 先看右侧“整体”：入队 → 最终回报；P50 看通常速度，P99 看少数慢单的尾部耗时。',
        '# 再看中间“订单往返”：发送起点 → 最终回报；包含本机收发、网络和 Exchange 处理。',
        '# 最后看左侧“发送前”：入队 → 发送起点；包括排队、唤醒、准备和线程交接。',
        '# 各段分位数独立计算，不能把两段 P50 或 P99 相加当成整体。',
        '',
        '# 4. 比较范围：本机、本轮条件下的四套客户端实现。',
        '# Kernel Socket 与 Onload 使用同一可执行文件；TCPDirect 和 DPDK 还改变了收发代码。',
        '# DPDK 包含线程交接，其成本已在各自计时窗口中体现，不能据此预判快慢。',
        '# 正式比较通过；接着执行“实验收尾”。',
        '# 完整样本、各轮统计及检查记录保存在：',
        f'evidence={evidence}',
    ]
    return '\n'.join(line.rstrip() for line in lines) + '\n'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('analysis_dir', type=Path)
    args = parser.parse_args()
    print(report(json.loads((args.analysis_dir / 'summary.json').read_text()), args.analysis_dir), end='')
