# 第 08/09 章 FPGA 行业案例核对（2026-09-17）

状态：DOC / SOURCE REVIEW；未执行设备实验，未改变上轮保留的行情缺口。用户要求沿用第七章：章末以一张图汇总真实案例，文字简短并留下原始出处。

## 第八章：交换机中的 FPGA

| 案例与原始来源 | 采用的事实 | 图示边界 |
| --- | --- | --- |
| [Enyx / Arista](https://www.arista.com/assets/data/pdf/CaseStudies/Enyx-Case-Study.pdf)，PDF 第 2–4 页 | Enyx 将 FPGA 应用部署到 7130；nxLink Secure 为无线与备用光纤做报文仲裁 | 厂商部署案例，未补造交易机构名称；不把 L1 交换时延当作 FPGA 应用时延 |
| [Deutsche Börse / MetaWatch](https://www.arista.com/assets/data/pdf/CaseStudies/CaseStudy-DeutscheBoerse.pdf)，PDF 第 2–3 页 | 7130 内置 FPGA 与 MetaWatch 用于报文监测、时间戳及汇聚 | 简化为业务路径旁的监测副本；不是监测程序代交易所处理订单 |
| [Netnod / Arista](https://www.arista.com/assets/data/pdf/CaseStudies/Arista-Netnod-CaseStudy.pdf)，PDF 第 1–3 页；[开源工程](https://github.com/Netnod/FPGA_NTP_SERVER) | NTP/NTS 公共时间服务部署到 7130 FPGA | 总览只画普通 NTP 查询，不把 NTS 密钥协商等全部软件职责画进 FPGA；原文固定版本工程与命令保持 |

Enyx 与德交所 PDF 表格、架构图已另取本地页面图核对；三份 PDF 的原文均通过网页工具读取。

### 同日补充：专用微波与光纤冗余

用户追问无线主用是否合理后，补查 [Euronext 的微波交易网络说明](https://www.euronext.com/en/news/reducing-latency-stock-exchange-order-data-transmission-wireless-microwave-networks)与 [nxLink 官方产品说明](https://www.exegy.com/products/nxlink/)。前者说明跨城专用微波与较直接路线的时延收益；后者明确微波天气敏感、光纤备用，以及复制报文和接收端去重能力。正文增加紫色“小知识”卡，图中改为“专用微波 / 光纤冗余 / 报文仲裁与去重”，不再让读者把它当作普通无线局域网或故障后才启用的冷备链路。图只表示一种受支持的冗余机制，未外推所有部署或给出实测时延。

## 第九章：FPGA 网卡与带网口的加速卡

| 案例与原始来源 | 采用的事实 | 图示边界 |
| --- | --- | --- |
| [Exegy / Enyx nxFeed](https://info.exegy.com/hubfs/Products/2025-03-OS-Exegy-FactSheets%20nxFeed.pdf)，PDF 第 1–2 页 | FPGA NIC 处理行情、A/B 仲裁、筛选及建簿；本机模式经 PCIe/API 交给应用 | 公开商用方案，图只画本机交付；不宣称某具名量化机构已部署 |
| [AMD / Algo-Logic CME Tick-to-Trade](https://www.amd.com/content/dam/amd/en/documents/products/accelerators/alveo/u50/algo-logic-t2t-product-brief.pdf)，PDF 第 1–2 页 | Alveo U50 上的行情处理、订单簿、可定制触发、订单发送及控制 API；规格明确含以太网接口 | 带网口的 FPGA 加速卡；公开商用方案，不等于本课 U250 镜像可直接运行该产品；省略厂商性能数字 |
| [Microsoft，Azure Accelerated Networking，NSDI 2018](https://www.microsoft.com/en-us/research/wp-content/uploads/2018/03/Azure_SmartNIC_NSDI_2018.pdf)，§2.4、§4、§5 | FPGA SmartNIC 卸载网络策略；新流由软件确定动作，已配置流由硬件处理 | 历史部署架构；FPGA 与 NIC 配合，经 NIC 交付 VM，不把所有流量画成无条件绕过软件 |

nxFeed 与 Azure 的原始架构图已本地渲染阅读。AMD PDF 网页正文完整读取；本地下载超时/HTTP2 错误，未假称另行审阅了该 PDF 的本地图片。图依据文字和产品规格概括功能，没有复制厂商架构图或加入未核验的性能数字。

## 改动与验证范围

两章均在硬件讲解末尾、回顾之前新增一个短案例小节；各用一张 1200×1380 SVG，正文显示同源 1600×1840 PNG 并链接 SVG。保留原 Netnod 工程、U250/OpenNIC 讲解、所有原图、绿色入口、代码围栏及终端样例。

检查结果登记在 [可提交核验索引](evidence/ch08-09-fpga-cases-20260917.json)：来源与事实边界、800/1200px 整图目视、800/1200/1600px 文字边界、箭头几何、Markdown/HTML/本地引用、保护文件摘要及两级图册 SHA。

本轮没有新 RUN_ID，没有接触设备或网页交易状态，没有实测这些外部硬件。此处保留 FPGA 案例的来源核对；退役 P4/软件模型的实跑报告不属于当前课程迁移范围。
