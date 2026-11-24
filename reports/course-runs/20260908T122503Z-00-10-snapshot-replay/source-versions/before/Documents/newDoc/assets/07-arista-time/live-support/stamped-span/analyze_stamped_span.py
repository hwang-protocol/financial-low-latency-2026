#!/usr/bin/env python3
"""把带戳副本与交易网卡硬件 RX 按真实行情帧配对，算出 T_live − T_in。"""

import json
import math
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path


MARKET_SRC = "20.1.1.1"
MARKET_DST = "20.1.1.2"
MARKET_DPORTS = range(42121, 42126)
KEYFRAME_SRC = "20.1.1.254"
KEYFRAME_PROTO = 253
ASIC_HZ = 350_000_000
TRAILER_HZ = 700_000_000
TICK_NS = 1_000_000_000 / TRAILER_HZ
MOD32 = 1 << 32


def read_pcap(path):
    """读取微秒或纳秒 pcap，返回 [(capture_ns, frame_bytes), ...]。"""
    data = Path(path).read_bytes()
    magic = data[:4]
    if magic == b"\xd4\xc3\xb2\xa1":
        nano = False
    elif magic == b"\x4d\x3c\xb2\xa1":
        nano = True
    else:
        raise SystemExit(f"unsupported pcap magic {magic.hex()} path={path}")
    offset = 24
    frames = []
    while offset + 16 <= len(data):
        ts_sec, ts_frac, incl, _orig = struct.unpack_from("<IIII", data, offset)
        frame = data[offset + 16 : offset + 16 + incl]
        offset += 16 + incl
        capture_ns = ts_sec * 1_000_000_000 + (ts_frac if nano else ts_frac * 1000)
        frames.append((capture_ns, frame))
    return {"nano": nano, "frames": frames}


def parse_ipv4(frame):
    """拆 IPv4 帧；非 IPv4 返回 None。"""
    if len(frame) < 34 or frame[12:14] != b"\x08\x00":
        return None
    header_len = (frame[14] & 0x0F) * 4
    ip = frame[14 : 14 + header_len]
    if len(ip) < 20:
        return None
    return {
        "proto": ip[9],
        "src": ".".join(str(item) for item in ip[12:16]),
        "dst": ".".join(str(item) for item in ip[16:20]),
        "ipid": int.from_bytes(ip[4:6], "big"),
        "l4": frame[14 + header_len :],
        "frame": frame,
    }


def signed_mod32(value):
    """把 32-bit 计数差收成最近的有符号步长。"""
    value %= MOD32
    if value >= (1 << 31):
        value -= MOD32
    return value


def percentile(values, pct):
    """nearest-rank 分位；空序列返回 None。"""
    if not values:
        return None
    ordered = sorted(values)
    if pct <= 0:
        return ordered[0]
    if pct >= 100:
        return ordered[-1]
    index = math.ceil(pct / 100 * len(ordered)) - 1
    return ordered[max(0, min(index, len(ordered) - 1))]


def is_market_udp(parsed, strip_trailer, market_sport):
    """判断是否为本课 UDP 行情。"""
    if parsed is None or parsed["proto"] != 17 or len(parsed["l4"]) < 8:
        return False
    if parsed["src"] != MARKET_SRC or parsed["dst"] != MARKET_DST:
        return False
    src_port = int.from_bytes(parsed["l4"][0:2], "big")
    dst_port = int.from_bytes(parsed["l4"][2:4], "big")
    if src_port != market_sport or dst_port not in MARKET_DPORTS:
        return False
    payload = parsed["l4"][8:-4] if strip_trailer else parsed["l4"][8:]
    return {
        "ipid": parsed["ipid"],
        "dport": dst_port,
        "payload": payload,
        "frame_len": len(parsed["frame"]),
        "trailer": int.from_bytes(parsed["frame"][-4:], "big") if strip_trailer else None,
    }


def collect_copy(frames, market_sport):
    """从副本 pcap 收集 keyframe 与带 4 字节尾戳的行情。"""
    keyframes = []
    market = []
    other = 0
    for capture_ns, frame in frames:
        parsed = parse_ipv4(frame)
        if parsed and parsed["proto"] == KEYFRAME_PROTO and parsed["src"] == KEYFRAME_SRC:
            payload = parsed["l4"]
            asic350 = int.from_bytes(payload[0:8], "big")
            keyframes.append(
                {
                    "capture_ns": capture_ns,
                    "asic350": asic350,
                    "asic700": asic350 * 2,
                    "utc_ns": int.from_bytes(payload[8:16], "big"),
                    "last_sync": int.from_bytes(payload[16:24], "big") if len(payload) >= 24 else None,
                }
            )
            continue
        row = is_market_udp(parsed, strip_trailer=True, market_sport=market_sport)
        if row:
            row["capture_ns"] = capture_ns
            market.append(row)
            continue
        other += 1
    return keyframes, market, other


