# newDoc 课程专用形象图

2026-09-19：第08章3.7改用 UG1301「Alveo Card Features」官方标注图 [08-ug1301-alveo-card-features.png](08-diagrams/08-ug1301-alveo-card-features.png)，原字节 972×776。黑壳侧视裁切与线序示意保留图册，不进正文。

2026-09-19：第08章1.2增加 U250 产品外观 [08-alveo-u250-card.png](08-diagrams/08-alveo-u250-card.png)（课堂裁切 1113×614）；未裁原件 [08-alveo-u250-card-source.png](08-diagrams/08-alveo-u250-card-source.png)。这是产品图，不是实验室现场照片。

2026-09-19：安装图册现14张，新增[AMD 2026.1官方下载页](08-vivado-install/00-amd-2026-1-download-page.png)；正文2.1嵌入为图2-1。该图是同一页上的Stand-Alone / Vivado Lab Edition分区，不是完整Vivado安装器列表。原图字节保留。以下U250 31张记录仍有效。

2026-09-19：U250实作图册现31张，新增28—31电路观察四图，嵌入第08章3.6：器件布局、Schematic入口、模块连接与内部单元。原图字节保留、摘要同步；现有实现结果可查看，无需重新构建。以下27/24张为历史阶段记录。

2026-09-19：现役课程收口为00～08，第八章入口为[FPGA：从代码到设备](../../08-fpga-from-code-to-device.md)。旧FPGA独立正文不在本仓库；第00章课程路线图同步为U250与交换机同属第08章，既有资产目录继续保留。

2026-09-19：U250实作图册现27张，新增25比特流生成成功、26文件属性、27硬件管理器Auto Connect入口，均嵌入第八章3.6/3.7。新工程.bit大小43,573,574字节；Hardware Manager仍未连接目标，实卡编程与收发待验证。下方24张阶段为历史记录。

2026-09-19：U250实作图册现24张；新增[实现完成图](08-u250-walkthrough/24-implementation-complete.png)显示QYT-FPGA工程布线完成、WNS 0.064 ns/WHS 0.010 ns与累计负裕量为0。安装图册现13张，正文采用11张；新增三张CMAC IP许可图，最终状态统一用[ALVEO与cmac_usplus完整列表](08-vivado-install/13-confirm-cmac-license.png)。本轮.bit生成完成、完整约束/规则报告及实卡结果仍按各自证据确认。

2026-09-19：第八章章首总导航改回与第01/03/06/07章相同的正文 Mermaid；`08-course-navigation.mmd/.svg` 保留参考，不再嵌入学生正文。18项、5组编号不变。四张机制图仍为 `08-u250-data-control.svg`、`08-u250-fields.svg`、`08-board-switch-paths.svg`、`08-switch-board-integration.svg`。现役用途与证据边界见[第08章图册](08-diagrams/README.md)，旧图继续保留。

2026-09-19：第八章安装与许可截图十三张归入[安装图册](08-vivado-install/README.md)，正文第2部分嵌入十一张，默认试用入口与仅Alveo状态页保留参考。所有PNG字节保持原样。

2026-09-19：合并第八章1.2用芯片、板卡、交换机、电脑和配置文件图标替换D02占位，显示AMD/Xilinx、Alveo U250、Arista 7135V与Vivado的关系。原生SVG及同源PNG见[第08章图册](08-diagrams/README.md)，800/1200px审阅通过。

2026-09-18：第09章导航补上第08章1.1—1.3共享准备：源码与离线缓存保存在`.111`，开发测试在`.101`；真实行情仍在`.2`，B3/B6区分本地可做与真卡条件。SVG1200×1880、PNG1600×2507，见[第09章图册](09-diagrams/README.md)。

2026-09-18：第08章图02标明可恢复快照的`.101`开发机，以及可执行本地步骤与真机前提；同源SVG/PNG已同步，详见[图册](08-arista-fpga-draft/README.md)。

2026-09-18：第09章以`09-branch-navigation`统一全章导航：共同1—2，左路仿真A1—A5，右路真卡B1—B7；图、标题和14张导航卡对应。旧代码双路线简图与V80构建装载总览保留参考，正文不重复展示。见[第09章图册](09-diagrams/README.md)。

2026-09-18：第08章备选稿合并编译比喻与流程图，图02作为全章1—8步导航；图下逐步说明与后文导航卡一一对应。00b/06保留参考，退出正文重复总览。见[图册](08-arista-fpga-draft/README.md)。

2026-09-18：第08章备选稿工具图改为源码、仿真、板卡适配、构建、打包、安装与装载的连续流程；PDI/SWIX及SystemVerilog/Python职责分开。SVG/PNG同步，见[图册](08-arista-fpga-draft/README.md)。

## 2026-09-18 · 第09章V80与AMD产品图

`09-diagrams/` 新增AMD产品分层、V80寄存器数据路径、Boot/PLD八步装载图，并重绘同一RTL的软件/硬件总览；四图含原生SVG与同源PNG。800/1200px审阅、文字边界、XML与摘要检查通过。当前路线AMR3.0.0/Vivado+Vitis2026.1，图示不提升真卡验证状态；详见子图册与 `refs/evidence/ch09-v80-local-20260918.json`。


2026-09-18：第08章备选稿图04脚注同步为25G，同源SVG/PNG与校验清单已更新；详见[图册记录](08-arista-fpga-draft/README.md)。

2026-09-17 图文同步：第08章备选稿的 `08-arista-fpga-draft/00a-fpga-resources.svg/.png` 已改用判断器、便签和内存比喻；两种课堂宽度审图通过。

2026-09-17 复核：备选稿中的五图已突出隔离台架、网口IP授权、板级前提与逐帧低速验证；参见同一[图册](08-arista-fpga-draft/README.md)。

2026-09-17：独立第08章 FPGA 交换机推演稿新增十张 SVG/PNG，从 FPGA 资源、配置电路讲到字段匹配、整帧过滤、管理寄存器与装载流程。800/1200px 审图；假设效果不对应现役网页。详见[备选稿图册](08-arista-fpga-draft/README.md)。

2026-09-17：第08章 SystemVerilog 小例前新增寄存器连线对照图，以①②标出被移除的中间保存级，展示两拍检查变成一拍并行后的数据连接。SVG 为逻辑示意，PNG 同源；800/1200px 审图通过，未作 FPGA 物理实现。详见[第08章图册](08-diagrams/README.md)。

2026-09-17：第08/09章末各新增一张三案例 SVG 合图，分别讲 FPGA 交换机与 FPGA 网卡的真实应用；同源 PNG 用于正文显示，点击查看 SVG。800/1200px 审图，原始出处写在正文。详见[第08章图册](08-diagrams/README.md)和[第09章图册](09-diagrams/README.md)。

2026-09-17：第07章原行业SVG重画为三案例共图，上方新增EPAM/Deltix交易时延测量，中间Cloudflare、下方Meta。正文以图为主，PNG显示、SVG可点击查看；800/1200px审图通过。[第07章图册](07-diagrams/README.md)

