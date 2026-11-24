# 第 06 章课程图片集

### 2026-09-16 · 图文接续校正

三图只改文字：`06-qos-port-roles.svg` 改为应用设置 DSCP；`06-pcap-frame-matching.svg` 采用 A 路组播端口 31032；`06-ptp-four-timestamps.svg` 补充去回程对称前提，校时改为持续调整 PHC。800px 与原尺寸均已查看，无新遮挡，几何保持，两级 SHA 同步。图中的 PTP 数字仍为教学示例，不提升历史实测等级。

### 2026-09-16 · PTP 四时刻算法图进入正文

`06-ptp-four-timestamps.svg`（1200×800）：Follow_Up 虚线到达后，学员右侧标出已有 t2、t1；Delay_Resp 虚线到达后，标出已有 t3、t4。底栏只放路延 / 钟差公式。四根箭头共用 12×12 头、2.5 线宽、12px 目标间隙。数字来自 IEEE 1588 工作组示例，本课实测仍归运行 ④。

### 当前正文用图 · 2026-09-13 第二轮复核

第06章现有 **23 个唯一图片引用：本目录 21 张 + 设备照片 2 张**；围栏27个、导航14张、运行①～⑤齐全。`06-qos-trading-flow.svg` 已退出正文，作为历史配套图留盘，文件与 SHA 保持；下方各轮数量均指当轮状态。[核验](../../../refs/evidence/chapter06-editorial-review-second-pass-20260913.json)

### 2026-09-13 · QoS 重复流程图退出正文

`06-qos-trading-flow.svg` 与端口职责图重复，现撤下正文引用；文件与 SHA 保留作配套资料。正文图片引用 24→23，两张生产方案图保持。未改任何图片字节，两级清单仍为 68/271 项且全部吻合。[核验](../../../refs/evidence/chapter06-editorial-review-20260913.json)

### 2026-09-13 · 两种生产方案分别成图

用户要求每个方案一张图，新增06-dmf-multipoint-analysis.svg（1200×590）与06-tap-tool-multipoint.svg（1200×690）。前者讲监控入口打戳→Service Node配对→Analytics展示；后者三路TAP Et1～3与TOOL Et10通过ANALYZE组汇聚到统一服务器，标明来源和入口戳。两图800/1200整图、2倍共11根箭头与正文嵌入均检查；共享12×12头、2.5线宽、12px间隙。SHA分别为505787b15985463443a9c393a13a181b4af7ecc976296602978098f29b57e3ec、9d8f6f6bd7cf34d829e8a24a94c2280785440f0fe0aac9606d090674d9d09561，两级清单68/271项通过。旧06-official-realtime-vs-dedicated-tapagg.svg/.png退出正文，文件字节保持供历史引用；该轮完成时正文24图，当前数量见页首。[核验](../../../refs/evidence/chapter06-production-two-diagrams-tap-tool-20260913.json)

### 2026-09-13 · 两份抓包按报文内容配对

新增 `06-pcap-frame-matching.svg`，1200×750：.2原帧与.11副本左右等宽，三组示意包的目的端口均42121，IP ID和MoldUDP64行情消息序号各不相同。副本先取出4字节短戳，再用IP ID＋目的端口＋完整UDP内容唯一匹配；序号只是载荷中的字段，图中501/1001等为明确标注的示意数据。800/1200整图、2倍三根等形直箭头及正文嵌图目视通过，统一12×12箭头、2.5线宽、12px目标间隙。SHA `b571411cae6e01a437fc1d56dd95726a687063504b78cd7380b4e0fdf02c0018`，两级清单66/269项通过；正文现23张图片。[核验](../../../refs/evidence/chapter06-frame-matching-and-user-ptp-results-20260913.json)

### 2026-09-13 · PTP 组播新图与主线配图收束

