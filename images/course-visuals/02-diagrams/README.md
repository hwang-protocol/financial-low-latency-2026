# 第02章课程图片集

2026-09-17：准备 A「哪些网卡能用」嵌入根级实物照 `images/solarflare-x2522-nic.png`（1536×1024，SHA256 `7e3692ea58c8f00c74935ea70a344a941d6cea5438dbd22c7bd174499be367c5`）。与 `Documents/course/images/` 下同名文件字节相同；本目录不复制第二份。照片是元件面，不是挡板侧端口。用户要求课堂显示为标准宽度的 2/3（图 533px / 框 547px）。未改图字节。

2026-09-15：用户截图 `screenshot_20260915_174342_20260915_174343_577922.png` 原字节移至 `02-ui-trading-terminal-ab.png`，替换正文旧网页总览图；不改图中报价、持仓或回执。旧图保留作历史资料。SHA256：`d73764618af13592515cf296cc1f1426ea3d3a66b877bcc139009861e294e8bb`。

2026-09-15 A/B 更新：三机运行图显示 A/B 组播进入共享接收器，保留 AUTO/MANUAL 下单链路；设备说明移出图标区，本机分发标签避开箭头。800/1200px 已渲染目视，当前摘要见 SHA256SUMS；这不是实机抓包证据。

## 2026-09-15 · IOMMU 图退出正文

用户要求 IOMMU 聚焦“限制网卡 DMA 可访问的内存”，随后直接讲启动参数；撤下 `02-iommu-vfio-dpdk.svg`，不再展开 CPU/MMU、隔离组及多角色图。原 SVG 留作备用，字节与两级 SHA 保持。Onload/DPDK 收发对比图继续使用；本条接管下方该图仍在正文的历史记录。

## 2026-09-15 · 配合 B1/B2 拆分更新图注

`02-dpdk-kernel-vs-user.svg` 与 `02-iommu-vfio-dpdk.svg` 的页脚“准备 B”改为“准备 B1”，明确隔离准备对应 B1；B2 另行安装软件。其余文字、图形与连线几何保持。本轮更改只涉及这两处步骤名，重新核对 800/1200px 字体边界与显示，两级 SHA 同步。

## 2026-09-15 · 核心技术对比与图文位置收口（当前）

本条接管下方同日“章首两图”的旧安排；保持平面原生SVG与自绘图标。

| 当前图 | 正文位置与用途 | 画布 |
| --- | --- | --- |
| `images/solarflare-x2522-nic.png` | 准备A：识别本课 X2522 双口卡；元件面实物照，文件在 `images/` 根级 | 1536×1024 |
| `02-onload-kernel-vs-user.svg` | 准备A：同一Socket程序普通启动或由onload加载用户态栈；分开收发与资源准备 | 1200×1010 |
| `02-dpdk-kernel-vs-user.svg` | 准备B：sfc/Linux TCP/IP与VFIO/DPDK PMD/F-Stack的收发对比 | 1200×1010 |
| `02-iommu-vfio-dpdk.svg` | 已撤出正文，原件备用 | 1200×1080 |
| `02-trading-lab-runtime.svg` | 运行①上线结果之后：.1/.2/.101，两种下单方式 | 1200×1030 |
| `02-auto-strategy.svg` | 运行②买一/卖一之后：真实一档信号与默认限制 | 1200×970 |

后两图相对本日上一轮字节保持，只移动正文位置。`02-runtime-prep-steps.svg` 与 `02-build-start-trade.svg` 退出正文、保留原件；`02-nasdaq-multicast-routing.svg` 随深入组播机制转至NETWORK-REFERENCE.md。原手工下单Mermaid保持。

压字反馈已修复：共用框将图标上移、正文下移，箭头通道不放长标签；专题三图102文字、15图标、33箭头经过实际Noto字体边界/相交检查及800/1200px审图，正文940px预览通过。箭头保持12×12用户坐标、refX=0、2.5线宽、butt，目标框外12px。局部/中央SHA当前41/282项。仅图文与来源核验，无设备或性能实测；收据 `refs/evidence/chapter02-core-topics-and-flow-20260915.json`。

