# 第03章课程图片集

## 2026-09-07 · DEC-377 全课顺稿配图

本轮新增下列原生 SVG，图标表示角色，保留旧图文件作历史审计。正文入口以本表为准；旧日期条目记录当时状态。

| 当前图 | 回答什么 | 替换的正文图 |
| --- | --- | --- |
| `03-message-and-receipt.svg` | 行情发布与 AUTO/MANUAL 独立订单连接 | `03-live-traffic-map.svg`（已退出正文） |

依据为本章现役正文与配套实现；不包含新增运行读数或硬件实测。使用自绘文件、包裹、时钟、芯片、内存、队列等矢量图标。箭头遵硬规则 §3.3.3：本组固定 12×12 用户坐标头部、refX=0、2.5 线宽、butt 线帽，尖端与目标框至少间隔 12；无箭头的比较图不强加方向。800px 与 1200px 已逐张检查，修复缺字和标题越界。


> 生成日期：2026-08-23
> 生成方式：Codex内置`imagegen`，用途分类`scientific-educational`
> 使用位置：`Documents/newDoc/03-live-trading-traffic-and-protocols.md`

## 2026-08-28 真实交易流量重写后的现用范围

第三章不再运行临时 Socket、`wire-v1` 或人工 Feed A/B 序列。正文沿第二章持续在线的 Trading Lab 使用十张原生 SVG：

| 现用 SVG | 当前职责 |
| --- | --- |
| `03-live-traffic-map.svg` | 区分 C++ 行情发布路径与 AUTO/MANUAL 两条独立订单会话 |
| `03-moldudp64-packet.svg` | 同一套 20 字节头如何读成数据包、心跳、收市和反向补包请求 |
| `03-mold-itch-layers.svg` | 字段尺、包型图、五种 ITCH 表是套叠的三层，不是并列格式 |
| `03-itch-message-types.svg` | 对照 `A/D/E/P/U` 各自字段与 Feed Handler 动作；`P` 的 Indicator 固定为 `B` |
| `03-wireshark-itch-add-order.svg` | 运行 ① 样例帧按 Wireshark Packet Details 树展开；ITCH 用 5.0 官方字段 |
| `03-market-transport-modes.svg` | 对照单播两份、组播一份与 DUAL 三份副本，以及应用 duplicate 责任 |
| `03-ouch-order-lifecycle.svg` | 谁发给谁：MANUAL 长连接上的 Soup `U/S` 与 OUCH `O/A/E` 状态链 |
| `03-soupbintcp-packet.svg` | 同一条字节怎么套：外层 Soup `U/S` 的 Message 里才是 OUCH `O/A/E` |
| `03-ouch-order-ids.svg` | 三个 ID 谁决定：client 写 UserRefNum / ClOrdID，Exchange 发 Match Number 与 Order Reference Number |
| `03-wireshark-ouch-enter-order.svg` | 运行 ③ 样例帧按 Packet Details 树展开；OUCH 用 5.0 官方字段 |

十张图统一为原生可编辑 SVG，正文 `max-width:800px`，没有 PNG 新引用。2026-08-29 为运行 ① 补三张包结构图：`03-moldudp64-packet.svg`、`03-mold-itch-layers.svg`、`03-itch-message-types.svg`。同日为运行 ③ 先补 Soup 尺和 OUCH 类型两张图，随后收成一张套叠图 `03-soupbintcp-packet.svg`；`03-ouch-message-types.svg` 退出正文，文件保留审计。随后补 `03-ouch-order-ids.svg`，只回答三个身份字段由谁决定、出现在哪一条消息。旧 29 张 PNG 与 3 张旧 SVG 均不删除。

2026-08-28 投屏复核发现三张新图沿用了 SVG marker 的默认 `strokeWidth` 缩放：线宽越粗，箭头头部会被再次放大。首轮固定尺寸又收得过小；逐轮复核后仍保留 `markerUnits="userSpaceOnUse"`，两张全宽消息链使用 `32×24` 画布单位箭头，三栏模式图使用 `26×20`。三栏图同时删除全部贝塞尔曲线：单播、组播分支和双路副本统一改为水平—垂直—水平的正交折线，Exchange 到组地址的线段由 12 延至 32 个单位，组地址到接收端的末段为 40 个单位。该返修只改变视觉表达，不改变端点、方向或协议语义。

2026-08-29 与第二章同一口径：marker `refX` 改到三角根部，尖端沿线伸出；线在目标框前结束，尖停在框边，不插进框内。现用三张箭头改为与第二章相同的 `16×12`。三栏传输图按同一格子重排：AUTO/MANUAL 相对 Exchange 上下等距，成对折线拐弯等长。三张退役 SVG 只改 marker，不改语义。