新增 `06-ptp-multicast-discovery.svg`，1200×700：7150 Et2与.2 ens64np1左右对称，五条消息标224.0.1.129及UDP319/320，明确Announce选源、同步、延迟请求/应答。800/1200整图及2倍五根箭头目视通过；共用12×12头、2.5线宽、12px目标间隙。SHA `0027d07bcff540e335d80caa5c87ce39aaccc33fed5342f7ea0160a7bbbc29ba`，局部/中央清单现65/268项。

正文主线保留本图及 `06-keyframe-vs-span.png`。`06-ntp-vs-ptp.png`、`06-ptp-how-it-works.png` 因与主线重复而撤出正文，保留为历史配套图，不删除文件或旧记录。正文全章现22张图。此前三图总览教学顺序由本条接管。[核验](../../../refs/evidence/chapter06-ptp-mainline-and-output-20260913.json)

### 2026-09-13 · LANZ 图改为两条去回折返路径

`06-lanz-stream-to-8088.svg` 根据用户最新要求重新布局：.101内分别列8088网页服务和8089 LANZ采集器，浏览器右侧两条等形折返线各自请求/返回网页与JSON；圆点为请求起点，箭头为返回终点。左侧仅画交换机向.101推送S/U/E，50001明确属于交换机管理口。底注保留采集器先建连。三个箭头统一12×12、线宽2.5、目标间隙12；800/1200及2倍目视通过。SHA256 `24e4b508918ca35561ad27dcb6fcacb9af4de070246afca33501dc118576b0f3`，两级清单已同步；本条取代下方四条直线的现役设计。

### 2026-09-13 · LANZ 路径图去掉跨章编号

`06-lanz-stream-to-8088.svg` 四条箭头改为中文动作名，移除③a/③b/④a/④b及沿用第01章说明；几何保持，明确采集器主动建连、交换机推送事件、内存/JSON存储和网页取数。800/1200整图及2倍箭头目视通过。SHA256 `148f7c3ad32dbea6af785aff94469ba384ec816538f805809af455ac0b664ea8`，两级清单已同步。

### 2026-09-13 · LANZ 无事件/有事件对照图改为中文

`06-15-lanz-noevent-vs-event.png` 使用内置 image_gen 参照原图编辑，保留蓝橙左右三行结构，所有解释改中文。原始数值来自 `20260903T060803Z-07-lanz-live-ab` 的两份 switch-dual-10k/25k-4096-post.txt；图中 28µs/64 缓冲段为其中一对 S/E 示例。图底标历史实验，正文链接原始证据。原尺寸及 800px 目视通过，两级 SHA 已同步。SHA256：`c6419dfdcebde43eda136028c062711355b41ba241eb32673b59dc398055628b`。最终提示词和来源见[核验记录](../../../refs/evidence/chapter06-lanz-chinese-figure-20260913.json)。

## 2026-09-13 · QoS对照图统一坐标，基础DSCP位图退出正文

`06-qos-contention-paths.svg` 保留上下A/B结构，两个实验面板等高、发送端/出口/接收端坐标一致；两路入口均为水平直线，出口汇合上下等距。A组共用一个Q1，B组分到Q1/Q5；汇合线表示两类流量共享Et1，不表示复制或增加物理出口。800/1200px全图与2倍箭头、32个文字节点边界通过；六根箭头统一12×12、2.5线宽、12px目标间隙。现SHA256：`650d42102bad6c03707e1aa8e4f49919eb0603d06ba2c50f704341e20d90dadb`，接管下方同日旧图哈希。

`06-dscp-bits.svg` 按用户要求退出正文，原文件及SHA保留；CoS路径、DSCP默认映射、订单流程和端口职责图继续使用。正文现23个图片引用（包含设备照片与本章总览），下方旧日期数量为历史记录。[核验](../../../refs/evidence/chapter06-qos-compact-symmetric-20260913.json)

## 2026-09-13 · QoS图补齐未标记订单进入Q1的路径

