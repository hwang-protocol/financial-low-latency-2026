#!/usr/bin/env python3
"""Show selected fields; full upstream output is retained by tee before this filter."""
import json
import sys


def render(kind, text):
    if kind == 'selftest':
        lines = [line for line in text.splitlines() if line.startswith('rtl_selftest=')]
        if len(lines) != 1:
            raise ValueError('missing or repeated selftest result; see raw/build-and-selftest.txt')
        return lines[0] + '\n'
    data = json.loads(text)
    if kind == 'feed':
        feed = data['feed']
        return (f"Feed：session={data['session']}  integrity={feed['integrity']}  "
                f"next_expected={feed['next_expected']}  gap_size={feed['gap_size']}\n"
                f"路径：Exchange={data['market_mode']}  Guardian={feed['path']}  "
                f"交易闸门={feed['trading_gate']}\n")
    if kind == 'gate':
        return f"订单API：http_status={data['http_status']}  error={data['error']}\n"
    if kind == 'gui':
        return (f"界面检查：result={data['result']}  Feed={data['live_feed_integrity']}\n"
                f"红条DOM={data['banner_dom']}  灰簿CSS={data['book_gray_css']}\n"
                f"下单按钮禁用：manual={data['manual_order_disabled']}  "
                f"transport={data['transport_orders_disabled']}\n")
    if kind == 'orders':
        feed = data['feed']
        return (f"恢复后Feed：session={feed['session']}  integrity={feed['integrity']}  "
                f"交易闸门={feed['trading_gate']}\n"
                '恢复后订单：' + ' / '.join(order['result'] for order in data['orders']) + '\n'
                'AAPL持仓：' + ' → '.join(map(str, data['position_AAPL'])) + '\n')
    raise ValueError(f'unknown output kind: {kind}')


if __name__ == '__main__':
    try:
        print(render(sys.argv[1], sys.stdin.read()), end='')
    except (ValueError, KeyError, TypeError) as exc:
        sys.exit(f'课堂字段提取失败：{exc}；完整原文见本次 raw/。')