2026-09-17：第07章新增源码查看、编译检查、装载挂载三步命令卡，同一布局在运行②/③/④分别高亮当前步骤。三组 SVG/PNG 均经 800/1200px 渲染检查，保留原图；详见[第07章图册](07-diagrams/README.md)。

2026-09-17：第二章 OpenOnload 讲卡处引用根级实物照 `images/solarflare-x2522-nic.png`，不搬进 `02-diagrams/`。详见[第02章图册](02-diagrams/README.md)。

2026-09-15：第03章 `03-gui-manual-order.png` 换成现役 A/B 网页截图（1874×924），SHA `f786c930d4bded5b099c511eecf8d5f6d8d2f23cc65956914f25c97e78f2a67c`。详见[第三章图册](03-diagrams/README.md)。

2026-09-15 A/B 更新：第 01～03 章共五张 SVG 同步 A/B 双组播，详见各章图册。800/1200px 已渲染目视，当前摘要见 SHA256SUMS；这不是实机抓包证据。

2026-09-15 第03章：`03-mold-envelope-strip.svg` 三行字段条加浅灰外缘，字段不变。详见[第三章图册](03-diagrams/README.md)。

2026-09-15 第02章最新：按用户要求撤下正文中的 IOMMU 图，保留两段说明及启动准备；原 SVG 作为备用保留，图件字节与 SHA 保持。Onload/DPDK 收发对比图继续使用。[第02章图册](02-diagrams/README.md)

2026-09-15 第02章 DPDK 段拆为 B1 隔离准备、B2 软件安装，两张 DPDK/IOMMU 图的页脚同步改成 B1，图形与连线保持。详见[第02章图册](02-diagrams/README.md)。

2026-09-15 第02章当前：新增 Onload、DPDK 收发对比图，重画 MMU/IOMMU 图；修复连线与图标压字。三机图放运行①上线后，AUTO图放运行②盘口后，接管下方同日章首安排；部署分发与“先启动再下单”图退出正文，原件保留。详见[第02章图册](02-diagrams/README.md)。

2026-09-15 第02章：章首以三机平面图说明行情、独立自动/手动订单、网页控制与状态上报；新增 AUTO 策略图，按买一/卖一数量和默认限制解释何时下单。原部署职责留在运行①。详见 [第02章图册](02-diagrams/README.md)。

2026-09-14 第01章顺稿：流量图改为章末查阅，国内接入图随选读扩展后移；所有图件字节与编号保持，详见 [第01章图册](01-diagrams/README.md)。

## 2026-09-14 · 第01章流量图只改顺序

`01-diagrams/01-traffic-flows-and-ports.svg` 保留 8 组 14 箭头与原画风，仅按课堂先看顺序重排编号：下单、行情、浏览器、切换、进程命令、SSH、LANZ、进度上报。几何规则仍为 12×12 箭头与框外 12px。

## 2026-09-12 · 当前00～09章

原监控章退出主线，原05～10图片目录与文件前缀顺次改为04～09。新第四章保留软件机制图，重新整理课程衔接、三点计时与预热采样三图；第一章接线/通信图去掉监控看板服务，通信图现为8组14条箭头。原监控图位于 `archive/04-diagrams/`。

下方带日期的条目保留当时的章号和验证身份；现役章节以 [课程目录](../../README.md) 为准，路径迁移见 `refs/evidence/chapter-renumber-20260912.json`。

2026-09-12 最新：新增用户提供的网页原图 `03-gui-manual-order.png`（1984×1012），仅从原文件screenshot_20260912_112345_20260912_112404_265317.png改名移动，SHA256 a0b7822f2e40b410d3c4622fe11b421fca64956184b4d3ff909c3b1abb32cb33。图中①为右侧手动下单面板；运行③导航后说明网页可下单、脚本自动提交一股。当前第三章9图，原SVG均保持；800/1200px目视、两级58/257项SHA通过，收据chapter03-first-order-connection-fix-20260912.json。

2026-09-12 最新：用户要求保留两张 Wireshark 风格详情树。`03-order-packet-details.svg` 已重新嵌入运行③，位于脚本与三块订单输出之间；行情树、六类型图和 O/A/E 时序图均保留，正文共8图。本轮所有 SVG 字节保持；订单树14行再对照历史解码一致，800/1200px目视通过，两级SHA仍有效。新收据 `refs/evidence/chapter03-light-edit-restore-tree-20260912.json` 接管下方“订单树仅在补充阅读”的展示范围。

2026-09-12 当前：订单交互图 `03-ouch-request-receipts.svg` 改为 1200×635，只画 O 请求、A 受理、E 成交三条业务消息，与终端分块对应。纯 ACK、完整包数与订单请求详情树移至补充阅读；正文现用7图，行情解码树保留。三箭头保留12×12用户坐标头部、2.5线宽、尖端距目标线12；800/1200px目视通过，灰蓝文字与浅色图框保持。收据 `refs/evidence/chapter03-order-message-display-20260912.json` 接管下方“四帧交互图/8图”的当前展示说明；历史pcap仍为9帧，未改写。

2026-09-12 最新：第三章8图主文字统一为灰蓝色，Packet Details标题栏改浅色。`03-ouch-request-receipts.svg`压至1200×740，按历史pcap帧1～4展示O/A/E/纯ACK；三模式图直写都用UDP，Mold的Session改称会话标识。8图均经800/1200px目视，当前摘要见SHA256SUMS；最新收据 `refs/evidence/chapter03-final-flow-polish-20260912.json`。下方同日尺寸与摘要记录保留各轮历史身份。

2026-09-12：恢复两张 Packet Details 解码树：`03-market-packet-details.svg`（1200×844，09-10行情第9帧，19行）、`03-order-packet-details.svg`（1200×664，09-10订单第1帧关键14行）。从原pcap重解码逐行核对，沿旧树形风格排版，非Wireshark截图；旧03-wireshark-*保留历史身份。两图800/1200px目视通过，当前第三章8图；收据见 `refs/evidence/chapter03-concise-packet-trees-20260912.json`。

2026-09-12：六类型共图保持布局、偏移和宽度；六处跟踪号填示例0，四处价格填报文整数2044800，删除格内“不判丢包”及“÷10000”。股票代码填NVDA，E/P成交编号填9001/9002；字段含义、补空格及价格换算放第三章图后表格；示例不冒充抓包。SHA256：`65b4b6af34dbb8d8ed631d77780f29b101706a6c11434485ecdca38bbe285335`。

2026-09-12：`03-diagrams/03-mold-envelope-strip.svg` 改为 1200×860 三层横条，IPv4 目的组播 `233.74.125.32`、UDP 目的端口 `31032`，Mold 载荷五格保持 58 字节示意。无箭头、无新抓包。详见[第三章图片说明](03-diagrams/README.md)。

2026-09-11 当前：第一章扩展只保留两张国内图；美国正文与 Cboe 嵌图已撤下，历史资产留存。`01-cn-access-relationships` 展开VDE实时/重建端口、VSS和SDS的分工；`01-sse-access-delivery` 展开独立UDP行情、交易线上的备用TCP行情及适用条件。两图均有SVG源与PNG显示版，不将备用许可画成自动切换。目录56项、总清单254项，详见[第一章图片说明](01-diagrams/README.md)。

