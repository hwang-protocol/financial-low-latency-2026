# 课程顺稿配套说明（教师）

## 2026-09-07 本轮统一平台与完整顺刷

第二章112313Z统一平台已接续完成03～10；总RUN102348Z含57个Bash课堂块、49份摘要核验和8个浏览器画面。第09/10四步最终现场均通过，暂停后可继续；当前三路下单、行情与网口已恢复。450包/九组依赖在`.111`课前备齐，第一章检查后本地分发。下面各章早期批次与待验证记录保留历史身份，当前覆盖范围以[最终报告](../design/FLLE_Unified_Trading_Platform_2026-09-07.md)为准：修复及补验通过，尚未再次恢复后以最终工作树零修改复刷。

## 全课准备和交接顺序

| 时点 | 先具备什么 | 本步做什么 | 交给后面什么 |
| --- | --- | --- | --- |
| 课前 `.111` | 固定源码、版本和快照内核 | 备齐大包及依赖，校验清单 | 后续安装不依赖公网 |
| 第01章 | 四机管理 SSH、预热快照、干净交换机 | 检查缓存、补基础工具、接通数据网 | 可辨认的网卡和可用交易链路 |
| 第02章 | Builder、Onload/IOMMU 条件 | 一次部署完整平台并成交 | 同一个平台 RUN、固定应用和三条可下单路径 |
| 第03～05章 | 同一平台正常交易 | 读报文、观测、比较线程配置 | 测量证据与恢复后的普通配置 |
| 第06章 | 已部署的完整客户端集合 | 切比较配置、四路测量、交还网卡 | sfc 管卡、三路在线、管理与数据网可用 |
| 第07章 | 交易在线、工具口空闲 | 队列/时间实验，结束撤回临时配置 | 原 VLAN 与可用行情交易 |
| 第08～10章 | 前一步过滤器已退出、行情正常 | 每次接入一种过滤路径，丢一次并恢复 | 无前一过滤器残留、行情健康、验证订单成交 |

实验失败先看本次回执和恢复状态，不能越过交接门直接贴下一章。章节脚本按保存的第二章平台身份工作；各实验目录保存自己的证据，不重新部署交易系统。

## 课前备包与课堂等待

大包和完整依赖放保留的 `.111`。上课前执行 `python3 artifacts/tools/check-course-package-cache.py`，确认 450 个包的 SHA 全部通过；第一章准备 A 也检查。现役准备入口从本机缓存分发，不在线更新索引或临时补下载。内核工具仅覆盖 Ubuntu 22.04 amd64 / 5.15.0-164-generic；换快照内核应课前重新备包验证。

P4 编译端、BMv2 运行端本轮离线首装分别约 50 秒、23 秒。这些是当前管理网读数；已安装时只检查版本。行情样本、TRex 和交易运行包继续由本地 vault 提供。正式性能比较仍需要完整采样时间，不能用缩短样本来换取“刷得快”。缓存位置、包组和课前维护工具见仓库 `artifacts/README.md`。


本文件保留从学生正文移出的构建、维护与取证细节。下列历史记录不是本轮重新运行的结果；现役事实和验证等级仍以 PINS / FREEZE-LEDGER 为准。

## 第 03 章

<div style="border-left:6px solid #7e22ce;background:#f3e8ff;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#7e22ce;color:#fff;font-weight:800;">事故钩子</span> <span style="font-weight:700;color:#581c87;">只知道“UDP 快、TCP 可靠”不足以维护低延迟交易系统：如果不知道 Mold 的 sequence 属于哪次 session、双路为何产生重复副本、Accepted 与 Executed 为什么不能合并，后面即使换成 XDP、Onload 或 DPDK，也只是更快地处理错误状态。</span></div>