`06-qos-contention-paths.svg`重画为上下A/B对照：两组Et2都已信任DSCP，A组订单DSCP0与背景共用Et1的Q1，B组DSCP46订单进入严格优先级Q5。背景过滤与回报方向只在图底简述，正文图注/alt和代码说明同步。1200×930及800×620整图、32个文字节点边界、六根箭头2倍局部检查通过；三色marker统一12×12、2.5线宽、尖端距目标12px。两级SHA同步，当前SHA256：`928ac7c536dbf750b9b144f8edd2cfb40cab27a81895a64866c41c72a6d29b92`。

## 2026-09-13 · LANZ 事件到 8088 用一张路径图收住

新增 `06-lanz-stream-to-8088.svg`：三个角色从左到右是 7150、`.101` 采集器、浏览器。上行③a/④a 是建连和取数，下行③b/④b 是事件和 JSON，四根水平直线左右对齐。编号与第 01 章通信图一致。1200×700，四根箭头共用 12×12 头部、2.5 线宽、12px 目标间隙。当前 SHA256：`a298cf534c555a5525a6cc2727b1e9ffd5e545a21f8a6a8cf151e5835b44e45c`。两级清单已更新。图不展开 protobuf 字段、CORS 或临时源端口。

## 2026-09-13 · CoS分类前后对照与DSCP二进制映射

三张图按网络工程师常用的入接口分类、TC、TX queue 解释：`06-cos-trust-path.svg`改为信任 CoS 前态和信任 DSCP 后态；`06-dscp-bits.svg`只保留六位 DSCP 与整字节的关系；`06-dscp-tc-decode.svg`改为六位二进制范围、十进制范围与 TC 的八行对应表，突出本课46。删除课堂图中的d1/d2行列排法，映射数值沿用官方FM6000默认表；正文先图后文，图注与alt同步。三图800/1200px整图目视通过、文字无越界；CoS图四根箭头统一12×12、2.5线宽、12px目标间隙，2倍局部检查通过。两级SHA已更新，当前哈希为：

- `06-cos-trust-path.svg`：`bf0516b10957550f1dfa96a195c516f32ef0488c96c7b81eba20c9975f2d369e`。
- `06-dscp-bits.svg`：`8b8b94357accb110159ce1cc3a4efae0ac904f29e4ba67917303e835a0074e48`。
- `06-dscp-tc-decode.svg`：`09296e0e0b949da76e29340425ceecb9c465418712711c554b42d9a0465c205e`。

## 2026-09-13 · 第②项具体命名为信号编解码与纠错

`06-low-latency-budget.svg`的第②栏、描述和优化文字同步正文；完整名称用两行显示，去掉泛称“物理层”及不必要的PHY缩写。1200×700五栏、所有矩形与五根箭头几何保持，800/1200px全图及箭头目视通过。当前SHA256：`23edfd4c382c215671572336c509e53518b9075b6417504e7a2c0a7cbad83428`；两级清单已更新。五栏按耗时来源区分，不表示严格串行的五个阶段。

## 2026-09-13 · 标题层级与五项编号顺序同步

正文导航现4组14项，第一部分按序列化、物理层、传播、转发展开；`06-queue-clock-interval.svg`仅将第一栏末行改为“按序展开机制与实例”，避免旧文字暗示转发先于序列化。其余文字和全部几何保持，800/1200px整图及箭头目视通过，16个文字节点边界无越界。新SHA256：`867173cb3def3fb2732ab49d6098adc8f5197f1588651752cf96dea71d19a65a`，两级清单同步。五项图字节保持，图下新增五行正文表；平台照片前移章首，生产监控图移到第三部分独立知识节，仍23张图片引用。

## 2026-09-13 · 五项耗时总览前置，章节采用三部分顺序

`06-low-latency-budget.svg`移到第一知识项，字节与SHA保持；`06-queue-clock-interval.svg`第一栏由Cut-through扩大为链路五项耗时，第三栏按计时起止点、同步与配对、时间戳相减组织，整体对应“耗时→队列→测量”。后者保留1200×620画布及两根12×12箭头、2.5线宽与12px目标间隙，800/1200px整图及箭头目视通过，16个文字节点边界无越界。新SHA256：`5763d54dad561634ec94e497b4e1571c9717beb70b8fcd57a3d323e44585f832`。两级清单同步；正文23张图片引用保持，行业案例图随盘纤/L1正文前移。

