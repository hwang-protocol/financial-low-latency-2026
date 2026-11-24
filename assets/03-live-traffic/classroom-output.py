#!/usr/bin/env python3
"""Display existing Chapter 03 evidence; never switch modes, capture live, or order."""
import shlex
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / 'assets/03-live-traffic'
HOST = socket.gethostname()
NOTES = {
    'market': 'LIVE_MARKET_FLOW_PASS 是解析器自拼的有限检查汇总，表示本窗口解析及内置检查走通；须核对原始端点、序号与字段，不代表长期无丢包。',
    'transports': 'THREE_TRANSPORT_MODES_PASS 是解析器自拼的有限检查汇总，表示三窗解析及内置检查走通；须核对目的地址、序号重合和应用计数，不代表长期无丢包。',
    'order': 'LIVE_ORDER_FLOW_PASS 是解析器自拼的有限检查汇总，表示所选订单解析及内置检查走通；须核对本单 order_id、O/A/E 和 filled，不代表长期无丢包或所有订单均成功。',
}
MARKERS = {'market': 'LIVE_MARKET_FLOW_PASS', 'transports': 'THREE_TRANSPORT_MODES_PASS', 'order': 'LIVE_ORDER_FLOW_PASS'}


def section(host, phase, title, obj, expected, meaning, command):
    print(f'\n{host} / {phase}\n===== {title} =====\n[{obj}] 对: {expected}  证: {meaning}')
    print('$ ' + command, flush=True)


def command(*args):
    return shlex.join(str(arg) for arg in args)


def native(out, name, count, title, expected, meaning):
    args = ['tcpdump', '-nn', '-t', '-r', str(out / 'raw' / name), '-c', str(count)]
    section(HOST, 'readback', title, '报文', expected, meaning, command(*args))
    # Read only a saved pcap. Display failure must not become a new business gate.
    try:
        result = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        output, status = result.stdout, result.returncode
    except OSError as exc:
        output, status = str(exc) + '\n', 1
    print(output, end='', flush=True)
    (out / 'raw' / (Path(name).stem + '-native.txt')).write_text(output)
    if status:
        print('[展示失败] 原生回读未完成，请检查上方错误；不要用解码汇总代替本项原文。')


def order_message(line):
    """Present decoded OUCH fields; raw decoder output remains in raw/decoded.txt."""
    name, *items = line.split()
    if name not in ('OUCH_O', 'OUCH_A', 'OUCH_E'):
        return None
    fields = dict(item.split('=', 1) for item in items)
    def price(key):
        whole, fraction = divmod(int(fields[key]), 10000)
        return f'{whole}.{fraction:04d}'
    if name == 'OUCH_O':
        side = {'BUY': '买入', 'SELL': '卖出'}[fields['side']]
        return [
            '① O · 下单请求｜MANUAL → Exchange',
            f"  客户端编号 UserRefNum：{fields['user_ref']}",
            f"  股票 Symbol：{fields['symbol']}  方向 Side：{side}  数量 Quantity：{fields['quantity']} 股",
            f"  限价 Price：{price('limit_x10000')}",
            '  含义：申请按上述股票、方向、数量和限价下单。',
        ]
    if name == 'OUCH_A':
        return [
            '② A · 受理回报｜Exchange → MANUAL',
            f"  客户端编号 UserRefNum：{fields['user_ref']}",
            f"  订单引用号 Order Reference Number：{fields['order_ref']}",
            '  含义：订单已受理；这条回报还不能证明成交。',
        ]
    return [
        '③ E · 成交回报｜Exchange → MANUAL',
        f"  客户端编号 UserRefNum：{fields['user_ref']}",
        f"  成交数量 Quantity：{fields['filled']} 股  成交价格 Price：{price('fill_x10000')}",
        f"  成交编号 Match Number：{fields['match']}",
        '  含义：这些股数已按上述价格成交。',
    ]