## 2026-09-15 · 章首三机流量与 AUTO 策略

章首使用两张平面原生 SVG，均用自绘服务器、屏幕、订单簿、机器人、手形及检查图标，无立体投影。

| 当前图 | 用途 | 画布 |
| --- | --- | --- |
| `02-trading-lab-runtime.svg` | 仅 `.1/.2/.101`；共享接收器、两个独立 Trader、各自下单/回报、网页控制与事件副本 | 1200×1030 |
| `02-auto-strategy.svg` | 买一/卖一数量比例、±0.35 阈值、5 秒间隔、含在途订单的±200股限制、25股对手价 IOC | 1200×970 |

运行架构图从运行①移到章首，不再包含管理机或部署箭头；部署分工由运行①原有文字表格和构建图承担。图中 .101 的屏幕是它提供的网页示意，不表示浏览器必须运行在该 VM。普通 Socket 配置为图示范围，Gateway 周期状态查询由正文说明，后续其他收发路径仍按各章展开。

策略以现役 `src/trader.cpp::maybe_trade` 为准，仅比较买一与卖一数量，五档是网页展示深度。900/300与0.50是教学算例，默认参数不是本轮现场配置读取；不添加实跑或盈利结论。两图共15支箭头，统一12×12 / refX=0 / 2.5线宽 / butt，目标框外留12px。验证收据见 `refs/evidence/chapter02-opening-flows-strategy-20260915.json`。下方旧尺寸、角色、图数与画风合同仅描述对应日期历史。

## 2026-09-10 · 评估后补齐操作线与线型职责

`02-runtime-prep-steps.svg` 仍为 1200×1000；第④行补管理机蓝框、SSH 发起安装的蓝色虚线，目标框统一为绿色，移除无独立语义的橙色。现有四支跨主机箭头，实线传材料/结果，虚线发起操作；①只校验一次、②～⑤先 .1 后 .2 的顺序不变。正文图卡和 alt 同步。

`02-iommu-vfio-dpdk.svg` 仍为 1200×830；上半图灰色实线仅表示步骤先后，下半图局部图例限定蓝虚线为设备访问/映射、绿实线为 DMA。内存框改为“用于报文收发的缓冲区”，不再暗示未画出的注册过程。六支箭头几何不变，新增灰色 marker 与蓝绿头部同形同尺寸。两图全部十支箭头保持 12×12 / refX=0 / 线宽 2.5 / butt，尖端距框 12px；Chrome 本地渲染 800/1200px 逐端目视通过。两级 SHA 同步，无设备操作，原始实测输出不改。

## 2026-09-10 · 准备 A 按主机展开五步

新增 `02-runtime-prep-steps.svg`（1200×1000），用管理机/当前目标机两列和①～⑤五行表现源码中的校验、依赖、分发、编译安装、检查返回。①只执行一次，②～⑤先为.1执行，再为.2执行；三支跨主机箭头分别标明依赖包、源码归档、原始检查结果。对应00a与install-offline-packages.py，强调课前缓存与本机编译，未执行新安装。800/1200px目视通过；箭头12×12/refX=0/线宽2.5，尖端距框12。

## 2026-09-10 · 准备 B 与 DPDK 的关系

新增 `02-iommu-vfio-dpdk.svg`（1200×830），先区分准备 B 的启用/检查与第六部分 Trader 数据口接管，再分开 VFIO 设备访问/映射配置和 NIC → IOMMU → 已映射缓冲区的 DMA 路径。仅为 Guest 视角机制图，省略 ESXi 直通映射层；无新实机结果。依据 Linux 5.15 VFIO、DPDK 21.11 官方文档及本仓库准备/切换脚本。六支箭头统一12×12、refX=0、线宽2.5、尖端距目标框12；800/1200px渲染目视通过。

## 2026-09-08 · DEC-393 统一流量与端口

本轮更新：`02-nasdaq-multicast-routing.svg`, `02-trading-lab-runtime.svg`, `02-build-start-trade.svg`。控制器归属 `.2`，行情由一个普通 Socket 接收后本机分发；组播 `233.74.125.32:31032`、单播 `.2:42121`。生产案例仅用官方公开端点，中间路由器为机制示意。本地无 PIM/RP 配置。800/1200px 渲染检查；历史抓包与旧性能图保留原始字节及其出处。


