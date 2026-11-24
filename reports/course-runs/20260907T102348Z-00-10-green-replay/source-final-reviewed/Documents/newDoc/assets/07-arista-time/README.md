# 第07章本地配套资产

本目录把“当前只读取证”“在线交易主实验”“可选精确维护窗”“历史备用证据”“课后模型”分开。学生绿色卡只使用正文明确列出的只读 / 准备脚本；会改 running-config、主机临时规则或占用 `.11` 的脚本只允许教师执行。口令不进入本目录。

第七章默认复用第二章部署、经第六章验证的同一交易系统，不调用 stop。三项主入口依次为 `11-qos-real-order-contention-live.sh`、`04b-lanz-stream-ab.sh`、`12-stamped-span-live.sh`。只有为隔离 PTP Transparent Clock 自变量而选择 `09-ptp-tc-live-ab.sh` 时，才进入停机维护窗；无论是否停过，章末都运行 `13-trading-online-final.sh`：仅在当前为 DPDK 时 handoff，再复用或恢复第二章固定平台，并以两笔风险感知、净持仓不变的 Socket/SoupBinTCP/OUCH 真单交还在线。

| 文件 | 性质 | 用途 |
| --- | --- | --- |
| `01-arista-fabric-inventory.sh` | 当前只读 | 读取 7150 / Et1 / Et2 / cut-through 工作方式 |
| `02-serialization-time.sh` | 课后模型 | 复算帧长与 10GbE 可见帧序列化时间 |
| `03-queue-fanin-model.sh` | 课后模型 | 复算短窗 fan-in 积压，不冒充 ASIC 实测 |
| `04-lanz-live-ab.sh` | 历史停机现场 | 旧的 1514B×4096 LANZ No-event / Event `show` A/B；新课堂不再以它为主入口 |
| `04b-lanz-stream-ab.sh` / `lanz_stream_collector.py` | 在线主实验二 | 保持当前交易 RUN 与三路客户端在线，以发往隔离测试 MAC 的 MoldUDP64/ITCH 受控负载打开 streaming，把 S/E 推到 `.101:8089` 并在 8088 最下方显示；结束后恢复实验前网页发布资产 |
| `04-lanz-verified-evidence.sh` / `lanz-native-20260820.txt` | 历史备用证据 | 无维护窗时审计旧 LANZ No-event / Event 原文，不代替 fresh live |
| `05-hardware-timestamp-capability.sh` | 当前只读 | 读取两端 X2522 hardware timestamp / PHC capability |
| `05b-linuxptp-tooling-prep.sh` | 基础准备 | 安装 `linuxptp` 工具，不启动同步 |
| `06-phc-readonly.sh` | 当前只读 | 先拒绝仍有 PTP 同步进程的现场，再确认 PHC 节点与纳秒读数；年份不是门闸，先前 PTP 校时也不会在退出时回滚 |
| `07-ptp-message-state.sh` / `ptp_message_model.py` | 历史模型 | 旧四报文字符串模型，正文已由机制图接管 |
| `08-ptp-tc-verified-evidence.sh` / `ptp-tc-native-20260820.txt` / `ptp-tc-client-20260820.pcap` | 历史备用证据 | 无维护窗时审计旧 EOS / ptp4l / pcap 三层收据 |
| `09-ptp-tc-live-ab.sh` | 可选精确维护窗 | 正常停止 Exchange 与 Trader 后，在原 `.1 ↔ 7150 ↔ .2` 物理路径运行 TC OFF / ON；以 Onload 实际内容、HugePages 与两侧 `flle-(trader|exchange)` 进程拦截在线或半停机交易；通过门后所有远端 / EOS 写入均先 arm cleanup，成功恢复后才 disarm；章末卡负责恢复交易 |
| `09-ptp-tc-pcap-ab.sh` | 历史备用实验 | 无维护窗时对 2026-07-21 TC OFF / ON 固定真包做全量 A/B 解码 |
| `10-qos-real-order-live.sh` | 在线快速映射 | 保持第06章当前交易系统运行，只给当前 Kernel Socket 订单连接临时打 DSCP 46；无争用地验证 pcap、DSCP→TC5→显式 strict Q5 与真实成交后恢复 |
| `11-qos-real-order-contention-live.sh` | 在线主实验一 | 保持当前交易系统在线，以 `.11` 发往隔离测试 MAC 的 MoldUDP64/ITCH 受控负载和真实 SoupBinTCP/OUCH 订单争用同一个 Et1；比较未标记 Q1 与 DSCP46 / strict Q5 的队列计数、LANZ 和订单 p99，最后完整恢复 |
| `11-oneway-latency-live.sh` / `live-support/oneway/` | 历史旁支 | 同卡两端硬件戳对照；`.1/.2` 共享 X2522 时基，不能用它证明两只独立钟经 PTP 对表，也不进入三项主实验 |
| `12-stamped-span-live.sh` | 在线主实验三 | 保持当前交易系统在线，7150 做本地 PTP 时间源，`.2` PHC 跟随；Et1 rx 镜像到 Et11 并只在副本打入口戳，与 `.2` 硬件 RX 按真实行情配对 |
| `13-trading-online-final.sh` | 章末必做 | DPDK 时才交还 SFC；复用或恢复第二章平台，并按当前持仓方向执行两笔净零真实订单，验收页面、客户端、数据链和业务闭环 |
| `PTP-AB-SHA256SUMS` / `ptp-*-client-20260721.pcap` | 固定备用输入 | 锁定旧 A/B pcap 身份；原始来源为 `20260721T024157Z-x2522-ptp-hwts-smoke` |
| `live-support/` / `LIVE-SUPPORT-SHA256SUMS` | tracked 运行依赖 | 保存教师卡所需的脚本、解析器与配置；入口在外部动作前逐项验 SHA，并把清单副本与清单 SHA 写入新 RUN |

