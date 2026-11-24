# 第07章课程图片集

## 2026-09-07 · DEC-377 全课顺稿配图

本轮新增下列原生 SVG，图标表示角色，保留旧图文件作历史审计。正文入口以本表为准；旧日期条目记录当时状态。

| 当前图 | 回答什么 | 替换的正文图 |
| --- | --- | --- |
| `07-queue-clock-interval.svg` | 排队、对表、同帧区间三步 | `07-course-story-map.svg`（已退出正文） |
| `07-serialization-byte-budget.svg` | 给定字节数换算与 FCS 口径 | `07-09-serialization-formula.png`（已退出正文） |

依据为本章现役正文与配套实现；不包含新增运行读数或硬件实测。使用自绘文件、包裹、时钟、芯片、内存、队列等矢量图标。箭头遵硬规则 §3.3.3：本组固定 12×12 用户坐标头部、refX=0、2.5 线宽、butt 线帽，尖端与目标框至少间隔 12；无箭头的比较图不强加方向。800px 与 1200px 已逐张检查，修复缺字和标题越界。

`07-low-latency-switch-feature-map.svg` 从开场总览移至教师速查，保留文件。序列化图统一说明 64 B 含 FCS、1514 B 抓包长度通常不含 FCS；数值仅按给定字节数换算。


> 生成日期：2026-08-23；当前主线重构：2026-09-04
> 生成方式：历史图使用Codex内置`imagegen`；当前补图使用仓库原生 SVG
> 使用位置：`Documents/newDoc/07-arista-cut-through-ptp-time.md`

## 当前正文主线（2026-09-04）

正文当前使用本目录 9 张 PNG 和 14 张原生 SVG。PTP 学生主线关键图仍是三张：`07-ntp-vs-ptp.png`、`07-ptp-how-it-works.png` 与 `07-official-realtime-vs-dedicated-tapagg.png`。`07-keyframe-vs-span.png` 是「Keyframe 是什么」的小节对照图，不是关键图 4/3。时间戳层级、PHC 读取、TC correction、生产时间链和旧版整章 `07-switch-queue-ptp.png` 全部留盘，不删除，但不再打断默认顺序。全章共有 25 个唯一图片引用：本目录 23 张、设备照片 2 张；若只统计课程视觉资产而不计设备照片，则是 23 张。

| 仓库原生 SVG（现用 / 留盘） | 教学任务 |
| --- | --- |
| `07-course-story-map.svg` | 用“转发与排队 → 统一时间 → 包到过哪里”串起整章故事 |
| `07-low-latency-switch-feature-map.svg` | 章首把 cut-through、序列化、共享缓冲/LANZ、硬件时间戳、PTP TC/BC 与 SPAN/TAP/TOOL 放进一张能力地图 |
| `07-cut-through-boundaries.svg` | 对比空闲同速、出口忙、速率转换和 FCS 坏帧四个 cut-through 边界 |
| `07-fan-in-one-egress.svg` | 用中文“多进一出”图说明两路各到 8、一个出口只能发 10、剩下 6 排队的 Fan-in 直觉 |
| `07-qos-trading-flow.svg` | 只画本课 DSCP→TC→TX queue 的五动作主链，并把标准码点、FM6000 默认表与本课 strict 策略分层；A/B 数字留给后文结果表 |
| `07-qos-port-roles.svg` | 订单从 Et2 进、从 Et1 出；Et2 trust DSCP、芯片 DSCP→TC5→Q5、Et1 出队；回程不打标 |
| `07-qos-contention-paths.svg` | 实验一脚本拓扑：上排 Et11/Et12 测试 MAC 进 Et1 Q1，下排 Et2↔Et1 走真 OUCH；静态 FDB 让测试 MAC 从 Et1 真发出去 |
| `07-dscp-tc-decode.svg` | 把 `show qos maps` 的 d1/d2 格子还原成 DSCP 0～63，再标到 TC；40～47 为 TC5，本课用 46 |
| `07-dscp-bits.svg` | IPv4 DS 字节：高 6 位是 DSCP 46，低 2 位是 ECN；d1/d2 是十进制十位和个位，不是 TOS 位域 |
| `07-cos-trust-path.svg` | 本机 Et2 变更前 Trust COS：untagged 帧走 Default COS 0→TC1→Q1；tagged 对照帧才读 PCP；完整八格表收成一条映射规则 |
| `07-layer1-vs-packet-switch.svg` | 对比 7130 L1 cross-connect 与 7150 packet switch 的责任、延迟来源和适用场景 |
| `07-phc-tc-bc-relationship.svg` | 已退出正文。TC / BC 角色图保留给进阶材料 |
| `07-ptp-production-chain.svg` | 已退出正文。UTC/GNSS 到应用日志的生产链保留给进阶材料 |
| `07-ptp-how-it-works.svg` | 正文 PNG 的可维护源：PTP 对表、原帧 / 副本双路抓包、Keyframe 还原、4 B 剪裁、同帧配对与离线相减 |
| `07-official-realtime-vs-dedicated-tapagg.svg` | 正文 PNG 的可维护源：官方 DMF 实时 Flow Diff 与朋友专职 7150 Tap Aggregation 的上下对照 |
| `07-keyframe-vs-span.svg` | 正文 PNG 的可维护源：SPAN 复制的 UDP 副本 + 4 字节短戳，对照 7150 自己另发的 IP 253 Keyframe |
| `07-span-vs-tap-tool.svg` | 已退出正文。旧稿把 SPAN 与 TAP 画成「模式 A / 模式 B」；当前正文改用 DEC-309 的上下对照 PNG |
| `07-7150-timestamp-frame.svg` | 已退出正文。trailer / Keyframe / 31-bit 回卷不再进学生主线 |
| `07-stamped-copy-triage.svg` | 已退出正文。判读收成第三幕那张三行表 |
| `07-switch-latency-bit-boundaries.svg` | 精确定义 FIFO / FILO / LILO / LIFO 的首尾 bit 边界，防止误读厂商纳秒数 |
| `07-low-latency-budget.svg` | 把序列化、PHY/FEC、传播、固定交换与排队拆成五项端到端时间账单 |
| `07-equalized-fiber.svg` | 用近端纤盘与远端直达光路解释等长接入、公平性与 OBR 验收 |