<div style="border-left:6px solid #7e22ce;background:#f3e8ff;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#7e22ce;color:#fff;font-weight:800;">本章证据边界</span> <span style="font-weight:700;color:#581c87;">三张卡使用第二部分当前 RUN `20260829T023952Z-02-trading-baseline` 的在线进程与 2026-06-12 AAPL/NVDA 历史字节。运行 ① 已按该基线重取；运行 ②③ 仍待沿同一基线重跑。本章证据证明当前应用在这些抓取窗口内的报文、端点和状态关系；不证明生产 Nasdaq 兼容、丢包率、吞吐上限或哪种模式延迟最低。</span></div>

| 路径 | 方向与端点 | 当前业务语义 | 应用必须补的责任 |
| --- | --- | --- | --- |
| 行情 | `.1 → .2`，UDP 单播、组播或双路 | 一串 ITCH 订单簿事件 | session 切换、sequence 连续交付、pending、duplicate 与缺口恢复入口 |
| AUTO 订单 | `.2 → .1:43120 → .2`，独立 TCP 长连接 | 自动策略产生的 OUCH 请求与回报 | 独立 ID 空间、在途风控、状态关联与账本 |
| MANUAL 订单 | `.2 → .1:43120 → .2`，另一条 TCP 长连接 | 网页意图转成的 OUCH 请求与回报 | 与 AUTO 并行；按本单 ID 判断结果 |

本章用的是标准协议的**可核实课堂范围**：ITCH 保留官方样例原字节，MoldUDP64 使用公开的 20 字节头与消息长度列表，OUCH 使用 `O/A/E/J` 布局，SoupBinTCP 使用登录与 `U/S` framing。生产连接还有认证、心跳、重传服务、更多消息类型与运营控制，本应用没有实现。

## 第 04 章

<div style="border-left:6px solid #7e22ce;background:#f3e8ff;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#7e22ce;color:#fff;font-weight:800;">本章证据边界</span> <span style="font-weight:700;color:#581c87;">进入延迟比较的时间戳仍由 C++ 读取；Python、Prometheus、Grafana 均在测量区间之外。本章建立普通 Linux 的可复算基线，不把 200 个样本外推成生产 SLA。准备 A、运行 ①② 样例来自干净快照 RUN `20260829T103653Z` / `103858Z` / `104032Z`；C++ / raw / Prom p99 同为 `69414 ns`。运行 ③ 以 2026-08-29 18:40 驾驶舱截图为准。</span></div>

验证等级以 FREEZE-LEDGER 为准；本轮只润色教材，没有重新运行四张操作卡。

## 第 05 章

现场是怎么一步步稳下来的，也要说清楚：早先的机器上，同一套交棒跨 RUN 曾经差到 `3.29×`；把这台虚拟机的延迟敏感度设成 High、CPU 全预留之后，AUTO 这把环境尺子才稳住；再把其余线程移出 CPU 2，开发基线的跨 RUN 波动降到 `1.20×`，正式前三次复测是 `1.14×`。功劳属于**这一整套组合**，不能单独记在某一个 ESXi 开关上——虚拟机内部的线程隔离同样参与了最后的收口。

当前仍是 `CURRENT-STATE PASS / CLEAN SNAPSHOT PENDING`。只有从第一部分开始零修改顺刷 01→05 后，才能把本章提升为 `FROZEN`。

## 第 06 章

v12 包封存三种 Trader、F-Stack、DPDK、TCPDirect 和运行库；课堂不会现场联网编译这些客户端。独立的 source、build-inputs 与 provenance 归档把源码、构建输入、命令和实际 ELF 连起来。按当前 Git 恢复合同，这四项加上准备 A 的 Onload 源码共 5 个固定文件都进入精确白名单；管理机即使恢复，也能从私有 Git checkout 后先验 5/5 SHA，再直接分发运行包。准备 A 仍可能为当前 Guest 内核编译 Onload 模块，这与应用运行包是两件事。

<div style="border-left:6px solid #7e22ce;background:#f3e8ff;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#7e22ce;color:#fff;font-weight:800;">目录卡 · 源码、编译记录、ELF 和部署路径</span> <span style="font-weight:700;color:#581c87;">平时改 `apps/`；重建时读 source / build-inputs / provenance；上课只验签并分发 runtime。</span></div>