2026-09-11 历史九图阶段：第一章曾使用9张`01-diagrams/01-market-*.svg`，展开国内交付/流量、cross-connect、Cboe四层、组播、PITCH恢复、订单容灾、出口队列、授时观测。当时总清单240项、第一章42项；该阶段结果保留历史身份，不提升课程设备验证状态。

2026-09-11 第一章国内图只将承载标签明确为“交易接入：局域”，布局、箭头和美国图字节保持；行情不按托管位置推定接入产品。两图44文字/800与1200px、正文940/390px检查通过，33/231两级SHA更新通过。新收据design/evidence/chapter01-network-review-20260911.json；不改写9月10日旧收据。

2026-09-10 第一章新增短扩展两图：`01-diagrams/01-china-market-access.svg` 与 `01-diagrams/01-us-market-access.svg`，均1200×680、三列同款卡片与12px箭头。按公开材料归纳客户—券商—市场连接，订单/行情分开；原图不直接嵌入课程。800/1200px目视与44文字/8箭头几何、940/390px正文图框通过，第一章目录33项与本级231项SHA通过。来源和边界见第一章图片README及design/FLLE_Trading_Network_Access_2026-09-10.md；无设备实验。

2026-09-10 用户纠正图形含义：一种ITCH消息一条，条内字段横向分格；六条紧邻在同一张 `03-diagrams/03-itch-type-strips.svg`（1200×1350）。Mold另用一条短图 `03-mold-envelope-strip.svg`（1200×460）。第3/8/9/10章均直接嵌入六类型共图，过滤看A行；前版七张字段长图退出正文但保留原字节，第三章当前6图。两图800/1200px、227文本边界及目视、55/229两级SHA通过；无箭头、无设备实验。下方每字段一条的记录已被用户否决，不是当前要求。详见03-diagrams最新登记与design/evidence/chapter03-type-strips-20260910.json。

2026-09-10 第三章字段图解调整：现役11图，Mold和A/F/E/D/U/P分别独立展示，撤掉三张字段表；共享A图1200×1624，由第3/8/9/10章直接嵌入。其余新图尺寸与用途见03-diagrams最新登记；含开场图共八图800/1200px渲染、465文本边界与六箭头12px间隙及目视通过。两级53/227图片SHA通过。当前图数/尺寸由本条接管下方历史版本；无设备实验，收据design/evidence/chapter03-field-reading-20260910.json。

2026-09-10 第三章开场补 `03-diagrams/03-protocol-and-envelope.svg`（1200×720）：四份官方规范分成行情/订单两套，MoldUDP64 封装 ITCH，SoupBinTCP 封装 OUCH。无箭头，只画套叠关系；正文现用五图，旧图保留。800/1200px 目视与两级 SHA 同步；无设备实验。

2026-09-10 第三章协议顺稿：新增 `03-diagrams/03-market-packet-fields.svg`（1200×1400）与 `03-ouch-request-receipts.svg`（1200×1130）。前者由第三、八章直接共用，第九、十章同源链接；协议字段与过滤开关分开。后者区分 Soup U/S、OUCH O/A/E 与客户端/Exchange 四类编号。两张现有第三章总览/三模式图只修职责及术语，几何不改；正文现用四图，旧图保留。四图800/1200px Chrome目视、字段偏移/RTL位切片与新图三箭头12px间隙通过，两级SHA同步；无设备实验。来源及替换范围见 `03-diagrams/README.md` 与 `08-diagrams/README.md` 本日条目。

2026-09-10 评估收口：第二部分两图尺寸保持 1200×1000 / 1200×830。准备 A 第④行补蓝框与 SSH 虚线箭头、统一目标框绿色，共四支跨主机箭头；IOMMU 图上层改灰色步骤先后线，下层图例限定访问/映射与 DMA，内存框改为对象描述，共六支箭头。十支箭头几何和 800/1200px Chrome 渲染目视通过，两级 SHA 同步；源码、实机和历史输出不变。详情见 `02-diagrams/README.md` 最新条目。

2026-09-10：第二部分准备 A 新增 `02-diagrams/02-runtime-prep-steps.svg`，两列按①～⑤交代管理机/目标机的任务、分发内容与产物；先.1后.2，公网下载0，编译在目标机。800/1200px目视通过，两级SHA同步，原安装脚本未改。

2026-09-10：第二部分准备 B 新增 `02-diagrams/02-iommu-vfio-dpdk.svg`，分开提前准备、VFIO 接管网口和 IOMMU 约束 DMA 内存访问。800/1200px 渲染与六支箭头检查通过，两级 SHA 同步；运行脚本和现场状态不变。

2026-09-10 DEC-427：流量图 `/metrics · 第04章` 改为 `/metrics · 第四部分`，与正文及附录统一；图形几何、端点与编号保持，800px/原尺寸目视和两级SHA通过。

2026-09-10：第一部分运行②③新增 `01-diagrams/01-interface-identities.svg` 与 `01-diagrams/01-driver-ownership.svg`，替换对应Mermaid。统一平面网卡和工具图标，原身份字段与实线/虚线关系保留；800/1200px目视和两级SHA（31/216）通过。

2026-09-10：`01-packet-and-evidence.svg` 增加①DMA、②中断通知、③读取、④a抓包、④b回应五个箭头编号；正文同步编号表。800/1200px目视通过，原几何与12px箭头间隙保持，两级SHA同步。

2026-09-10 DEC-420：设备总览明确 .1/.2/.11 及 ESXi vSwitch 管理连接，删去管理物理上联待确认提示。

2026-09-09 DEC-418：01两图统一设备名“监测 VM · .101”，内部服务用网页后台/Gateway、LANZ等说明；⑧保留同机三服务关系。两图800/1200与208文字边界通过，结构/箭头不变，两级SHA29/214同步。收据 `refs/evidence/monitor-vm-naming-20260909.json`。

2026-09-09 DEC-414：00总结图改①DMA→②IRQ通知→③④取数处理→⑤应用读取，A～D保持；描述与正文图注同步，限定常见中断驱动路线。800/1200、32文字边界、五箭头、74卡、SHA29/214通过，无实验。报告 `refs/FLLE_Receive_Order_2026-09-09.md`。

2026-09-09 DEC-413：三张00现役SVG补中文（英文）重要标签，Onload图两处Socket接口实现对照并延长库框；正文压短和减少加粗。三图800/1200、77文字边界、12箭头、74卡及SHA29/214通过，十图总数保持，无实验。报告 `refs/FLLE_Socket_Labels_2026-09-09.md`。

2026-09-09 DEC-412：第零部分旁路段新增1200×920网卡/CPU软件分工SVG，两编号与两行表，明确Onload协议库在应用进程内、网卡仍收发/DMA及内核资源职责。原九张图保持，全文10图；800/1200、18文字边界、74卡和SHA29/214通过，无实验。详见 `refs/FLLE_Onload_Hardware_Software_2026-09-09.md`。

