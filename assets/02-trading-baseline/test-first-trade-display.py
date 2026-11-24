#!/usr/bin/env python3
"""离线核对首单课堂打印：解释在输出里，JSON 不进终端。"""
import contextlib
import importlib.util
import io
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "assets/02-trading-baseline"
spec = importlib.util.spec_from_file_location("format_first_trade", ASSETS / "format_first_trade.py")
formatter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(formatter)

VERIFY = ROOT / (
    "reports/course-runs/20260910T043800Z-02-trading-platform"
    "/raw/verify-before-trade.txt"
)
TRADE = ROOT / (
    "reports/course-runs/20260910T043800Z-02-trading-platform"
    "/raw/first-trade.txt"
)


class FirstTradeDisplay(unittest.TestCase):
    def test_verify_keeps_each_pid_and_hides_json(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            formatter.display_verify(VERIFY.read_text())
        text = out.getvalue()
        self.assertIn("exchange=ONLINE pid=3532", text)
        self.assertIn("trader-manual=ONLINE pid=21802", text)
        self.assertIn("gateway=ONLINE pid=10046", text)
        self.assertIn("restore_verdict=TRADING_LAB_READY", text)
        self.assertIn("pid 是该主机上的进程编号", text)
        self.assertNotIn('"mode":"SFC"', text)
        self.assertNotIn("ed7a7b1aa05151165316db67c99910715d6c63ab9d5c7635c73c6bd4e9441573", text)

    def test_trade_explains_id_price_and_rtt(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            formatter.display_trade(TRADE.read_text())
        text = out.getvalue()
        self.assertIn("order_id=2100000000", text)
        self.assertIn("客户端编号 client_order_id", text)
        self.assertIn("限价 298.87（整数 2988700 ÷ 10000）", text)
        self.assertIn("成交价 293.87（整数 2938700 ÷ 10000）", text)
        self.assertIn("order_rtt_ns=58117", text)
        self.assertIn("不是本章性能结论", text)
        self.assertIn("verdict=FIRST_TRADE_PASS", text)
        self.assertIn("不要只看总持仓差", text)

    def test_chapter_excerpt_matches_formatter(self):
        chapter = (ROOT / "02-host-native-trading-system-baseline.md").read_text()
        current_raw = ROOT / "reports/course-runs/20260915T073229Z-02-trading-platform/raw"
        verify = io.StringIO()
        trade = io.StringIO()
        with contextlib.redirect_stdout(verify):
            formatter.display_verify((current_raw / "verify-before-trade.txt").read_text())
        with contextlib.redirect_stdout(trade):
            formatter.display_trade((current_raw / "first-trade.txt").read_text())
        self.assertIn(verify.getvalue().strip(), chapter)
        self.assertIn(trade.getvalue().strip(), chapter)


if __name__ == "__main__":
    unittest.main()
