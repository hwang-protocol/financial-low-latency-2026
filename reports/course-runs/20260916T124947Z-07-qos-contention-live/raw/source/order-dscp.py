#!/usr/bin/env python3
"""Ask the compiled POSIX order thread to set/read IP_TOS; no firewall rules."""
import argparse
import json
import socket
import time

PORTS = {'SOCKET':48122, 'OPENONLOAD':48123}
LABELS = {'SOCKET':'POSIX_SOCKET', 'OPENONLOAD':'OPENONLOAD'}

def command(host, port, value):
    with socket.create_connection((host, port), timeout=5) as connection:
        connection.sendall(value.encode('ascii') + b'\n')
        reply = json.loads(connection.makefile('rb').readline(65536))
    if 'error' in reply: raise RuntimeError(reply['error'])
    return reply

def main():
    p = argparse.ArgumentParser()
    p.add_argument('value', choices=['GET']+[str(i) for i in range(64)])
    p.add_argument('--host', default='10.1.1.2')
    p.add_argument('--transport', choices=PORTS, default='SOCKET')
    p.add_argument('--expect', type=int)
    p.add_argument('--expect-pid', type=int)
    p.add_argument('--connected', action='store_true')
    p.add_argument('--json', action='store_true')
    a = p.parse_args()
    state=command(a.host,PORTS[a.transport],'STATE')
    if state.get('order_dscp_control') != 'POSIX_QOS_V1':
        raise RuntimeError('客户端未安装打标功能，请先执行第 05 章准备 B。')
    if state.get('order_transport') != LABELS[a.transport]:
        raise RuntimeError('订单连接与所选路径不一致。')
    request = 'ORDER_DSCP|' + a.value
    if a.expect_pid: request += '|' + str(a.expect_pid)
    reply=command(a.host,PORTS[a.transport],request)
    expected=a.expect if a.expect is not None else (int(a.value) if a.value!='GET' else None)
    if expected is not None and reply.get('dscp') != expected:
        raise RuntimeError(f'DSCP 核对失败：{reply}')
    if a.expect_pid and reply.get('pid') != a.expect_pid:
        raise RuntimeError('客户端进程已变化。')
    if a.connected and not reply.get('connected'):
        raise RuntimeError('订单 TCP 连接尚未建立；先完成第 05 章对应路径的单笔验证。')
    if reply.get('connected') and (type(reply.get('tos')) is not int or reply['tos']>>2 != reply['dscp']):
        raise RuntimeError('IP_TOS 回读与 DSCP 配置不一致。')
    if a.json:
        print(json.dumps(reply, sort_keys=True))
    else:
        print(f"===== 订单连接打标 · {a.transport} =====")
        print('[执行说明] 脚本发控制指令，订单线程调用 setsockopt(IP_TOS)，再用 getsockopt 回读。')
        if reply['connected']:
            print(f"DSCP={reply['dscp']}  TOS=0x{reply['tos']:02x}  源端口={reply['local_port']}  PID={reply['pid']}")
        else:
            print(f"DSCP={reply['dscp']}  TCP 尚未建连，将在建连时应用；当前没有 Socket 回读值。")
        print('[读法] DSCP 0 为默认值；DSCP 46 对应 TOS 0xb8。')

if __name__=='__main__':
    try: main()
    except (OSError,ValueError,KeyError,RuntimeError) as error: raise SystemExit(str(error))