def collect_live(frames, market_sport):
    """从交易网卡 pcap 收集硬件 RX 戳行情。"""
    market = []
    other = 0
    for capture_ns, frame in frames:
        parsed = parse_ipv4(frame)
        row = is_market_udp(parsed, strip_trailer=False, market_sport=market_sport)
        if row:
            row["rx_ns"] = capture_ns
            market.append(row)
            continue
        other += 1
    return market, other


def nearest_keyframe(keyframes, capture_ns):
    """用同一份副本 pcap 的主机到达时刻选最近的 keyframe。"""
    return min(keyframes, key=lambda item: abs(item["capture_ns"] - capture_ns))


def pair_frames(copy_market, live_market):
    """以交易网卡收到的行情为准，按 ipid + 目的端口 + UDP 载荷一对一配对。"""
    index = defaultdict(list)
    for item in copy_market:
        index[(item["ipid"], item["dport"], item["payload"])].append(item)
    pairs = []
    miss_live = 0
    ambiguous = 0
    used = set()
    for item in live_market:
        key = (item["ipid"], item["dport"], item["payload"])
        hits = index.get(key, [])
        if len(hits) == 1:
            pairs.append((hits[0], item))
            used.add(id(hits[0]))
        elif len(hits) > 1:
            ambiguous += 1
        else:
            miss_live += 1
    copy_only = sum(1 for item in copy_market if id(item) not in used)
    return pairs, miss_live, ambiguous, copy_only


def linear_residual(pairs):
    """用连续解开的 ASIC tick 对 PHC 做直线拟合，看频率是否锁住。"""
    ticks = []
    rx_ns = []
    current = None
    previous = None
    for copy, live in pairs:
        trailer = copy["trailer"]
        if previous is None:
            current = trailer
        else:
            current = current + signed_mod32(trailer - previous)
        previous = trailer
        ticks.append(current)
        rx_ns.append(live["rx_ns"])
    count = len(ticks)
    mean_x = sum(ticks) / count
    mean_y = sum(rx_ns) / count
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(ticks, rx_ns))
    denominator = sum((x - mean_x) ** 2 for x in ticks)
    slope = numerator / denominator
    intercept = mean_y - slope * mean_x
    residuals = [y - (slope * x + intercept) for x, y in zip(ticks, rx_ns)]
    return {
        "ns_per_tick": slope,
        "expected_ns_per_tick": TICK_NS,
        "ppm": (slope - TICK_NS) / TICK_NS * 1e6,
        "resid_ns": {
            "min": min(residuals),
            "p50": percentile(residuals, 50),
            "p99": percentile(residuals, 99),
            "max": max(residuals),
            "abs_p50": percentile([abs(item) for item in residuals], 50),
            "abs_p99": percentile([abs(item) for item in residuals], 99),
        },
    }