## 2026-09-13 · 五项耗时先图后文，突出出口排队

`06-low-latency-budget.svg`保留1200×700五栏结构；在相同帧长、路径与配置前提下，前四项标“相对固定”，红色队列栏标“主要变动项”。原横向连接改为五根向下的小箭头，各自对应优化手段，不表示五项依次串行。统一12×12用户坐标箭头、2.5线宽和12px目标间隙；缩短文字并增大正文字号。800/1200px整图及全部箭头目视通过，浏览器34个文本节点中五栏文字边界检查无越界。图中不将350 ns写作查表耗时。新SHA256：`018a30db28fcd7187d9b49418b83804cba4d4df9f36184095d978e4d8d40c6d5`；下方旧SHA与布局为历史记录。

## 2026-09-13 · 序列化改为短文与数值表

按用户反馈，`06-serialization-byte-budget.svg` 仅重复长短帧占线对比，现退出正文，文件与SHA保持供历史审计。正文使用统一含帧尾校验的64/1518字节，聚焦固定线速下不可省去的出口发送时间；下方旧图口径是历史记录。

## 2026-09-12 · 现役第06章

本目录由原第07章前移，现役图文件与链接采用新编号；下方历史条目保留原日期和验证身份。本轮未新增设备实验。

## 2026-09-07 · DEC-377 全课顺稿配图

本轮新增下列原生 SVG，图标表示角色，保留旧图文件作历史审计。正文入口以本表为准；旧日期条目记录当时状态。

| 当前图 | 回答什么 | 替换的正文图 |
| --- | --- | --- |
| `06-queue-clock-interval.svg` | 五项耗时总览、QoS 队列与 LANZ、PTP 对时及延迟测量三个部分 | `06-course-story-map.svg`（已退出正文） |
| `06-serialization-byte-budget.svg`（2026-09-13已退出正文） | 历史给定字节数换算与 FCS 口径 | `06-09-serialization-formula.png`（已退出正文） |

依据为本章现役正文与配套实现；不包含新增运行读数或硬件实测。使用自绘文件、包裹、时钟、芯片、内存、队列等矢量图标。箭头遵硬规则 §3.3.3：本组固定 12×12 用户坐标头部、refX=0、2.5 线宽、butt 线帽，尖端与目标框至少间隔 12；无箭头的比较图不强加方向。800px 与 1200px 已逐张检查，修复缺字和标题越界。

`06-low-latency-switch-feature-map.svg` 从开场总览移至教师速查，保留文件。序列化图统一说明 64 B 含 FCS、1514 B 抓包长度通常不含 FCS；数值仅按给定字节数换算。


> 生成日期：2026-08-23；当前主线重构：2026-09-04
> 生成方式：历史图使用Codex内置`imagegen`；当前补图使用仓库原生 SVG
> 使用位置：`06-arista-cut-through-ptp-time.md`

## 当前正文主线（2026-09-04）

正文当前使用本目录 8 张 PNG 和 14 张原生 SVG。PTP 学生主线关键图仍是三张：`06-ntp-vs-ptp.png`、`06-ptp-how-it-works.png` 与 `06-official-realtime-vs-dedicated-tapagg.png`。`06-keyframe-vs-span.png` 是「Keyframe 是什么」的小节对照图，不是关键图 4/3。时间戳层级、PHC 读取、TC correction、生产时间链和旧版整章 `07-switch-queue-ptp.png` 全部留盘，不删除，但不再打断默认顺序。全章共有 24 个唯一图片引用：本目录 22 张、设备照片 2 张。