2026-09-09 DEC-411：第零部分第5节换普通收包厨房SVG，另拆RSS/通知高级延伸SVG并独立编号；第6节图内恢复清单/DMA/缓存/CPU/应用、标A～D等待点。Onload对照SVG退出正文留历史，旁路在正文只留入口。Socket用词统一，正文9图；三图800/1200、71文字边界、12箭头、74卡与SHA28/213通过，无实验。详见00-diagrams/README和 `refs/FLLE_Receive_Waits_Flow_2026-09-09.md`。

2026-09-09 DEC-410：第零部分新增普通收包/Onload对照SVG（1600×1660，八箭头）及内存/通知概要SVG（1200×690，三箭头），替换正文原00-17/00-20 PNG，原文件保留历史。图中直接表达缓冲区、通知、驱动批量取包、协议/队列、应用接口、库加载与内核职责，正文八行表对应。平面图标；800/1200、57文字边界、74卡及SHA26/211通过，无实验。详见00-diagrams/README与 `refs/FLLE_Network_Bypass_Basics_2026-09-09.md`。

2026-09-09 DEC-409：调度SVG按用户要求统一平面构图，候选架/调度面板/处理器/暂停区全部纯色正视，删除立体侧面与阴影。1200×940、五箭头及精简文字保持。800/1200、22文字边界、74卡、SHA24/209通过，无实验。下方为前版记录。

2026-09-09 DEC-408：调度SVG参照原PNG立体构图重画（1200×940），使用线程候选架、彩色标牌、金属选择机构、两块处理器及较小等待区。全中文、五编号箭头；①～③突出执行前等待。图后解释区370→192汉字。800/1200、21文字边界、74卡及SHA24/209通过。原PNG保留，下方DEC-407等为前版记录。

2026-09-09 DEC-407：第零部分调度SVG现为1200×920，主图突出已就绪线程等待调度、CPU才开始执行，橙色括线标记开始前的等待；执行中等数据缩为底部补充。两编号箭头与正文表同步。800/1200预览、19文字边界、74卡及SHA24/209通过，无实验。下方DEC-406/405是先前图形版本。

2026-09-09 DEC-406：`00-diagrams/00-scheduler-thread-states.svg` 重画为1200×900四时刻连续过程，上排甲的进度保留，下排同一处理器依次执行甲/乙/乙/甲。三编号箭头对应图下三行表；图标改为执行记录与处理器。800/1200预览、31文字边界和SHA24/209通过，无实验。下方DEC-405是被本轮替换的图形版本。

2026-09-09 DEC-405：第零部分第4节替换为 `00-diagrams/00-scheduler-thread-states.svg`（1200×1000），四种原生图标、全中文标签、五条编号箭头。正文仍八图，旧调度PNG保留历史。800/1200预览及两级SHA24/209通过，无新实验。

2026-09-09 DEC-404：第零部分新增 `00-diagrams/00-page-write-code-walkthrough.svg`（1200×1690），A～E代码动作与内存变化对照，C关联前图⑤/⑥。正文增至八图，代码前置讲解整合为图与计数说明，完整代码同步中文注释；旧图保留。两级SHA同步，无实机实验。

2026-09-09 DEC-403：第零部分地址翻译图新增原生 `00-diagrams/00-address-translation-numbered.svg`，1200×1270，六种矢量图标、七条编号箭头；正文七行表逐条说明，整合命中/缺页分类及大页承接。原 `00-diagrams/00-03-tlb-translation.png` 保留历史身份并退出正文，图册及两级SHA同步。无新设备实验。

2026-09-09 DEC-398：第01总图改为设备/IP/接线总览（1200×1850），删除流量速查和后续实验索引，保留设计未接入的 7130/U250。四个插座使用真实接口名，标签框加宽，距网卡框及设备底边均 24px，设备外框加宽、延长，右侧双接口外侧各留 24px。通信详情仍在独立通信图；正文图注、两级 SHA 与800/1200px审图同步。历史条目保留当时版本身份。

2026-09-08 DEC-393：01 总览与通信图、02 真实 Nasdaq 传播图及应用图、03 单接收器模式图、08 字段图、10 模型/真卡接收图统一更新。真实厂商 logo 保留；所有现役行情端点为 `233.74.125.32:31032` 与 `.2:42121`，控制服务为 `.2:48606`。旧抓包图明确标为历史样例。


2026-09-08 DEC-392：第01章新增独立`01-diagrams/01-traffic-flows-and-ports.svg`（1200×2630），TCP蓝/UDP橙、9组通信16条编号箭头，节点源目的地址与监听端口齐全；正文新增逐箭头16行用途表。LANZ建连与事件流反向分别画；Grafana查询按配置标`127.0.0.1:9090`。800/1200px、图表编号/箭头几何/104文字边界、实际表解析与31围栏保持通过，正文7图、中央205/局部29项SHA。旧物理拓扑仍负责接线，8089改称LANZ API。

2026-09-08 DEC-391：按用户要求在第01总图加入官网下载的 AMD、Broadcom、Arista 原版 logo（3原件、6处逐字嵌入），为本图接管历史 `no logos` 约定；管理横框四侧留12px、X2522插座补口0/口1。后台端口明确 `.111:48606` 承接 `.101` 网页切换请求，`.101:46120/UDP` 收交易事件，LANZ 则由 `.101` 主动连接交换机 `.253:50001/TCP`。800/1200px、118文字边界、31围栏、中央204/局部28项SHA通过；来源与原件摘要见第01图册README。

2026-09-08 DEC-390：第01章原 `01-diagrams/01-physical-topology-host-owned.svg` 扩充为全课程设备、地址与接线总览（1200×2530）。统一自绘图标，补齐 `.111/.101/.11`、Arista 四口、服务端口、P4 VLAN 切换和未接入的 FPGA 延伸；管理虚线与四根 DAC 分开，接口留在所属 VM/设备内。800px/1200px 审图、XML、正文围栏保持与中央201/局部25项摘要通过。未改设备或实验代码；依据与边界见第01章图册 README。

2026-09-07 DEC-377：第00～10章全课顺稿新增8张图标化原生SVG（00/01/02/03/04/06各1，07两张）。对应章节README登记替换关系；旧图不删。800/1200px逐图审查，箭头固定用户坐标、尾部相接、尖端停框外；中央与局部摘要同步。第05/08/09/10现有机制图保持，沿阅读顺序调整说明。无新设备实验。

2026-09-07 DEC-369：第10真卡部分改具体操作，保留真实数据路径图；构建/缓存两图只在工程补充引用，学生正文6SVG、目录12图。没有图片字节修改或新增渲染；核对引用与193/13项摘要。台架操作单和硬件边界见第10配套材料。

2026-09-07 DEC-368：第10运行①改中文任务并接回前文规则/额度/控制指令；旧XDP/软件/真卡对比图撤正文留教师参考，新增`09-filter-result-check.svg`（1200×650）解释丢弃与缺失序号对账。示意101/102/103非实测，历史505不改。800/1200px审图，两箭头遵DEC-365；正文8SVG、目录12图，中央193/局部13摘要，无新实测。

2026-09-07 DEC-367：第10新增`09-one-shot-filter-control.svg`，后续扩为1200×1020：上层脚本启动进程/写控制文件、C++读block给模型一次额度，下层三阶段展示放行/丢一次/继续放行。实现变量和格式检查移教师说明，用户确认保留NVDA案例。800/1200px审图，九箭头遵DEC-365；正文8SVG、目录11图，中央192/局部12摘要，无新实测。

