# 第一章交易网络扩展：来源与编排说明

初稿 2026-09-10；读者顺序与官方原图修订 2026-09-11；客户协议图文修订 2026-09-14。对应[第一章扩展](../01-financial-low-latency-architecture.md#market-access-cases)及迁入的[第六章教师资料中的真实授时案例](../assets/06-arista-time/README.md#cboe-timestamp-case)。

## 当前编排与范围

2026-09-17 当前编排：保留“下单与行情分区图 → XTP-Pro 协议表 → LDDS 实时与补发 → 备用线路/A/B 冗余短文”，末尾按用户要求增加美国接口的加密与认证紫色主题卡。正文分别举 IBKR 公网 API、Nasdaq INET FIX 与 TotalView-ITCH A/B 组播，不将三个接口拼成 IBKR 实际订单路由的证明。此前删除的行情商名单、授权办理表、会员实例及行情档位介绍仍只作历史资料。

## 2026-09-17 · 美国接口加密与认证核验

本轮为官方文档核查，不是交易所现场抓包；不修改程序、设备或绿色运行入口。中国接口的加密结论尚不足以统一概括，本卡不作判断。

| 官方资料 | 本轮确认内容 | 证据边界 |
| --- | --- | --- |
| [IBKR Web API Introduction](https://www.interactivebrokers.com/docs/web-api/v1/endpoints/introduction) | OAuth 1.0a 客户使用公网 `https://api.ibkr.com/v1/api`；HTTPS 由 TLS 保护 | 只证明这个公网 API 接入，不泛化所有券商接口；`localhost:5000` 是另一段本地网关连接 |
| [Nasdaq INET FIX 4.2](https://classic.nasdaqtrader.com/content/technicalsupport/specifications/TradingProducts/inet_fix_sb.pdf)，2026-03 更新，§1.2、§4.1 | 明确不支持接口加密；先 Logon、核验 SenderCompID、等登录确认；§4.1 明确用于券商提交订单 | 不外推 Nasdaq 所有协议或其他交易所；此文不证明承载线路没有 VPN/MACsec |
| [MoldUDP64 1.00](https://www.nasdaqtrader.com/content/technicalsupport/specifications/dataproducts/moldudp64.pdf)，第2～4、6页；[TotalView-ITCH 5.0](https://www.nasdaqtrader.com/content/technicalsupport/specifications/dataproducts/NQTVITCHspecification.pdf)，Architecture / Data Types / Message Formats | 原生 UDP 下游报文为20字节头、消息长度及 ITCH 字段，官方接收流程直接检查序号并处理消息 | “原生行情未加密”是两份完整格式与接收流程支持的技术判断，不伪造官方“不加密”原句，也不从二进制或 UDP 名称单独推断 |
| [Nasdaq 美国行情地址表](https://www.nasdaqtrader.com/Trader.aspx?id=FeedMIPs)，TotalView-ITCH / New York Metro / Standard Network | A `233.54.12.111:26477`，B `233.49.196.111:26477`，协议 MoldUDP64 | A/B 为两路接入，不是加密标志；正文不复刻地址表 |

排版核验：CommonMark 实际解析与 HTML 标签配对检查；卡片三行、五个官方链接，保留加粗与颜色；第一章所有代码围栏和绿色运行卡与编辑前逐字相同。未执行设备操作或外部交易。

正文只嵌一张总图。`01-cn-access-relationships` 已重绘为上下两大分区：上框为客户经券商下单；下方行情大框内，第一层为服务商向客户交付 UDP 组播或 TCP 行情，以 XTP-Pro 同机房生产/公网测试分别举例；第二层为 LDDS 的 DDS/SDS—VDE—VSS，均使用 TCP，并列出实时与补发方向。图示单路，注明 LDDS 支持独立多路 TCP 接入。客户与上游分别举例，不据此认定中泰使用 LDDS 取得这些客户行情。

用户随后指出第二张图与总图的角色/流向重复，`01-sse-access-delivery` 已撤出正文，SVG/PNG 保留历史字节。备用 TCP 借交易线路及 A/B 冗余压成两段短文，仍保留产品范围、地面接入条件和带宽管理；撤下运行中心定义、重复图卡与 G4 通信配置旁支；总图前后进一步压成客户协议三行表、LDDS角色简述和实时/补发两条路径。当前只用一张总图，现行检查见[单图编排收据](evidence/chapter01-single-access-diagram-20260914.json)。

券商 API/SDK、TCPDirect 与 OpenOnload 的适配问题及南华实施案例已移入[第 05 章工程选型](../05-openonload-tcpdirect-dpdk-kernel-bypass.md#broker-sdk-access)，来源与边界见[第六章配套说明](FLLE_Chapter06_Broker_SDK_2026-09-11.md)。第一章不再展开软件改造；附录端口表仍保留实际客户端名称，命令转发示例改用普通 Socket。

Lime、Equinix、Cboe 及 OnixS CME 示例均退出第一章正文；其原始资料、旧图片和旧收据留在本页及资产目录供历史核查。下方来源表因此同时含现行和历史资料，不表示所有来源仍进入课堂。第七章此前独立的真实授时案例本轮未改。国内的 TCP/UDP、组播接收、LDDS 连接及市场双路/隔离/备用条件继续保留；不把美国 BGP、MTU 或整形参数移植到国内。

## 当前图件与原图对照

下表文件均位于 `images/course-visuals/01-diagrams/`；原图保留直接下载的字节，同日重绘阶段的两图核验见[客户协议与市场线路修订收据](evidence/chapter01-client-protocols-20260914.json)，上一版见[接口与备用行情说明收据](evidence/chapter01-tcpdirect-ldds-backup-20260911.json)。

| 文件 | 身份与来源 | 本节怎样使用 |
| --- | --- | --- |
| `01-smartx-deployment-official.png` | [中泰官方原图](https://smarttest.ztqft.com/sdkDoc/assets/img/relationship.22932a50.png) | 仅在配套资料保留；软件部署分组不能证明同一机房空间、机柜或网络隔离方式 |
| `01-equinix-cross-connect-official.png` | [Equinix Standard Cross Connect](https://docs.equinix.com/cross-connect/) 原图 | 保留 A/Z 两端及机房分组，供对照 |
| `01-equinix-standard-cross-connect.svg` | 上一行的中文重绘，已撤下 | 两端直连不足以解释配线，用户要求替换为下方实际交付架 |
| `01-cboe-ny5-expanded-official.jpg` | [Cboe NY5 Expanded View](https://www.cboe.com/document/tech-spec/document/technical-specifications/cboe-titanium-u.s.-equitiesoptions-connectivity-manual/) 原图 | 已退出第一章；保留原始 JPEG 作历史资料 |
| `01-cboe-ny5-expanded-cn.svg` | 上一行的中文重绘，已退出第一章 | 保留历史字节；不迁入国内案例 |
| `01-equinix-demarc-official.png` | [Equinix 2-Post Demarcation Rack](https://docs.equinix.com/cross-connect/installation/xc-demarcations/) 原图 | 原始 PNG，161×269；已撤出正文，保留为历史参考 |
| `01-equinix-demarc-patch-panel.svg` | 上一原图的课程风格试绘，已撤下 | 用户指出三维关系有问题；仅留历史，不作现行教学图 |
| `01-szse-market-access-official.jpeg` | [深交所开发指南 Ver1.09](https://docs.static.szse.cn/www/marketServices/technicalservice/guide/P020260519353303152094.pdf) PDF第6页图2-1 | 直接提取原始 JPEG；封面2026年4月，发布2026-05-19 |
| `01-szse-market-access.svg` | 上一原图的课程风格重绘源文件 | 市场参与者侧的三类网关经交易通信网连接交易所；不增加旧版通信公司分组 |
| `01-szse-market-access.png` | 同一 SVG 导出的2400×1520 PNG | 前轮显示版；本次由下方关系总图接管，历史字节保持 |
| `01-cn-access-relationships.svg` | 上交所委托规则、XTP-Pro 客户接口、LDDS1.2.3 | 1200×1450，47段文字、8条连接、14个箭头；客户UDP/TCP与LDDS的四条TCP连接分层示意 |
| `01-cn-access-relationships.png` | 上一 SVG 的同源导出 | 2400×2900，正文显示版 |
| `01-sse-access-delivery.svg` | 上交所技术局域/广域服务、接入要求第7—11条；已撤出正文 | 历史字节保留，1200×1320，32段文字、3条业务流、4个箭头；下单与行情分框，行情框内说明UDP独立线/TCP借交易线，底部区分路径冗余 |
| `01-sse-access-delivery.png` | 上一 SVG 的同源导出；已撤出正文 | 2400×2640，历史显示版；两图箭头均12×12，尖端距框12px |

## 2026-09-14 重绘阶段的原文复核与协议取舍

LDDS 总册 1.2.3 官方 PDF 重新下载后 SHA-256 为 `811aea82aa01d6830d2f19e2e1453ef733860bda5f1fc3aee407f8e5c88f6588`，与既有记录一致。§2.4.2、2.4.3、2.9、4.5 确认四条 TCP 连接与补发路径；§2.5 及图 2-3 确认独立发布源、多路接入，各路仍按 LDDS 的 TCP 接口工作。原文不把这种高可用结构称为“TCP 一路、UDP 一路”。

XTP-Pro 原始接入指引 §1.1、§2.3 订阅节后的 A/B 条目、§4.1、§4.3—4.4 明确生产 UDP 组播/公网测试 TCP。A/B 条目是环境区分，图内改用协议与环境标签。配置指引 §1.3 的 normal/fpga 是生产 UDP 的两路源，不能据此推定物理双路独立。旧 classic XTP 头文件不与 Pro 指引拼成统一的客户回补传输协议；首图不额外绘制未核定协议的客户回补通道。

上交所技术公司广域行情页面仍说明专线 UDP 接入（Level-1 FAST、期权），属于第二张图的产品范围。上交所会员接入要求 PDF 再次下载，SHA-256 `60c543ea94a5ad371958e20140754218063de5b30c3e54a740e1497bb1ec4772`；第 8 条确认满足地面接入条件的会员可借交易线接收备用 TCP 行情并管理带宽。局域/广域官方页面再次核对：A/B 是双路双活，广域经不同运营商接不同站点。这些条件保留在第二图，运营商具体地名等次要信息退出图内。完整来源、重新下载的文件摘要及各结论边界见[研究记录](../artifacts/research/ldds-tcp-udp-20260914.md)。

## 来源及核验范围

下表包含当前引用与历史阶段资料，保留各次核验身份。AMD、OnixS 与南华资料不再进入第一章正文；南华及 AMD 的采用范围另见第六章配套说明。下方历史记录保留原件取得方式和失败情况，不随迁移覆盖旧收据。

| 官方资料 | 版本或日期 | 采用内容与适用边界 | 核验日期 |
| --- | --- | --- | --- |
| [上交所交易规则](https://www.sse.com.cn/lawandrules/sselawsrules2025/stocks/exchange/c/c_20260424_10816482.shtml) | 2026-04-24 发布，2026-07-06 施行；§2.2.1—2.2.2、3.1.1—3.1.2、11.5 | 普通客户委托、获准参与人申报；交易单元是基本业务单位，不是物理线路。现正文只解释本节需要的参与资格 | 2026-09-11 |
| [中泰 SmartX 开发者指南](https://smarttest.ztqft.com/sdkDoc/introduction/1.0.0/guide/howTo_develop.html) | 路径版本 1.0.0；无发布日期 | SmartX 交易软件、XTP 极速交易平台、本地客户端与托管后台两种运行位置；原图按地点分组 | 2026-09-11 |
| [上交所技术局域接入](https://www.ssetech.com.cn/product/exchange/jyjyservice/) | 无发布日期 | 获准用户的局域连接与 A/B 双路；不推定普通客户可自行购买市场端口 | 2026-09-11 |
| [上交所技术广域接入](https://www.ssetech.com.cn/product/exchange/SDH_MSTP/) | 无发布日期 | 运营商专线承载；页面中的旧报盘库描述不作现行唯一接口 | 2026-09-11 |
| [XTP 交易 API](https://github.com/ztsec/xtp_api_python/blob/master/XTP_API_20250806_2.2.50.8/bin/include/xtp_trader_api.h#L661) | 目录 20250806_2.2.50.8 | 服务 IP/端口与 TCP 交易登录 | 2026-09-10 |
| [XTP 行情 API](https://github.com/ztsec/xtp_api_python/blob/master/XTP_API_20250806_2.2.50.8/bin/include/xtp_quote_api.h#L408) | 同上 | 行情登录支持 TCP/UDP；UDP 不能直接推成组播 | 2026-09-10 |
| [上交所技术行情广域服务](https://www.ssetech.com.cn/product/exchange/gsdmhqNetwork/) | 无发布日期 | 专线承载 UDP 组播；仅列 Level-1 FAST 和期权行情，限制允许的组播源；不能推广到全部行情产品 | 2026-09-11 |
| [上交所技术行情局域服务](https://www.ssetech.com.cn/product/exchange/hqjyservice/) | 无发布日期 | 页面列明 Level-1，不据此推定 XTP 的 Level-2 上游 | 2026-09-11 |
| [广域共享交易行情服务](https://www.ssetech.com.cn/product/exchange/gywgxtdjyhqjrfw/) | 无发布日期 | 向深证通托管／金融云用户提供服务，是“托管不等于局域”的一手反例 | 2026-09-11 |
| [上交所接入管理](https://www.sse.com.cn/services/tradingtech/services/c/10761335/files/e7093fcfabbb4089ae059feb0cb6a848.pdf) | 2024-09-06；第7—11条，PDF第2—3页 | 互备中心、双运营商接入同城两站点、托管中心双路局域网、UDP行情独立线路；第8条允许符合地面接入条件的会员以交易线接收备用TCP行情，但须管理带宽；第11条要求隔离。属于机构接入要求，不是中泰现网审计 | 2026-09-11 |
| [上证所信息行情产品](https://www.sseinfo.com/services/assortment/market/) / [LDDS 接入总册](https://www.sseinfo.com/services/assortment/market/hqywwd/wdzsjk/c/10821682/files/f79fbdd9f5274766940b7b9b0e0b1eff.pdf) | LDDS 1.2.3，2026-06-11；§1.4、2.4、2.6—2.9、4.5 | Level-2 有独立产品/许可/接口；LDDS支持L1/L2；VDE在信息商侧，经TCP长连接DDS、按需短连接SDS；VSS在同一安全网络接VDE实时/重建端口；SDS定义为数据重建和用户认证服务器，按请求返回静态/重建数据；快照类不支持重建。不能断言全部L2分发均为TCP | 2026-09-11 |
| [Lime Hosting & Colocation](https://lime.co/lime-hosting-and-colocation/) | 无发布日期 | Secaucus 接入布局、托管与 1G/10G cross-connect、另有远程连接服务 | 2026-09-11 |
| [Equinix Cross Connect](https://docs.equinix.com/cross-connect/) | 无统一发布日期 | 物理交付点间跳接；同一IBX内的双线不保证物理路径分离；新订单单模范围按独立发布记录核对 | 2026-09-11 |
| [Equinix 发布记录](https://docs.equinix.com/releases/cross-connect-releases/) / [EOL FAQ](https://docs.equinix.com/internet-access/eia-ec-eol-migration-faq/) | 2024.2；变更起点 2024-03-31 | 新 Cross Connect 订单仅 SMF 单模光纤；不代表全部存量线路当天换为单模 | 2026-09-11 |
| [Lime TS+ Guide](https://docs.lime.co/binary/LimeTSPlusGuide.pdf) | 1.8.0，2022-06-06；§2、3.1、4.4 | TCP 代理、BOE 接口、入场前检查；该版只提供二进制协议、不提供 FIX，避免与 Cboe 的 BOE/FIX 网关图混同；仅作历史实现 | 2026-09-10；2026-09-11复核 |
| [Cboe Connectivity Manual](https://www.cboe.com/document/tech-spec/document/technical-specifications/cboe-titanium-u.s.-equitiesoptions-connectivity-manual/) | 10.4.29，2026-08-17；NY5 Expanded View、L3 Network Overview、Latency Equalization、Required Information、Overview/Carriers | BZX四层、设备数量/型号/转发模式、上联容量、Core3/4及ToR主备接线；原图在两级Core之间画TAP观测分支到Corvil/Cboe Timestamping；具体加戳位置由独立时间戳规范解释；另有光程均衡/OBR、ASN/前缀/Transit IP、微突发及容灾规则。C1独立架构、逐端口矩阵和客户BGP策略不由本图推定 | 2026-09-11 |
| [SEC 市场接入 FAQ](https://www.sec.gov/rules-regulations/staff-guidance/trading-markets-frequently-asked-questions/divisionsmarketregfaq-0) / [Rule 15c3-5 正式发布稿](https://www.sec.gov/files/rules/final/2010/34-63241.pdf) | FAQ 页尾审核 2014-06-06；Q9/10/12/17；2010 发布稿 PDF 128—129 页 | 可部署在客户处，但财务风控须由接入券商直接且排他控制；(d)(1)仅准特定监管控制经尽调/书面合同等条件分配给合格注册券商客户，(d)(2)不免除接入券商总责 | 2026-09-11 |
| [RFC 9776](https://www.rfc-editor.org/rfc/rfc9776.html) / [RFC 4541](https://www.rfc-editor.org/rfc/rfc4541.html) / [RFC 7761](https://www.rfc-editor.org/rfc/rfc7761.html) | 2025 / 2006 / 2016 | 主机成员、二层snooping、三层PIM、RPF和出接口列表的通用机制；客户R1/R2、VLAN及PIM落点为教学设计，不冒充Cboe美国接入边界的公开配置 | 2026-09-11 |
| [RFC 1812](https://www.rfc-editor.org/rfc/rfc1812.html) | 1995；§5.3.9 | 源/目的前缀、协议与端口过滤是规范允许的路由器能力；不能写成Cboe实配ACL | 2026-09-11 |
| [RFC 4271](https://www.rfc-editor.org/rfc/rfc4271.html) / [RFC 4607](https://www.rfc-editor.org/rfc/rfc4607.html) / [RFC 1112](https://www.rfc-editor.org/rfc/rfc1112.html) / [RFC 7679](https://www.rfc-editor.org/rfc/rfc7679.html) | 2006 / 2006 / 1989 / 2016 | BGP 可达信息/下一跳、SSM、组播 TTL、跨点时延测量的时钟和测点关系；属于通用设计知识，不冒充市场配置要求 | 2026-09-11 |
| [Cboe Multicast PITCH](https://www.cboe.com/document/tech-spec/document/technical-specifications/cboe-titanium-u.s.-equitiesoptions-multicast-pitch-specification/) | 修订表 2.41.77，2026-09-09；Feed Connectivity、GRP、US Equities Production 配置表 | BZX Unit1生产ZA/ZB的源前缀、RP、实时/补包组、UDP30001及MTU1500；GRP在TCP接请求，Gap Server以UDP组播重放，回复和重放可任意先后；Spin在TCP给簿状态并与实时增量衔接。GRP/Spin连接参数由Cboe分配；未来交易时段条款不作为已生效事实 | 2026-09-11 |
| [Equinix Demarcations](https://docs.equinix.com/cross-connect/installation/xc-demarcations/) | 在线文档，无发布日期 | Cross Connect终止于获准分界点；客户负责分界点到自身设备的跳纤，可另行委托实施。图中机柜与面板位置是交付责任示意 | 2026-09-11，本轮新增 |
| [Equinix 以 LOA 下单及验光](https://docs.equinix.com/cross-connect/ordering/xc-order-cc-with-loa/) | 在线文档，Configure the Connection | LOA给出Z侧信息；下单选择机房/机柜/配线架/端口、介质和连接器；验光可核Tx/Rx。光模块/速率及Ethernet/IP/应用项目按具体服务另行确认 | 2026-09-11，本轮新增 |
| [Arista Microbursts, Jitter and Buffers](https://www.arista.com/assets/data/pdf/TechBulletins/AristaMicrobursts.pdf) | 4页；PDF第1—3页；末页版权2016，不作为当前型号规格 | 短时突发被粗粒度均值隐藏；fan-in产生排队；cut-through遇拥塞仍需缓冲。两路10G汇聚算例是教学计算，不是该白皮书实测或某市场现网负载 | 2026-09-11，本轮新增 |
| [Arista 7150S Family White Paper](https://www.arista.com/assets/data/pdf/Whitepapers/Arista_7150S_Family_WP.pdf) | 16页；PTP段PDF第9—10页，另见LANZ段 | BC向上游同步并向下游分发，TC修正PTP报文驻留时间；硬件时间戳、LANZ队列观测与转发职责分开。支持机制与产品能力说明，不证明案例方部署或本课绝对精度 | 2026-09-11，本轮新增 |
| [Linux Kernel Timestamping](https://docs.kernel.org/networking/timestamping.html) | 在线内核文档；§1.3.1、硬件时间戳相关章节 | NIC生成RX硬件时间戳，软件时间戳测点位于驱动交包之后；需分别核硬件/驱动能力、接口配置与时钟域。不能用时间戳分辨率代表跨点准确度 | 2026-09-11，本轮新增 |
| [Cboe Equities Timestamping Service Specification](https://cdn.cboe.com/resources/membership/Equities_Timestamping_Service_Specification.pdf) | 1.0.15，2026-03-18；PDF第7页（页内6），Table 2 | Optical TAP把副本送入aggregation switch，由后者添加时间戳头；汇聚交换机通过PTP同步Cboe GPS时间源。Network Discovery Time与订单处理服务器NIC时间戳是不同测点；被动TAP不负责加戳 | 2026-09-11，本轮新增 |
| [RFC 3290：Diffserv 排队模型](https://www.rfc-editor.org/rfc/rfc3290.html#section-7) | 2002；§7，Informational | 队列与调度器的通用模型，解释QoS在竞争资源上的选择；不作为Cboe实配 | 2026-09-11，本轮新增 |
| [上交所 Level-1 产品](https://www.sseinfo.com/services/assortment/level1/) | 无发布日期；连续竞价产品说明 | 基础行情、最新成交价与累计量、买卖各五档；VDE 为可用接入客户端之一 | 2026-09-11 |
| [上交所 Level-2 产品](https://www.sseinfo.com/services/assortment/level2/) | 无发布日期；产品说明 | 增值行情、买卖各十档、委托笔数及逐笔成交；不借产品层次推定传输协议 | 2026-09-11 |
| [Lime FINRA 报告](https://files.brokercheck.finra.org/firm/firm_11826.pdf) | 本轮公开报告；CRD 11826 / SEC 8-27061 | 说明 Lime Trading Corp. 是券商，不把机房商和券商混为一类 | 2026-09-11 |
| [Equinix 公司介绍](https://www.equinix.com/about) / [LOA](https://docs.equinix.com/cross-connect/digital-loa/xc-loa-create/) | 在线资料 | 数据中心/互联服务商；LOA 为接线授权，指定接线资产，不授予股票交易权限 | 2026-09-11 |
| [上交所技术金桥托管服务](https://www.ssetech.com.cn/product/data/jqdcIntro/) | 无发布日期 | 机柜、布线等托管基础设施；结合交易规则解释托管服务与交易资格分别申请 | 2026-09-11 |
| [Pico Corvil Analytics](https://www.pico.net/products/corvil-analytics/) | 无发布日期 | 从网络报文分析交易和网络状态；仅解释 Cboe 原图中的产品名，不引入宣传精度 | 2026-09-11 |
| [XTP-Pro 交易 QuickStart](https://xtp.zts.com.cn/xtp-pro/API4/交易XTrader-API使用指南QuickStart.html) | §2.6、3；无发布日期 | 交易TCP；与Pro行情资料配套，不再拿classic版本头文件混用 | 2026-09-11 |
| [XTP-Pro 行情接入前指引](https://xtp.zts.com.cn/xtp-pro/API4/行情服务接入前指引/行情服务接入前指引.html) | §1.1、4.3、4.4；无发布日期 | 生产UDP组播/公网测试TCP、同机房连接、本地网卡成员关系与防火墙放行；未公布券商交换机QoS或ACL | 2026-09-11 |
| [XTP-Pro 行情配置](https://xtp.zts.com.cn/xtp-pro/API4/行情配置及参数调优/行情配置及参数调优.html) | §1.3；采用SDK1.2.1示例 | 核验接收接口配置边界；normal/fpga择快不当作物理线路冗余，正文不扩展此机制 | 2026-09-11 |
| [上交所交易接入实施指南总述](https://www.sse.com.cn/services/tradingtech/policy/c/10829610/files/85b8fa13dda7455a9aa3f6e390b08b3a.pdf) | 1.0，2026年8月，发布8月21日；§2.4、2.6 | 面向G4升级：报盘至少两个主备通信地址、不同链路/数据中心、年度切换演练；Level-2至少20Mbps。前轮本地下载失败，本轮浏览工具成功解析13页，未保存本地PDF或重绘其中部署图 | 2026-09-11 |
| [深交所交易系统接口开发指南](https://docs.static.szse.cn/www/marketServices/technicalservice/guide/P020260519353303152094.pdf) | Ver1.09，封面2026年4月；官网发布2026-05-19 | 图2-1三类网关；§4.3为OMS到TGW按平台TCP；§5.7为网络版MDGW实时/重传TCP端口，不能套所有接口形态。沿用17页原件复读 | 2026-09-11 |
| [Equinix 配线交付架原图](https://docs.equinix.com/assets/images/xc-post-demarc-14747da1140e61075ca893790a7ff0b1.png) | 2-Post Demarcation Rack；无版本日期 | 客户机柜、顶部走线架、独立双柱配线架与线束；责任注释来自Demarcations正文 | 2026-09-11 |
| [上交所技术公司](https://www.ssetech.com.cn/) / [深证通公司介绍](https://www.sscc.com/aboutUs/gongsigaikuang/index.html) | 在线介绍 | 前者为上交所旗下技术公司；后者为深圳证券通信有限公司，提供金融通信与托管等服务，补首次出现的机构身份 | 2026-09-11 |
| [深证通托管业务](https://www.sscc.com/product/dataCenter/index.html) | 无发布日期 | 主机交易托管限有深交所交易资格与报盘网关的用户；综合托管区不直接提供该报盘接入。仅作资格与基础设施区分的补充证据，未把深交所交付细目扩写到上交所案例 | 2026-09-11 |
| [深交所网关部署及接入指引](https://www.szse.cn/marketServices/technicalservice/serveGuide/P020260512403297957730.pdf) | V1.01，官网2026-05-12；25页 | 表2-1、3-1及§5.2/5.4/6/8：三类网关位置、流量、文件实例，福田/南方服务端；未逐段核定网关到市场端TCP/UDP | 2026-09-11 |
| [深交所交易系统接入技术规范](https://www.szse.cn/marketServices/technicalservice/serveGuide/P020260529566082416677.pdf) | Ver1.06，官网2026-05-29 | §4—5：不同运营商接主备中心、市场互联必须三层路由端口、托管冗余、互联网隔离与边界/重要节点访问控制；不写成中泰实配 | 2026-09-11 |
| [上交所会籍业务常见问题](https://one.sse.com.cn/member/hyjgzj/hy_hyzc_cjwt/) | 在线问答，无发布日期 | 基金/保险机构租用会员交易单元、租用方相应业务权限；区别普通经纪客户与获准机构安排，不按租机柜推资格 | 2026-09-11 |
| [2026年基金发售公告中的会员实例](https://www.sse.com.cn/disclosure/fund/announcement/c/new/2026-02-13/560370_20260213_LYSW.pdf) | 易方达中证全指红利质量ETF，2026-02-13披露 | 发售代理机构列中泰、中信、华泰为上交所会员单位；只举具名例子，不冒称拿到当前完整会员名册 | 2026-09-11 |
| [AMD TCPDirect User Guide](https://docs.amd.com/v/u/en-US/SF-116303-CD-TCPDirect_User_Guide) | 实取 Issue19，门户2026-06-10；§1、3.2 | 用户态TCP/UDP库；修改自编程序网络调用并重编译，不自动替换封闭SDK，也不改变市场业务协议或资格 | 2026-09-11 |
| [Linux XDP／AF_XDP](https://www.kernel.org/doc/html/latest/networking/af_xdp.html) | 在线内核文档 | 收包处理与重定向，区别于券商XTP平台；不将XDP说成交易API或TCP协议栈 | 2026-09-11 |
| [上证信息非展示行情产品](https://www.sseinfo.com/services/cpfwjg/) | 在线产品说明，无发布日期 | 行情许可涵盖程序等非展示使用；数据接入许可不能替代订单申报权限 | 2026-09-11 |
| [上交所会员信息技术管理指引](https://www.sse.com.cn/lawandrules/sselawsrules2025/member/personnel/c/c_20250704_10783964.shtml) | 2025-07-04；§2、26 | 普通客户委托由会员自有并管理系统接收的范围与法定例外；不由内核旁路技术推定可以跳过会员控制 | 2026-09-11 |
| [Wind Client API](https://www.wind.com.cn/mobile/ClientApi/zh.html) | 在线产品页，无发布日期 | 金融数据、行情与自编程序接口的服务实例；不将该产品当作原始行情专线或指定低时延指标承诺 | 2026-09-11 |
| [同花顺数据接口示例](https://quantapi.10jqka.com.cn/gwstatic/static/ds_web/quantapi-web/example.html) | 在线官方开发文档，无发布日期 | iFinD程序接口及实时行情查询实例；接口可用性、市场范围和授权按所购产品确认 | 2026-09-11 |
| [上证云产品介绍手册](https://www.sseinfo.com/services/technical/cloud/dynamic/c/10010742/files/61fe596c116c48b3b8cf2fa96f34ec87.pdf) | 14页PDF，印刷页13—14；未据网页抓取日期认定手册版本日期 | 行情托管段明确列通达信、同花顺、大智慧、钱龙等信息商；不据合作名单宣称逐家当前全部市场/API再分发许可已核实 | 2026-09-11 |
| [OnixS CME iLink3 TCPDirect 示例](https://ref.onixs.biz/cpp-cme-ilink3-handler-guide/group__tcp-direct-getting-started-sample.html) | 页面标C++ SDK1.19.3，无发布日期 | 历史参考，已退出正文。创建TcpDirectStack，传给Session，建会话并发送NewOrderSingle；证明该SDK有适配和源码示例，不证明XTP支持或某客户已实盘。Windows模拟使用普通socket，不拿它证明TCPDirect实跑 | 2026-09-11 |
| [南华期货NHTD2官方报道](https://www.nanhua.net/news/2020/04/85ff7329-0327-4ad2-a602-bc0e54090674.html) | 2020-04-28，作者南华期货 | 自述NHTD2采用TCPDirect，并可支持TCPDirect/RDMA两类客户交易；仅引用实现事实，不采纳宣传延迟、也不作为当前沪市股票接口兼容性证明 | 2026-09-11 |
| [南华期货客户技术服务与托管报道](https://www.nanhua.net/news/2020/10/2196ee99-f610-4122-84a2-4dfb6b27dad0.html) | 2020-10-14，作者南华期货 | 客户 API 开发/测试指导、托管或租借、网络策略开通；NHTD2 等部署在调优专用服务器。托管区使用 Nexus 3548 与 Metamako 一层交换机连接交易所、交易系统区与客户主机；不推定逐跳拓扑或当前产品配置 | 2026-09-11 |

时间戳服务规范原件在九图阶段取回292301字节，SHA256为`c49f2ae9402fbf6e5067c0a65543c739f0fbfd06aa4c0eb1f06709adc02d5b64`。表中nanoseconds描述字段精度，不据此承诺纳秒级绝对准确度。Connectivity、PITCH和Lime TS+原件的本轮摘要将随新验证收据登记，不依赖临时下载目录作为跨会话唯一证据。

## 历史：九张图的职责与归纳边界

下表记录上一轮九图阶段，全部已退出现行正文，文件与旧收据保留。原“教学布局”包含客户网络和观察拓扑，用户本轮明确不再采用这些自行补充的设计。

| 九图阶段文件 | 当时回答的问题 | 官方资料明确的部分 | 教学布局与限制 |
| --- | --- | --- | --- |
| `01-market-cn-delivery.svg` | 局域A/B与远程双运营商怎样交付 | 上交所局域产品A/B与交付限制；2024指引的双中心/双运营商/UDP独立线路及备用TCP例外 | 左右对照与客户设备摆放为教学设计；不声称某券商设备数、接线矩阵或全部现役站点 |
| `01-market-cn-flows.svg` | XTP、市场交易接口和行情分别在哪结束 | SmartX托管/计算单元、XTP交易TCP及行情TCP/UDP、L1与LDDS接口边界 | 券商内部分组和连接归纳；不将XTP上游画成已确认采购链；管理网络独立隔离 |
| `01-market-cross-connect.svg` | 设备光口到双方DMARC之间怎样接 | Equinix分界点、LOA、配线架/端口及延伸跳纤责任；Lime的cross-connect服务 | 机柜、端口位置、光路分段为交付示意；Ethernet/IP/应用检查属于设计，不宣称Equinix替客户配置 |
| `01-market-cboe-fabric.svg` | Cboe四层、网关/撮合/行情与TAP怎样相连 | NY5 Expanded View和BZX四层表、数量/型号/上联、Core3/4、ToR主备、TAP观测分支与光程均衡；时间戳规范补全PTP同步的汇聚交换机加戳位置 | 课程风格重排公开连接关系；未给出逐端口矩阵、客户BGP策略或所有内部传输协议；不套C1 |
| `01-market-multicast-edge.svg` | IGMP、snooping、PIM和RPF落在哪 | RFC成员/二层分发/建树规则；PITCH公开RP、源前缀、组地址及端口另在正文对照 | R1/R2、客户VLAN、PIM邻接和接口名称是教学设计；美国市场边界接收IGMP或PIM的具体合同未在所核材料中公开 |
| `01-market-pitch-recovery.svg` | ZA/ZB合并、GRP重放与Spin如何分路 | PITCH双feed、TCP缺口请求、UDP组播重放、回复/重放无强制先后、TCP Spin与实时流衔接 | 客户接收器布局与分层为教学设计；图中顺序数字是局部示例；服务地址/登录参数仍由市场分配 |
| `01-market-order-sessions.svg` | 两段TCP、财务风控和站点切换谁负责 | Lime TS+1.8.0的历史代理实现、SEC控制归属、Cboe主备站行为 | 不是Lime当前兼容性承诺；网络可达恢复与应用会话/未决订单核对分别处理 |
| `01-market-egress-queues.svg` | 汇聚出口为何积压，cut-through/QoS放哪 | Arista说明fan-in、突发、缓冲与转发机制；Cboe手册给出容量/排队问题 | 2×10G汇聚至10G及积压计算为明确教学算例；具体队列、调度及容量方案不是Cboe配置要求 |
| `01-market-timing-observation.svg` | 业务直通、PTP授时与监测副本怎样分开 | Arista BC/TC、LANZ及硬件戳能力；Linux NIC RX测点；RFC7679跨点测量边界 | GM/BC与客户观测拓扑为教学设计；入口TAP直通业务，分光副本送硬件采集卡t1，再与业务NIC的t2对照，须计入分支延迟和时钟误差 |

## 历史：九图阶段的 Cboe 参数核对

四层设备数据取自Connectivity 10.4.29的Equities/Options表，范围限定NY5和BZX Equities。型号属于该版本公开架构，不是本课采购建议或现场设备清单。

| 层或测点 | 公开对象 | 连接与转发信息 | 适用边界 |
| --- | --- | --- | --- |
| Customer Access | NY5共6台10G接入，Arista DCS-7050SX3-96YC8 | 表列2×100G上联至对应DC Core组；标Cut-Through并注明10G→100G方向实际为store-and-forward | NY5另有2台1G DCS-7280SR3-48YC8，标Store-and-Forward；数量不能套其他PoP |
| Data Center Core | NY5共4台DCS-7304；BZX跨Core3/4 | 到Environment Core为4×100G Port-Channel，标Cut-Through | 每个业务环境分布于两台DC Core；没有逐端口交叉矩阵 |
| Environment Core | BZX Equities共2台DCS-7260CX3-64E-R | 连接BZX ToR与DC Core，标Cut-Through | 其他交易环境有各自的这一层；C1单独架构不套用 |
| Top of Rack | BZX Equities共4台DCS-7050SX3-48YC8 | 每个订单服务器NIC连接两个ToR，active/passive；标Cut-Through | 原文给出冗余模型，未给服务器端口与ToR端口完整配对 |
| TAP观测分支 | NY5 Expanded View结合时间戳规范Table 2 | 在两级Core之间分光；Cboe时间戳服务支线经PTP同步的汇聚交换机加戳；Corvil沿原架构图保留独立观察支线 | Optical TAP自身不加戳；汇聚交换机与采集器是业务旁路 |

BZX Unit1参数取自PITCH 2.41.77的US Equities Production配置表及BZX Multicast Routing Parameters，不能用Certification表或Cboe欧洲组播接入规则替换。

| 项目 | ZA / A feed | ZB / B feed | 解释与边界 |
| --- | --- | --- | --- |
| 源地址前缀 | `174.136.161.160/28` | `174.136.161.192/28` | 是源网段，不能直接拿前缀冒充单一S写入`(S,G)` |
| RP | `74.115.128.140` | `74.115.128.142` | 美国生产表公开了RP；这不单独证明客户边界使用哪种IGMP/PIM接入模式 |
| 实时组 | `224.0.130.128` | `233.209.92.128` | 实时订阅与补包订阅分别核对 |
| Gap Response组 | `224.0.130.144` | `233.209.92.144` | GRP重放走这些专用组播组；收到TCP响应不等于收到补包 |
| Unit1 UDP目的端口 | `30001` | `30001` | 端口参与应用/ACL匹配，不属于PIM建树键 |
| MTU | `1500` | `1500` | 来自生产配置限制，不推算成UDP净载荷，也不套客户隧道开销 |

在本轮已核对的美国Connectivity/PITCH材料中，未找到足以断言客户边界必须采用IGMP或PIM的具体交付规定。退役图5只演示客户内部跨子网的PIM设计；实际市场边界须按所购连接的技术交付合同确认。PITCH的RP不能因通用SSM更简洁而删去，也不能从RP表反推完整PIM邻接与地址族配置。

GRP使用TCP处理请求，Gap Server在专用UDP组播重放，重放可早于或晚于Gap Response到达；Spin Server按unit通过TCP提供簿状态，客户端与缓存实时增量按序号衔接。GRP/Spin的地址、端口与认证参数由Cboe分配，图中不填猜测值。Feed A/B合并只表达应用数据完整性责任，不自动证明客户拥有两套独立物理故障域。

## 历史阶段保留

以下记录解释旧收据的对应稿件。现行范围以页首的读者顺序与官方原图修订为准。

| 阶段 | 当时编排 | 对应原件或收据 | 本轮处理 |
| --- | --- | --- | --- |
| 2026-09-10初稿 | 参考稿约1/4～1/3；2329可见字符、两图三表 | [初稿收据](evidence/chapter01-market-access-20260910.json) | `01-china-market-access.svg`和`01-us-market-access.svg`原件留历史；不改写旧摘要 |
| 2026-09-11网络边界复核 | 保持长度附近，补BGP/四层/MTU等；2542字符 | [网络修订收据](evidence/chapter01-network-review-20260911.json) | 产品、接口和控制归属仍适用；旧图数/篇幅限制被本轮授权接管 |
| 2026-09-11格式收尾 | 来源表21条统一四列；正文2538字符 | [格式收尾收据](evidence/chapter01-source-table-closeout-20260911.json) | 作为本轮字数基线；该阶段没有重新联网核验 |

初稿曾将接线细目、完整补包过程等移出正文；本轮按网络设计需求重新选取相关内容，原“未带入正文”清单不再作为排除规则。原参考稿的12个本地图片引用当时无对应文件，官方图仅用于核对后重绘，不据引用存在宣称取得原件。上交所2023白皮书附件当次下载失败，没有把其中图片登记为成功取得。

仍保留的事实边界：无日期广域页面中的站点/运营商名称不等于全部现役布局；托管可使用共享广域服务；Equinix单模要求限定新订单；SEC财务风控与有限监管控制分配例外分别解释；客户VLAN、ACL、电源与接口计数检查等设计建议不得冒称Cboe规定。此前LDDS1.2.3官方PDF已核对第11/13页，552199字节，SHA256为`811aea82aa01d6830d2f19e2e1453ef733860bda5f1fc3aee407f8e5c88f6588`；该记录保留原核验身份，不代表本轮再次下载。此前eCFR直访失败的事实也不改写，SEC依据仍为正式发布稿和官方FAQ。

## 历史：九图阶段验证入口与范围

本轮只修改教材、来源说明和图资产；公开资料核对与本地渲染不属于课程设备验证。没有连接课程设备、生成RUN_ID或提升已有实验的实机范围。

新收据为[九图扩展验证](evidence/chapter01-network-expansion-20260911.json)：正文4501可见字符、9图5表；本来源表28条资料、四列。Markdown与940/390px渲染、九图800/1200px显示及347文字边界/无重叠、60箭头几何、8 Bash/17 text/2 Mermaid与扩展外正文保持、原参考稿/历史两图保持、80导航、42/240图片SHA已完成本地检查。收据记录最终源码摘要与核验边界，前三份历史收据保持原样。

## 历史：读者顺序修订与后续修补

本次只修改第一章扩展、第七章真实授时案例及配套图件/来源/治理。保留原命令、输出、导航与旧图字节；不操作设备、不生成 RUN_ID、不写 Git 历史。前一节九图阶段的显示结果不代替本次检查。

最终文稿与图件摘要、原图对应关系、术语复核、实际 Markdown/浏览器检查见[读者顺序修订收据](evidence/chapter01-access-flow-20260911.json)。

2026-09-11 后续图片修复：Equinix 改嵌官方原图，深交所改用同源 PNG。此前本地 SVG 解码通过，未能复现用户预览裂图的具体原因；不将兼容处理记为根因已定位。当前显示和文件身份见[图片修复收据](evidence/chapter01-image-display-fix-20260911.json)，上一收据保留修订前身份。

2026-09-11 资格与托管措辞补修：正文先明确本例普通量化客户必须委托券商；取消交易参与人资格长段，保留沪市股票与普通客户范围。删除“机房框内同时列有……”及该处原图链接；SmartX 软件分组不能证明三方共用实际机房空间。上交所规则 §2.2.1、3.1.1—3.1.2、3.2.1 经官方域名搜索解析正文重新核对，DOCX 本地下载 TLS 失败；中泰指南和已保存原图复核成功。收据见[资格与托管说明修订](evidence/chapter01-broker-colocation-clarity-20260911.json)。

2026-09-11 配线架图取舍：用户认为实体配线架外观对本节无帮助，已撤图及图卡，不补画替代图。交付文字改按办理顺序解释 LOA、Demarc、客户跳线；单模光纤、路径冗余、交易接口与券商风控内容保持。扩展现2图7表；该美国小节外正文、导航、全部围栏及其余嵌图保持，Markdown加粗与表格检查、52/250图片SHA通过。图片与摘要清单字节均未改；本轮无重新联网或设备实验。


## 历史：2026-09-11 三分区关系图收尾

本次只改第一章国内段、新关系图与配套说明/治理。普通客户下单与行情许可分开，补会员具名实例及基金/保险租用交易单元的限定；SmartX、XTP、TCPDirect、XDP按所在层解释。文件网关补具体输入输出，LDDS/VDE/VSS按发布—接入—处理串起；美方网络要点及第七章均保持。

新取得原件：深交所网关部署1.01为2173504字节、SHA256 `57601c4455499637f6763de31d4e5b41cbc3a33d4dc9c95fdf61a473ef180d03`；接入技术规范1.06为257081字节、SHA256 `31607803d01917e5614546dd06557fc831fcd03fe8101cd1ccf873a771aac7ae`；TCPDirect Issue19为479067字节、SHA256 `970113b513bc9beb8baf4ec5d4d567e19ef613baa1e8e45604447a9956b5b616`。前两份浏览工具直取超时，Python直接下载官方URL成功，已提取全文并查看相关图页；AMD实际PDF为Issue19，不采用搜索摘要中的旧Issue18。

灰色连接仅表示网关与交易所通信服务的业务往来；当前两份指引未逐段给出其传输协议，没有以旧2018灾备环境地址表代替2026生产协议。完整网关手册/机构实际交付参数仍待取得。会员动态总表未取得可用行数据，具名实例依基金发行人公开披露；不据此宣称完成全部机构名册核对。另查2022港股通指南支持基金/保险租用单元的例子，但正文采用直接的会籍问答，避免再引入跨境业务。

最终图文摘要、50行四列来源表、Markdown/本地HTTP显示、800/1200px图形与箭头检查、两级54/252图片SHA、范围保护结果见[关系图收据](evidence/chapter01-access-relationships-20260911.json)。本地显示通过不等于用户的VSCode远程预览已确认；无课程设备操作、RUN、部署或Git历史写入。


## 深交所接口补充资料

本节只供比较来源，不带入第一章的沪市主线。按深交所2026部署指引，三类网关在市场参与者一侧运行，分别与市场侧服务通信：

| 网关 | 处理什么 | 与低延时主线的关系 |
| --- | --- | --- |
| TGW 交易网关 | 接收业务程序委托、送回订单和成交结果 | 交易路径；开发指南规定相应 OMS—TGW 接口采用 TCP |
| MDGW 行情网关 | 接收 Level-1/Level-2 等行情 | 行情路径；网络版面向业务程序提供 TCP 实时/重传端口 |
| FxClient 文件网关 | 收参考资料、收盘行情、成交汇总等文件，也可按业务上传 | 属业务文件交换；如基金申购赎回清单、融资融券文件，本章不展开 |

依据：[网关部署指引 V1.01](https://www.szse.cn/marketServices/technicalservice/serveGuide/P020260512403297957730.pdf)、[开发指南 Ver1.09 §4.3、5.7](https://docs.static.szse.cn/www/marketServices/technicalservice/guide/P020260519353303152094.pdf)。应用接口的 TCP 不能据此推定每段网关—市场端的协议。

[深交所接入规范 Ver1.06 §4—5](https://www.szse.cn/marketServices/technicalservice/serveGuide/P020260529566082416677.pdf)另要求不同运营商冗余、市场互联使用三层路由端口、托管冗余、接入网与互联网隔离及重要边界访问控制。它与上交所某一局域产品“无需额外路由器”属于不同接入规范。

## 历史：2026-09-11 图文压缩与核验

行情服务商资料来自本会话已联网读取的 Wind 产品页、iFinD 接口示例及上证云手册；主来源表53行四列。正文保留前两家的程序接口实例，上证云手册中的通达信、大智慧、钱龙等仍可在来源表查到。产品介绍与合作信息商列表不是完整现行授权名册；动态许可公示此前未取得可用名单。

两张国内图均按已核文字/接口关系整理：订单图的客户接口仅以 XTP-Pro 标 TCP，券商到市场段不推定传输协议；LDDS 图的 TCP 只覆盖已核的 DDS/SDS—VDE—VSS。SDS 的重建/静态数据接口不是 FxClient 的批量业务文件交换。物理图的运营商/站点仅代表所引无日期服务页，不能推定全部现役布局。

最新取得的8月指南处于G4升级语境，Level-2的“至少20Mbps”与6月LDDS总册“建议20Mbps”分别标版本。2024接入条款沿用本会话已成功解析证据，本轮再取超时；尚未通过本次浏览证明特定券商现网配置或G4已上线。

当前文稿摘要、图线来源、两级图片清单、Markdown 与本地 HTTP 显示、范围保护见[图文压缩收据](evidence/chapter01-quote-vendors-20260911.json)。此前三分区图收据保留历史身份；本地检查不等于用户远程预览已确认。无设备访问、RUN或Git历史写入。

## 历史：2026-09-11 TCPDirect实例、LDDS分工与备用行情

南华官方HTML已直接取回96395字节，SHA256 `0333e178f274c675bbd04f6cc7439dcffa5366bf65b2c6d845e29764b8861d62`；OnixS页面浏览工具成功读取源码，本地urllib下载TLS失败，不记录本地原件摘要。后者是厂商参考实现，前者是机构自述案例，均未在本课复现。没有把搜索中的同名SmartX超融合产品当作中泰SmartX，也未用未提TCPDirect的恒生API手册作支持证据。

LDDS原件PDF第5页表1-2将SDS写为“数据重建和用户认证服务器（Static-data Distribution Server）”，VSS为Vendor Supplied System；第11—13页及第19页给实时/重建连接和请求流程。图按这些关系补两端口；认证只在职责注明，不补画未核实的认证会话。源文件身份沿用1.2.3既有SHA，未冒称重新下载。

上交所接入第8条先要求不同运营商、同城双站点与独立UDP行情线路，再允许已满足条件的会员以交易线接备用TCP行情并管理带宽。正文/图仅表达这一许可，不声称UDP故障必然自动切换、切换时长、完整数据无缝衔接或交换机协议转换。局域/广域图下方只说明交易接入产品；LDDS重建和此备用接入分别解释。

现来源表55行四列，图片资产数仍56/254。文稿、图形与检查摘要见[本轮收据](evidence/chapter01-tcpdirect-ldds-backup-20260911.json)；前轮压缩收据与旧图保持历史身份。美国段、第七章、代码/输出围栏及课堂设备状态不变。

## 历史：2026-09-11 只讲国内，展开南华的实施分工

南华 2020-10-14 官方 HTML 于本轮成功取回，100899 字节，SHA256 `873e8488e8f148167cbd10788a18b05dd95b28b9bfc0a8e02887508e81c25961`。4 月报道浏览直访本轮失败，官方域搜索仍返回全文，与本会话已取得的 HTML 内容一致；其原件摘要沿用上条，不声称重新下载。两篇分别证明研发选择和客户接入服务，不能由此推定 2026 年产品状态。

本轮撤去美国正文及 Cboe 嵌图，把 OnixS/南华并列表改成南华的开发、客户接入、托管网络三层说明。客户 API 路径是两篇报道的功能关系归纳；公开资料未给 TCPDirect 客户端包选择、调用名、完整业务编码、网卡型号或交换机逐跳图，不据此编造配置或实例源码。AMD 指南用于解释一般适配动作，不冒称南华源码。

最新文稿、56 行四列来源、图片引用与本地显示、范围保护见[国内与南华案例收据](evidence/chapter01-china-only-nanhua-20260911.json)。两张国内图及全部旧图片、旧收据、第七章保持原字节；图片清单仍为 56/254 项。无设备操作、RUN 或 Git 历史写入。
