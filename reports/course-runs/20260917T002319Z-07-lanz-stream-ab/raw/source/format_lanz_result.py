#!/usr/bin/env python3
"""Display receiver counts alongside the EOS output captured before restoration."""

import json
from datetime import datetime, timezone
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


def event_clock(event):
    if event.get("timestamp_tick_us") != 10:
        raise ValueError("LANZ 时间单位未确认，请更新读取工具后重新采集")
    us = event["timestamp_us"]
    if us != event["timestamp_raw"] * 10:
        raise ValueError("LANZ 原始刻度与微秒换算不一致")
    return datetime.fromtimestamp(us // 1_000_000, timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S") + f".{us % 1_000_000:06d} UTC"


def verify_sample(sample, switch_text):
    """Compare the same Et2/TC1 run, not retained counts with cumulative counts."""
    sections = switch_sections(switch_text)
    stats = sections["show queue-monitor length statistics"]
    match = re.search(r"^Et2\s+1\s+(\d+)\s*$", stats, re.M)
    if not match:
        raise ValueError("交换机未返回 Et2 / TC1 累计计数")
    total = int(match[1])
    counts = sample["counts_by_queue"]["Ethernet2/TC1"]
    eos_rows = []
    for line in sections["show queue-monitor length Ethernet 2"].splitlines():
        m = re.match(r"\s*([SUE])\s+\S+\s+ago\s+Et2\(1\)\s+(\S+)\s+(\d+)\*?", line)
        if m:
            eos_rows.append((m[1], int(m[3]), m[2]))
    kind = {"START": "S", "UPDATE": "U", "END": "E"}
    if not (total == counts["START"] == counts["END"]):
        raise ValueError(f"拥塞累计次数不一致：EOS={total}, 接收器={counts}")
    for name, letter in kind.items():
        if sum(row[0] == letter for row in eos_rows) != counts[name]:
            raise ValueError(f"交换机完整 {letter} 记录数与接收器不一致")
    events = [e for e in sample["events"]
              if e["intf_name"] == "Ethernet2" and e["traffic_class"] == 1]
    if not events:
        raise ValueError("缺少 Et2 / TC1 接收明细")
    identities = [(e["timestamp_raw"], e["entry_type"]) for e in events]
    if len(set(identities)) != len(identities):
        raise ValueError("接收器保留明细存在重复记录")
    observed = [(kind[e["entry_type"]], e["queue_size"]) for e in reversed(events)]
    if observed != [(r[0], r[1]) for r in eos_rows[:len(events)]]:
        raise ValueError("接收器与交换机最近记录的类型、顺序或队列长度不一致")
    # The switch clock is local, not necessarily synchronized to the management VM.
    report_time = re.search(r"Report generated at ([\d-]+ [\d:]+)",
                            sections["show queue-monitor length Ethernet 2"])[1]
    report_seconds = datetime.strptime(report_time, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
    first_row = re.search(r"^\s*[SUE]\s+(\d+):(\d+):(\d+\.\d+) ago",
                          sections["show queue-monitor length Ethernet 2"], re.M)
    age = int(first_row[1])*3600 + int(first_row[2])*60 + float(first_row[3])
    for e in events:
        event_clock(e)
    clock_error = abs(report_seconds - age - events[-1]["timestamp_us"] / 1_000_000)
    if clock_error >= 1.1:
        raise ValueError("流式事件时刻与 EOS 报告时刻/相对时间不符")
    return {"result": "PASS", "scope": "Ethernet2/TC1", "switch_congestions": total,
            "collector_counts": counts, "eos_records": len(eos_rows),
            "retained_records_matched": len(events), "unique_records": True,
            "timestamp_tick_us": 10, "clock_alignment_error_seconds": round(clock_error, 6),
            "latest_start_utc": event_clock(latest_pair(events)[0]),
            "latest_end_utc": event_clock(latest_pair(events)[1]),
            "latest_eos_duration_us": int(eos_rows[0][2])}


def display_section(command, text, record_limit=None):
    if record_limit:
        print("最近两条记录节选（最近一次拥塞的 E/S；完整累计次数见上表）：")
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
        counts = sample["et2_tc1_counts"]
        print(f"{label} / Et2 TC1：累计开始 {counts['START']} 次，更新 {counts['UPDATE']} 条，累计结束 {counts['END']} 次。")
    print(f"采集器保留最近 {len(high['et2_events'])} 条 Et2 记录（上限 80 条）；下方与网页默认展示最近一次完整拥塞。")
    print("采集器连接：" + ("已连接交换机 TCP 50001。" if high["connected"] else "未连接。"))
    pair = latest_pair([e for e in high["et2_events"] if e["traffic_class"] == 1])
    if pair:
        start, end = pair
        print(f"最近一次完整事件：{start['intf_name']} / TC{start['traffic_class']}")
        print(f"  S 开始：{event_clock(start)}；队列长度 {start['queue_size']} 段。")
        print(f"  E 结束：{event_clock(end)}；本次最大队列长度 {end['queue_size']} 段。")
        print("  每段 480 B；时刻粒度 10 µs，持续时间读取下方 EOS duration。")
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
    check = json.loads((run / "derived/cross-check.json").read_text())
    print(f"逐条核对：交换机与接收器累计均为 {check['switch_congestions']} 次；最近 {check['retained_records_matched']} 条记录一致。")


if __name__ == "__main__":
    if sys.argv[1] == "--verify":
        run = Path(sys.argv[2])
        print(json.dumps(verify_sample(
            json.loads((run / "raw/collector-dual-25k-4096.json").read_text()),
            (run / "raw/switch-post.txt").read_text()), ensure_ascii=False, indent=2))
    else:
        render(sys.argv[1])