2026-09-07 DEC-366：第10原Ready/Valid图重画C++原始报文路径与模型判决往返；模型内显示valid/ready/时钟接收条件及remaining_drops/drop_count。1200×1450，ready先按“准备好接收”定义；八条箭头遵守DEC-365。800/1200px及局部目视，正文7SVG与目录10图不变，无新实验。

2026-09-07 DEC-364：重画第10原`09-ready-valid-handoff.svg`（1200×1480），说明同一个模型保存额度、valid/ready由谁提供、时钟上升沿和首包丢弃/后包放行。800/1200px审图；正文7SVG、目录10图片与路径保持，无新实验，来源见10图册README。

2026-09-07 DEC-363：原第10字段图`09-rtl-filter-circuit.svg`扩为1200×1510，以代码来源、一个程序中的调用、内部比较逻辑三层解释生成C++与手写适配代码。800/1200px目视复核；正文7SVG、目录10图片文件与引用路径保持，来源和边界见10图册README，无新实测。

2026-09-07 DEC-361：第10新增`09-rtl-verilator-fpga-overview.svg`，章首用同一设计分成CPU软件模型和FPGA硬件配置两路；原收包位置图移运行①替换重复Mermaid。现正文7SVG、目录10图片文件，800/1200px审图通过。`.2`编译/自测已实测，真卡仍设计未实测；详情见10图册与教师说明。


2026-09-06 DEC-360：第10按第09风格收短正文，新增中文图标Ready/Valid SVG并保留旧PNG；原真卡路径SVG重画NVDA行情进入U250、缓存/过滤、PASS到DMA与主机配置。当前第10正文6SVG、目录9图片文件，真卡为设计未实测，任务仍为同一NVDA过滤。详情见10图册README。

2026-09-06 DEC-359：第09图文件保持原样，理论图分别移到运行①②导航后；VLAN三态SVG补紫卡和统一800px灰框，800px重渲染审图通过。当前7图/目录14文件，规范、ITCH、Tofino生命周期与固定BMv2实现来源见09图册README；仅图文编排与公开资料核对。

2026-09-06 DEC-358：第09原FPGA案例图展开为一张安装/装载总图（1200×1750）：开发机代码与包、设备存储、CPU上的MOS/Python调用、FPGA六类功能电路及请求回复路径。准确区分应用no shutdown、网口no shutdown和寄存器参数；来源与审图记录在09图册README。文件与正文图数不变。

2026-09-06 DEC-357：第09硬件节改为Netnod在Arista7130-48LB上的具体NTP案例。原08-arista-fpga-path.svg重画CPU过滤/机内FPGA报时对照，撤旧journey正文引用并保留资产；当前7图（3PNG+4SVG）、目录14文件。固定版本与依赖边界见09图册README及ARISTA-HARDWARE-NOTES.md；外部部署有官方依据，本课未硬件复现。



2026-09-06 DEC-355：第09按用户最终要求收为NVDA策略简述与关键代码，撤09-13/09-17 PNG正文引用，旧图留档，无新图。正文7图（3PNG+4SVG）、目录13图片文件；图册README记录旧图适用边界与源码依据。



2026-09-06 DEC-351：第09章开头新增两张原生 SVG 与同源 PNG。`09-asic-p4-fpga-programmability` 用固定灰框和紫色可改内容比较传统 ASIC / P4 可编程 ASIC / FPGA，FPGA 以相同资源格子展示两种逻辑连接；`09-p4-software-and-hardware-targets` 区分 BMv2 的 CPU 与 Tofino 的 ASIC 执行。正文引用 PNG，原09-20/09-25撤正文留档。第09正文仍8图（5PNG+3SVG），目录12图片文件；800/1200px审图、来源复核及静态检查通过，无新设备实验。来源、边界与重渲染方式见09图册README。

2026-09-05 DEC-347：第08行业主图换为`08-diagrams/07-xdp-real-world-cases.svg/.png`，讲Cloudflare L4Drop防攻击与Meta Katran分配访问流量的业务用途；AF_XDP技术图转补充。正文仍11图（8PNG+3SVG）、目录23图片文件；官方案例来源/800px目视通过，无新设备实验。

2026-09-05 DEC-346：第08行业节原AF_XDP资源图由`08-diagrams/07-af-xdp-explained.svg/.png`替换，比较普通UDP交付行情载荷与AF_XDP交付完整帧，旧图留档。当前正文11图（8PNG+3SVG）、目录21图片文件；800px目视、官方资料复核通过，无AF_XDP现场验证。

2026-09-05 DEC-345 补充：第08新增`08-diagrams/07-live-steps-and-evidence.svg/.png`，正常脚本七步与输出对应，历史丢1包/同序号GAP在中心框突出；正文结果表合入图。最终第08正文11图（8PNG+3SVG），目录19图片文件，800px目视通过，无新实机结果。

2026-09-05 DEC-345：第08运行⑤的共享额度图、接口/program/map图撤出学生主线，原文件保留为教师参考。当前第08正文10图（7PNG+3SVG）、目录17图片文件；不新增或重画图。

2026-09-05 DEC-344：第08新增`08-diagrams/07-parser-safety-and-policy.svg/.png`，替换运行③通用Verifier/JIT课件图，框内中文+C条件解释装载安全审核与逐包策略；PPT07留作参考。正文图数不变、目录17图片文件，800px审图通过，无现场实验。

2026-09-05 DEC-343 释义补充：报文图明确Stock字符/空格各1B，NVDA加4空格填满8B；Locate标为行情内部编号，当日固定、跨交易日可能重新分配。图尺寸及引用数量不变。

2026-09-05 DEC-343：第08报文图`08-diagrams/07-shared-filter-wire.svg`重画并新增PNG显示版，移到运行②字段/样例解释之前，运行③回指同图；共12张正文图，协议与一次性规则、占位样例边界见局部README。800px目视通过，无新现场实验。

2026-09-05 DEC-333：第08章改为客户端 `.2` 的 native XDP；装载/RX 图的 PASS 终点改成行情程序，横向比较图明确 `.2` 驱动。两图已在 800 px 渲染复核，图数不变；PPT 原图与 map 解释保留。

> 最新更新：2026-09-02
> 生成方式：Codex内置`imagegen`与仓库原生矢量图；位图用途分类统一为`scientific-educational`
> 使用边界：这些图片负责建立角色、路径与因果位置的直觉，不替代命令输出、pcap、counter、VCD或RUN证据。

当前章首图与正文使用的课程原生 SVG，统一摘要见本目录 `SHA256SUMS`；每张 SVG 也纳入所属章节目录的摘要清单。历史 PNG 的完整摘要保留在各章目录。

## 第00章Mermaid替换试做

2026-08-22按用户要求先处理第00章：该章原20张Mermaid已全部替换为20张独立的`1672×941`PNG，包括概念图、实验逻辑图、证据归属图和结案总图。新增资产位于`00-diagrams/`；统一prompt、逐图约束、人工返修记录和20/20摘要分别见`00-diagrams/README.md`与`00-diagrams/SHA256SUMS`。

