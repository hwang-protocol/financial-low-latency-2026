# 绿卡现象核对 · 20260908T025322Z-00-10-green-replay

对照正文绿卡「预期」与当次 stdout。56/56 课堂 Bash 卡 exit 0。第04运行 ③ Grafana 浏览器按用户要求未用浏览器工具验收；第10「命令(模拟)」未执行。

## 第00章

- 运行 ①：`page_size=4096`，`touched_pages=128`，`minor_fault_delta=128`。同量级且相等。

## 第01章

- 准备 A：四机 jammy/amd64 系统检查通过；`.101` `g++-11` / `make` / `python3`。
- 准备 B：课程 `ssh-ed25519` 公钥已写入 EOS admin。
- 准备 C：VLAN20 `20.1.1.254/24`；Et1/Et2 `forwarding` 10G。
- 运行 ①：`.1` `10.1.1.1` / `20.1.1.1`；`.2` `10.1.1.2` / `20.1.1.2`。
- 运行 ②：两端 `1924:0b03` X2522。
- 运行 ③：driver `sfc`。
- 运行 ④：Et1/Et2 `connected / VLAN 20 / 10G`。
- 运行 ⑤：ping `3/3`；tcpdump 三条 `.1 → .2` echo request。

## 第02章

- 准备 A：两端 `Onload 9f330e7` 与 Kernel module 一致；`/dev/onload`、`/dev/sfc_char`；仍由 `sfc` 管卡；数据口地址保留。约 238 秒冷装。
- 准备 B：IOMMU 组仅 `0000:03:00.0`；`enable_unsafe_noiommu_mode=N`。
- 运行 ①：平台 `20260908T025930Z-02-trading-platform`，`TRADING_LAB_READY`，`platform=READY`，SOFTWARE，Socket/Onload/TCPDirect/DPDK/FeedGuardian。
- 运行 ②：`FIRST_TRADE_PASS`，AAPL BUY 1 股 `ORDER_EXECUTED`。

## 第03章

- 运行 ①：`LIVE_MARKET_FLOW_PASS`，ITCH Add Order（含 NVDA Type A）。
- 运行 ②：`THREE_TRANSPORT_MODES_PASS`，单播/组播/双路各 120 包。
- 运行 ③：Soup `U` + OUCH Enter Order，AAPL 1 股。

## 第04章

- 准备 A：Prometheus 2.31.2 Ready；Grafana 13.1.0 `database=ok`；`up=1`。
- 运行 ①：20+200 笔，p50=41534 ns，p99=63908 ns。
- 运行 ②：PromQL p99 `0.000063908` s 与 raw 63908 ns 对账。
- 运行 ③：用户自看 Grafana，本轮不验收浏览器画面。

## 第05章

脚本均 exit 0，但运行 ① 自己宣布基线不可用。

- 准备 A：dashboard 拷贝成功。
- 运行 ① `20260908T030243Z-05-deque-cv`：**不能用**（同套 6.66 倍，门限 1.50）。AUTO 8/8 稳。不得当性能基线。
- 运行 ② `030442Z`：**能用**。换格子对比跨 0，说不出谁更快。
- 运行 ③ `030902Z`：**能用**。盯着看更快。
- 运行 ④ `031322Z`：**能用**。独占座位快于挤杂活核。

## 第06章

- 准备 A/B/C：两端 READY；control_assets/builder/RSS/transport_preflight PASS。
- 准备 D：切到 TRANSPORT 比较配置。
- 运行 ①～③：Socket / Onload / TCPDirect 各 `ORDER_EXECUTED`。
- 运行 ④：DPDK `ORDER_EXECUTED`，恢复 `SFC/READY/sfc`（77.14 秒）。
- 运行 ⑤：16/16 格，warmup 1600 + measured 16000 = 17600；send→final P50 Socket 34512 / Onload 20681 / TCPDirect 19812 / DPDK 23969 ns。

## 第07章（本轮改为绿卡运行 ①～⑤）

- 运行 ①：`Current switching mode: cut through`；Et1/Et2 10G VLAN20。
- 运行 ② QoS：A/B 各 120 成交；Q1 p99=2290945 ns，Q5 p99=187470 ns，`12.22×`；Q5 `+240`；恢复后 2/2 真单，startup 未写。
- 运行 ③ LANZ：10k START/END=0/0；25k 40/40；Et2 tc=1；running 已撤。
- 运行 ④ PTP：配对 `40870/40870`；p50/p99=122624/175104 ns；`last_sync=0`，方法验证不是 350 ns。
- 运行 ⑤：SFC/READY；三路 ONLINE；ping 3/3；2/2 成交；AAPL 0→0。

## 第08章

- 准备 A + 运行 ①～④：工具、只读口、action 模型、bounds、BPF 对象。
- 运行 ⑤：one-shot NVDA Type A DROP；GAP 后恢复 HEALTHY；2/2 成交，AAPL 0→0。

## 第09章

- 准备 A/B：p4c 1.2.4.2；BMv2 1.15.0。
- 运行 ①：编译取回。
- ②-1～②-4：120 秒课堂停顿后接续。丢包序号 290 = Feed `next_expected=290`，gap_size=1，API 400；恢复 VLAN20、HEALTHY、两笔成交、AAPL 0→0。

## 第10章

- 准备 A：Verilator/make 可用。
- 运行 ①：六项自测 PASS，策略丢包 0，HEALTHY。
- 运行 ②：消费 `block`，现场暂停。
- 运行 ③：`rtl_drop sequence=209`，gap_size=1，API 400。
- 运行 ④：HEALTHY/OPEN，两笔成交，AAPL 0→0。
- 真卡「命令(模拟)」未执行。