## 2026-09-07 · DEC-377 全课顺稿配图

本轮新增下列原生 SVG，图标表示角色，保留旧图文件作历史审计。正文入口以本表为准；旧日期条目记录当时状态。

| 当前图 | 回答什么 | 替换的正文图 |
| --- | --- | --- |
| `02-build-start-trade.svg` | 运行①构建启动，运行②首笔交易 | `02-snapshot-restore-flow.svg`（已退出正文） |

依据为本章现役正文与配套实现；不包含新增运行读数或硬件实测。使用自绘文件、包裹、时钟、芯片、内存、队列等矢量图标。箭头遵硬规则 §3.3.3：本组固定 12×12 用户坐标头部、refX=0、2.5 线宽、butt 线帽，尖端与目标框至少间隔 12；无箭头的比较图不强加方向。800px 与 1200px 已逐张检查，修复缺字和标题越界。


> 生成日期：2026-08-23  
> 生成方式：Codex内置`imagegen`，用途分类`scientific-educational`  
> 当前定位：第02章图片目录；正文使用2张交易系统SVG，原3张wire教学SVG与25张PNG全部保留作审计

## 2026-08-28交易系统基线重写

第02章不再以自定义`wire-v1`和五个本机语义实验作为主线，改为从持久管理机恢复普通Linux交易系统，并完成一笔确定性纸面IOC。新增两张可编辑SVG：

| 文件 | 当前职责 | 画布 |
| --- | --- | --- |
| `02-trading-lab-runtime.svg` | 分开`.1/.2` C++热路径、`.101` Python观察路径与管理机持久真源 | `1200×720` |
| `02-snapshot-restore-flow.svg` | 从第一章环境交接，经预检/构建/部署/验签到首笔交易 | `1200×560` |
| `02-ui-replay-book-order.png` | 干净快照网页：回放、盘口与手工下单 | `3192×1456` |
| `02-ui-trend-latency.png` | 干净快照网页：价格走势、延时基线与策略开关 | `3202×866` |
| `02-ui-blotter-path.png` | 干净快照网页：统一交易记录与系统路径 | `3186×1140` |
| `02-ui-first-trade-receipt.png` | 干净快照运行 ②：网页手动订单回执，与 `raw/first-trade.txt` 同一笔 | `782×222` |

正文统一限制`max-width:800px`。两张图都只解释架构与恢复关系，不填性能数字；现行交易协议和成交证据来自真实应用与RUN。原`02-order-book-l1-l2.svg`、`02-price-time-priority.svg`和`02-wire-v1-byte-layout.svg`暂不删除，继续保留此前冻结章的视觉审计历史。

同日返修`02-trading-lab-runtime.svg`的四组箭头：marker改用`userSpaceOnUse`固定尺寸，不再随热路径粗线成倍放大；第一次收小后按投屏反馈放大到主箭头`28×24`、旁路箭头`26×22`，两条热路径仍保持较细的4画布单位。灰色旁路线改为圆角折线，箭头前竖直末段加长到40画布单位，使转折和方向可以同时看清。路径职责与文字内容没有变化。

同日按实机进程边界再次收口两图：`.2 Trader`不再画成同时承载手动与自动的单进程，而是明确为`AUTO/MANUAL`两个C++客户进程、两份Feed状态与两条SoupBinTCP/OUCH会话；首笔交易流程改为历史行情持续回放时并行提交IOC，不再画“暂停历史行情”。

## 2026-08-27正文重审

第02章已经按第01章的最新载体规则收敛：普通流程、状态、分支和证据链改用Mermaid；订单簿、Price-Time队列和52-byte精确偏移改用仓库原生SVG。25张PNG全部保留在本目录作生成历史与语义审计，不因正文撤下而删除。

