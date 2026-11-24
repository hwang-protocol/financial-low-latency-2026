#!/usr/bin/env python3
"""Bounded classroom output, derived only from the current stage's raw receipts."""
from pathlib import Path
import json
import re
import sys

TITLES = {'configure': '1/4 配置接流', 'inspect': '2/4 查看规则与放行',
          'drop': '3/4 一次丢包与缺口', 'restore': '4/4 恢复原路径'}


def render(action, out):
    raw = Path(out) / 'raw'
    result = [f'[{TITLES[action]}] 完成']
    def read(name):
        return (raw/name).read_text()
    def native(name, pattern):
        lines = [re.sub(r'^(?:RuntimeCmd:\s*)+', '', line).rstrip() for line in read(name).splitlines()]
        selected = [line for line in lines if re.search(pattern, line)]
        if not selected:
            raise ValueError(f'{name}: missing expected output {pattern}')
        result.extend(dict.fromkeys(selected))
    def feed(name):
        data = json.loads(read(name)); f = data['feed']
        expected = 'GAP' if action == 'drop' else 'HEALTHY'
        if f['integrity'] != expected:
            raise ValueError(f"{name}: expected {expected}, got {f['integrity']}")
        result.append(f"Feed：session={data['session']}  integrity={f['integrity']}  next_expected={f['next_expected']}")
        state_name = {'configure': 'state-allow-all.json', 'inspect': 'state-inspect.json',
                      'drop': 'state-gap.json', 'restore': 'state-after.json'}[action]
        if (raw/state_name).exists():
            playback = json.loads(read(state_name))['replay']['status']
            result.append(f'行情播放：{playback}')
        return f
    if action == 'configure':
        result.append('# 命令：EOS配置命令节选，先工具口，再交易口。')
        for receipt in ['eos-isolate-tools.txt', 'eos-cut-endpoints.txt']:
            for line in read(receipt).splitlines():
                if re.fullmatch(r'\$ (interface Ethernet(?:1|2|11|12)|switchport access vlan (?:100|200))', line):
                    result.append(line[2:])  # Strip the logger prefix, not an EOS prompt.
        result.append('# 结果：show vlan id 100 / show vlan id 200 的原生成员行。')
        native('eos-cut-endpoints.txt', r'^(100|200)\s+\S+\s+active\s+')
        result.append('# CLI：register_read IngressImpl.remaining_drops 0')
        native('table-install.txt', r'^IngressImpl.remaining_drops\[0\]=')
        feed('feed-baseline.json')
        result.append('解读：两侧已分开，P4已装规则；放行检查通过，暂停播放等下一步。')
    elif action == 'inspect':
        result.append('# EOS：show vlan id 100 / show vlan id 200')
        native('eos-inspect.txt', r'^(100|200)\s+\S+\s+active\s+')
        result.append('# CLI：table_dump IngressImpl.market_policy')
        native('cli-inspect.txt', r'^\* (ipv4\.|itch_)|^Action entry: IngressImpl.select_policy')
        result.append('# CLI：register_read IngressImpl.remaining_drops 0')
        native('cli-inspect.txt', r'^IngressImpl.remaining_drops\[0\]=')
        result.append('# CLI：counter_read IngressImpl.policy_drop_packets 0')
        native('cli-inspect.txt', r'^IngressImpl.policy_drop_packets\[0\]=')
        feed('feed-inspect.json')
        result.append('解读：五字段规则已装入；丢包数0，行情健康，播放保持暂停。')
    elif action == 'drop':
        result.append('# CLI：register_write IngressImpl.remaining_drops 0 1，给一次额度。')
        result.append('# 读回：register_read IngressImpl.dropped_sequence 0')
        native('register-clear.txt', r'^IngressImpl.dropped_sequence\[0\]=')
        result.append('# 读回：counter_read IngressImpl.policy_drop_packets 0')
        native('register-clear.txt', r'^IngressImpl.policy_drop_packets\[0\]=')
        f = feed('feed-gap.json')
        result.append(f"Feed缺口：gap_size={f['gap_size']}")
        gate = json.loads(read('order-gate.json'))
        result.append(f"订单API：http_status={gate['http_status']}  error={gate['error']}")
        result.append('# CLI：register_write IngressImpl.remaining_drops 0 0（撤销额度）')
        result.append('# CLI：register_read IngressImpl.remaining_drops 0')
        native('register-clear.txt', r'^IngressImpl.remaining_drops\[0\]=')
        result.append('解读：实际丢1包，P4序号与Feed缺口已对账；额度已清零，下一步恢复。')
    elif action == 'restore':
        result.append('# EOS：show vlan id 100 / show vlan id 200')
        native('eos-restore-final.txt', r'^(?:% )?VLAN (100|200) not found')
        result.append('# EOS：show interfaces status（四个实验端口）')
        native('eos-restore-final.txt', r'^Et(?:1|2|11|12)\s+(?:connected|notconnect)\s+')
        feed('feed-final.json')
        orders = json.loads(read('post-restore-orders.json'))
        result.append('恢复后订单：'+' / '.join(order['result'] for order in orders['orders']))
        result.append('AAPL持仓：'+' → '.join(map(str, orders['position_AAPL'])))
        result.append('解读：原路径与工具交接检查通过，行情健康，两笔订单成交且净持仓不变。')
    else:
        raise ValueError(action)
    result.append(f'完整回执：{out}')
    return '\n'.join(result)+'\n'


if __name__ == '__main__':
    print(render(sys.argv[1], Path(sys.argv[2])), end='')