| 阶段 | 当前项目中的固定位置 | 它保存什么、什么时候使用 |
| --- | --- | --- |
| 日常开发源码 | `apps/flle-trading-lab/Makefile` 与 `apps/flle-trading-lab/src/` | Git 跟踪的 C/C++ 真源；需要改业务或 Transport 时改这里 |
| 封存源码 | `artifacts/blobs/x2522/ch06-four-path/v12/flle-ch06-four-path-v12-source.tgz` | 本次构建对应的 17 文件不可变快照；用于审计“当时到底编了什么” |
| 固定构建输入 | `artifacts/blobs/x2522/ch06-four-path/v5/flle-ch06-four-path-v5-build-inputs-x86_64-jammy.tgz` | 实际消费的 TCPDirect / F-Stack 头文件与静态库；需要复现应用 ELF 时使用 |
| 编译说明书 | `artifacts/blobs/x2522/ch06-four-path/v12/BUILD-PROVENANCE.json` | Ubuntu、编译器、flags、命令、输入 SHA 与 6 个输出 ELF SHA 的对应关系 |
| 编译后运行包 | `artifacts/blobs/x2522/ch06-four-path/v12/flle-ch06-four-path-v12-x86_64-jammy-runtime.tgz` | 课堂真正复制的固定包；含 `bin/`、F-Stack 配置、运行库、工具与内部 manifest |
| 部署后目录 | `.1/.2:/var/tmp/flle-trading-lab-&lt;RUN_ID&gt;/transport-runtime/flle-ch06-four-path/` | controller 验 SHA 后解包；`.1` 从 `bin/` 启动 Exchange，`.2` 从同一 `bin/` 启动 Trader |

<div style="border-left:6px solid #d97706;background:#fffbeb;padding:14px 16px;border-radius:8px;margin:14px 0;color:#78350f;"><strong>为什么 DPDK 更底层，单笔 TCP 延迟却不一定更低？</strong><p style="margin:10px 0 0;"><strong>已确认：DPDK 确实使用了 X2522。</strong>本轮已取证 VFIO / IOMMU type 1、<code>net_sfc_efx</code> PMD、ULL firmware 与端口 RX/TX 增长，没有落回普通虚拟网卡。</p><p style="margin:8px 0 0;"><strong>当前路径：<code>OUCH → F-Stack TCP → DPDK PMD → X2522</code>。</strong>测的不是“裸 DPDK 发一个以太网帧”。DPDK 提供高速包处理底座，不提供完整 TCP；为保持与前三路相同的 SoupBinTCP/OUCH 业务，本实现必须叠加 F-Stack 的 TCP、<code>ff_*</code> 接口和 reactor。而 Onload 与 TCPDirect 本来就是针对 Solarflare/X2522 优化的低延迟 TCP 路径，并有 CTPIO / VI 活路径收据。</p><p style="margin:8px 0 0;"><strong>边界：二层或 UDP 可能更短，但已不是同一 TCP 业务。</strong>减少栈层次后本机处理时间可能更低，可靠传输、顺序、重传、会话与 SoupBinTCP 登录语义也随之改变，不能与本表混排；若自行实现同等 TCP 语义并做 run-to-completion 优化，需要另开实验重新测量。本 RUN 只能说明当前 F-Stack TCP 实现相对 Onload / TCPDirect 慢约数微秒，不代表 DPDK 的性能上限；现有计时没有把 F-Stack、PMD 和 NIC 分段，不能把差值唯一归给某一层。</p></div>

### 证据封存与复现边界

