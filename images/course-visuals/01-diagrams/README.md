# 第01章课程图片集

2026-09-15 A/B 更新：第 01 章流量图把行情箭头拆为 A/B 两个 UDP 组播端点，保留管理与交易通道。800/1200px 已渲染目视，当前摘要见 SHA256SUMS；这不是实机抓包证据。

## 2026-09-14 · 顺稿后图片位置

图件字节与编号保持。流量图及8组短表移至第01章末尾查阅区，逐箭头明细与Trader管理端口说明移入 [TRAFFIC-REFERENCE.md](../../../assets/01-architecture/TRAFFIC-REFERENCE.md)。国内接入总图随沪市扩展移到总结、理解检查之后；厨房、接线、设备身份、驱动、收包和资源恢复图均保留。

## 2026-09-14 · 流量图只改阅读顺序

`01-traffic-flows-and-ports.svg` 仍是 1200×2320、8 组 14 箭头、原配色与框线。按用户要求只调整上下位置和编号：①下单、②行情、③浏览器、④切换、⑤进程命令、⑥SSH、⑦LANZ 队列、⑧UDP 进度。不删组、不改画风。正文短表与附录 A 同步。核验见[流量顺序收据](../../../refs/evidence/chapter01-traffic-order-20260914.json)。

## 2026-09-14 · 开场厨房类比图

新增 `01-kitchen-nic-pcie-driver.svg`（1200×1040），放在开场厨房引入之后，替换原三行角色对照表。内嵌线稿图标包括交换机、收货口/自动搬运车、食材箱、货架、主厨、CPU、清单、线缆和设备身份牌；底部列接线/接口名、PCIe设备身份、当前驱动三项检查。按用户反馈，交换机改为正面平面图标；网卡框内补“PCIe身份：地址/型号”，把PCIe设备身份落到具体对象，区别于两框之间的PCIe总线标签。

紫色虚线分开“备接收缓冲区”与“向网卡登记设备可访问地址”；绿色实线表示报文经网卡/PCIe写内存、CPU随后读取处理。驱动明确为CPU执行的软件；图不描述完整IRQ/NAPI/Socket流水线、缓存一致性或实际机器布局，不增加某张卡的性能结论。底部三项检查对应本章运行①～③，不增加实验步骤。