正文继续使用的 9 张本目录 PNG 为 `07-04/05/09/14/15`、`07-ntp-vs-ptp.png`、`07-ptp-how-it-works.png`、`07-official-realtime-vs-dedicated-tapagg.png` 与 `07-keyframe-vs-span.png`，分别承担 ASIC 流水线、cut-through 时序、序列化、LANZ、NTP/PTP 对照、完整时间戳实验、两种生产旁路架构对照，以及 Keyframe 与 SPAN 副本分色。`07-17/18/22/25/28/29/31` 和旧英文 `07-11-fanin-microburst.png` 都继续留盘，但退出学生主线。

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

- `07-11-fanin-microburst.png` 虽有两入口与 `16 − 10 = 6`，但全英文且没有先把 Fan-in 解释成“多进一出”，用户仍无法建立直觉；正文已改用 `07-fan-in-one-egress.svg`。新图第一次栅格审图发现“6 份”贴到第六个队列槽，返修为把数量写入标题；最终在 `1200×720` 与正文 `800×480` 两档带中文字体复核无越界。
- `07-phc-tc-bc-relationship.svg` 首版只过 XML/引用/SHA，没有完成带中文字体的目标宽度审图；用户指出文字出框后，长句改为主动拆行、PHC 卡与 TC 公式框增宽、底部总结改短卡。最终用 Noto Sans CJK SC 在 `1200×940` 与正文 `800×627` 两档栅格复核，无文字越界。
- `07-7150-timestamp-frame.svg` 原“短窗内可排顺序”漏掉 31-bit counter 的模运算条件；现改为按 `2^31` 取模还原相邻间隔，并把 Keyframe 限定为 UTC 映射所需。`1200×570` 与正文 `800×380` 两档带 Noto Sans CJK SC 复核无越界。
- `07-cut-through-boundaries.svg` 原标题容易把“10G→1G 会产生缓存积压”误读成“速率不同就一定不能提前发送”；现只保留速率适配与帧尾积压事实，是否仍能 cut-through 交由具体 ASIC 实现。两档带字体审图后才更新摘要。同图 `.flow` 曾用 `stroke-width:8` 且箭头按 strokeWidth 放大，箭头头几乎与方块等高；已改为 `stroke-width:2.5` + `markerUnits=userSpaceOnUse` 的 12px 箭头。
- `07-low-latency-budget.svg` 右侧第④框描边由 `2 → 1.5`，第⑤框由 `3 → 2`；红色排队框继续保留语义强调，但不再显得压住相邻固定转发框。`1200×700` 与正文 `800×467` 两档带 Noto Sans CJK SC 审图无出框，文字、尺寸与内容未改。当前 SHA=`8e385e13…6ba8c2e`。
- `07-low-latency-budget.svg` 底部第二格原写“换成 25G/100G 后多一截”，未点明多的是哪一笔；该版改为“多出 FEC / 第②笔账 · 编解码等待”。当时 SHA=`9140cc3a…5bd4f9`，当前文件见上条。
- `07-qos-trading-flow.svg` 首次带字体渲染时，`.mono` 只列了未加载的西文字体，导致 DSCP / TC / counter 关键证据整行消失；已把该类改为 Noto Sans CJK SC。旧版后来又把 24 笔 A/B 结果固化在图内，正文实验已升级到 120 样本后形成陈旧双口径；当前版删除结果表与重复的行业依据卡，只保留五动作链、入口分类边界和三层出处，实验数字统一由后文 RUN 表承担。

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