| 对象 | 章末状态 |
|---|---|
| `.2` X2522 | PCI owner 为 `sfc`；`ens64np1` 与 `20.1.1.2/24` 在；SFC 控制台按合同保留 128×2 MiB 大页 |
| `.1` X2522 | 保持 `sfc` 与 `20.1.1.1/24`；四路在线测量的 RSS / IRQ 合同继续由当前 RUN 持有 |
| 四路进程 | Exchange、Socket、Onload、TCPDirect、Gateway 与控制器在线；DPDK Trader 未启动并显示 WAITING |
| 网页交接 | `http://10.1.1.101:8088/` 为 HTTP 200；可继续前三路下单，也可重新切换 DPDK |
| 固定产物 | v12 source=`4e79723b…6903e`、provenance=`796c83ef…37b1`、runtime=`163618cc…c9f3`；build-inputs 继承 v5 `6caa8e25…f451` |
| 当前状态完整证据 | `Documents/reports/course-runs/20260903T004905Z-06-four-path-orders/`；准备 D、四张单笔、Williams 比较、GUI 交接收据及各层 SHA 齐全，目录受 gitignore 保护 |
| 正式发布复现基线 | DEC-191 的 `20260902T020809Z-06-four-path-orders` 与 `20260902T021948Z-06-four-path-orders`；两份都闭合 16 格、17,600 笔和首次现场交还。旧 RUN 未同时固定 Exchange RSS/IRQ 与 irqbalance，只作问题定位历史 |

这份 RUN 是已经完成准备的 current-state 实机验收；它不冒充“四机 clean snapshot 从准备 A 到恢复四路控制台一次顺刷”。发布前最后一道门仍是从课程快照按绿卡全链执行。

第七章可以直接从这个 `SFC/READY/sfc` 现场继续。若教师要完全关机、做快照或重刷前序章节，再单独使用控制器的全停机动作；它不是本章面向学员的默认收尾。

## 第 07 章

### 三项主实验共用一套在线交易基线

第二章已经部署完整平台，第六章已切回 SFC 比较配置。本章沿用第二章的 `RUN_ID` 和现有 Socket 长连接、8088 页面，在实验前、中、后硬验 `SFC / READY / sfc`，让交易全程在线。

| 主实验 | 在线业务怎样参与 | 为了看清现象额外加什么 | 本章主证据 |
| --- | --- | --- | --- |
| 实验一：QoS | 两档各下 120 笔真实 SoupBinTCP/OUCH Socket 订单，全部成交；每档 60 组 `SELL→BUY`，净持仓不变 | Et11+Et12 的受控 MoldUDP64/ITCH 负载争用订单所走的 Et1 出口 | DSCP、TC、Q1/Q5、LANZ 与订单 p99 同窗对账 |
| 实验二：LANZ 可视化 | 交易 GUI 和当前交易 RUN 保持在线；实验一已经证明真实订单与 Et1 队列事件能同窗出现 | 双入口 MoldUDP64/ITCH 受控负载稳定跨过 LANZ 阈值，并把 S/E 推送到 `.101` 的 8088 页面 | 10k 无事件、25k 有事件，EOS 本地统计与 streaming 接收窗口相互印证 |
| 实验三：PTP 时间 | Exchange 持续播放真实 UDP 行情，Trader 持续接收；不另发业务探针 | 7150 临时提供 PTP 时间，Et1 入向副本在 Et11 盖戳 | `.2` 进入 `SLAVE`，真实行情 `15505/15505` 配对并得到 p50/p99 |

三条纪律贯穿三项实验：

- **业务是真的，拥塞是造的。** 订单太小，堵不住 10G 出口；QoS / LANZ 用课程生成、结构合法的 MoldUDP64/ITCH 负载制造可重复的拥塞，负载发往隔离测试 MAC，不进 Trader。
- **交换机只写 running-config。** 退出先停负载，再撤销临时 QoS、LANZ、PTP、镜像和测试 MAC；startup-config 从不保存。
- **PTP 报文只负责对表。** 实验三被测的仍是真实历史 ITCH 行情。

### 补充速查

先用一个比喻建立整章的直觉。把交换机想成快递分拨站：

| 本章概念 | 分拨站里对应什么 |
| --- | --- |
| cut-through | 扫到面单就启动下一条传送带，不等整件货物卸完 |
| serialization（序列化） | 货物再急，也得按闸口宽度一点点过，快不了 |
| 出口队列 / LANZ | 出口只有一条道，排队时门口的感应器把队伍长度记下来 |
| PTP | 给各站的秒表统一对表，事后才能拼出完整时间线 |
| SPAN / TAP（流量复制） | 不拦原车，另派一辆取证车沿途拍照 |