2026-08-29 字段名收口：`03-itch-message-types.svg` 格子只写 TotalView-ITCH 5.0 官方英文名（`Stock`、`Shares`、`Executed Shares`、`Match Number`、`Order Reference Number`）。中文含义只放在正文字段表。

2026-08-29 协议精度收口：TotalView-ITCH 5.0 的 `P` Trade 自 2014 年起把 Buy/Sell Indicator 固定为 `B`，不能据此推断真实 resting side。`03-itch-message-types.svg` 与正文同步标明该边界；`A` 改为“创建展示订单状态”，不再用容易和 `P` 字段组合混淆的“唯一带齐字段”。

2026-08-29 运行 ① 结果改为 Packet Details 树：新增 `03-wireshark-itch-add-order.svg`。干净快照实测 RUN `20260829T080513Z-03-live-market` 已把图上的值换成第 1 帧：`Session 0612260001`、`Sequence Number 15165566`、`Stock NVDA`、`Shares 20`、`Price 2052400`。图左侧 1～19 与正文字段表同一行号。Ethernet / IPv4 / UDP 用 Wireshark 详情树同名；Mold 与 ITCH 按 Nasdaq 官方字段解。Ubuntu 自带 NASDAQ-ITCH 是 2.0/3.0，不能拿来当本课结果。解析器终端同步打印同一棵树。正文不再复贴这 19 行。

2026-08-29 运行 ③ 对齐同一口径：Enter Order 用 Packet Details 树展示。Soup/OUCH 结构收成一张套叠图 `03-soupbintcp-packet.svg`：上排三格写明 `U` 里是 `O`、`S` 里是 `A`、`S` 里是 `E`，下排绿框才是 OUCH 字段。`03-ouch-message-types.svg` 与它重叠，退出正文。树上 1～14 来自旧当前态 RUN `20260828T081946Z-03-live-order`；干净快照重跑后替换。抓包仍用 `tcpdump`，不把 `tshark` 写进绿卡。

2026-08-29 用户要求把 UserRefNum、ClOrdID、Match Number 的归属和关系写清。新增 `03-ouch-order-ids.svg`：左边是 client 自己写的两个请求号，右边是 Exchange 另发的成交号与挂单号；下排三块写明 `O` 带前两个、`A` 原样带回并加 Order Reference Number、`E` 只带回 UserRefNum 再加 Match Number。字段格子仍只用官方英文名。

## 2026-08-27 深度重构后的现用范围

第三章按「一个问题 → 一个最小理论 → 一张必要图或表 → 一张真实卡」重排后，正文不再引用本目录29张PNG；旧图全部原样保留作历史审计，不删除。退役原因不是统一判为“画错”，而是其中多数重复伪代码、编排或证据归档，继续全量展示会把八个真实实验扩成双重教学主线。

当时正文只引用`03-first-valid-decision.svg`，并统一限制`max-width:800px`。该图已随当时运行⑥改为按`(session, sequence)`去重；2026-08-28 重写后它也退出正文。

以下两张原生SVG也退出正文但继续保留：

| 退役SVG | 退役原因 |
| --- | --- |
| `03-first-valid-logic.svg` | 只画两份合法副本A先B后；新版运行⑥改为坏A→合法B→后到合法A，图已不对应 |
| `03-feed-b-recovery.svg` | 画的是B只提供4；新版运行⑦让B发送完整0～5并同时观测5个duplicate |

以下五张旧证据PNG尤其不能继续支撑新版脚本：`03-15-order-response-evidence.png`未包含服务端新增的`received=ORDER:7001`边界，`03-18-multicast-evidence.png`画的是裸`PRE/JOINED/POST`而新版发送三份wire-v1 Tick，`03-24-first-valid-evidence.png`只画两份合法副本，`03-26-feed-recovery-evidence.png`未画完整B流，`03-28-true-gap-evidence.png`未呈现新增的receipts/unique边界。

## 2026-08-27 首轮退役记录

以下3张按新口径退役，正文改引本目录的同名原生SVG；旧PNG仍在本目录保留作历史审计：

| 退役PNG | 退役原因 | 现用载体 |
| --- | --- | --- |
| `03-22-first-valid-decision.png` | 画了`PUBLISH ONCE`终态，脚本无下游发布动作 | `03-first-valid-decision.svg` |
| `03-23-first-valid-logic.png` | 画了`publish_count=1`与`downstream publishes`，均非脚本观测量 | `03-first-valid-logic.svg` |
| `03-25-feed-b-recovery.png` | 写了`continuous logical sequence`，把集合补齐说成按序交付 | `03-feed-b-recovery.svg` |