第00章视觉方向经用户确认后，2026-08-22继续处理第01章：原20张Mermaid已全部替换为20张独立的`1672×941`PNG。资产、逐图逻辑合同、人工返修记录与摘要见`01-diagrams/README.md`和`01-diagrams/SHA256SUMS`。

2026-08-25重新审查第01章全部正文图片：当前正文保留DAC照片，并在`01-diagrams/`新增1张可编辑的主机归属拓扑SVG；交易链、端到端路径、NIC身份、Driver owner、pcap边界和章节导航使用Mermaid。流程与证据链优先使用可维护的Mermaid；拓扑必须先保留设备包含关系和准确端点，Mermaid不能稳定表达时使用原生SVG。

2026-08-29：第01章环境提醒补入两张用户提供的 `.1` vSphere 编辑页截图（`1024×824` JPEG），Reservation 现场值为 `9200 MHz`，Latency Sensitivity 为 `High`。第五章隔离图同步把 `4 × 2350` 改为 `4 × 2300`。

2026-08-23继续处理第02章：原25张Mermaid已全部替换为25张独立的`1672×941`PNG，其中13张位于投屏主线、12张保留在原有折叠实验/审计层。图片覆盖市场微观结构、订单状态、52-byte字节合同、fail-closed、sequence分类与correlation幂等；逐图逻辑合同、返修记录与摘要见`02-diagrams/README.md`和`02-diagrams/SHA256SUMS`。

2026-08-27按第01章的最新载体规则重新审查第02章：正文现用8张Mermaid与`02-diagrams/`内3张可编辑SVG，不再引用PNG。订单簿、Price-Time队列与精确52-byte布局使用小尺寸SVG；业务泳道、生命周期、导航、身份、Header门禁、sequence与幂等使用Mermaid。原25张PNG继续留在`02-diagrams/`作历史审计。

2026-08-27晚按设计脊椎第4节重写第02章后，正文载体收敛为6张Mermaid与`02-diagrams/`内3张可编辑SVG，仍不引用PNG。三张SVG（订单簿L1/L2、Price-Time、52-byte布局）全部保留；Mermaid减为最小消息链、章节导航、消息身份、Header门禁、sequence分类与幂等时序。撤下的是订单生命周期泳道图和旧链路取证流程图——对应的订单类型、Pre-trade Risk与pcap取证小节已随本次重写移除。

2026-08-28按新的课程基线重写第02章：正文只使用2张Mermaid和`02-diagrams/`内新增的2张可编辑SVG。`02-trading-lab-runtime.svg`分开C++热路径、Python旁路与管理机持久真源；`02-snapshot-restore-flow.svg`固定快照恢复到首笔交易的验收链。旧3张SVG和25张PNG继续留在章节目录作历史审计，正文引用为0。

同日对`02-trading-lab-runtime.svg`做投屏返修：四组箭头改为不随线宽放大的固定中等尺寸marker，两条热路径收细，灰色旁路的圆角转折和末段加长；首轮小箭头按用户反馈放大一倍，架构语义未改。

随后按实机进程边界把`.2`侧改为AUTO/MANUAL两个独立C++客户进程、两条订单会话；恢复图的首笔交易也改为行情持续回放时并行下单。两图不再暗示验收会暂停市场或把手动与自动塞进同一进程。

同日继续处理第03章：原29张Mermaid已全部替换为29张独立PNG，其中14张位于投屏主线、15张保留在原有折叠实验/审计层。图片覆盖Snapshot/Incremental恢复、UDP sequence、TCP framing、ORDER/ACK/Execution、Multicast membership、IPv4组地址映射、Feed A/B first-valid/补缺/真gap及交换机证据边界；逐图逻辑合同、返修与拒收记录、尺寸说明和摘要见`03-diagrams/README.md`与`03-diagrams/SHA256SUMS`。

2026-08-27按第02章新钉死的「到达分类不等于按序交付」口径复核第03章图片，替换其中3张语义与脚本不符的PNG：`03-22-first-valid-decision.png`画了`PUBLISH ONCE`、`03-23-first-valid-logic.png`画了`publish_count=1`与`downstream publishes`、`03-25-feed-b-recovery.png`写了`continuous logical sequence`，而第03章脚本只做到达分类与`accepted`登记，没有任何下游发布动作。`03-diagrams/`内新增3张仓库原生SVG（`03-first-valid-decision.svg`、`03-first-valid-logic.svg`、`03-feed-b-recovery.svg`），统一`max-width:800px`，只描述「结构门禁 → sequence 去重 → 登记首份合法来源 → accepted keys 覆盖范围」。原3张PNG继续留在同目录作历史审计，不再被正文引用。

2026-08-27深度重构并完成跨章实验去重后，第03章正文载体收敛为5张小型Mermaid与`03-diagrams/03-first-valid-decision.svg`一张现用原生SVG，PNG引用为0。原29张PNG与另外两张SVG全部留在章节目录作历史审计，不删除；其中旧first-valid、裸`PRE/JOINED/POST`、B只发4和旧证据链图已与新脚本不匹配。现用SVG统一`max-width:800px`并改为按`(session, sequence)`去重；章节导航、TCP framing/请求链、membership时序和gap后恢复边界使用可维护Mermaid。`gap / duplicate / late`分类图只留在第二部分的唯一实验中，第三部分不重复。

2026-08-28第三章改为复用在线Trading Lab的三次真实流量取证：新增`03-live-traffic-map.svg`、`03-market-transport-modes.svg`与`03-ouch-order-lifecycle.svg`，分别对应双业务通道、单播/组播/双路真实复制关系和两条长连接并存时的SoupBinTCP/OUCH `O/A/E`状态链。正文只引用这3张新SVG并限制`max-width:800px`，旧29张PNG与3张旧SVG继续留作历史审计。投屏逐轮返修后3图marker均以`userSpaceOnUse`固定：全宽图`32×24`、三栏图`26×20`；三栏图不再使用贝塞尔曲线，所有消息线均为正交折线。中央摘要现为25/25，第三章局部为35/35。

2026-08-29运行 ③ 补 `03-ouch-order-ids.svg`：只回答 UserRefNum / ClOrdID / Match Number 由谁决定、出现在 O / A / E 的哪一条。现用第03章正文图为十张原生 SVG。

同日继续处理第04章：原29张Mermaid已全部替换为29张独立PNG，其中11张位于投屏主线、18张保留在原有折叠实验/审计层。图片覆盖延迟区间、跨机时钟边界、raw与warmup资格、nearest-rank、相同mean不同Tail、累计Histogram、Metrics/Logs职责、Prometheus主动scrape与`up`边界、RUN_ID三态时间线及Grafana panel来源映射；逐图逻辑合同、返修与拒收记录、尺寸说明和摘要见`04-diagrams/README.md`与`04-diagrams/SHA256SUMS`。