<div style="border-left:6px solid #7e22ce;background:#f3e8ff;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#7e22ce;color:#fff;font-weight:800;">仅供展示</span> <span style="font-weight:700;color:#581c87;">下表是本章高频缩写的速查，读到正文时不必回头查资料；每一项在对应小节还会再展开一次。</span></div>

| 缩写 | 全称 | 一句话解释 |
| --- | --- | --- |
| ASIC | Application-Specific Integrated Circuit | 交换机里专门做转发的芯片，转发决定由它做，不经过 CPU |
| FM6000 | Fulcrum / Intel 交换芯片型号 | 本课这台 7150 里面那颗做转发的芯片 |
| FDB | Forwarding Database | MAC 地址转发表，决定目的 MAC 该从哪个口出去 |
| FCS | Frame Check Sequence | 以太帧末尾的校验字段，帧收完才能验 |
| LANZ | Latency Analyzer | Arista 的出口队列观测功能，队列变长时记一条事件 |
| PHC | PTP Hardware Clock | 网卡上那只独立的硬件钟，`/dev/ptp0` 就是它 |
| SPAN | Switched Port Analyzer | 交换机把某个口的流量复制一份送到观测口 |
| TAP | Test Access Point | 旁路复制点；可以是无源光 TAP，也可以接到专用 TAP aggregator 的输入口 |
| E-Series | Optical Transceivers | Arista 的光模块，插在交换机口或网卡口上；不是交换机 |
| p50 / p99 | 中位数 / 99 分位数 | 一批时延样本的中间值，以及约 99% 样本不超过的阈值 |

<div style="border-left:6px solid #7e22ce;background:#f3e8ff;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#7e22ce;color:#fff;font-weight:800;">关键图</span> <span style="font-weight:700;color:#581c87;">整章只讲一个故事，分三幕：数据怎么走、时间怎么比、慢在哪一段。</span></div>

| 幕 | 这一幕的角度 | 正文走到哪 | 现场 |
| --- | --- | --- | --- |
| 第一幕 | 慢在转发，还是慢在排队？ | 运行 ① → 推演 A → 推演 B → 实验一 QoS → 实验二 LANZ；盘纤 / L1 是旁支 | 在线真实订单与 LANZ 可视化 |
| 第二幕 | 两只钟怎样先对上表？ | 原理：NTP 与 PTP | 看懂对时关系 |
| 第三幕 | 从交换机入口到网卡花了多久？ | 实验三：入口戳 → 网卡戳 → 相减 | 在线真实行情 |

三幕串故事，后文用 4 个内容组定位；每张导航卡同时标出全章和组内位置。

<div style="border-left:6px solid #7e22ce;background:#f3e8ff;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#7e22ce;color:#fff;font-weight:800;">关键图</span> <span style="font-weight:700;color:#581c87;">这张地图把 7150 的能力分成两半：左侧是业务流量真正要走的那条路，右侧是为了留下证据而额外加的观测手段。</span></div>

<div style="background:#f8fafc;border:1px solid #cbd5e1;border-radius:12px;padding:10px;max-width:820px;margin:14px auto;">
<img src="images/course-visuals/07-diagrams/07-low-latency-switch-feature-map.svg" alt="7150 低延迟转发、队列观测与精确时间能力地图" style="display:block;width:100%;max-width:800px;height:auto;margin:0 auto;border-radius:8px;background:#fff;">
</div>

贯穿全章的判断是：**cut-through 缩短固定等待，调度决定谁先走，LANZ / 时间戳 / PTP 负责留下证据。** 先辨明职责，再判断它们如何改变延迟。

