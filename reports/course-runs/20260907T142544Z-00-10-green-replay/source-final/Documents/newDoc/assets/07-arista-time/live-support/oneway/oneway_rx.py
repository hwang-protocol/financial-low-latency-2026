#!/usr/bin/env python3
"""接收端：用网卡硬件时间戳记下每一帧的到达时刻。

在 Trader（.2）上运行。收到的每一帧都从 SCM_TIMESTAMPING 辅助数据里取出
raw hardware 时刻，这个时刻由 X2522 的 PHC 打出，和发送端的 PHC 已由 PTP 对过表。
输出 JSONL，每行 {"seq": n, "rx_hw_ns": t}。
"""

import json
import os
import socket
import struct
import sys

# ----- 模块级配置：改这里即可重跑 -----
LISTEN_IP = os.environ.get("LISTEN_IP", "20.1.1.2")
LISTEN_PORT = int(os.environ.get("LISTEN_PORT", "30001"))
EXPECT_COUNT = int(os.environ.get("EXPECT_COUNT", "2000"))
IDLE_TIMEOUT_S = float(os.environ.get("IDLE_TIMEOUT_S", "10"))
OUT_PATH = os.environ.get("OUT_PATH", "oneway-rx.jsonl")
READY_MARKER = os.environ.get("READY_MARKER", "")

# SO_TIMESTAMPING 相关常量，Python 标准库未导出，按 Linux uapi 定义。
SO_TIMESTAMPING = 37
SCM_TIMESTAMPING = 37
SOF_TIMESTAMPING_RX_HARDWARE = 1 << 2
SOF_TIMESTAMPING_RAW_HARDWARE = 1 << 6

# struct scm_timestamping = 三个 timespec；ts[2] 才是 raw hardware。
TIMESPEC_FMT = "qq"
TIMESPEC_SIZE = struct.calcsize(TIMESPEC_FMT)
SCM_TIMESTAMPING_SIZE = TIMESPEC_SIZE * 3


def open_timestamped_socket(listen_ip, listen_port):
    """建立 UDP 套接字并打开网卡硬件接收时间戳。"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(
        socket.SOL_SOCKET,
        SO_TIMESTAMPING,
        SOF_TIMESTAMPING_RX_HARDWARE | SOF_TIMESTAMPING_RAW_HARDWARE,
    )
    sock.bind((listen_ip, listen_port))
    sock.settimeout(IDLE_TIMEOUT_S)
    return sock


def parse_hw_timestamp(ancdata):
    """从辅助数据里取出 raw hardware 时刻，单位纳秒；没有硬件戳时返回 None。"""
    for level, ctype, payload in ancdata:
        if level != socket.SOL_SOCKET or ctype != SCM_TIMESTAMPING:
            continue
        if len(payload) < SCM_TIMESTAMPING_SIZE:
            continue
        raw = payload[TIMESPEC_SIZE * 2 : TIMESPEC_SIZE * 3]
        sec, nsec = struct.unpack(TIMESPEC_FMT, raw)
        if sec == 0 and nsec == 0:
            return None
        return sec * 1_000_000_000 + nsec
    return None


def receive_samples(sock, expect_count):
    """循环接收，直到收满预期数量或空闲超时；返回样本列表与无硬件戳计数。"""
    samples = []
    missing_hw = 0
    while len(samples) < expect_count:
        try:
            data, ancdata, _flags, _addr = sock.recvmsg(2048, 1024)
        except socket.timeout:
            break
        if len(data) < 8:
            continue
        seq = struct.unpack_from("!Q", data, 0)[0]
        rx_hw_ns = parse_hw_timestamp(ancdata)
        if rx_hw_ns is None:
            missing_hw += 1
            continue
        samples.append({"seq": seq, "rx_hw_ns": rx_hw_ns})
    return samples, missing_hw


def receive_demo(listen_ip, listen_port, expect_count, out_path):
    """按顺序建套接字、发就绪信号、收样本并落盘。"""
    sock = open_timestamped_socket(listen_ip, listen_port)
    # 就绪标记必须在 bind 之后写，发送端据此判断可以开打。
    if READY_MARKER:
        with open(READY_MARKER, "w", encoding="utf-8") as handle:
            handle.write("ready\n")
    samples, missing_hw = receive_samples(sock, expect_count)
    sock.close()
    with open(out_path, "w", encoding="utf-8") as handle:
        for item in samples:
            handle.write(json.dumps(item) + "\n")
    print(json.dumps({
        "received": len(samples),
        "missing_hw_timestamp": missing_hw,
        "out_path": out_path,
    }, ensure_ascii=False))
    if not samples:
        sys.exit("no frame received")
    if missing_hw:
        sys.exit("hardware receive timestamp missing on %d frames" % missing_hw)


if __name__ == "__main__":
    receive_demo(LISTEN_IP, LISTEN_PORT, EXPECT_COUNT, OUT_PATH)
