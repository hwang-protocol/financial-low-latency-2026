# GUI 全量重置验证 — 20260905T073501Z-gui-full-reset

2026-09-05，用户授权清空整个纸面交易 GUI。部署当前 Gateway/UI、Controller 与 LANZ Collector；保留原第06运行时二进制和 NIC 模式。

- 初始持仓：{"trader_auto": {"AAPL": 0, "NVDA": 0}, "trader_manual": {"AAPL": 200, "NVDA": 10}, "trader_onload": {"AAPL": 20, "NVDA": 0}, "trader_tcpdirect": {"AAPL": 20, "NVDA": 0}, "trader_dpdk": {"AAPL": 0, "NVDA": 0}}。
- 实机 Socket、OpenOnload、TCPDirect 各发送 AAPL BUY 1，三个管理响应均 ok；再通过 GUI 使用的 `/api/replay` 与 `clear_trades=true` 重置。
- 最终 Session：`0612260103`；三路 orders/fills/positions/latency samples、Exchange ledger 均零，LANZ events/counts 均零。新行情指标从新 Session 继续累计。
- 164 项 Python 测试通过；shell 语法与 git diff --check 通过。历史打印检查13脚本68块通过。课程卡片检查被既有引用 `08-xdp-modes-and-skb.svg` 缺失阻断，本轮没有编造或替换图片；该问题不影响交易重置。
- DPDK 重置分支、非 transport-lab profile 未实机验证；没有将 SFC 成功扩写为这些分支成功。
- 实机采样与重置之间用户可能继续下单：after-first.json 中 Socket 的新 10 股不代表旧 200 股回填；最终即时验收使用 after-final.json。
- 待提交：应用服务/GUI/控制脚本、LANZ collector、两份应用回归测试与治理文件；之前第08～10章打印与重复执行修改保留。
- 建议提交信息：`fix: reset all GUI paper trading and LANZ history`。未执行 commit/push/tag。