def analyze(copy_path, live_path, market_sport):
    """解析两份 pcap，返回可审计的配对与延时统计。"""
    copy_pcap = read_pcap(copy_path)
    live_pcap = read_pcap(live_path)
    keyframes, copy_market, copy_other = collect_copy(copy_pcap["frames"], market_sport)
    live_market, live_other = collect_live(live_pcap["frames"], market_sport)
    if len(keyframes) < 4:
        raise SystemExit(f"need at least 4 keyframes, got {len(keyframes)}")
    window_lo = keyframes[1]["utc_ns"]
    window_hi = keyframes[-2]["utc_ns"]
    live_interior = [
        item for item in live_market if window_lo <= item["rx_ns"] <= window_hi
    ]
    pairs, miss_live, ambiguous, copy_only = pair_frames(copy_market, live_interior)
    delays = []
    for copy, live in pairs:
        keyframe = nearest_keyframe(keyframes, copy["capture_ns"])
        delta = signed_mod32(copy["trailer"] - (keyframe["asic700"] & (MOD32 - 1)))
        t_in = keyframe["utc_ns"] + delta * TICK_NS
        delays.append(live["rx_ns"] - t_in)
    asic_hz = []
    for left, right in zip(keyframes, keyframes[1:]):
        dt = (right["utc_ns"] - left["utc_ns"]) / 1e9
        if dt > 0:
            asic_hz.append((right["asic350"] - left["asic350"]) / dt)
    copy_lens = Counter(item["frame_len"] for item in copy_market)
    live_lens = Counter(item["frame_len"] for item in live_market)
    result = {
        "schema": "flle.ch07-stamped-span.v1",
        "market_source_port": market_sport,
        "copy_pcap": str(copy_path),
        "live_pcap": str(live_path),
        "copy_frames": len(copy_pcap["frames"]),
        "live_frames": len(live_pcap["frames"]),
        "copy_market": len(copy_market),
        "live_market": len(live_market),
        "live_interior": len(live_interior),
        "window_utc_ns": [window_lo, window_hi],
        "window_seconds": (window_hi - window_lo) / 1e9,
        "copy_other": copy_other,
        "live_other": live_other,
        "keyframes": len(keyframes),
        "keyframe_last_sync": [item["last_sync"] for item in keyframes],
        "asic_hz_median": percentile(asic_hz, 50),
        "paired": len(pairs),
        "miss_live": miss_live,
        "copy_only": copy_only,
        "ambiguous": ambiguous,
        "copy_frame_len": copy_lens.most_common(5),
        "live_frame_len": live_lens.most_common(5),
        "delay_ns": {
            "n": len(delays),
            "negatives": sum(1 for item in delays if item < 0),
            "min": min(delays) if delays else None,
            "p50": percentile(delays, 50),
            "p90": percentile(delays, 90),
            "p99": percentile(delays, 99),
            "max": max(delays) if delays else None,
        },
        "freq": linear_residual(pairs) if pairs else None,
        "gates": {},
    }
    def number(value, digits=0):
        return "n/a" if value is None else f"{value:.{digits}f}"
    delay = result["delay_ns"]
    result["gates"] = {
        "pair_complete": (
            result["paired"] == result["live_interior"]
            and result["live_interior"] >= 1000
            and miss_live == 0
            and ambiguous == 0
        ),
        "all_positive": delay["n"] > 0 and delay["negatives"] == 0,
        "max_under_1ms": delay["max"] is not None and delay["max"] < 1_000_000,
        "typical_copy_plus4": bool(copy_lens) and bool(live_lens) and copy_lens.most_common(1)[0][0] == live_lens.most_common(1)[0][0] + 4,
        "asic_near_350mhz": result["asic_hz_median"] is not None and abs(result["asic_hz_median"] - ASIC_HZ) < 200_000,
    }
    result["pass"] = all(result["gates"].values())
    return result


def render_summary(result):
    """把分析结果收成课堂可读的几行。"""
    def number(value, digits=0):
        return "n/a" if value is None else f"{value:.{digits}f}"
    delay = result["delay_ns"]
    freq = result["freq"]
    return "\n".join(
        [
            f"result={'PASS' if result['pass'] else 'FAIL'}",
            f"paired={result['paired']}/{result['live_interior']}",
            f"live_market={result['live_market']}",
            f"copy_market={result['copy_market']}",
            f"window_s={result['window_seconds']:.3f}",
            f"copy_only={result['copy_only']}",
            f"miss_live={result['miss_live']}",
            f"keyframes={result['keyframes']}",
            f"last_sync={result['keyframe_last_sync']}",
            f"T_live-T_in_ns min/p50/p99/max={number(delay['min'])}/{number(delay['p50'])}/{number(delay['p99'])}/{number(delay['max'])}",
            f"negatives={delay['negatives']}",
            f"freq_resid_abs_p99_ns={number(freq['resid_ns']['abs_p99'] if freq else None)}",
            f"freq_ppm={number(freq['ppm'] if freq else None, 3)}",
            f"asic_hz_median={number(result['asic_hz_median'], 1)}",
            f"copy_len={result['copy_frame_len']}",
            f"live_len={result['live_frame_len']}",
            f"gates={result['gates']}",
        ]
    )


if __name__ == "__main__":
    print("~~~~~~~~~~~~~~~~~~~~~带戳副本配对~~~~~~~~~~~~~~~~~~~~~")
    if len(sys.argv) != 5:
        raise SystemExit("usage: analyze_stamped_span.py COPY.pcap LIVE.pcap OUT.json MARKET_SPORT")
    market_sport = int(sys.argv[4])
    if not 1 <= market_sport <= 65535:
        raise SystemExit("invalid market source port")
    analysis = analyze(sys.argv[1], sys.argv[2], market_sport)
    Path(sys.argv[3]).write_text(json.dumps(analysis, indent=2) + "\n", encoding="utf-8")
    print(render_summary(analysis))
    if not analysis["pass"]:
        raise SystemExit(2)
