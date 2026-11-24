# FLLE Historical Trading Lab

这是课程后续所有低延时优化共用的“普通 Linux 基线”应用。行情不是随机数，也不是课程自定义 `struct`：Exchange 独立、持续重放 Nasdaq 官方公开的 2026-06-12 TotalView-ITCH 5.0 样例；`.2` 上的 AUTO 与 MANUAL 是两个独立 C++ 客户进程，各自接收行情、维护 AAPL/NVDA 五档订单簿，并各自建立 SoupBinTCP/OUCH 会话。

```text
.1 C++ Replay Exchange                    .2 C++ clients
BinaryFILE → original ITCH → MoldUDP64 ──┬→ AUTO: Feed → L2 → strategy → risk
       │                                 └→ MANUAL: Feed → L2 → manual order
       │                    two independent SoupBinTCP / OUCH 5.0 sessions
       └─ immutable historical book ← paper execution ←───────────────┘

       best-effort management telemetry only
       .1/.2 ─────────→ .101 Python HTTP/SSE ─────────→ browser
```

## 真实性边界

- **真实历史行情**：过滤器只选择 AAPL/NVDA 相关事件，不改写保留下来的 ITCH 字节。原始 6-byte 纳秒时间戳原样进入 C++ 回放和网页历史时钟。
- **真实协议布局**：行情使用 ITCH 5.0 经 MoldUDP64；订单使用 OUCH 5.0 `Enter Order / Accepted / Executed / Rejected` 经 SoupBinTCP 登录和数据包封装。
- **纸面成交**：今天发出的订单不可能改变 2026-06-12 已发生的市场。Exchange 只读取当时订单簿，在独立内存 ledger 中模拟 IOC 成交；无论订单大小，纸面订单都不会反写历史订单簿。AUTO 使用 `AUTO…` ClOrdID 与低段 UserRefNum，MANUAL 使用 `MANU…` ClOrdID 与独立高段 UserRefNum；Gateway 保存当前回放轮次的两类记录，网页按来源各取最近 7 条合并展示，持续 AUTO 流量不会把最后一笔 MANUAL 记录顶掉。
- **课程子集**：实现的是课堂需要的消息与会话子集，不宣称可直接连接 Nasdaq 生产系统，也不提供真实券商、账户或资金。

课堂只回放常规交易时段 `09:30:00–16:00:00`。窗口内严格按原始事件时间推进，不压缩空档；1× 一轮正好 6 小时 30 分，倍速只等比例缩短墙钟时间。部署时先从 09:30 前的真实 ITCH 增量生成开盘订单簿检查点，避免从文件中段硬切造成仍在簿订单丢失。到达 16:00 后切换新的 10-byte MoldUDP64 Session，并清空上一轮的订单、成交、持仓、P&L 与延时样本。

## 性能边界

- BinaryFILE 读取、回放定时、UDP 发布、两份行情接收、ITCH 解码、订单簿、连续序号、策略、风险、OMS、两条 SoupBinTCP/OUCH 会话、纸面撮合和延时打点全部是 C++。
- Python 只承担离线数据过滤和旁路 HTTP/SSE。浏览器或网关停止不会阻塞自动交易链。
- 网页主延时卡显示 AUTO C++ 进程的订单 RTT；每笔手动单在交易记录中显示自己的 MANUAL C++ RTT。两者都由各自进程的 monotonic clock 计算，不包含 Python 和浏览器，也不合并成同一个分布。
- 当前数字是未加速功能基线，不是严格 benchmark。正式 A/B 必须固定 CPU、频率、电源、IRQ、队列、负载、消息率和测量点，并使用独立 RUN。
- 宿主机原生交付，不使用 Docker；系统只使用 C++ 与 Python，不引入 Rust。

## 主机与端口

| 主机 | 角色 | 端口 |
|---|---|---|
| `.1 / 20.1.1.1` | C++ Replay Exchange | MoldUDP64 multicast `239.20.1.20:42120`、unicast `.2:42121`；SoupBinTCP orders `:43120`；management `10.1.1.1:48120` |
| `.2 / 20.1.1.2` | C++ AUTO client + C++ MANUAL client | multicast Feed；unicast `:42121/:42122`；management `:48121/:48122`；两条独立订单会话 |
| `.101 / 10.1.1.101` | Python Observer + 宿主机观测面 | telemetry UDP `:46120`；HTTP/SSE/metrics `:8088`；Prometheus `:9090`；Grafana `:3000` |