原`02-02-price-time-priority.png`的业务关系正确，但16:9位图在正文中占幅过大；当前入口改为本目录更紧凑的`02-price-time-priority.svg`，继续保持`S1 100 + S2 50 = B1 150`与剩余`S2 150`。其余PNG或与正文重复，或把内存实验画成真实网络路径，或存在超出代码证据的状态结论，因此不再作为当前教学入口。

## 统一视觉与证据合同

```text
16:9 clean white classroom slide; premium flat-isometric technical illustration;
crisp vector-like edges; restrained depth; deep navy outlines; cyan normal data,
orange mutation or warning, purple identity or state, green pass/evidence;
large English labels readable from a classroom screen.
No logos, watermark, fabricated commands, filenames, hashes, IDs, output values,
field widths or business data. Exact state ownership, arrow direction, byte offsets,
parser order, sequence update rule and idempotency boundary.
```

| 文件范围 | 教学任务 | 硬约束 |
| --- | --- | --- |
| `02-01`～`02-04` | 订单簿、撮合、订单状态与交易前风控 | Best Bid/Ask与Spread使用正文样例；ACK不等于Fill；Cancel竞态保留三种结果 |
| `02-05`～`02-08` | bytes到业务动作与本章五步路线 | 先门禁再Body；sequence与correlation职责分开；不填虚构实验值 |
| `02-09`～`02-11` | session、sequence、correlation身份分类与取证 | 先排除旧session；当前session内再查重；远端证据图不伪造命令 |
| `02-12`～`02-16` | 大端法、52-byte布局与round-trip | Header 32 bytes、Body 20 bytes；offset 0～51逐格服从字段合同 |
| `02-17`～`02-19` | fail-closed门禁、单变量坏包与证据链 | size→magic→version→length顺序固定；Body只在全部通过后解析 |
| `02-20`～`02-22` | duplicate、gap、late状态机与证据 | 固定输入`0,1,2,2,4,3`；未见序号写入`seen`；`max_seen`只取最大值 |
| `02-23`～`02-25` | 订单请求幂等、缓存决策与证据 | `correlation`只做trace；作用域内的`client_order_id`承担幂等职责 |

## 人工返修记录

- `02-03`重画为“正常生命周期 + Cancel竞态三种结果”双面板，删除重复终态和含混交叉箭头。
- `02-05`把生成器误写的标的修正为`AAPL`，并移除与协议无关的企业Logo。
- `02-08`清除生成器添加的随机ID、字段尺寸、订单值与结果值，只保留五站教学路线。
- `02-11`清除虚构的SSH、目录与Python命令，保留取证阶段和三类分类名称。
- `02-13`按字段表重画精确offset，不接受生成器自行分配字段宽度。
- `02-18`删除虚构hex和长度值，重画为四道门禁与三个单变量mutation。
- `02-19`清除虚构文件树和证据文件名，只保留拒绝原因分类与证据阶段。
- `02-21`按真实Python实现纠正状态更新：LATE和GAP也写入`seen`，GAP推进`max_seen`，LATE不降低`max_seen`。
- `02-trading-lab-runtime.svg`把随线宽失控的大箭头改为固定中等尺寸，并给旁路折线留下可见的圆角转折与末段。
- 2026-08-29按四机恢复合同把两张现役SVG中的持久管理机纠正为`.111 / 10.1.1.111`，并明确`.101`工具链由第一章在fresh快照后重新物化。
- 2026-08-29重画`02-trading-lab-runtime.svg`：补上`.111 → .101 构建 → 分发到 .1/.2`；网页看盘与手工单都接到`.2` client；`.1` 的 History/Market/Paper/Execution 改成框内四枚短标签；底部说明条改为浅底深字，避免全局 `text{fill}` 把白字盖成看不见。
- 2026-08-29两张现役SVG的箭头改为`refX`落在三角根部，尖端沿线方向往前伸，避免尖端与线尾平齐、看起来像平头。
- 内置服务出现1次网络失败；使用同一内置服务重试，没有切换到需要API key的CLI。

25张PNG均为`1672×941`并继续保留；本目录5张SVG与25张PNG的30项固定摘要见同目录`SHA256SUMS`。旧“13张主线、12张折叠层”只描述2026-08-23生成时的版式；当前正文没有折叠层，也不再引用本目录PNG。