| 仓库原生 SVG（现用 / 留盘） | 教学任务 |
| --- | --- |
| `06-course-story-map.svg` | 用“转发与排队 → 统一时间 → 包到过哪里”串起整章故事 |
| `06-low-latency-switch-feature-map.svg` | 章首把 cut-through、序列化、共享缓冲/LANZ、硬件时间戳、PTP TC/BC 与 SPAN/TAP/TOOL 放进一张能力地图 |
| `06-cut-through-boundaries.svg` | 对比空闲同速、出口忙、速率转换和 FCS 坏帧四个 cut-through 边界 |
| `06-fan-in-one-egress.svg` | 两帧争用同一出口：本例先发送 A，B 在缓冲区等待；区分逐帧发送与发送前的排队 |
| `06-qos-trading-flow.svg` | 配套资料，已退出正文：DSCP→TC→TX queue 五动作链；学生正文使用端口职责图讲解 |
| `06-qos-port-roles.svg` | 订单从 Et2 进、从 Et1 出；Et2 trust DSCP、芯片 DSCP→TC5→Q5、Et1 出队；回程不打标 |
| `06-qos-contention-paths.svg` | A/B上下对照：A组未标记订单与背景共用Et1的Q1；B组DSCP46订单进入严格优先级Q5，背景仍在Q1；两组Et2都信任DSCP |
| `06-lanz-stream-to-8088.svg` | 运行 ③：采集器连 50001、同一 TCP 回送 S/U/E、8088 向 8089 取 JSON 画底栏 |
| `06-dscp-tc-decode.svg` | 六位二进制范围与十进制范围并列，每行八个 DSCP 值对应一个 TC；突出 101110（46）→TC5→Q5 |
| `06-dscp-bits.svg`（已退出正文，留盘） | 历史基础位图：六位 DSCP 101110 即 46，本课 ECN 为 00，整字节 10111000 即 0xb8 |
| `06-cos-trust-path.svg` | 同一课堂入口的两种分类：信任 CoS 时无标签帧使用默认 CoS 0→TC1→Q1；信任 DSCP 后订单 46→TC5→Q5；两种映射都有默认表 |
| `06-layer1-vs-packet-switch.svg` | 对比 7130 L1 cross-connect 与 7150 packet switch 的责任、延迟来源和适用场景 |
| `06-phc-tc-bc-relationship.svg` | 已退出正文。TC / BC 角色图保留给进阶材料 |
| `06-ptp-production-chain.svg` | 已退出正文。UTC/GNSS 到应用日志的生产链保留给进阶材料 |
| `06-ptp-how-it-works.svg` | 正文 PNG 的可维护源：PTP 对表、原帧 / 副本双路抓包、Keyframe 还原、4 B 剪裁、同帧配对与离线相减 |
| `06-official-realtime-vs-dedicated-tapagg.svg` | 正文 PNG 的可维护源：官方 DMF 实时 Flow Diff 与朋友专职 7150 Tap Aggregation 的上下对照 |
| `06-keyframe-vs-span.svg` | 正文 PNG 的可维护源：SPAN 复制的 UDP 副本 + 4 字节短戳，对照 7150 自己另发的 IP 253 Keyframe |
| `06-span-vs-tap-tool.svg` | 已退出正文。旧稿把 SPAN 与 TAP 画成「模式 A / 模式 B」；当前正文改用 DEC-309 的上下对照 PNG |
| `06-7150-timestamp-frame.svg` | 已退出正文。trailer / Keyframe / 31-bit 回卷不再进学生主线 |
| `06-stamped-copy-triage.svg` | 已退出正文。判读收成第三幕那张三行表 |
| `06-switch-latency-bit-boundaries.svg` | 精确定义 FIFO / FILO / LILO / LIFO 的首尾 bit 边界，防止误读厂商纳秒数 |
| `06-low-latency-budget.svg` | 把序列化、PHY/FEC、传播、固定交换与排队拆成五项端到端时间账单 |
| `06-equalized-fiber.svg` | 用近端纤盘与远端直达光路解释等长接入、公平性与 OBR 验收 |