判定依据：第03章运行⑥～⑧只做到结构检查、`accepted`登记、集合补项与共同缺项判断，`next_expected`游标与pending buffer不在本章实现范围内。

## 统一视觉与证据合同

```text
16:9 clean white classroom slide; premium flat-isometric technical illustration;
crisp navy outlines; restrained depth; cyan market/feed data, orange order/action,
purple membership/control, green accepted/evidence, red only for reject or true gap;
large English labels readable from a classroom screen.
No logos, watermarks, fabricated commands, filenames, timestamps, ports, hashes,
packet values or switch output. Arrow direction, sequence state, membership window,
TCP framing, correlation and host/switch evidence boundaries must match the chapter.
```

| 文件范围 | 教学任务 | 硬约束 |
| --- | --- | --- |
| `03-01`～`03-05` | 行情/订单双通道、Snapshot恢复、九步路线与交付契约 | 行情与订单方向分开；Snapshot后只应用连续增量；UDP/Multicast/TCP不混写 |
| `03-06`～`03-09` | UDP datagram、sequence分类与两条证据链 | `0,1,3,3,4`精确对应NEW/GAP/DUPLICATE；证据图不伪造输出 |
| `03-10`～`03-15` | TCP byte stream、length framing、订单响应与证据 | TCP保序但无消息边界；`ACK:7001`与`EXECUTION:7001`独立，不增加Side/Qty/Status |
| `03-16`～`03-21` | Multicast控制/数据面、join/leave、地址映射与主机证据 | Query/Report/Data/Leave方向正确；`239.20.0.6`、`060014EF`和MAC精确；主机证据不冒充交换机表 |
| `03-22`～`03-24` | Feed A/B first-valid决策、样例与证据 | A/B是对等输入；本轮A胜只因先到；同sequence只登记首份合法来源 |
| `03-25`～`03-28` | 单路补缺、双路真gap及两条证据链 | A缺4且B有4时`accepted keys`覆盖0到5；A/B都缺4时才得到`missing=[4]` |
| `03-29` | 可选交换机侧只读取证 | 不把可选show写成已采证据；没有group/querier输出时只保留短窗口结论 |

## 人工返修与拒收记录

- `03-02`纠正Snapshot恢复回路，确保连续分支和恢复分支都回到按序应用，而不是反向流入快照。
- `03-04`把UDP实验与Feed A/B实验改成sequence状态后的并列分支，避免误画成串行依赖。
- `03-06`拒收Header/Body尺寸颠倒的草图，重画后删除未被正文证明的字段尺寸与伪输出。
- `03-07`、`03-09`、`03-12`、`03-15`和其他证据图清除了生成器添加的端口、价格、时间戳、文件名、随机摘要和终端文本，只保留采证阶段与真实判读字段。
- `03-15`拒收把`7001`误当数量并添加BUY/MARKET/OK/FILLED的草图；最终图只保留真实的correlation、ACK与Execution。
- `03-16`重画Query、Report、Group Data、Copy和Leave箭头，并把Snooping概念模型与本实验实际证据边界拆开。
- `03-19`拒收有歧义的位格，改成可逐行验算的`AND 0x007FFFFF`公式，并保留32组地址可能映射同一MAC的边界。
- `03-22`～`03-28`逐图检查A/B对等、first-valid、补缺与真gap顺序，不把单路丢包提前报告成逻辑缺口。
- `03-29`只画条件式结论；图中没有伪造EOS group表、querier状态或PASS结果。
- `03-17`的标准画布重画稿把离组后误写为`NOT YET JOINED`，因此拒收并保留语义正确的原图。
- 内置图片编辑接口累计出现3次网络失败（早期返修连续2次、封账前局部文字返修1次）；随后仍使用同一内置服务从头重画或保留已通过版本，没有切换到需要`OPENAI_API_KEY`的CLI备用方案。

## 尺寸与投屏层级

29张PNG中27张为`1672×941`；`03-17`为内置服务返回的`1717×916`，`03-20`为`1671×941`。原29张PNG与3张SVG均保留；重构后正文引用0张PNG、1张现用SVG，其余只作历史审计。正文没有折叠层。

本目录现有 43 项固定摘要见同目录 `SHA256SUMS`；清单同时覆盖现用与退役资产，不代表全部仍在正文展示。