| 能力 | 在低延迟网络里解决什么 | 代价与本章边界 |
| --- | --- | --- |
| cut-through | 减少"等整帧收完"的固定等待 | 仍受线速、速率转换与出口队列约束 |
| strict priority / WRR（Weighted Round Robin，加权轮转） | 决定多个队列谁先出、各占多少份额 | 本章用真实 Socket 订单验证 DSCP→TC→队列命中；只改 running-config，结束即回滚 |
| multicast / mirror replication（组播 / 镜像复制） | 一份行情扇出给多个接收者，或复制给观测工具 | 多出口和工具口都要单独做容量预算；章末展开 SPAN / TAP / TOOL |
| LANZ / 硬件时间戳 / PTP | 分别记录队列长度、帧到达时刻和时钟之间的关系 | 它们让问题变得可观察、可比较，但不会缩短业务转发路径 |

### 历史证据范围

<div style="border-left:6px solid #7e22ce;background:#f3e8ff;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#7e22ce;color:#fff;font-weight:800;">证据边界</span> <span style="font-weight:700;color:#581c87;">正文数字来自 2026-09-03：QoS `095143Z`、LANZ `100334Z`、PTP `085652Z`，共用第六章 `20260903T061746Z`在线基线。2026-09-04 又按正文连跑五个入口并全部通过（`091422Z / 091432Z / 091617Z / 091728Z / 091852Z`）。PTP 使用 7150 软件戳本地 Master，因此当前绝对值只用于方法验证，不对标数据手册 `350 ns` 或 UTC 合规精度。</span></div>

## 第 09 章

