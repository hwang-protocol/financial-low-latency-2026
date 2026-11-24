#!/usr/bin/env python3
"""Display receiver counts alongside the EOS output captured before restoration."""

import json
from pathlib import Path
import re
import sys


def latest_pair(events):
    pending = {}
    latest = None
    for event in events:
        key = (event["intf_name"], event["traffic_class"])
        if event["entry_type"] == "START":
            pending[key] = event
        elif event["entry_type"] == "END" and key in pending:
            latest = (pending.pop(key), event)
    return latest


def switch_sections(text):
    parts = re.split(r"^\$ (show[^\n]+)\n", text, flags=re.M)
    return dict(zip(parts[1::2], parts[2::2]))


def display_section(command, text, record_limit=None):
    if record_limit:
        print("最近两条记录节选：")
    print(f"$ {command}")
    records = 0
    lines = []
    for line in text.splitlines():
        if (line.startswith(command) or line.startswith("Report generated at")
                or line.startswith("GH-High") or "Segment size for GL" in line
                or line.startswith("+ Period") or line.startswith("Global Hit Count")):
            continue
        if re.match(r"^\s*[SUE]\s+\d", line):
            records += 1
            if record_limit and records > record_limit:
                break
        lines.append(line.rstrip())
    print("\n".join(lines).strip())
    print()


def render(run_dir):
    run = Path(run_dir)
    low = json.loads((run / "derived/collector-dual-10k-4096.json").read_text())
    high = json.loads((run / "derived/collector-dual-25k-4096.json").read_text())
    result = json.loads((run / "result.json").read_text())
    sections = switch_sections((run / "raw/switch-post.txt").read_text())
    print("===== LANZ 接收器 =====")
    for label, sample in (("每入口 10k pps", low), ("每入口 25k pps", high)):
        counts = sample["et2_counts"]
        print(f"{label}：开始 {counts['START']} 条，更新 {counts['UPDATE']} 条，结束 {counts['END']} 条。")
    print("以上为当前保留的 Et2 明细计数；采集器仅保留最近 80 条事件记录。")
    print("采集器连接：" + ("已连接交换机 TCP 50001。" if high["connected"] else "未连接。"))
    pair = latest_pair(high["et2_events"])
    if pair:
        start, end = pair
        print(f"最近一次完整事件：{start['intf_name']} / TC{start['traffic_class']}")
        print(f"  开始记录：队列长度 {start['queue_size']} 个缓冲段。")
        print(f"  结束记录：本次事件最大队列长度 {end['queue_size']} 个缓冲段。")
    else:
        print("当前明细中没有完整的开始/结束记录对。")
    print()
    print("===== 交换机查询结果（恢复配置前） =====")
    for command, limit in (
        ("show queue-monitor length statistics", None),
        ("show queue-monitor length Ethernet 2", 2),
        ("show queue-monitor streaming clients", None),
    ):
        display_section(command, sections[command], limit)
    restored = all(result.get(key) is True for key in (
        "switch_restored", "startup_unchanged", "vm11_restored", "collector_left_running"))
    if result.get("result") != "PASS" or not restored:
        raise ValueError("LANZ 实验或恢复检查未通过")
    print("恢复检查：交换机配置和发流网卡已恢复，采集器保留事件记录。")


if __name__ == "__main__":
    render(sys.argv[1])
