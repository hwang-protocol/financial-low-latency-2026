#!/usr/bin/env python3
"""Render saved XDP/Feed fields for the classroom; raw records stay unchanged."""
import json
import re
import sys
import unicodedata


def row(label, value):
    width = sum(2 if unicodedata.east_asian_width(c) in 'WF' else 1 for c in label)
    return label + ' ' * max(2, 16 - width) + str(value)


def render_feed(text):
    data = json.loads(text)
    feed = data['feed']
    mode = data['market_mode']
    modes = {'MULTICAST_A': '组播 A', 'MULTICAST': '组播 A',
             'MULTICAST_B': '组播 B', 'DUAL': 'A/B 双路', 'UNICAST': '单播'}
    health = feed['integrity']
    gate = feed['trading_gate']
    lines = [
        '行情关键字段：',
        row('会话', data['session']),
        row('发送方式', f'{modes.get(mode, mode)}（{mode}）'),
        row('接收程序', data['trader_auto']),
        row('行情状态', f'{"正常" if health == "HEALTHY" else "有缺口" if health == "GAP" else health}（{health}）'),
        row('交易闸门', f'{"开放" if gate == "OPEN" else "暂停下单" if gate == "INHIBITED_FEED_GAP" else gate}（{gate}）'),
    ]
    if health == 'GAP':
        lines += [row('序号对照', f'已交付 {feed["last_delivered"]} → 期望 {feed["next_expected"]} → 最早待处理 {feed["first_pending"]}'),
                  row('缺失消息', f'{feed["gap_size"]} 条；等待补齐后处理的消息 {feed["pending"]} 条')]
    else:
        lines.append(row('下一条期望', feed['next_expected']))
    return '\n'.join(lines)+'\n'


def render_proof(text):
    match = re.fullmatch(r'xdp_drop_packets=(\d+) sequence=(\d+) locate=(\d+)\s*', text)
    if not match:
        raise ValueError('invalid XDP drop receipt')
    count, sequence, locate = match.groups()
    return '\n'.join([
        row('实际丢包', count+' 包'),
        row('被丢序号', sequence),
        row('接收端缺失序号', sequence+'（已核对一致）'),
        row('股票编号', locate+'（NVDA）'),
    ])+'\n'


def render_link(text):
    # Keep the original interface and program lines; verbose NIC capabilities stay in raw.
    lines = [line.rstrip() for line in text.splitlines()
             if re.match(r'^\d+: ', line) or re.match(r'^\s*prog/xdp ', line)]
    if not lines:
        raise ValueError('missing interface output')
    return '\n'.join(lines)+'\n'


if __name__ == '__main__':
    try:
        render = {'feed': render_feed, 'proof': render_proof, 'link': render_link}[sys.argv[1]]
        print(render(sys.stdin.read()), end='')
    except (ValueError, KeyError, TypeError, IndexError) as exc:
        sys.exit('输出字段无法解读：'+str(exc))
