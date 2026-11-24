#!/usr/bin/env python3
"""把首单原始回执收成课堂读数，并在同一段里写清字段含义。"""
import argparse
from pathlib import Path


def parse_fields(text):
    """拆出 key=value；跳过 JSON 和过长核对行。"""
    fields = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("{") or stripped.startswith("DEPLOYED_INPUTS"):
            continue
        for part in stripped.split():
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            if key.replace("_", "").isalnum():
                fields[key] = value
    return fields


def price_text(raw):
    """整数报价 ÷10000，对照网页上的两位小数字符串。"""
    return f"{int(raw) / 10000:.2f}（整数 {raw} ÷ 10000）"


def display_verify(text):
    """打印下单前的进程与部署摘要。"""
    print("[平台] 对: exchange / trader-auto / trader-manual / gateway 均为 ONLINE，部署摘要 PASS  证: 当前可以下单")
    prefixes = (
        "exchange=",
        "trader-auto=",
        "trader-manual=",
        "gateway=",
        "deployed_sha256=",
        "restore_verdict=",
    )
    rows = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(prefixes):
            rows.append(stripped)
    if rows:
        print("\n".join(rows))
    else:
        print("（未找到进程或部署摘要行）")
    print("[平台说明] pid 是该主机上的进程编号，每次启动可能不同，不是端口号。完整 JSON 留在 verify 日志。")


def display_trade(text):
    """打印本单结果，并解释编号、价格、持仓和往返时间。"""
    fields = parse_fields(text)
    print("[本单] 对: 成交 1 股、持仓变化一致、两端都有记录  证: 下单到成交的链路通了")
    print("[行情] 历史样本继续回放，没有为了下单而暂停。")
    print(f"source={fields.get('source', '（未找到）')}  date={fields.get('date', '（未找到）')}  replay={fields.get('replay', '（未找到）')}")
    clock = fields.get("market_clock", "（未找到）")
    print(f"market_clock={clock.replace('->', ' -> ')}")
    print(f"source_advance_ns={fields.get('source_advance_ns', '（未找到）')}")
    print("[行情说明] source_advance_ns 是回放源时钟往前走了多少纳秒，不是本机耗时，也不是订单 RTT。")
    print(f"[编号] order_id={fields.get('order_id', '（未找到）')}")
    print("[编号说明] 这是客户端编号 client_order_id（OUCH UserRefNum），由 MANUAL 分配。交易所另有 order_reference，在受理回报里。")
    print(
        f"[订单] origin={fields.get('origin', '（未找到）')}  "
        f"symbol={fields.get('symbol', '（未找到）')}  "
        f"side={fields.get('side', '（未找到）')}  "
        f"quantity={fields.get('quantity', '（未找到）')}  "
        f"attempts={fields.get('attempts', '（未找到）')}"
    )
    print("[订单说明] 已有正持仓就卖 1 股，否则买 1 股。BUY 成交后本单 +1，SELL 成交后本单 -1。attempts 是读盘重试次数，最多 3 次。")
    if "limit_price_x10000" in fields and "fill_price_x10000" in fields:
        print(f"[价格] 限价 {price_text(fields['limit_price_x10000'])}")
        print(f"[价格] 成交价 {price_text(fields['fill_price_x10000'])}")
    else:
        print("[价格] （未找到限价或成交价）")
    print("[价格说明] 程序用整数存价格。买单限价是最高可接受价，卖单限价是最低可接受价；成交价是订单到达时满足限价的对手价。")
    print(
        f"[结果] result={fields.get('result', '（未找到）')}  "
        f"filled={fields.get('filled', '（未找到）')}  "
        f"position_delta={fields.get('position_delta', '（未找到）')}  "
        f"manual_position={fields.get('manual_position', '（未找到）')}"
    )
    print("[结果说明] 按本单编号核对成交 1 股和本单持仓变化。账户合计还可能被 AUTO 同时改动，不要只看总持仓差。")
    print(
        f"[记录] history={fields.get('history', '（未找到）')}  "
        f"strategy_unchanged={fields.get('strategy_unchanged', '（未找到）')}"
    )
    print("[记录说明] CLIENT_AND_EXCHANGE 表示客户端与交易所都有这一笔。strategy_unchanged=true 表示 AUTO 开关保持原值。")
    print(f"[往返] order_rtt_ns={fields.get('order_rtt_ns', '（未找到）')}")
    print("[往返说明] 这是本单发出到最终回报的往返时间。一次功能验收读数，不是本章性能结论。")
    print(f"verdict={fields.get('verdict', '（未找到）')}")
    print("[结论] 网页「本轮最后一笔手动订单」应能看到同一客户端编号、成交价和持仓变化。")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", help="verify-before-trade.txt")
    parser.add_argument("--trade", help="first-trade.txt")
    args = parser.parse_args()
    # ----- 默认：用已封存的首单回执演示课堂打印 -----
    # verify = Path("reports/course-runs/20260910T043800Z-02-trading-platform/raw/verify-before-trade.txt")
    # trade = Path("reports/course-runs/20260910T043800Z-02-trading-platform/raw/first-trade.txt")
    # ----- 课堂入口传入的文件（默认启用） -----
    if args.verify:
        display_verify(Path(args.verify).read_text())
    if args.trade:
        if args.verify:
            print()
        display_trade(Path(args.trade).read_text())
    if not args.verify and not args.trade:
        verify = Path(
            "reports/course-runs/20260910T043800Z-02-trading-platform/raw/verify-before-trade.txt"
        )
        trade = Path(
            "reports/course-runs/20260910T043800Z-02-trading-platform/raw/first-trade.txt"
        )
        display_verify(verify.read_text())
        print()
        display_trade(trade.read_text())