正文继续使用的 9 张本目录 PNG 为 `07-04/05/09/14/15`、`06-ntp-vs-ptp.png`、`06-ptp-how-it-works.png`、`06-official-realtime-vs-dedicated-tapagg.png` 与 `06-keyframe-vs-span.png`，分别承担 ASIC 流水线、cut-through 时序、序列化、LANZ、NTP/PTP 对照、完整时间戳实验、两种生产旁路架构对照，以及 Keyframe 与 SPAN 副本分色。`07-17/18/22/25/28/29/31` 和旧英文 `06-11-fanin-microburst.png` 都继续留盘，但退出学生主线。

## 统一视觉与证据合同

```text
16:9 clean white classroom slide; premium flat-isometric/vector technical
illustration; crisp navy outlines; cyan packet/data path, orange egress queue
and correction ownership, purple hardware time/PTP control, green evidence or
observation, red only for a real boundary; large readable English labels.
No logos, watermarks, fabricated IPs, MACs, timestamps, hashes, packet counts,
queue values, latency values, synchronization claims or production-SLA claims.
```

| 文件范围 | 教学任务 | 硬约束 |
| --- | --- | --- |
| `07-01`～`07-03` | 历史双证据链与旧九卡导航（已退出正文） | “快”和“准”分别证明；LANZ只属于队列观察，PTP/TC只属于时间关系 |
| `07-04`～`07-08` | ASIC流水线、cut-through时机、Fabric身份与只读取证 | Parser→VLAN→FDB→decision→egress queue→serialization顺序固定；mode/FDB不是逐包时延 |
| `07-09`～`07-13` | 10GbE序列化公式与Fan-in单变量模型 | `64B/1514B`是可见帧字节口径；右侧残余队列必须精确为6个模型单位；模型不冒充交换机实测 |
| `07-14`～`07-16` | LANZ S/U/E生命周期、No-event/Event对照与tracked证据审计 | S跨高阈值开始、E回落低阈值结束；只使用原生存在字段；LANZ事件不是逐包端到端时延 |
| `07-17`～`07-24` | 软件/硬件时间戳位置、两端能力、LinuxPTP准备与PHC只读边界 | capability不等于同步；PHC可读不等于两端可直接相减；准备工具不启动`ptp4l/phc2sys` |
| `07-25`～`07-30` | PTP四消息、TC residence/correction与三层真包证据 | 四方向固定为Sync→、Follow_Up→、Delay_Req←、Delay_Resp→；非零correction必须与EOS、ptp4l、pcap交叉核对 |
| `07-31` | 本章交接与第08章入口 | `.2`与`.11`是交换机后的独立主机分支；不存在`.2→.11`数据路径；时间层和LANZ都不是转发hop |

## 人工返修与拒收记录