浏览器入口：

```text
http://10.1.1.101:8088/
```

Grafana 课堂驾驶舱：

```text
http://10.1.1.101:3000/d/flle-trading-baseline/
```

页面只保留课程需要的行情、所选股票最近360个旁路采样的价格走势、五档盘口、回放进度、手工下单、交易记录、持仓与 C++ 延时基线。走势图和延时基线在桌面端并排，不单独占一整行；它只帮助观察历史价格变化，不进入被测链，也不冒充完整日线或逐条 ITCH 延时图。回放区显示当前百分比、源时间、倍速和预计剩余墙钟时间；可暂停、继续、重新开始或选择 `0.5×–20×`。最近一笔手工单固定显示在下单区，不会被自动订单瞬间顶走；统一交易记录从当前轮次中分别选取最近的手动与自动订单，因此一类高频记录不会把另一类完全挤出页面。

## 数据准备

公开样例源：

```text
https://emi.nasdaq.com/ITCH/Nasdaq%20ITCH/S061226-v50.txt.gz
```

实现按 Nasdaq 原始规格核对：[TotalView-ITCH 5.0](https://www.nasdaqtrader.com/content/technicalsupport/specifications/dataproducts/NQTVITCHSpecification_5.0.pdf)、[MoldUDP64](https://www.nasdaqtrader.com/content/technicalsupport/specifications/dataproducts/moldudp64.pdf)、[OUCH 5.0](https://www.nasdaqtrader.com/content/technicalsupport/specifications/TradingProducts/OUCH5.0.pdf)、[SoupBinTCP](https://www.nasdaqtrader.com/content/technicalsupport/specifications/dataproducts/soupbintcp.pdf) 与 [BinaryFILE](https://www.nasdaqtrader.com/content/technicalsupport/specifications/dataproducts/binaryfile.pdf)。

完整 gzip 很大，只需下载一次。课堂恢复默认从唯一不随 `.1/.2/.11/.101` 快照恢复的 `.111` 管理机读取 `artifacts/blobs/nasdaq/S061226-v50/` 中已验 SHA 的过滤结果，不在课堂重新下载17.9GB源文件。离线过滤器输出仍是 BinaryFILE，保留消息原字节，并生成带哈希、消息计数、首尾时间和 `truncated_input` 状态的 manifest。推荐使用 C++ 快速过滤器：

```bash
make tools
bash tools/prepare_itch_sample_fast.sh \
  /var/tmp/flle-market-data/S061226-v50.txt.gz \
  /var/tmp/flle-market-data/AAPL_NVDA.itch \
  /var/tmp/flle-market-data/AAPL_NVDA.manifest.json \
  build/flle-itch-filter
```

纯 Python 版本用于可移植复核和截断流联调：

```bash
python3 tools/prepare_itch_sample.py \
  --input /var/tmp/flle-market-data/S061226-v50.txt.gz \
  --output /var/tmp/flle-market-data/AAPL_NVDA.itch \
  --manifest /var/tmp/flle-market-data/AAPL_NVDA.manifest.json
```

`--allow-truncated` 仅供下载期间联调；这样的输出必须以 `partial-test` 命名，不得用作正式演示或证据。

## 编译、部署与验证

```bash
make clean test

RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-nasdaq-replay"
scripts/labctl.sh preflight "$RUN_ID"
scripts/labctl.sh deploy "$RUN_ID"
scripts/labctl.sh start "$RUN_ID"
scripts/labctl.sh status "$RUN_ID"
scripts/labctl.sh verify "$RUN_ID"
python3 tests/first_trade.py --base-url http://10.1.1.101:8088
python3 tests/live_smoke.py --base-url http://10.1.1.101:8088
python3 tests/latency_regression.py --base-url http://10.1.1.101:8088
```

`selftest` 冻结 MoldUDP64、ITCH `A/E` 订单簿变化、开盘检查点往返、SoupBinTCP 登录以及 OUCH `O/A/E/J` 的长度与字段。`first_trade.py` 在行情继续播放且不改变自动策略开关的条件下提交一笔手动 IOC，并按订单 ID 核对独立成交结果、持仓增量和统一交易记录。`live_smoke.py` 验证用户主动暂停/继续、倍速、重启清仓、DUAL 重复抑制和一笔 OUCH 纸面成交。`latency_regression.py` 只防止 TCP delayed-ACK/Nagle 尾部故障复发，不替代后续正式 benchmark。

第四章的宿主机观测面由 `scripts/observabilityctl.sh` 恢复。Gateway 的 `/metrics` 只在旁路导出低基数摘要；固定负载使用独立 C++ measurement generation，逐笔 `order_rtt_ns` 通过只读 `MEASUREMENT_SAMPLES` 收据交给 `tests/baseline_measurement.py`，并保存为 raw CSV。普通 GUI 单和 AUTO 单不进入该 generation。Prometheus、Grafana、Python 和浏览器都不进入 `OUCH send → final E/J` 的计时区间。

```bash
bash scripts/observabilityctl.sh install
bash scripts/observabilityctl.sh verify
```

第五章继续使用同一个 MANUAL C++ 进程，不另造队列 benchmark。订单在热路径中记录三个 `CLOCK_MONOTONIC` 时间点：进入线程交接队列、发出 OUCH `O`、收到最终 `E/J`。`tests/software_measurement.py` 用相同的 40 warmup + 400 measured、50 Hz 负载交替复测三种实现：

- `DEQUE_CV`：原始 `std::deque + mutex + condition_variable`；
- `FIXED_CV`：1023 个可用槽位的固定数组 ring，但仍保留 mutex/CV；
- `SPSC_SPIN`：一生产者/一消费者的固定 ring，以 release/acquire 交接并在隔离核上执行 x86 `PAUSE` 真忙轮询。

每个候选重复八轮；成对实验按 `ABBA → BAAB` 配平。MANUAL order thread固定到CPU 2，独立AUTO order thread固定到CPU 3，其余Trader线程限制在CPU 0–1；最后一组保持SPSC不变，只比较隔离CPU 2与共享housekeeping CPU 0。MANUAL每轮以50Hz提交40笔warmup+400笔measured；AUTO以10Hz随行提交8+80笔环境哨兵。行情继续`PLAYING`、原AUTO策略不关闭，两队列都要求无full drop。每个arm合并3200个MANUAL measured，以固定种子做4000次percentile bootstrap，输出queue、order RTT与submit-to-final的p99及差值95%区间。

MANUAL自己的`order_rtt`会被处理影响，因此是第二结果，不是环境控制。裁判读取AUTO半窗漂移、方向性环境等价、相邻配对方向和单profile轮间spread。当前正式RUN把旧DEQUE↔FIXED假阳性收回为`-84 ns`且CI跨0；FIXED到真忙轮询的queue p99为`17210→6847 ns`，submit-to-final净降`8159 ns`；同一个忙轮询与housekeeping共用CPU 0时，正式queue p99为`6780→65319 ns`。共享核六次资格复测完整序列为6/8、7/8、7/8、8/8、8/8、8/8，不隐藏拒绝。V11两份使用`yield()`的同名旧profile虽已隔离CPU角色仍测得SPSC更慢；等待指令必须进入profile身份。这些结论只属于冻结profile，不是生产SLA或普遍倍数。

第五章独立 dashboard：

```text
http://10.1.1.101:3000/d/flle-software-hot-path/
```

工程验收还可运行 `python3 tests/concurrent_trading.py --base-url http://10.1.1.101:8088`：它不暂停行情，在短暂提高自动策略触发率的同时提交手动单，要求统一记录中同时出现 `AUTO_STRATEGY` 与 `MANUAL_GUI`，并核对 Exchange ledger 至少接到两笔订单；结束后恢复原策略配置。这是进程并发回归，不是性能 benchmark。

结束时只停止对应 RUN：

```bash
scripts/labctl.sh stop "$RUN_ID"
```

默认 `DISPLAY` 档会发送非阻塞旁路遥测。正式性能 A/B 使用独立 RUN，并设置 `FLLE_TELEMETRY_HOST=off`；该档不提供实时网页状态，两档结果不能混成一个分布。

## 当前未完成的生产能力

内存 ledger 不跨 Exchange 进程重启；没有完整 SoupBinTCP 恢复、Nasdaq 生产认证、持久化对账、行情重传服务或真实券商连接。HTTP 管理面也没有生产级认证，只能放在隔离课程管理网。这些边界必须与“协议消息确实在线路上跑过”同时说明。