机制依据：同日复核 [Linux DMA 指南](https://docs.kernel.org/core-api/dma-api-howto.html)的CPU/DMA地址与缓冲区准备说明；设备身份依据 [PCI sysfs](https://docs.kernel.org/PCI/sysfs-pci.html)。厨房图标为课程原生SVG，未引用外部图片。核验见[开场配图收据](../../../refs/evidence/chapter01-kitchen-visual-20260914.json)。现行SVG与历史图件分别登记，下方撤图记录保持当时身份。

## 2026-09-12 · 课程撤下监控教学

物理接线图的.101说明改为交易网页/API与LANZ；流量图删除原监控查询一组，SSH顺接为⑧，现8组14箭头。四根DAC、管理网络、数据IP与业务端口保持。驱动关系图的后续入口改为第五章。

## 当前：一张总图说明下单、客户行情与 LDDS 接入

第一章扩展只嵌一张总图。2026-09-14 按用户要求重绘 `01-cn-access-relationships`：上方独立“下单”框，下方“行情”大框内含客户 UDP 组播/TCP 推送（XTP-Pro 生产/测试分别举例）与 LDDS 四条 TCP 连接及实时/补发两层；图示单路，另注明 LDDS 支持独立多路 TCP 接入。1200×1450 SVG、2400×2900 PNG，47 段文字、8 条连接、14 个箭头。没有把生产/测试画成 TCP/UDP 双活，也不把中泰与未核实的 LDDS 上游采购串联。

`01-sse-access-delivery` 已按用户反馈撤出正文：下单与行情两端关系在总图中已有交代，备用 TCP 借交易线、A/B 路径冗余改为两段短文字。SVG/PNG 保留历史字节（1200×1320 / 2400×2640），不再作为第二张教学图。

现行总图与撤下的线路图均为有出处的关系整理，不冒称单张官方原图重绘或具体券商现网。未添加未知内部设备、生产行情采购或机房共址；统一12×12箭头及框外12px间隙。

旧深交所单图/原件、SmartX软件部署图、Equinix配线架/A-Z图及九图阶段文件保留历史字节，均不恢复正文。队列不重复讲，第七章真实授时案例本次未改。

| 文件 | 来源与用途 |
| --- | --- |
| `01-smartx-deployment-official.png` | [中泰原图](https://smarttest.ztqft.com/sdkDoc/assets/img/relationship.22932a50.png)，158648 字节；按部署地点分区，不是内部接线图 |
| `01-equinix-cross-connect-official.png` | [Equinix Standard Cross Connect](https://docs.equinix.com/cross-connect/)，396×295，官方原始字节 |
| `01-equinix-standard-cross-connect.svg` | 上一原图中文重绘，1200×520；两个通用客户节点、一条无向物理连接；已撤下 |
| `01-cboe-ny5-expanded-official.jpg` | [Cboe NY5 Expanded View](https://www.cboe.com/document/tech-spec/document/technical-specifications/cboe-titanium-u.s.-equitiesoptions-connectivity-manual/)，910×1172，官方原始字节 |
| `01-cboe-ny5-expanded-cn.svg` | 上一原图中文重绘，1200×1810；13 组对象、19 段连接；单播/组播方向沿用原图，TAP 仅取副本；已退出第一章 |
| `01-equinix-demarc-official.png` | [Equinix 配线交付架](https://docs.equinix.com/cross-connect/installation/xc-demarcations/)原图，161×269；已退出正文，留作历史参考，原始字节保持 |
| `01-equinix-demarc-patch-panel.svg` | 双柱配线架试绘，1200×790；用户指出三维关系有问题，已退出正文，留作历史 |
| `01-szse-market-access-official.jpeg` | [深交所 Ver1.09](https://docs.static.szse.cn/www/marketServices/technicalservice/guide/P020260519353303152094.pdf) 图2-1，836×341；直接提取原始JPEG |
| `01-szse-market-access.svg` | 上一原图重绘源，1200×760；保留三类网关、8条无向连接，不加入旧版通信公司节点 |
| `01-szse-market-access.png` | 上一 SVG 原样导出，2400×1520；已由新关系总图接管正文，历史字节保持 |
| `01-cn-access-relationships.svg` | 上交所委托规则、XTP-Pro客户接口和LDDS1.2.3；上层委托/回报；中层XTP-Pro生产UDP组播/公网测试TCP；下层LDDS实时与重建TCP |
| `01-cn-access-relationships.png` | 上一SVG导出；Chromium131 headless-shell、1200×1450 CSS px、DPR=2、完整SVG画布导出 |
| `01-sse-access-delivery.svg` | 已撤出正文、保留历史。上交所接入要求第8条的独立UDP行情与备用TCP行情归入行情框；虚线表示备用，底部解释路径冗余 |
| `01-sse-access-delivery.png` | 已撤出正文、保留历史。上一SVG导出；Chromium131 headless-shell、1200×1320 CSS px、DPR=2、完整SVG画布导出 |

2026-09-14 重绘阶段的原文复核、两图 79 段文字边界与 18 个箭头检查、800/1200px 整图审阅及正文显示检查见[客户协议修订收据](../../../refs/evidence/chapter01-client-protocols-20260914.json)。两图上一版的依据与显示记录见[接口与备用行情说明收据](../../../refs/evidence/chapter01-tcpdirect-ldds-backup-20260911.json)。两级 SHA 清单同步；各阶段数量见相应收据。原件版权属于发布机构，用于课程引用及对照，不表示机构认可课程。

当前撤图与短文核验见[单图编排收据](../../../refs/evidence/chapter01-single-access-diagram-20260914.json)。撤图阶段不改图片或 SHA 清单。

此前[读者顺序收据](../../../refs/evidence/chapter01-access-flow-20260911.json)与[显示修复收据](../../../refs/evidence/chapter01-image-display-fix-20260911.json)保留各自稿件身份。用户远程预览裂图根因未定位，本次PNG只记录本地加载结果。

## 2026-09-11 · 历史：专业网工网络设计扩展（九图）

该阶段扩展按下表顺序使用9张新原生SVG，现已退出正文；旧`01-china-market-access.svg`、`01-us-market-access.svg`也保留历史。所有图宽1200，正文统一800px图框；该阶段的官方结构与客户补充布局逐图标明。

| 历史SVG | 当时回答什么 |
| --- | --- |
| `01-market-cn-delivery.svg` | 上交所局域A/B、双运营商与独立UDP电路 |
| `01-market-cn-flows.svg` | 客户NIC、XTP会话、券商报盘与行情转换 |
| `01-market-cross-connect.svg` | 双方设备口、DMARC、LOA及延伸跳纤 |
| `01-market-cboe-fabric.svg` | NY5四层、转发模式、Port-Channel、撮合/行情及PTP时间戳旁路 |
| `01-market-multicast-edge.svg` | 客户R1/R2、IGMP、snooping、PIM、RPF与ACL位置 |
| `01-market-pitch-recovery.svg` | BZX Unit1 ZA/ZB、GRP请求与Gap Server组播重放 |
| `01-market-order-sessions.svg` | Lime历史代理、两段TCP与BZX主备恢复 |
| `01-market-egress-queues.svg` | 汇聚出口、微突发积压、缓冲、cut-through与QoS |
| `01-market-timing-observation.svg` | TAP采集卡/NIC测点、PTP与独立监测支线 |

来源版本与各图事实边界见[来源说明](../../../refs/FLLE_Trading_Network_Access_2026-09-10.md)。本轮检查记录见[九图扩展收据](../../../refs/evidence/chapter01-network-expansion-20260911.json)。图的本地显示不证明市场实机状态。下方两图/33项等描述保留对应历史阶段身份。

## 2026-09-11 · 国内图承载标签范围修正

`01-china-market-access.svg` 的“第二段：局域接入”改为“交易接入：局域”，避免把下方所有行情产品套用同一承载说明；市场行情按正文产品接口说明。仅替换一个文本对象，图形/箭头保持；美国图字节不变。两图44文字边界/无重叠、800/1200px目视及940/390px嵌图通过，两级33/231SHA更新通过。新核验见[9月11日收据](../../../refs/evidence/chapter01-network-review-20260911.json)，前日记录保留旧稿身份。

## 2026-09-10 · 中美交易网络短扩展

| 新增原生SVG | 课堂用途 | 公开依据 |
| --- | --- | --- |
| `01-china-market-access.svg` | 客户托管程序—券商—上交所；订单、行情、办公室管理分开 | 中泰SmartX/XTP与上交所技术接入服务 |
| `01-us-market-access.svg` | 客户托管程序—Lime—Cboe；市场行情使用独立获准连接 | Lime托管/TS+2022实现与Cboe公开架构/PITCH |

两图均1200×680、三列圆角卡片、24px正文、蓝色交易/紫色行情，统一12px箭头；均为教学归纳，不代表某客户生产布线。官方原图仅供核对，未嵌入正文。出处版本与范围见[来源说明](../../../refs/FLLE_Trading_Network_Access_2026-09-10.md)。800/1200px目视、44文字边界/零重叠、8箭头净空与940/390px正文图框通过；本目录33项、上级231项SHA核验通过，详见[验证收据](../../../refs/evidence/chapter01-market-access-20260910.json)。

2026-09-10 DEC-427：流量图 `/metrics · 第04章` 改为 `/metrics · 第四部分`，与正文及附录统一；图形几何、端点与编号保持，800px/原尺寸目视和两级SHA通过。

## 运行②③关系图 · 2026-09-10

| 当前 SVG | 信息与布局 | 替换位置 |
| --- | --- | --- |
| `01-interface-identities.svg` | 1200×835；网卡平面插图，硬件/软件/网络三组字段卡；保留BDF、PCI ID、驱动、接口、MAC、IPv4 | 运行②原硬件/软件身份 Mermaid |
| `01-driver-ownership.svg` | 1200×780；当前sfc/网络接口/Socket实线关系；第六部分用户态收发独立虚线入口 | 运行③原驱动路径 Mermaid |

两图均为可编辑原生SVG，图标全部内嵌；连线表达关系，不增加步骤箭头。800/1200px渲染与目视、文字边界和零重叠、图标引用、XML、两级SHA通过。正文仅换图及图注，命令与输出不变。收据 `refs/evidence/identity-driver-visuals-20260910.json`。

2026-09-10：`01-packet-and-evidence.svg` 增加①DMA、②中断通知、③读取、④a抓包、④b回应五个箭头编号；正文同步编号表。800/1200px目视通过，原几何与12px箭头间隙保持，两级SHA同步。

2026-09-10 DEC-420：读图说明逐一列出 .1 交易所、.2 Trader、.11 实验 VM；管理口经 ESXi vSwitch 接入管理网，删除物理上联待确认字样。仅改说明与图中页脚/无障碍描述，接线和布局保持。

### 2026-09-09 · DEC-418 设备与服务名称

当前两图设备统一叫“监测 VM · .101”；通信图①②③④⑦框内再标参与通信的服务，⑧是监测VM内部的Grafana→Prometheus→网页后台。Gateway为网页后台的软件名称，不是主机名。两图800/1200与208文字边界通过，箭头/接线结构保持，SHA同步。

## 2026-09-09 · DEC-398 设备接线总览精简

`01-physical-topology-host-owned.svg` 收紧为 1200×1850 的设备、接口、IP 与接线图。删除业务报文、管理与观测地址速查及“后续实验仍使用上面的设备与接线”区域；设备框内保留角色说明，服务端口与通信关系集中在下方独立通信图。保留真实厂商 logo 和标明“设计、未接入”的 Arista 7130 FPGA、AMD Alveo U250，不虚构其接线与 IP。

四个插座改为实际接口名：`.1 ens64np0 → Et1`、`.2 ens64np1 → Et2`、`.11 ens64f0np0 → Et11`、`.11 ens64f1np1 → Et12`。标签框从 64×22 扩为 132×30；用户追加指出边缘仍拥挤，最终与上方网卡框间距及下方设备边缘留白均为 24px。设备框宽度分别增至 360/360/370px、底边延长至 y=1175；右侧双接口区域左右外侧各留 24px、两标签间留 58px。共享 X2522 说明同步下移，避免与设备框重叠。四根 DAC 保持对应端口与横坐标。

正文图卡、alt、读图说明与两级 SHA 同步；800/1200px 完整渲染目视、96 项文字画布边界、四接口框内文字、XML、六处 logo 原件保持通过。独立通信章节及后文逐字保持，31 个代码围栏保持；导航静态检查通过。检查摘要：`refs/evidence/wiring-overview-20260909.json`。下方日期条目为历史版本，不代表当前总图仍含流量与章节索引。

## 2026-09-08 · DEC-396 管理端口与第四章指标链

`01-traffic-flows-and-ports.svg` 第⑧组改为 Grafana（左）→ Prometheus（中）→ Gateway（右）的一行三节点；保留⑧b查询/⑧a抓取编号、蓝色HTTP/TCP、9090/8088目的端口及全部16箭头映射。框内标明职责和地址，Gateway标注`/metrics · 第04章`；图注区分独立周期抓取与看板查询，返回沿原连接。800/1200px渲染、文字边界、12px框外间隙与XML通过。正文第⑦组逐项解释48121～48125；第⑧组对齐第四章八块面板的12个实际指标名，明确C++计时/Prometheus保存/Grafana展示职责。程序与设备配置保持。


## 2026-09-08 · DEC-394 角色位置与文字边界

保留当前总览图内容，统一 Win2019 浏览器标题。通信图的⑤/⑥固定 Exchange 在左、Trader 在右；⑥订单由右向左发起，回执由左向右返回。⑦同步将 Exchange/Trader 管理接口放左侧并反转请求/响应箭头。`.2` 节点统一名为 Trader，Socket 接收器仍准确标注为其内部组件。两图按800/1200px渲染检查，Win2019标题右边界分别303/290，框右边界380/355；16条箭头均保持12px框外间隙。

## 2026-09-08 · DEC-393 统一流量与端口

本轮更新：`01-physical-topology-host-owned.svg`, `01-traffic-flows-and-ports.svg`。控制器归属 `.2`，行情由一个普通 Socket 接收后本机分发；组播 `233.74.125.32:31032`、单播 `.2:42121`。生产案例仅用官方公开端点，中间路由器为机制示意。本地无 PIM/RP 配置。800/1200px 渲染检查；历史抓包与旧性能图保留原始字节及其出处。


## 2026-09-08 · DEC-392 独立通信图与逐箭头说明表

新增 `01-traffic-flows-and-ports.svg`（1200×2630），放在物理拓扑读图说明之后。按用户要求，TCP蓝色 `#2563eb`、UDP橙色 `#b66a0b`，每条线同时写协议文字、监听端口和唯一编号。方框写设备/进程与源目的地址；管理网、数据网和同机回环分别标注。正文同位置新增16行解释表，对应每一条编号箭头的双方、触发/目的与接收方处理。

| 图中编号 | 源码/配置依据 | 核对点 |
| --- | --- | --- |
| ①a/b | `apps/flle-trading-lab/flle_trading/transport_controller.py`、`scripts/transport_labctl.sh` | `.101`发起HTTP控制、`.2:48606`返回；切换作用与SSH登录分清 |
| ②a | `src/common.hpp`的`EventEmitter`、`src/exchange.cpp`、`src/trader.cpp`、`flle_trading/gateway.py`的`telemetry_loop` | `.1/.2`将JSON业务事件发到`.101 UDP46120` |
| ③a/b | `assets/06-arista-time/lanz_stream_collector.py` | `.101`主动连接`.253 TCP50001`，交换机在同一连接上反向传LANZ事件；客户端端口不编造 |
| ④a/b | Gateway、Grafana配置及LANZ采集器HTTP处理 | 8088网页/API、3000看板、8089 JSON查询；旧拓扑的“LANZ页面”同步准确改称“LANZ API” |
| ⑤a/b、⑥a/b | Exchange/Trader现役源码与第02/03/06章资产 | UDP行情组播/单播按模式选择；TCP43120是订单会话，回执源端口43120不能标成回程目的端口 |
| ⑦a/b | Gateway的`component_targets/send_command`与端口默认值 | `.101`向`.1:48120/.2:48121～48125`发送课程命令，返回JSON；不误称HTTP |
| ⑧a/b | `observability/prometheus.yml`、`observability/grafana-datasource.yml` | Prometheus抓`.101:8088/metrics`；Grafana实际查询`127.0.0.1:9090`，都在`.101`本机 |
| ⑨a | 现役SSH/SCP调用及EOS CLI工具 | `.111`通过SSH/TCP22访问四VM和交换机；文件分发说明限VM |

图中的IP/端口是现役源码配置身份，不是本轮新的监听核验。教师浏览器源IP留为实际终端地址；客户端临时端口由系统分配，不预填。⑧、⑨只画发起方向，HTTP/SSH返回沿原连接，正文明确此简化。

验证：800px与1200px目视；104个文字边界、16个箭头编号和16表行一一对应；两marker统一`userSpaceOnUse / 12×12 / refX=0`，线宽2.5、butt线帽，尖端到目标框12px。SVG/XML、7个正文图片引用、31围栏与原HEAD逐字一致、实际Markdown解析1表17行（含表头）、中央205/局部29项SHA通过。新SVG SHA=`667bc487fe905ebf2b019f931591eaa5833402ac54886d30de1994f058cfc759`。无实验、部署或新RUN。

## 2026-09-08 · DEC-391 官方 logo、框外连线与后台端口释义

用户明确要求真实厂商 logo，并指出管理支线穿入横框、X2522 底部端口框为空；本图按此要求接管下方历史 `No logos` 约定。保留通用角色图标，厂商标识使用官网下载的原文件，原色与长宽比不变。AMD 官网将 X2522 列为 AMD Solarflare，图中文字仍保留 Solarflare/X2522；logo 不是设备丝印照片。

| 本地原件 | 官方直接来源（2026-09-08 读取） | SHA-256 |
| --- | --- | --- |
| `01-logo-amd.svg` | [AMD 官网页首 logo](https://www.amd.com/content/dam/code/images/header/amd-header-logo.svg)；见 [X2522 官方产品页](https://www.amd.com/en/products/ethernet-adapters/x2522.html) | `637d36ef706c905033ec2de7023b78918bfd2c4e740ad108e2c34461fa17b820` |
| `01-logo-broadcom.svg` | [Broadcom 官网 logo](https://www.broadcom.com/img/broadcom-logo.svg)，由官网 CSS 的 `.navbar-brand` 引用 | `7cfeac006499e51f19f2c9a9dc62dee279b78c9a43c3e4c91d633cde87af1ab1` |
| `01-logo-arista.png` | [Arista 官网蓝色 logo](https://www.arista.com/templates/arista_v2/img/logo_arista_blue.png)；[品牌指南](https://www.arista.com/assets/data/pdf/Arista-Brand-Guidelines.pdf) | `d41e7f6659d4da7e8f938ba173ea5f16118349239365b3b11e0b9d30f5147bae` |

三个原件在总图内以 data URI 使用六次，解码后逐字等于原件，离线显示不请求厂商网站。AMD 白色原版置于深色底，Broadcom 与 Arista 保留官网配色；图形形状未重绘。标识属于相应厂商，用于设备身份说明，不表示厂商赞助本课程。

管理横框四侧接线均停在框外并留 12px，框内只放网络名称和网段；两 X2522 插座补 `口0/口1`。设备物理 DAC 继续连接准确插座，不能把所有连线机械地改成无端点虚线。

用户另问高位端口的用途，图内按真实调用关系补写。它们是课程应用的后台接口，不能与登录或 LANZ 混称：

| 监听端点 | 谁使用、做什么 | 源码依据 |
| --- | --- | --- |
| `.2 TCP 48606` | `.101` Gateway 通过 HTTP 调用控制器，执行 DPDK/SFC/基线切换；控制器也提供状态和纸面账户复位接口。不是 SSH/SCP 端口 | `apps/flle-trading-lab/flle_trading/transport_controller.py`、`scripts/transport_labctl.sh` 的 `start_controller/start_gateway` |
| `.101 UDP 46120` | `.1/.2` 的 `EventEmitter` 上报交易事件，Gateway 接收后供网页展示；不是交换机 LANZ 数据流 | `src/common.hpp`、`src/exchange.cpp`、`src/trader.cpp`、`flle_trading/gateway.py` |
| `.253 TCP 50001` | `.101` 的 LANZ 采集器主动建立 TCP 连接并解码交换机队列事件；采集器的 `8089` 是 HTTP 查询/显示接口 | `assets/06-arista-time/lanz_stream_collector.py` 的 `stream_once()` 与端口常量 |

验证：800/1200px目视、118文字边界、XML与6个logo嵌入逐字校验通过；31围栏保持、6正文图片引用有效，中央204/局部28项SHA通过。原图尺寸不变，新增3个logo原件，不增加正文图数。仅本地制图/源码核对与官方素材读取，没有设备查询、部署或新RUN。

## 2026-09-08 · DEC-390 全课程实验台总览

原路径 `01-physical-topology-host-owned.svg` 扩充为 1200×2530 的可编辑原生 SVG。正文仍以 800px 宽度显示；主机、终端、网卡、交换机、时钟、观测屏幕与芯片使用同一套自绘矢量图标，全部内嵌，无外部图标下载依赖。下面的旧日期条目保留历史身份。

| 区域 | 内容与证据来源 | 读图边界 |
| --- | --- | --- |
| 管理与观测 | PINS §2/§3 的 `.111/.101`、四台 VM 与交换机管理地址；现役 `apps/flle-trading-lab/scripts/transport_labctl.sh`、`src/exchange.cpp`、`src/trader.cpp`、`assets/06-arista-time/04b-lanz-stream-ab.sh` 的服务端口 | 虚线表示管理网逻辑连接；.1/.2/.11 的 ens33 经 ESXi vSwitch 接入，Arista Management1 使用同一管理网段 |
| VM 与物理链路 | PINS §3/§4 的接口、PCI BDF、驱动、Et1/Et2/Et11/Et12 映射；2026-09-03 同卡身份记录 | 两台 X2522 VM 各直通同一物理卡的一口；`.11` 双口基线无 IP/DOWN；四条实线各代表一根 10G 全双工 DAC |
| 地址与实验索引 | 第01章 VLAN20 配置、Exchange/Trader 现役源码与第06～10章当前资产 | SVI `.254` 配合 `no ip routing`，同网段业务做二层转发；业务服务与实验按章节启用，不表示同时运行 |
| P4 与硬件延伸 | 第09章 VLAN100/200 双臂方案与第09/10章硬件教学节 | BMv2 位于 `.11`；TRex/SPAN/P4 按场景切换；7130/U250 是设计、未接入，未分配虚构 IP 或接线 |

本轮只读核对仓库记录和源码，未 SSH、配置设备、创建 RUN 或更新现场验证日期。原路径替换，无新增图片数量；正文图卡、alt、读图说明、中央与局部 SHA 同步。

验证：带 Noto Sans CJK SC 的本地 Chromium 在 800px 与 1200px 两档渲染并目视检查；115 个文字边界均在画布内，四根 DAC 与 Management1 虚线分别落到所属端口；全图无方向 marker。SVG XML/图标引用通过，正文 31 个围栏与修改前逐字一致、6 个图片引用存在，中央 201 项/局部 25 项 SHA 通过。修复了管理支线穿过说明文字及交换机底板遮住端口接线末段的问题；详见 PIT-20260908-01。

## 2026-09-07 · DEC-377 全课顺稿配图

本轮新增下列原生 SVG，图标表示角色，保留旧图文件作历史审计。正文入口以本表为准；旧日期条目记录当时状态。

| 当前图 | 回答什么 | 替换的正文图 |
| --- | --- | --- |
| `01-packet-and-evidence.svg` | DMA 字节路径、中断通知、抓包副本与 ICMP 回应 | `运行⑤原 Mermaid`（已退出正文） |

依据为本章现役正文与配套实现；不包含新增运行读数或硬件实测。使用自绘文件、包裹、时钟、芯片、内存、队列等矢量图标。箭头遵硬规则 §3.3.3：本组固定 12×12 用户坐标头部、refX=0、2.5 线宽、butt 线帽，尖端与目标框至少间隔 12；无箭头的比较图不强加方向。800px 与 1200px 已逐张检查，修复缺字和标题越界。


> 生成日期：2026-08-22；正文选图复核：2026-08-25
> 生成方式：Codex内置`imagegen`；用途分类`scientific-educational`
> 使用位置：`01-financial-low-latency-architecture.md`

## 统一视觉与证据合同

```text
16:9 clean white classroom slide; premium flat-isometric technical illustration;
crisp vector-like edges; restrained depth; deep navy outlines; recognizable servers,
NICs, switch ports, terminals and evidence files; cyan data/collection; orange order
or sender action; purple ownership/control; green evidence; large English labels.
No logos, watermark, unverified measurements, fake command output, counters or hashes.
Exact arrow direction, host ownership, management/data separation and evidence boundary.
```

本目录保留原20张PNG作审计，并存放当前章首拓扑`01-physical-topology-host-owned.svg`。第01章当前正文的流程、关系、分支和证据链使用Mermaid，另保留DAC实体照片。

当前6张Mermaid统一为“块内LR、块间TB”：每个阶段横向阅读，阶段之间纵向推进；跨块连线连接subgraph，防止块内方向被外部节点连线破坏。拓扑不套用流程分块，接口必须保留在所属VM内。

| 文件范围 | 教学任务 | 硬约束 |
| --- | --- | --- |
| `01-01` | 行情到订单的业务链 | Feed与Gateway分离；风控不可绕过；三色方向固定 |
| `01-02`～`01-03` | 端到端路径与章节路线 | 两个BDF各属于本机；八步不重排 |
| `01-04`～`01-08` | 三项准备与接口映射 | 管理/数据面分离；远端只读；SHA最后生成 |
| `01-09`～`01-14` | PCI身份与Driver owner | MAC不能单独证明硬件；sysfs与ethtool独立交叉 |
| `01-15`～`01-17` | 链路分层与两端对齐 | admin/carrier/address/neighbor/packet各自取证 |
| `01-18`～`01-20` | pcap边界与三包取证 | NIC在主机内存外；DMA到RAM；先抓后发；不伪造输出 |

## 人工返修记录

- `01-01`移除生成器添加的错误回环，并修正Order Book→Publisher方向。
- `01-02`把Trader侧无依据的`0000:04:00.0`改回实测本机BDF `0000:03:00.0`。
- `01-03`、`01-10`移除虚构BDF与示例MAC。
- `01-14`重画为每个host/netdev都执行sysfs与`ethtool -i`两路。
- `01-15`移除示例IP、MAC与提前出现的PASS标记。
- `01-18`把DMA起点从wire纠正为NIC，终点为主机RAM packet buffer。
- `01-20`清空生成器虚构的终端报文与时间戳。
- 内置服务出现5次网络失败；均使用内置服务重试，没有切换到需要API key的CLI。
- 同轮正文撤下`01-07`、NIC背板照片与`01-15`：分别与章首拓扑重复、无法展示课程要辨认的端口、与近邻五层状态表重复。资产本身未删除。
- 2026-08-25曾短暂尝试5张原生SVG替代图，但投屏复核仍发现线宽、箭头比例、文字压线和越框；临时SVG已删除，正文最终使用Mermaid。

原20张PNG均保留；当前正文引用本目录1张拓扑SVG，以及三张 vSphere 截图：`01-vsphere-cpu-reservation-9200mhz.jpg`、`01-vsphere-latency-sensitivity-high.jpg`（均为 `1024×824` JPEG），以及 2026-08-31 用户提供的 `01-vsphere-iommu-enabled.png`（`1274×868` PNG）。24项摘要见同目录`SHA256SUMS`，DAC照片位于上级课程图片目录。

2026-08-29：把 `.1` 编辑页截图纳入正文，Reservation 从误写的 `4×2350=9400` 更正为现场可保存的 `4×2300=9200`；High Latency Sensitivity 截图同步证明 100% CPU/内存预留门闸。
2026-08-31：按 DEC-20260831-143 把同一页 CPU 区的 `I/O MMU → Enabled` 截图纳入正文，与预留、High 并列。表里旧行「Guest vIOMMU / Nested virtualization 均关闭」作废。`Hardware virtualization` 保持关闭，不与 I/O MMU 混为一谈。