同日继续处理第05章：原32张Mermaid已全部替换为32张独立PNG，其中13张位于投屏主线、19张保留在原有折叠实验/审计层。图片覆盖Cold/Hot Path、动态分配与预分配、slot所有权、Mutex/Condition、SPSC release/acquire、RSS配置与逐包证据边界、queue/IRQ/CPU三层位置、NUMA局部性、process affinity及公平A/B合同；逐图逻辑合同、返修与拒收记录、尺寸说明和摘要见`05-diagrams/README.md`与`05-diagrams/SHA256SUMS`。

2026-08-28按真实 Trading Lab 重写第05章后，正文撤下全部旧PNG，新增4张可维护SVG：全课优化位置、三点计时合同、三种真实订单队列和RSS/IRQ/order-thread位置。四图统一`max-width:800px`，箭头固定为20×16且连接只用直线/正交折线；旧32张PNG暂不删除，继续作历史审计。中央摘要增加至32/32，第05章局部摘要为36/36。

第06章历史上生成过37张独立PNG；2026-08-31当前正文已收口为3张原生SVG + 3张经逐图复核的PNG，其余PNG只作历史审计。当前六图分别服务章间交接、课程位置、四门边界、Kernel syscall证据、Onload回退与PCI所有权；逐图合同、退役边界和摘要见`06-diagrams/README.md`与`06-diagrams/SHA256SUMS`。

2026-09-02按网络工程师课堂主线重构第07章，2026-09-03～04继续补 Fan-in、真实订单 QoS 与 PTP 教学图。当前正文使用本目录7张PNG与14张仓库原生SVG；PTP 主线只保留 NTP/PTP 对照和完整实验两张 PNG，其余时间戳、PHC、TC correction、生产时间链与旧版整章总览继续留盘审计。QoS 图仍把 Socket DSCP 打标、Et2 trust、FM6000 TC 映射、显式 strict Q5 和共享出口队列证据串成完整链。全章当前共引用本目录21张与设备照片2张，即23个唯一图片引用；按“课程视觉资产”口径排除2张设备照片则为21张。图集合同和摘要见`07-diagrams/README.md`与`07-diagrams/SHA256SUMS`。

2026-09-05 第08章：现役 8 PNG + 3 SVG；模式图改用同源PNG显示，SVG保留为源文件。按 DEC-338 新增 `07-xdp-modes-and-skb.svg`，现按DEC-340先画未挂载XDP的普通收包，再对照三个挂载位置，突出本课Native在skb前执行；Offloaded标明当前卡/驱动组合不支持。DEC-330 的 map 身份图、DEC-329 的内核分层/Hook/验证三张课件图继续保留。原 `08-11` 留作参考，目录共 23 个图片文件；旧 ICMP/九槽/RUN 图仍按 DEC-275 退出。当前以 `08-diagrams/README.md` 与局部摘要为准。

2026-09-06 第09章：现役 3 PNG + 4 SVG；硬件节使用Netnod/7130-48LB实际应用案例的机制图，既有BMv2路径独立展示。当前图集与历史资产边界见 `09-diagrams/README.md`。

2026-09-05 第10章（DEC-334）：正文使用 1 PNG + 5 SVG，另保留 2 PNG 参考图。新增软件模拟/真卡三行对照：模型在 socket 后、临时组播转单播；真卡设计在 DMA 前、保留原组播订阅。其余 RTL 电路、U250/OpenNIC 路径、整帧缓存与镜像装载图保留；现役核心没有 FIFO，不沿用旧 160-bit/四槽模型解释它。U250 真卡方案仍待验证；当前图集见 `10-diagrams/README.md`。

原第11、12章的专属图不在本仓库图集中，不计入现役图集。

## 统一视觉合同

所有图片采用白色课堂背景、16:9横图、深蓝设备轮廓与一致的路径颜色：

| 颜色 | 固定含义 |
| --- | --- |
| 青色 / 蓝色 | 行情、正常报文或热路径 |
| 橙色 | Order请求或设备所有权交接 |
| 绿色 | ACK/Execution、PASS、恢复或健康状态 |
| 红色 | Drop、队列、burst、fault或慢路径 |
| 紫色 | 时间、控制面、map、waveform或内存 |
| 灰色虚线 | 管理/观测旁路，或被绕过的通用入口 |

图形合同：**普通流程、关系、分支和证据链优先使用Mermaid**；只有事件先后或报文方向使用箭头，物理连接和对象归属使用无箭头线。拓扑图先表达设备容器、接口归属和准确端点；自动布局无法保持这些关系时使用可编辑SVG。需要体现CPU、内存、NIC内部位置或实体外观时，也使用PNG/SVG形象图。

箭头硬合同（DEC-365 · LOCKED）：线条接箭头尾部，禁止平头/露线；同图所有箭头头部同尺寸同形状；尖端停在目标框外并留可见间隙。前移箭头时必须同步缩短线条，不得扎入框内。

布局合同：节点较多的流程图采用**块内横排、块间竖排**——整体使用`flowchart TB`，相关节点放入`subgraph`并设置`direction LR`；避免逐节点竖排成高塔，也避免把长流程压进一条横线后整体缩小。拓扑图不套用这条流程布局规则。

通用prompt骨架：`clean white classroom slide; polished flat-isometric technical illustration; recognizable servers, NICs, switches and packet paths; crisp vector-like edges; wide 16:9; readable exact labels; no logos; no watermark; no unverified performance numbers`。

## 逐章prompt集合与教学任务

| 文件 | 最终prompt重点 | 近邻正文负责消除的边界 |
| --- | --- | --- |
| `00-cpu-hot-path.png` | NIC、interrupt、CPU core、L1/L2/L3、RAM与application放进同一处理画面 | 蓝线是概念定位，不是芯片内部单一串行总线，也不表示每包必访RAM |
| `01-diagrams/01-physical-topology-host-owned.svg` + 第01章Mermaid | 管理/观测节点、三台数据VM内的接口归属、四根DAC与Arista四口、IP/服务端口和各章实验索引 | 管理网络不接入Arista数据端口；拓扑保设备包含关系，流程保持可编辑 |
| `02-diagrams/02-trading-lab-runtime.svg`、`02-diagrams/02-snapshot-restore-flow.svg` + 第02章Mermaid | 普通Linux交易系统角色、C++热路径、旁路观察、快照恢复与首笔交易 | 架构图不填性能数字；真实协议细节与流量证据留给第03章 |
| `03-diagrams/03-protocol-and-envelope.svg`、`03-message-and-receipt.svg`、`03-market-packet-fields.svg`、`03-market-transport-modes.svg`、`03-ouch-request-receipts.svg` | 四份规范的信封/信件关系、行情与订单方向、Type A 字段、三种复制位置与 Soup/OUCH 编号链 | 当前DUAL为同NIC/fabric逻辑冗余；图示不提供传输延迟排名 |
| `04-diagrams/04-live-observability-path.svg`、`04-two-read-paths.svg`、`04-order-rtt-contract.svg`、`04-evidence-layers.svg` | 真实 C++ 订单 RTT、两条摘要读取路径、Prometheus 抓取与 Grafana 驾驶舱的三层证据 | 管理命令由 helper/Gateway 发起，JSON 回执反向返回；Python/Prometheus/Grafana 不进入计时区间；聚合视图必须能回到 raw CSV |
| `05-diagrams/`当前4张SVG | 真实订单三点计时、DEQUE/FIXED/SPSC单变量、RSS/IRQ与order-thread位置 | 不预先宣称固定储存、SPSC或pinning必然更快；精确数字回到RUN |
| `06-kernel-bypass-paths.png` | Kernel Socket、Onload、TCPDirect、DPDK四条路径逐层对照 | 每条路径都有CPU；Onload加速数据面不穿过通用syscall/network stack；OS并未消失 |
| `07-switch-queue-ptp.png` | cut-through、egress queue/LANZ与PTP双向交换并列 | 不在形象图中冒险固定四类PTP消息方向，精确状态以后文真包为准 |
| `08-xdp-early-hook.png` | NIC→driver RX→XDP hook→PASS/DROP map与attach/count/detach | counter槽不填虚构数字，精确增量以后文回执为准 |
| `10-rtl-cycle-pipeline.png` | ready/valid、四格FIFO、backpressure、waveform与同序scoreboard PASS | cycle simulation不是FPGA纳秒、Fmax或P&R证据 |

