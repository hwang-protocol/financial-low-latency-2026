# 第六章券商 SDK 与网络栈适配：来源及范围

日期：2026-09-11。对应[第 05 章真实接入小节](../05-openonload-tcpdirect-dpdk-kernel-bypass.md#broker-sdk-access)。

## 编排

用户明确第一章只介绍网络架构，将券商协议、SDK 和旁路适配移到第六章。新小节位于四路实验之后的“从结果回到工程选型”，以接口交付方式连接实验和真实接入，不增加实验步骤。第一章保留网络双图、TCP/UDP、组播、LDDS、冗余及备用线路；第零章南华实例的展开链接同步改到本节。

## 官方依据

本会话已联网读取以下官方页面，并复读已取得的 AMD 原件。下表区分公开实施事实、通用机制与尚未证实的兼容性。

| 官方资料 | 版本或日期 | 采用内容 | 适用边界 |
| --- | --- | --- | --- |
| [中泰 XTP-Pro 交易开发指南](https://xtp.zts.com.cn/xtp-pro/API4/交易XTrader-API使用指南QuickStart.html) | 页面无发布日期；2026-09-11 核对 §1—2 | 头文件 `xtpx_trader_api.h`、Linux 库 `libxtpxtraderapi.so`；创建接口、登录、下单和回调 | 说明库的交付及调用方式，不等于已取得完整业务报文规范或内部源码 |
| [AMD Onload Transparency](https://docs.amd.com/r/en-US/ug1586-onload-user/Onload-Transparency) | UG1586 在线指南；2026-09-11 核对 | 利用 LD_PRELOAD 拦截标准 BSD socket 调用；受支持的应用通常无需修改或重编译 | 需确认目标 SDK 的调用方式、硬件及运行环境；不保证 XTP-Pro 兼容 |
| [AMD TCPDirect User Guide](https://docs.amd.com/v/u/en-US/SF-116303-CD-TCPDirect_User_Guide) | Issue 19；门户日期 2026-06-10；PDF 第15页 §1.1 | 要改用 TCPDirect 网络 API 并重编译、链接；无收发源码时考虑 Onload | 开发者可以是应用作者，也可以是 SDK 供应方；客户不必重写 TCP 协议栈 |
| [南华 NHTD2 研发报道](https://www.nanhua.net/news/2020/04/85ff7329-0327-4ad2-a602-bc0e54090674.html) | 2020-04-28 | 南华研发团队重构 NHTD2，采用 TCPDirect，委托与回报流分离，支持 TCPDirect 客户交易 | 期货、期权系统的历史自述；未公开本节可复现的客户端 SDK 调用或配置 |
| [南华客户技术与托管服务](https://www.nanhua.net/news/2020/10/2196ee99-f610-4122-84a2-4dfb6b27dad0.html) | 2020-10-14 | 客户 API 开发与测试指导、主机托管或租用、网络策略开通 | 支持接入分工，不证明当前产品配置或其他券商的接口兼容性 |

AMD Issue 19 原件为 479067 字节，SHA256 `970113b513bc9beb8baf4ec5d4d567e19ef613baa1e8e45604447a9956b5b616`，沿用本会话已取得的官方 PDF，迁移时重新提取相关页核对。取得记录见[第一章接口关系历史收据](evidence/chapter01-access-relationships-20260911.json)。南华两篇原件摘要及取得方式见[原来源说明](FLLE_Trading_Network_Access_2026-09-10.md)，不覆盖历史收据。

## 讲解边界

- 库级 API 与协议级规范是两个层次。自编程序调用库，与绕过库实现业务报文收发，拥有的改造范围不同；`.so` 文件本身不证明许可证或源码开放政策。
- XTP-Pro 公开交付说明不足以证明其完整私有编码格式，也不足以确认或否认全部 HTTP/REST/gRPC 接口。本节只写已核实的库交付和 TCP 登录，不推测未公开报文。
- OpenOnload 的透明机制是可评估的路径，须检查目标订单连接实际加速；TCPDirect 需收发代码适配，或由供应方提供已适配的库。不把表中的条件选项写成中泰已支持。
- 南华实例回答由谁改系统、客户怎样开发及接入。未取得源码，不给出虚构的 NHTD2 初始化调用，也不将其视为本课实盘结果。
- 不采用固定 300—350 ns 差值或 HTTP/JSON 固定数十微秒开销。生产兼容性与收益需要目标 SDK 的独立测试，本课原 RUN 和四路测量结论不变。

南华 2020 年客户服务文章还列出调优专用服务器、Nexus 3548 与 Metamako 一层交换机，用于连接交易所、交易系统区与客户托管主机。此处保留网络事实供来源核查，公开报道没有逐跳拓扑，正文不由型号编造设备次序。

## 本轮验证

本轮仅迁移、压缩文稿和更新交叉链接。局部 Markdown、导航、命令/输出保护、图片摘要与浏览器预览结果记录在[本地核验收据](evidence/chapter01-06-sdk-relocation-20260911.json)。无新增运行代码、设备操作、RUN 或生产 SDK 验证。