2026-09-03 三项在线主证据为：QoS RUN `20260903T095143Z-07-qos-contention-live`（根清单 `c86a2cad…04e58d`）、LANZ streaming RUN `20260903T100334Z-07-lanz-stream-ab`（根清单 `8c654aed…c1c2d9`）和带戳真行情 RUN `20260903T085652Z-07-stamped-span-live`（根清单 `4cd1e17d…0c0f94d`）。QoS 两档各 120 笔真实 SoupBinTCP/OUCH 订单，未标记 Q1 p99 `2,333,197 ns`，DSCP46→TC5→strict Q5 p99 `190,867 ns`，B 档 240 个方向受限订单帧与 Q5 `+240` 对账。LANZ 以隔离 MoldUDP64/ITCH 负载得到 `10k=0`、25k 接收窗口 START/END=`40/40`，同轮 EOS 本地统计 `Et2 / TC1 / 160`；两个观察窗口相互印证，但不冒充精确计数相等。退出后 `.101` 的第六章 `source.sha256` 重新通过。PTP 内部窗为 `15505/15505`，p50 `56832 ns`。章末 RUN `20260903T100854Z-07-trading-online-final` 以两笔真实订单把 AAPL 持仓保持在 `200`，根清单 `3b770219…f2d60f`，并封存执行脚本。同配方复现审计 `102049Z / 102234Z / 102356Z` 再次得到 QoS `13.50×`、LANZ `0/0 → 40/40` 和真行情 `6870/6870`；它们证明方向可复现，不替换前三份权威原件。旧不透明二层背景流 RUN `083310Z` / `072638Z`、旧 LANZ `show` RUN `060803Z` 与可选 PTP/TC RUN `061536Z` 只保留为历史 / 精确对照，不再定义默认课堂顺序。

运行时唯一允许写入 `Documents/reports/course-runs/` 的是新证据；任何源码、配置或解析器都必须来自 tracked assets / app 源码。换言之，即使快照恢复后本地没有任何历史 `Documents/reports/` 内容，LANZ、PTP、QoS 与带戳副本教师卡的代码依赖仍然完整；QoS / 带戳副本卡按设计依赖教师先拉起第06章当前交易 RUN，但不读取任何历史 raw 作为输入。`Documents/reports/` 按项目决策受 `.gitignore` 管理：PINS / DECISIONS / FREEZE 只保存耐久摘要、口径和根 SHA，不能替代原始文件；根 SHA 只有在本机 RUN 仍存在时才能复算，clean snapshot 或新机器上的发布验收必须重新运行相应卡，不能声称从 Git 恢复了历史 raw。

`09-ptp-tc-pcap-ab.sh` 保留为无维护窗时的快速后备：它不启动 `ptp4l`、不登录 7150、也不改变网卡，只验签并扫描两份固定 pcap。旧原件 baseline `42+38=80` 条全零、TC `66+66=132` 条全非零；这只是历史复算，不得写成当堂重新抓包。