## 生成后人工修正记录

- 第01章初稿曾把管理与数据面画混；最终版改为独立 `MANAGEMENT NETWORK`。
- 第01章旧拓扑容易被读成每台主机到交换机有两张网卡、两根线；一次Mermaid返修曾明确每台主机只有X2522通过一根DAC接入Arista。
- 随后发现按管理/数据平面分块的Mermaid又让ens33脱离所属VM；最终章首改为主机容器优先SVG，两类接口均留在各自VM框内，线落到准确接口与交换机端口。
- 第01章曾尝试用固定画布SVG修正旧图，实际投屏仍出现线条过粗、箭头过小、线压文字和标签越框；最终撤下并删除临时SVG，六类普通图统一回到Mermaid。
- 第01章业务图使用交易所/参与方双泳道，只有行情、订单和结果画跨角色箭头；端到端和pcap图由节点内连续编号表达顺序，不在连线上重复`N→N+1`。身份与Driver owner使用无箭头关系线，应用未证明边界使用虚线。
- 第01章正文撤下重复的管理/数据平面图、不能看到SFP+端口的X2522背板照片和与五层状态表重复的链路图；旧资产继续保留作审计。
- 第02章撤下把内存round-trip画成出网收包、把ICMP pcap画成wire-v1前置证据、宣称gap已经恢复、以及混用correlation幂等语义的PNG；对应关系改为可审计的Mermaid。
- 第02章订单簿、Price-Time和52-byte偏移均改为原生SVG，并限制正文展示宽度；旧PNG不删除，继续作为历史生成资产审计。
- 第02章`02-diagrams/02-wire-v1-byte-layout.svg`画布由1600×760重排为1110×670，Header与Tick Body两行统一按29px/byte等比排布且无缝相接，正文展示宽度由1040px收到800px，与同章另两张SVG一致；缩小画布而不是缩小字号，800px下字段字号仍约16px。
- 第04章教学主线从 29 张构造样本 PNG 收口为 3 张可维护 SVG；旧 PNG 暂不删除，仅作审计。新图只画真实应用的热路径/旁路、C++ RTT 合同和证据层级，不预填虚构曲线或性能值；箭头固定为适中可见尺寸，折线只用正交线段。
- 第06章初稿把Onload数据面画过`SYSCALL`；当前 `06-13` 的绿色主路绕过 Kernel Socket，灰色实线支路表示 unsupported socket 回退内核。正文不得把这条实线说成虚线，也不得把回退画成加速主路。
- 第07章初稿把PTP消息方向画错；最终版只保留可靠的主从双向交换，精确消息顺序留给正文状态图。
- 第08章初稿给counter map填入虚构数字；最终版清空数字，只表达计数动作。
- 第10章初稿scoreboard的actual序列不完整；最终版改为`D0→D1→D2→D3`同序PASS。

新增或替换图片时必须重新检查：箭头方向、设备物理连接、管理/数据面边界、硬件/模型边界、虚构数值、正文caption和本地引用。

2026-09-17：FPGA备选稿00b构建图已增加RTL/GCC/构建产物类比，用日常动作解释构建过程；SVG与PNG同步，800/1200px复看通过。详见 `08-arista-fpga-draft/README.md`。

2026-09-17：第08章独立FPGA稿迁移到7135V/BVL/EOS，六张构建与管理图同步为PDI、EOS临时命令及实际端口查询；来源和显示检查见 `08-arista-fpga-draft/README.md`。

2026-09-18：第08章 `08-arista-fpga-draft/01-packet-path` 已与正文同步具体接口名Ethernet1、Ethernet2、Application1/1；仍为未上板教学示例。SVG/PNG同源更新，800/1200px审图及三宽度检查通过，见 `refs/evidence/ch08-interface-figure-sync-20260918.json`（仓库根目录起算）。

2026-09-18：第08章图02b按3.1—3.6重画为自动分拣机故事，连接仿真、管理测试、两部分通用网表和可选归档。输入/工具/产物与脚本及正文对应，SVG/PNG、两级清单同步；详见08-arista-fpga-draft/README.md与refs/evidence/ch08-local-story-and-output-20260918.json。

2026-09-18：第08章图02b输入使用真实.sv文件名加中文用途，正文列清3.1与3.4各自输入；加高首行后重新渲染并核验，见08-arista-fpga-draft/README.md。

2026-09-18：第08章图02b改为3.1—3.5，区分测试台向电路发额度、Python向模拟设备发令及真机寄存器控制链路；两条虚线表示同源RTL分别仿真/综合。撤掉3.6课堂归档，继续自动保存日志。SVG/PNG与清单同步，见08-arista-fpga-draft/README.md。

2026-09-18 教学表述收口：用正向流程说明源码、两类独立测试、两份JSON逻辑接线表及Vivado生成PDI；构建在开发机完成，装载和实测连接真机。图02b保留Python→control_regs→drop_once授额链路。

2026-09-18 第08章新增02c-board-integration与02d-pdi-build两张SVG/PNG：按4.1—4.4准备完整板卡工程，按5.1—5.5构建检查并输出PDI。正文编号、输入与交付物一致，待执行身份保留；见08-arista-fpga-draft/README.md。

2026-09-18 第08章新增7张AMD官方Vivado界面截图，存于08-arista-fpga-draft/official-vivado，配套来源清单与官方示例身份。第4—5步就近嵌图讲解操作，像素原样保存；不作为本课构建实测证据。

2026-09-18 第08章5.5改为图形界面导出：正文与图02d统一为点击Write Device Image生成PDI，移除Tcl命令。镜像实际文件名按工程设置，打包时统一为flle_filter-bvl.pdi。02d同源PNG重新渲染，800/1200目视及三宽度边界检查通过。

2026-09-18 图01移至第7步接线命令前，原接口角色表与配置流向表合入图；①②③对应三条配置，明确前面板口与内部Application1/1。下方汇总连接条件、路径和无额度试通检查，含FEC匹配及板级错误计数。SVG1200×940/PNG1600×1253，5箭头保留12×12/3px/12px间隙，800/1200目视及三宽度字体边界检查通过。证据refs/evidence/ch08-wiring-diagram-and-checks-20260918.json。