已发布的真实产品中，[APS Networks 的可编程交换机](https://www.aps-networks.com/products/)采用 Tofino ASIC。部署自己的 P4 程序需要适配该芯片的编译工具、设备 SDK（软件开发工具包）及板级驱动，BMv2 的 JSON 不能直接用于芯片装载。[P4 Studio 工具说明](https://github.com/p4lang/open-p4studio)

**Tofino 在这里作为已发布的硬件实例。** Intel 停产通知列出的 Tofino / Tofino 2 型号，最后出货日为 2025-02-28；Open P4 Studio 的说明写明，Intel 自 2026-01-01 起停止批准新的专有 BSP / SerDes 驱动访问申请。真机部署须具备相应授权和驱动，并向整机厂商确认供货与支持。[Intel 停产通知](https://cdrdv2-public.intel.com/827577/PCN827577-00.pdf)、[项目依赖说明](https://github.com/p4lang/open-p4studio#what-is-included)

### 厂商的软件系统与 P4 怎样分工

交换机的管理、路由协议等软件可以用 C/C++ 等语言在 CPU 上运行；支持 P4 的芯片则按 P4 定义执行逐包处理。Cisco Silicon One 就公开采用了 P4 开发路径。P4 为数据面提供共同的编程语言，完整交换机仍需要操作系统、驱动和管理软件。[Cisco 架构说明](https://www.cisco.com/c/en/us/solutions/collateral/silicon-one/silicon-one-foundation-success-wp.html)

## 快照恢复与历史审计

### 快照恢复后，01 到 05 怎样一把顺刷

当前恢复边界是：`.1/.2/.11/.101` 四台远端都会回到快照，只有当前管理机 `.111`（`10.1.1.111`）上的仓库、行情制品、观测安装包与课程证据持久保留。第一部分准备 A 必须在全新 `.101` 上物化 `g++-11/make/python3`；第二部分再从 `.111` 构建并部署四项交易服务；第四部分才在全新 `.101` 上安装 Prometheus/Grafana。不能借用恢复前 `.101` 的旧 Gateway、工具链或观测服务。

四台开机后先在`.111`做一次**只读身份门**，不要先接受新host key，也不要先安装软件：

```bash
for h in 10.1.1.1 10.1.1.2 10.1.1.11 10.1.1.101; do
  printf '%-12s ' "$h"
  ssh -o ConnectTimeout=5 "root@$h" 'hostname' || { echo FAIL; exit 1; }
done
```

四台都返回预期hostname才进入第一部分准备A。`HOST KEY VERIFICATION FAILED`表示快照身份与`.111`上的固定基线不一致；`Permission denied`表示快照内没有课程公钥。两者都必须停下核对快照或通过控制台补回已确认的课程公钥，不能用`StrictHostKeyChecking=no`、`ssh-keygen -R`或临时接受未知key绕过。

| 顺序 | 入口 | 它交给下一章什么 |
| --- | --- | --- |
| 01 | 按第一部分依次运行准备 A/B/C、运行①～⑤ | 四机SSH、`.101`构建工具、VLAN20、`.1/.2`数据地址、10G链路和pcap证据；本章不发布应用state |
| 02 | 运行两张卡 | 运行①唯一生成七字段`02-trading-baseline.env`；运行②用首笔成交验收同一RUN |
| 03 | 运行三张卡 | 只读第二部分state并取证，退出时恢复行情模式，不另造应用指针 |
| 04 | 准备A、运行①～③ | `04-observability-stack.env`只记录观测栈；应用身份仍读取第二部分state |
| 05 | 准备A、运行①～④ | 依次生成本章四个测量state；每张卡只读取上一张已生成的入口 |

任何一步非零退出都停在原地查对应 RUN，不能手写或截短 `reports/run-state/*.env` 后继续。管理机上恢复前留下的 state 只允许脚本用来安全停止旧 RUN；每章成功后必须由脚本覆盖为新 RUN。只有从实际恢复后的四台远端完成整条顺刷，才可把“静态通链”升级为 clean-snapshot 验收。

### 2026-08-29 恢复前审计收据

这份收据只说明“当前仓库与当前在线环境已具备顺刷条件”，不冒充恢复后的执行结果：

| 检查 | 结果 | 恢复后怎样判断 |
|---|---|---|
| VM 可见资源 | `.1/.2` 均为4 vCPU、约16 GB；vSphere 全预留以第01章截图为准：`9200 MHz` 与 High | 四台VM成功开机且无资源不足后，再运行准备A |
| 远端入口 | `.1/.2/.11/.101` Strict SSH 4/4；EOS root-only凭据为0600 | 任一SSH失败就停在第一部分，不跳到应用部署 |
| 本地制品 | AAPL/NVDA行情561,727,241字节与manifest通过内置SHA；Prometheus/Grafana本地包存在 | 第二、四部分各自preflight再次验签 |
| 学生脚本 | 01～05正文Bash 24/24通过`bash -n` | 使用正文粘贴或现役asset，不能混用旧目录 |
| 双入口一致性 | 02～05正文/asset 14/14逐字一致 | asset变化必须同步正文后再顺刷 |
| 状态链 | 13/13读取边均由更早步骤生成；第二部分应用state保持7字段 | 禁止复制旧state或手工补字段 |
| 全新`.101` | 恢复前在线状态只作历史证据，不作为顺刷前提 | 准备A重装构建工具；第二部分部署新Gateway；第四部分重装观测栈 |

第五部分当前正式五RUN SHA为32/32，CPU成本收据另2/2；它们仍标为`CURRENT-STATE PASS / CLEAN SNAPSHOT PENDING`。真正恢复后必须产生新的RUN ID，不能把这份恢复前收据直接升级成最终验收。

## 现役资产入口

| 章节 | 现役入口 | 旧目录怎样处理 |
| --- | --- | --- |
| 01 | 正文八张短脚本直接粘贴 | `assets/01-architecture/`已退役；第一章刻意保持正文唯一真源 |
| 02 | `assets/02-trading-baseline/` | `assets/02-wire/`只留历史归档，不再是学生入口 |
| 03 | `assets/03-live-traffic/` | `assets/03-network/`保留旧实验审计，不与现役三卡混用 |
| 04 | `assets/04-live-observability/` | `assets/04-observability/`是旧课形态 |
| 05 | `assets/05-live-software/` | `assets/05-software/`是旧独立小程序形态 |

第二至第五章允许“粘贴正文”或“执行现役asset”两种等价入口；第一章不保留脚本副本，是为避免冻结章节出现双真源。

