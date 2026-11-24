#!/usr/bin/env python3
"""Format the measured PTP, frame matching and delay results for the lesson."""

import json
from pathlib import Path
import sys
import unicodedata


def pad(text, width):
    used = sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)
    return text + " " * max(0, width - used)


def render(analysis, ptp):
    total = analysis["live_interior"]
    paired = analysis["paired"]
    ratio = f"{paired / total:.2%}" if total else "无有效样本"
    offset = ptp.get("offset_ns_last")
    delay = analysis["delay_ns"]
    lines = [
        "===== PTP 对时 =====",
        "跟随状态：" + (".2 已进入 SLAVE。" if ptp["slave_lines"] > 0 else ".2 未进入 SLAVE。"),
        "ptp4l 最后估计的时钟偏差：" + (f"{offset:,.0f} ns。" if offset is not None else "无读数。"),
        "",
        "===== 同帧配对 =====",
        f"有效时间窗内配对：{paired:,} / {total:,} 帧（{ratio}）",
        f"未找到副本：{analysis['miss_live']:,} 帧；匹配不唯一：{analysis['ambiguous']:,} 帧。",
        f"用于还原入口时间的 Keyframe：{analysis['keyframes']:,} 帧。",
        "",
        "===== 时间差：网卡 RX 时间 − 交换机入口时间 =====",
        pad("统计项", 10) + " | 时间差（µs）",
        "-----------+-------------",
    ]
    for label, key in (("最小值", "min"), ("p50", "p50"), ("p99", "p99"), ("最大值", "max")):
        value = delay.get(key)
        shown = f"{value / 1000:,.3f}" if value is not None else "无读数"
        lines.append(pad(label, 10) + " | " + shown.rjust(12))
    lines.extend((f"负值样本：{delay['negatives']:,} 帧。", "",
                  "配对与时间差检查：" + ("通过。" if analysis["pass"] else "未通过。")))
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    run = Path(sys.argv[1])
    analysis = json.loads((run / "derived/analysis.json").read_text())
    ptp = json.loads((run / "derived/ptp4l-summary.json").read_text())
    print(render(analysis, ptp), end="")
