#!/usr/bin/env python3
"""发送端：发帧并用网卡硬件时间戳记下每一帧真正离开的时刻。

在 Exchange（.1）上运行。内核把 TX 硬件时间戳放在套接字的错误队列里，
用 SOF_TIMESTAMPING_OPT_ID 给每次 sendmsg 编号，回收时按这个编号和 seq 对上。
输出 JSONL，每行 {"seq": n, "tx_hw_ns": t}。
"""

import json
import os
import socket
import struct
import sys
import time

# ----- 模块级配置：改这里即可重跑 -----
DEST_IP = os.environ.get("DEST_IP", "20.1.1.2")
DEST_PORT = int(os.environ.get("DEST_PORT", "30001"))
SRC_IP = os.environ.get("SRC_IP", "20.1.1.1")
FRAME_COUNT = int(os.environ.get("FRAME_COUNT", "2000"))
PAYLOAD_BYTES = int(os.environ.get("PAYLOAD_BYTES", "64"))
SEND_GAP_S = float(os.environ.get("SEND_GAP_S", "0.001"))
DRAIN_TIMEOUT_S = float(os.environ.get("DRAIN_TIMEOUT_S", "10"))
OUT_PATH = os.environ.get("OUT_PATH", "oneway-tx.jsonl")

# SO_TIMESTAMPING 相关常量，Python 标准库未导出，按 Linux uapi 定义。
SO_TIMESTAMPING = 37
SCM_TIMESTAMPING = 37
SOF_TIMESTAMPING_TX_HARDWARE = 1 << 0
SOF_TIMESTAMPING_RAW_HARDWARE = 1 << 6
SOF_TIMESTAMPING_OPT_ID = 1 << 7
SOF_TIMESTAMPING_OPT_TSONLY = 1 << 11
IP_RECVERR = 11

TIMESPEC_FMT = "qq"
TIMESPEC_SIZE = struct.calcsize(TIMESPEC_FMT)
SCM_TIMESTAMPING_SIZE = TIMESPEC_SIZE * 3

# struct sock_extended_err：ee_data 里放的是 OPT_ID 编号。
EXTENDED_ERR_FMT = "IBBBBII"
EXTENDED_ERR_SIZE = struct.calcsize(EXTENDED_ERR_FMT)


def open_timestamped_socket(src_ip, dest_ip, dest_port):
    """建立 UDP 套接字并打开网卡硬件发送时间戳。"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_IP, IP_RECVERR, 1)
    sock.setsockopt(
        socket.SOL_SOCKET,
        SO_TIMESTAMPING,
        SOF_TIMESTAMPING_TX_HARDWARE
        | SOF_TIMESTAMPING_RAW_HARDWARE
        | SOF_TIMESTAMPING_OPT_ID
        | SOF_TIMESTAMPING_OPT_TSONLY,
    )
    sock.bind((src_ip, 0))
    sock.connect((dest_ip, dest_port))
    return sock


def parse_errqueue_entry(ancdata):
    """从错误队列的辅助数据里取出 (OPT_ID 编号, raw hardware 时刻)。"""
    tx_hw_ns = None
    tsid = None
    for level, ctype, payload in ancdata:
        if level == socket.SOL_SOCKET and ctype == SCM_TIMESTAMPING:
            if len(payload) >= SCM_TIMESTAMPING_SIZE:
                raw = payload[TIMESPEC_SIZE * 2 : TIMESPEC_SIZE * 3]
                sec, nsec = struct.unpack(TIMESPEC_FMT, raw)
                if sec or nsec:
                    tx_hw_ns = sec * 1_000_000_000 + nsec
        elif level == socket.SOL_IP and ctype == IP_RECVERR:
            if len(payload) >= EXTENDED_ERR_SIZE:
                fields = struct.unpack_from(EXTENDED_ERR_FMT, payload, 0)
                tsid = fields[6]
    return tsid, tx_hw_ns


def drain_available(sock, stamps):
    """把错误队列里当前已就绪的发送戳全部取走；返回本次取到几条。

    错误队列不会在 select 的异常集里报告，只能非阻塞轮询；队列容量有限，
    必须边发边收，否则发完再取会丢掉绝大部分条目。
    """
    taken = 0
    while True:
        try:
            _data, ancdata, _flags, _addr = sock.recvmsg(
                2048, 1024, socket.MSG_ERRQUEUE | socket.MSG_DONTWAIT
            )
        except BlockingIOError:
            return taken
        tsid, tx_hw_ns = parse_errqueue_entry(ancdata)
        if tsid is None or tx_hw_ns is None:
            continue
        stamps[tsid] = tx_hw_ns
        taken += 1


def send_frames(sock, frame_count, payload_bytes, send_gap_s, drain_timeout_s):
    """按固定间隔发帧并同步回收发送戳；帧头 8 字节写入 seq。"""
    filler = b"\x00" * max(0, payload_bytes - 8)
    stamps = {}
    for seq in range(frame_count):
        sock.send(struct.pack("!Q", seq) + filler)
        if send_gap_s > 0:
            time.sleep(send_gap_s)
        drain_available(sock, stamps)
    deadline = time.monotonic() + drain_timeout_s
    while len(stamps) < frame_count and time.monotonic() < deadline:
        if drain_available(sock, stamps) == 0:
            time.sleep(0.002)
    return stamps


def send_demo(dest_ip, dest_port, frame_count, out_path):
    """按顺序建套接字、发帧、回收发送戳并落盘。"""
    sock = open_timestamped_socket(SRC_IP, dest_ip, dest_port)
    stamps = send_frames(sock, frame_count, PAYLOAD_BYTES, SEND_GAP_S, DRAIN_TIMEOUT_S)
    sock.close()
    # OPT_ID 从 0 开始，每次 sendmsg 加一，因此编号就是 seq。
    with open(out_path, "w", encoding="utf-8") as handle:
        for tsid in sorted(stamps):
            handle.write(json.dumps({"seq": tsid, "tx_hw_ns": stamps[tsid]}) + "\n")
    print(json.dumps({
        "sent": frame_count,
        "tx_hw_timestamps": len(stamps),
        "payload_bytes": PAYLOAD_BYTES,
        "out_path": out_path,
    }, ensure_ascii=False))
    if not stamps:
        sys.exit("no hardware transmit timestamp returned")


if __name__ == "__main__":
    send_demo(DEST_IP, DEST_PORT, FRAME_COUNT, OUT_PATH)