- `06-11-fanin-microburst.png` 与 `06-fan-in-one-egress.svg` 的早期版本使用 `16 − 10 = 6` 短窗模型。2026-09-16 纠正其教学歧义：时间窗内能发完，不等于没有排队；删除“立即离开 10 份”的画法。现役 SVG 改为两帧争用出口、A 发送期间 B 等待，保留平面帧图标；箭头统一尺寸且尖端距目标框 12px。已在 `1200×720` 与正文 `800×480` 目视确认文字、图标与箭头无重叠。此图为机制示意，不是实测读数。
- `06-phc-tc-bc-relationship.svg` 首版只过 XML/引用/SHA，没有完成带中文字体的目标宽度审图；用户指出文字出框后，长句改为主动拆行、PHC 卡与 TC 公式框增宽、底部总结改短卡。最终用 Noto Sans CJK SC 在 `1200×940` 与正文 `800×627` 两档栅格复核，无文字越界。
- `06-7150-timestamp-frame.svg` 原“短窗内可排顺序”漏掉 31-bit counter 的模运算条件；现改为按 `2^31` 取模还原相邻间隔，并把 Keyframe 限定为 UTC 映射所需。`1200×570` 与正文 `800×380` 两档带 Noto Sans CJK SC 复核无越界。
- `06-cut-through-boundaries.svg` 原标题容易把“10G→1G 会产生缓存积压”误读成“速率不同就一定不能提前发送”；现只保留速率适配与帧尾积压事实，是否仍能 cut-through 交由具体 ASIC 实现。两档带字体审图后才更新摘要。同图 `.flow` 曾用 `stroke-width:8` 且箭头按 strokeWidth 放大，箭头头几乎与方块等高；已改为 `stroke-width:2.5` + `markerUnits=userSpaceOnUse` 的 12px 箭头。
- `06-low-latency-budget.svg` 右侧第④框描边由 `2 → 1.5`，第⑤框由 `3 → 2`；红色排队框继续保留语义强调，但不再显得压住相邻固定转发框。`1200×700` 与正文 `800×467` 两档带 Noto Sans CJK SC 审图无出框，文字、尺寸与内容未改。当前 SHA=`8e385e13…6ba8c2e`。
- `06-low-latency-budget.svg` 底部第二格原写“换成 25G/100G 后多一截”，未点明多的是哪一笔；该版改为“多出 FEC / 第②笔账 · 编解码等待”。当时 SHA=`9140cc3a…5bd4f9`，当前文件见上条。
- `06-qos-trading-flow.svg` 首次带字体渲染时，`.mono` 只列了未加载的西文字体，导致 DSCP / TC / counter 关键证据整行消失；已把该类改为 Noto Sans CJK SC。旧版后来又把 24 笔 A/B 结果固化在图内，正文实验已升级到 120 样本后形成陈旧双口径；当前版删除结果表与重复的行业依据卡，只保留五动作链、入口分类边界和三层出处，实验数字统一由后文 RUN 表承担。

- `07-01`首稿把LANZ画成独立网络设备，已返修为贴近交换机队列的观察面板，并保留`OBSERVATION ONLY · NOT IN PATH`。
- `07-02`首稿把Follow_Up与Delay_Req方向画反，并把TC证据画成拥塞队列；最终导航不在缩略卡内画消息方向，只保留四类消息清单与Transparent Clock correction证据。
- `07-03`首稿在“四类PTP消息”缩略卡内生成不可靠方向箭头，已拒收；最终版只保留四只中性信封。
- `07-04`的返修候选擅自生成`42%` buffer usage和虚构曲线，已拒收；最终版回到无数值的ASIC流水线，并把LANZ保持为队列虚线观察点。
- `07-11`与`07-12`首稿都把`queued=6`画成7个橙色方块，已拒收；最终版使用明确编号`1～6`的六槽队列。
- `07-15`首稿自动增加不存在的S/U/E计数列并重复接口字段，已拒收；最终版只保留`10k`空表边界和`25k`的Et2/TC1/Count、S、E原生字段。
- `07-25`首稿在单台TC内虚构`link 1/2/3 residence`，已返修为`OLD CORRECTION + RESIDENCE TIME`；四条消息方向逐一复核正确。
- `07-29`与`07-30`首稿用装饰箭头暗示错误消息方向，已返修为四只中性信封；方向只由`07-25`、`07-26`和原始pcap承担。
- `07-31`首稿把`.2`与`.11`错误画成串联路径并生成产品Logo，已拒收；最终版使用抽象框图，明确两者是从Arista出去的独立分支。
- 内置绘图服务多次返回临时网络错误；均继续使用同一内置模式重试，没有改用外部图片、CLI/API Key或脚本占位。

## 尺寸与投屏层级

31 张历史 PNG 均为 `1672×941`；当前正文原生 SVG 继续使用 800px 展示合同。新实验图源为 `1400×820`，正文引用其同尺寸 PNG，并放在 `max-width:820px` 容器 / `max-width:800px` 图像中，不拉伸。

DEC-189/190 的“全部 PNG 展开”是上一轮课堂版式记录；本轮用户把受众明确为网络工程师，并要求按第五章做法补原生 SVG、保留真正讲得清的位图。当前因此恢复“主线图 / 留盘审计图”分层：文件不删除，正文不再为每张输出重复一张取证流程图。

当前目录全部 36 张 PNG + 25 张 SVG 的固定摘要见同目录 `SHA256SUMS`。