def display(action, kind, args):
    if action == 'annotate':
        details = False
        for line in sys.stdin:
            if kind == 'order':
                if line.startswith('Frame '):
                    details = True
                if details:
                    continue
                if line.startswith(('OUCH_O ', 'OUCH_A ', 'OUCH_E ')):
                    try:
                        print('\n' + '\n'.join(order_message(line)), flush=True)
                        continue
                    except (KeyError, ValueError) as exc:
                        print('[展示失败] 保留原始解码行：' + str(exc), flush=True)
            print(line, end='', flush=True)
            if 'verdict=' + MARKERS[kind] in line:
                print('[就绪说明] ' + NOTES[kind], flush=True)
        return
    if action == 'verify':
        section(HOST, 'verify', '查基础业务服务', '平台', '第二章基础服务在线', '具备本步抓包前提', command('bash', args[0], 'verify', args[1]))
        return
    if action == 'capture':
        remote = args[0]
        if kind == 'market':
            title, expected = '抓取 200 个组播行情包', '200 packets captured；kernel drops 为 0'
            cmd = command('timeout', '8', 'tcpdump', '-i', 'ens64np1', '-nn', '-s', '0', '-c', '200', '-w', remote, 'udp dst port 31032 and dst host 233.74.125.32')
        elif kind == 'transports':
            title, expected = f'抓取 {args[1]} 窗口的 120 包', '120 packets captured；kernel drops 为 0'
            cmd = command('timeout', '8', 'tcpdump', '-i', 'ens64np1', '-nn', '-s', '0', '-c', '120', '-w', remote, 'udp and src host 20.1.1.1')
        else:
            title, expected = '启动四秒订单抓包', 'TCP 43120 双向业务字节'
            cmd = command('timeout', '-s', 'INT', '4', 'tcpdump', '-i', 'ens64np1', '-nn', '-s', '0', '-U', '-w', remote, 'tcp port 43120')
        section('10.1.1.2', 'capture', title, '抓包', expected, '本窗口的抓包完整性', cmd)
        return
    if action == 'mode':
        api, mode = args
        section(HOST, 'market', '设置行情发送模式', '模式', mode, '仅改变目的地址与副本数量', command('curl', '-fsS', '--max-time', '10', '-X', 'POST', '-H', 'Content-Type: application/json', '-d', '{"market_mode":"' + mode + '"}', api + '/api/market'))
        return
    if action == 'trade':
        section(HOST, 'first-trade', '提交一股 MANUAL IOC', '本单', 'ORDER_EXECUTED、filled=1；记下 order_id', '关联本次成交与报文', command('python3', args[0], '--base-url', args[1]))
        return
    if action == 'capture-result':
        out = Path(args[0])
        section('10.1.1.2', 'capture', '查订单抓包统计', '抓包', '捕获到包、kernel drops 为 0', '本窗口抓取情况', command('cat', out / 'raw/tcpdump.txt'))
        print((out / 'raw/tcpdump.txt').read_text(), end='')
        return
    if action == 'sessions':
        run_dir = Path(args[0])
        cmd = "printf 'auto_pid='; " + command('cat', run_dir / 'trader-auto.pid') + "; printf 'manual_pid='; " + command('cat', run_dir / 'trader-manual.pid') + '; ' + command('ss', '-ntpH', 'state', 'established', '( dport = :43120 )')
        section('10.1.1.2', 'sessions', '下单后查订单连接与进程归属', '连接', 'MANUAL 有到 .1:43120 的已建立连接', '用 MANUAL PID 确认本单连接；AUTO 未下过单时可以尚未连接', cmd)
        return
    if action != 'decode':
        raise ValueError('unknown display action: ' + action)
    out = Path(args[0])
    if kind == 'market':
        native(out, 'live-market.pcap', 3, '查行情包的原始端点', '源 20.1.1.1，目的 233.74.125.32.31032', '组播包到达 Trader 数据口')
        title, expected, meaning = '解码 Mold 与 ITCH 字段', '同一 session 内序号连续，Type A 长度 36', '消息顺序与字段边界'
        cmd = command('python3', TOOLS / 'inspect_market_pcap.py', out / 'raw/live-market.pcap')
    elif kind == 'transports':
        for mode, expected in (
            ('MULTICAST_A', '仅 A 路组播 233.74.125.32:31032'),
            ('MULTICAST_B', '仅 B 路组播 233.74.125.33:31033'),
            ('DUAL', 'A 路 233.74.125.32:31032 与 B 路 233.74.125.33:31033 均有包'),
        ):
            native(out, mode + '.pcap', 2, f'查 {mode} 的原始目的地址', expected, '识别本窗口的交付路径')
        section('10.1.1.2', 'membership', '查行情组的主机订阅', '成员', 'inet 233.74.125.32 与 inet 233.74.125.33；各有一个订阅', '行情接收器已加组', 'ip maddr show dev ens64np1')
        for line in (out / 'raw/membership.txt').read_text().splitlines():
            fields = line.split()
            if fields[:2] in (['inet', '233.74.125.32'], ['inet', '233.74.125.33']):
                print(line)
        title, expected, meaning = '对照三种模式与应用计数', 'DUAL 两端点有包、重合与 duplicate_delta 大于 0、pending/gaps 为 0', '短窗口副本及去重关系'
        flags = ['--duplicates-before', '--duplicates-after', '--membership-users', '--membership-users-b', '--pending', '--gaps']
        values = [item for pair in zip(flags, args[1:]) for item in pair]
        cmd = command('python3', TOOLS / 'inspect_transport_pcaps.py', out / 'raw/MULTICAST_A.pcap', out / 'raw/MULTICAST_B.pcap', out / 'raw/DUAL.pcap', *values)
    else:
        section(HOST, 'first-trade', '查本次提交结果', '本单', 'ORDER_EXECUTED、filled=1；记下 order_id', '与 O/A/E 的 user_ref 对号', command('sed', '-n', '/^order_id=/p; /^result=/p', out / 'raw/first-trade.txt'))
        for line in (out / 'raw/first-trade.txt').read_text().splitlines():
            if line.startswith(('order_id=', 'result=')):
                print(line)
        native(out, 'live-order.pcap', 2, '查订单包的原始端点', 'MANUAL 临时端口与 Exchange 43120 双向通信', '订单沿同一 TCP 连接往返')
        title, expected, meaning = '关联 OUCH 请求与回报', 'O/A/E 的 user_ref 等于本单 order_id，E 的 filled=1', '同一笔订单受理并成交'
        cmd = command('python3', TOOLS / 'inspect_order_pcap.py', out / 'raw/live-order.pcap', out / 'raw/sessions.txt', '--first-trade', out / 'raw/first-trade.txt')
    print('[解码说明] 以下字段由配套解析器读取原始文件生成；统计与 verdict 是程序汇总，不是 tcpdump 原文。')
    section(HOST, 'decode', title, '解码', expected, meaning, cmd)


if __name__ == '__main__':
    # Display errors are explicit but do not change the existing lesson's hard gates.
    try:
        display(sys.argv[1], sys.argv[2], sys.argv[3:])
    except (OSError, ValueError, IndexError) as exc:
        print('[展示失败] ' + str(exc), file=sys.stderr)
