#!/usr/bin/env python3
"""把两端的硬件时间戳按 seq 配对，相减得到单向延时。

用法：analyze_oneway.py <tx.jsonl> <rx.jsonl>
发送戳来自 Exchange 的 PHC，接收戳来自 Trader 的 PHC；两只 PHC 已由 PTP 对表，
所以两个数才有资格相减。输出 JSON，供入口脚本判定与正文引用。
"""

import json
import sys


def load_samples(path, key):
    """读取一端的 JSONL 硬件时间戳，返回 {seq: 时刻}。"""
    samples = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            samples[int(item["seq"])] = int(item[key])
    return samples


def pair_and_subtract(tx_samples, rx_samples):
    """按 seq 配对并相减，返回升序的单向延时列表（纳秒）。"""
    common = sorted(set(tx_samples) & set(rx_samples))
    return sorted(rx_samples[seq] - tx_samples[seq] for seq in common), len(common)


def percentile(values, fraction):
    """取 nearest-rank 分位数；values 必须已升序。"""
    if not values:
        return None
    rank = max(1, min(len(values), int(-(-len(values) * fraction // 1))))
    return values[rank - 1]


def analyze_demo(tx_path, rx_path):
    """读取两端样本、配对相减并打印统计量。"""
    tx_samples = load_samples(tx_path, "tx_hw_ns")
    rx_samples = load_samples(rx_path, "rx_hw_ns")
    deltas, paired = pair_and_subtract(tx_samples, rx_samples)
    print(json.dumps({
        "tx_count": len(tx_samples),
        "rx_count": len(rx_samples),
        "paired_count": paired,
        "unpaired_tx": len(tx_samples) - paired,
        "one_way_ns": {
            "min": deltas[0] if deltas else None,
            "p50": percentile(deltas, 0.50),
            "p99": percentile(deltas, 0.99),
            "max": deltas[-1] if deltas else None,
        },
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    analyze_demo(sys.argv[1], sys.argv[2])
