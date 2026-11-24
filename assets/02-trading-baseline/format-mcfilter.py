#!/usr/bin/env python3
"""Display Linux mcfilter source counters; use ifindex, not truncated Device."""
from ipaddress import IPv4Address
from pathlib import Path
import sys


def display(text, ifindex, interface):
    rows = []
    for line in text.splitlines():
        columns = line.split()
        if not columns or columns[0] == 'Idx':
            continue
        if len(columns) != 6:
            raise ValueError('mcfilter 行格式不完整，检查原始输出。')
        index, _device, group, source, include, exclude = columns
        if int(index) != ifindex:
            continue
        # igmp_mcf_seq_show prints ntohl(address), independent of host byte order.
        group, source = (str(IPv4Address(int(value, 16))) for value in (group, source))
        rows.append(f'{interface} (Idx={ifindex})  源 {source} → 组 {group}  INC={int(include)} EXC={int(exclude)}')
    if rows:
        print('\n'.join(rows))
    else:
        print(f'[未读到] {interface} 没有源过滤记录，请核对接收器版本与订阅。')


if __name__ == '__main__':
    try:
        display(Path(sys.argv[1]).read_text(), int(Path(sys.argv[2]).read_text()), sys.argv[3])
    except (OSError, ValueError, IndexError) as error:
        raise SystemExit(str(error))
