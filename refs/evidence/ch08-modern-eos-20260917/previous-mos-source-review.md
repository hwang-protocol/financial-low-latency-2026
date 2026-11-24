# FPGA 推演稿：来源与逐项核对

核对日期：2026-09-17。本文是教师/维护者的依据页；正文按确定的一条路线讲授，不把资料检索过程穿插进课堂。

**结论：Arista 7130 开放 FPGA 应用开发，报文过滤是其公开支持的用途；本章 RTL 描述了能实现一次过滤的电路逻辑。当前交付包含功能仿真与通用综合通过的核心，尚未包含完成板级连接的可加载工程。** 有设备、匹配的完整 FDK 与许可并完成这些连接，才具备构建、装载与上板验收的条件。“有一台交换机”本身不等于当前目录直接 make 即可部署。

## 固定资料版本

- OpenFDK：[`13a7aac5b0aaba1ed7bbeb04dd71c5b3bded6d9d`](https://github.com/aristanetworks/openfdk/tree/13a7aac5b0aaba1ed7bbeb04dd71c5b3bded6d9d)。参考示例 Makefile 的版本是 `3.2.0.openfdk`，本课衍生应用约定 `flle_filter` / `0.1.0`。
- 台架：DCS-7130-48LB / `lb2` / XCVU9P-FLGB2104-3-E，管理路线为 MOS。官方示例表列 MOS 0.37.0+；这不是本课已安装的系统版本。
- 工具参考：Vivado 2023.1。核对的 `resources/vivado.mk` 列出 2019.2 或 2023.1 的完整许可要求；选定完整 FDK 的 IP/器件依赖仍须保持一致。
- Netnod：[`04c89fd2f2347843246ad825ace986db7408fe89`](https://github.com/Netnod/FPGA_NTP_SERVER/tree/04c89fd2f2347843246ad825ace986db7408fe89/FPGA/targets/ntps_arista)。只借助其公开 MOS 部署确认安装/应用通道的机制，不把 NTP 工程冒充本课 NVDA 过滤工程。该项目 `build.sh` 使用 FDK 2.5.0；README 留有更旧版本文字，不混入本章 OpenFDK 工具版本。

## 逐项依据

| 正文内容 | 第一手依据 | 已确认的事实与边界 |
| --- | --- | --- |
| FPGA 基础资源 | [AMD UG574](https://docs.amd.com/r/en-US/ug574-ultrascale-clb/Introduction) | LUT 实现逻辑函数，存储单元可实现边沿触发寄存器，可编程互连连接逻辑/存储资源；资源与金属线路已经制造，配置改变功能和可选连接 |
| 网络附着 FPGA 可以过滤报文 | [Arista Developer](https://www.arista.com/en/products/7130-developer) | 厂商明确列出 filtering、aggregation、timestamping；有 FPGA 开发工具包、Vivado 项目与管理接口 |
| 48LB 的器件与板标准 | [nullverilog 支持表](https://github.com/aristanetworks/openfdk/blob/13a7aac5b0aaba1ed7bbeb04dd71c5b3bded6d9d/examples/nullverilog/README.md#supported-board-standards-and-operating-systems) | lb2、XCVU9P-FLGB2104-3-E；不从型号名称猜芯片 |
| 下载与安装 Vivado | [AMD 2023.1 下载页](https://www.amd.com/en/support/downloads/adaptive-socs-and-fpgas/development-tools/2023-1.html)、[UG973 Installation Flow](https://docs.amd.com/r/2023.1-English/ug973-vivado-release-notes-install-license/Installation-Flow) | 正文 `./xsetup` 指解压完整 Linux 安装包后运行；工具装在开发机 |
| FDK 工具要求 | [vivado.mk](https://github.com/aristanetworks/openfdk/blob/13a7aac5b0aaba1ed7bbeb04dd71c5b3bded6d9d/resources/vivado.mk) | 版本与许可要求可回源；不把 Lab Edition 当完整综合工具 |
| nullverilog 能做什么 | [官方示例说明](https://github.com/aristanetworks/openfdk/blob/13a7aac5b0aaba1ed7bbeb04dd71c5b3bded6d9d/examples/nullverilog/README.md) | 可复制为衍生应用框架；原示例没有本课报文过滤逻辑，修改支持不作厂商保证 |
| SystemVerilog → 硬件 | [UG901 综合](https://docs.amd.com/r/2023.1-English/ug901-vivado-synthesis)、[UG904 实现](https://docs.amd.com/r/2023.1-English/ug904-vivado-implementation) | 组合逻辑、寄存器和连接由综合映射，实现再布局/布线；没有运行本课 Vivado 构建 |
| 本地开源验证工具 | [Icarus](https://steveicarus.github.io/iverilog/usage/installation.html)、[YoWASP](https://yowasp.org/)、[PyPI包](https://pypi.org/project/yowasp-yosys/)、[pip安装](https://pip.pypa.io/en/stable/installation/) | Ubuntu Icarus11.0、独立环境 Yosys0.69；实际完成仿真及通用综合，不生成7130配置镜像 |
| XSim 命令 | [UG900 Batch Mode](https://docs.amd.com/r/2023.1-English/ug900-vivado-logic-simulation/Running-the-Vivado-Simulator-in-Batch-Mode) | xvlog 读源码、xelab 展开、xsim 运行；本轮真正运行的是 Icarus |
| IPv4/UDP 长度 | [RFC791](https://www.rfc-editor.org/rfc/rfc791)、[RFC768](https://www.rfc-editor.org/rfc/rfc768) | IHL=5 时 IPv4 头 20 字节；UDP 头 8 字节，其 length 包括 UDP 头 |
| MoldUDP64 头与消息长度 | [Nasdaq 规范，第3–4页](https://nasdaqtrader.com/content/technicalsupport/specifications/dataproducts/moldudp64.pdf) | 10 字节 session、8 字节第一条消息序号、2 字节消息数；每条消息另有 2 字节长度，不计入消息长度值；数值大端 |
| ITCH A 字段 | [ITCH 5.0，第4、13页](https://www.nasdaqtrader.com/content/technicalsupport/specifications/dataproducts/NQTVITCHspecification.pdf) | A 长36字节；Locate 偏移1、Stock 偏移24且长8，字符左对齐补空格；8095 是课程数据事实而非固定证券编号 |
| 100 字节及偏移 | 上述协议＋本课 `nvda_match.sv` | 14+20+8+20+2+36=100；序号52–59、Locate65–66、Stock88–95；限定无VLAN/选项/分片且一包一条 |
| make / 产物名 | [示例 Makefile](https://github.com/aristanetworks/openfdk/blob/13a7aac5b0aaba1ed7bbeb04dd71c5b3bded6d9d/examples/nullverilog/Makefile) | BOARDSTD 限定板型，PROJECT/VERSION_ID 参与命名，默认构建 RPM/SWIX；本课未生成制品 |
| 打包依赖 | [app.mk](https://github.com/aristanetworks/openfdk/blob/13a7aac5b0aaba1ed7bbeb04dd71c5b3bded6d9d/resources/app.mk) | 使用 rpmbuild、Python venv；SWIX 规则固定 switools1.2 等依赖，并非正文臆造打包器 |
| Python 装载和停用 | [Arista example.py](https://github.com/aristanetworks/openfdk/blob/13a7aac5b0aaba1ed7bbeb04dd71c5b3bded6d9d/examples/nullverilog/src/example.py) | get_fpga_devices、board_standard、communicator、load_image/unload_image、App 生命周期均有原代码 |
| CSV 和 CLI | [RegisterFile](https://github.com/aristanetworks/openfdk/blob/13a7aac5b0aaba1ed7bbeb04dd71c5b3bded6d9d/resources/libapp/register_file.py)、同上 example.py | CSV number 映射寄存器编号，库实施只读保护；cli_command 与 config-app 模式有示例；arm once/disarm/show filter 是本课新增命令 |
| MOS 安装与应用通道 | [Netnod 部署 README](https://github.com/Netnod/FPGA_NTP_SERVER/blob/04c89fd2f2347843246ad825ace986db7408fe89/FPGA/targets/ntps_arista/README.md) | install app .swix、重新登录、app/no shutdown、Et1 source ap1 / destination ap1 为公开工程用法；正文两口连接是按此语义构造的过滤台架，待上板核对 |
| 真实行业应用 | [既有三案例核对](../../FLLE_Ch08_09_FPGA_Cases_2026-09-17.md) | Enyx、德交所、Netnod 依公开部署资料，保留原始链接；没有把厂商指标移植到本课 |

## 外部评估复核与修订（2026-09-17）

评估的工程缺口判断成立；下列项目重新按一级来源核对。课堂只保留影响流程的条件，具体争议留在本页。正文41个代码/命令/输出围栏、16段源码摘录与所有实现文件均未改动。

| 评估项 | 核对结果与正文处理 |
| --- | --- |
| 有7130就能完成 | 不成立。显著前置⑦～⑨的条件：配套FDK/IP/许可，以及MAC/队列、寄存器总线/CDC、时钟复位三组适配。当前没有板级工程、`.bit` 或 `.swix`。 |
| MAC/PCS来源 | [Arista IP Cores](https://www.arista.com/en/products/7130-ip-cores)明确将10G MAC-PHY作为许可IP提供。不能假设公开OpenFDK或买设备就自动包含所需许可；最终组件范围按授权材料核对。 |
| 48LB生命周期 | [官方公告](https://www.arista.com/en/support/advisories-notices/end-of-sale/13234-end-of-sale-7130-48l-b)：停售2022-03-30；软件修复支持终止2024-03-30；TAC/RMA及EOL为2025-03-30。正文定位为历史教学台架。 |
| 替代型号 | 同上公告为48LB→48LBS；[另一公告](https://www.arista.com/en/support/advisories-notices/end-of-sale/13444-end-of-sale-7130-48la)是48LBA→48LBAS。不能混成同一替代关系。 |
| 48LBS/48LBAS是否lb2 | 固定 [device.py](https://github.com/aristanetworks/openfdk/blob/13a7aac5b0aaba1ed7bbeb04dd71c5b3bded6d9d/resources/libapp/device.py) 的 `DCS-7130-(32\|48)LB(A\|C)?S?` 正则明确映射lb2；48L/48LS另为l/VU7P。型号识别不等于任意OS/FDK/IP组合可部署。 |
| MOS与EOS | 本章锁定MOS。EOS使用 [l1 source](https://www.arista.com/en/um-eos/eos-7130-layer-1-commands) 与 [l1 connect](https://www.arista.com/en/um-eos/eos-configuring-layer-1-on-the-7130-platform) 等命令，不能直接照抄MOS安装/连接步骤。 |
| 顶层必须VHDL | 评估错误。固定 [cfg.json](https://github.com/aristanetworks/openfdk/blob/13a7aac5b0aaba1ed7bbeb04dd71c5b3bded6d9d/examples/nullverilog/src/nullverilog-lb2-cfg.json) 真实列 `nullverilog-lb2-top.sv` 与 `src/boards/lb2/board_top.sv`；README的VHDL文件表与实现不一致，按实际构建清单保留SV。课内flle_filter顶层只是待实现文件名。 |
| 双口架构与命令 | [MetaProtect](https://www.arista.com/en/products/7130-meta-protect)正式支持端口对单向/双向过滤及未过滤方向直通，架构成立。但[Netnod部署](https://github.com/Netnod/FPGA_NTP_SERVER/blob/04c89fd2f2347843246ad825ace986db7408fe89/FPGA/targets/ntps_arista/README.md#production-use-using-a-sfp-port)证明单口连法；本课六行仍为两口设计，须读回、抓包验证。 |
| ap1是否会出现 | device.py根据SKU的固定 `app_ports` 构造端口列表，并非从用户RTL枚举。不能断言没有MAC就不显示ap1；可以确定没有收发数据通路就不能过包。 |
| 单缓冲与线速 | RTL的FORWARD/DECIDE阶段不接收下一帧。将台架明确改为逐帧低速发送，队列由板级补齐；未交付持续10G实现；吞吐还取决于内部时钟和缓冲，不能仅凭单缓冲就断言任意时钟下均不可能10G。核心前的队列丢包不自动进入核心 `error_count`，必须另计。 |
| 提前转发 | 本例必须等Stock第95字节到齐；先发帧头再命中不能保持“整帧未发出”。不能把所有生产过滤器概括为无需缓存的cut-through。 |
| 光模块与DAC | Netnod说明仅针对其自用MAC：铜SFP可能不稳，要求当时使用10G SR/LR光模块。不能外推所有DAC/厂商MAC。本文改为介质、MAC/PCS与板卡共同支持才接线。 |
| 下载与构建耗时 | [AMD2023.1](https://www.amd.com/en/support/downloads/adaptive-socs-and-fpgas/development-tools/2023-1.html)完整统一SFD为110.85GB，Linux网页安装器265.94MB后续仍下载组件。大包准备与完整实现放课前；没有本课小时数实测。 |
| 内存估计 | [UG973入口](https://docs.amd.com/r/2023.1-English/ug973-vivado-release-notes-install-license/System-Memory-Recommendations)导向[AMD当前表](https://www.amd.com/en/products/software/adaptive-socs-and-fpgas/vivado/vivado-buy.html)，XCVU9P典型20GB/峰值32GB，基于约75%LUT利用率与单次综合/实现。不能改写为本课2023.1的32–64GB硬门槛。 |
| load_image后立即读ID | device.py默认 `blocking=True`，EOS分支等profile applied；MOS交给mosapi，公开代码不足以断言非阻塞。`RegisterFile`异常重试等待1/10/100/200/250/1000ms，不对成功读出的错误ID重试。保留ID校验，不加入无依据sleep；板级验收须确认配置→时钟锁定/复位释放→寄存器就绪。 |
| 假设台架与现役平台 | 图中改为台架发包/收包端；仅模拟课程地址和包型，不串入现役`.1/.2/7150`，不继承7150的VLAN/IGMP/PTP/QoS能力。 |

本轮只改讲义与图示，沿用实现摘要一致的既有Icarus/Yosys证据；未重跑硬件验证。新核验索引：[评估修订与精简检查](../ch08-arista-fpga-review-20260917.json)。

## 第二次评估复核（2026-09-17）

此次重新下载固定提交的6份工程文件，逐行核查顶层和构建产物；另核NASDAQ协议、RFC768、Arista生命周期及MOS/EOS来源。当前核心代码未发现由本次评估证明的新错误，板级未交付的结论保持。

| 追问 | 已确认的结果 |
| --- | --- |
| `top_v` 是不是必须保留 | 沿用原封装时是。[应用源码L29](https://github.com/aristanetworks/openfdk/blob/13a7aac5b0aaba1ed7bbeb04dd71c5b3bded6d9d/examples/nullverilog/src/nullverilog-lb2-top.sv#L29)声明top_v，[board_top L254](https://github.com/aristanetworks/openfdk/blob/13a7aac5b0aaba1ed7bbeb04dd71c5b3bded6d9d/src/boards/lb2/board_top.sv#L254)按此名实例化。Vivado工程根模块为board_top，[vivado.mk L63](https://github.com/aristanetworks/openfdk/blob/13a7aac5b0aaba1ed7bbeb04dd71c5b3bded6d9d/resources/vivado.mk#L63)取board_top.bit。文件改名不等于模块可以随意改名；正文已补。 |
| 教学接口是否“不是AXI4” | 不能据此下结论。data/valid/ready/keep/last符合[AXI4-Stream基本语义](https://docs.amd.com/r/2023.1-English/ug1393-vitis-application-acceleration/Streaming-Interfaces)；[Arista公开页](https://www.arista.com/en/products/7130-ip-cores)只给RX/TX AXI4描述。缺的是指定IP版本的位宽、错误旁带、时钟复位及接收流控合同验证，不能声称直接兼容，也不能声称所有信号都不同。 |
| Et2缺destination是否漏配 | 按正文MOS语义，Et1的source et2已表达Et2 RX→Et1 TX；另两条表达Et1 RX→ap1 RX、ap1 TX→Et2 TX。三条方向已覆盖，没有依据补命令。该判断仍是设计推导；公开[Netnod](https://github.com/Netnod/FPGA_NTP_SERVER/blob/04c89fd2f2347843246ad825ace986db7408fe89/FPGA/targets/ntps_arista/README.md#production-use-using-a-sfp-port)只证明单口，本课双口未上板。MOS官方手册入口重定向登录，本轮未取得全文。 |
| EOS手册被挡住能否核实 | 本轮成功读取[配置页](https://www.arista.com/en/um-eos/eos-configuring-layer-1-on-the-7130-platform)；该页包含l1 source与l1 connect，后者还用于文中的Switch/MetaMux场景。[命令页](https://www.arista.com/en/um-eos/eos-7130-layer-1-commands)只列source不意味着connect不存在。未拿EOS手册证明MOS语法。 |
| 流水能力是否等于本核心并行多包 | 不等于。frame_filter单缓冲按RECEIVE→DECIDE→FORWARD处理一帧；DECIDE/FORWARD时s_ready为0。第①项已把通性与本例行为分开。 |
| UDP的58和66 | [RFC768](https://www.rfc-editor.org/rfc/rfc768.txt)长度含8字节UDP头。载荷20+2+36=58，头部Length=66；与第03章tcpdump输出一致，正文补一句对照。 |
| 生命周期的“结束支持” | 仍按官方三档：2022停售、2024软件修复终止、2025 TAC/RMA/EOL；没有把软件维护延长到2025。48LB→48LBS与48LBA→48LBAS分开记录。 |

本轮未改41个围栏、RTL/管理源码/测试/图片，未运行Vivado、XSim或设备命令。完整许可/IP、板级适配、双口抓包和性能仍待完成。核验索引：[第二次复核](../ch08-arista-fpga-followup-20260917.json)。

## 最后复核与阅读顺序调整（2026-09-17）

本次继续核对用户最新评估。`top_v`、UDP 58/66、单缓冲和 Et1 反向连接的判定保持；没有新增已证实的 RTL 错误。以下补充只修正协议表述，未修改实现：

| 项目 | 核实结果 |
| --- | --- |
| keep 的限制适用于谁 | 本核心要求非尾拍全1、尾拍非零且从低位连续；AMD [UG1393 的 Vitis 流接口](https://docs.amd.com/r/2023.1-English/ug1393-vitis-application-acceleration/Streaming-Interfaces)有相应限制。[Arm IHI0051B](https://documentation-service.arm.com/static/64819f1516f0f201aa6b963c) §2.5.1 允许空字节及全零 TKEEP，§3.3 的 Continuous_Packets 属性另限定连续数据包。因此不能把本课要求写成所有 AXI4-Stream 接口的通用限制。 |
| 等待时保持什么 | 同一规范 §2.2/2.2.1：valid 已置1而 ready 为0时，保持 valid、数据与控制信息直到握手。原正文省略 valid 前提，现已写完整；valid=0时无须把无效数据锁住。 |
| s_error 是否 AXIS 必选脚 | 不是。它是本课增加的接收错误标志，由指定 MAC 的适配层产生；公开 Arista IP 页不足以确定实际错误旁带的位号或时序。正文表中明确其归属。 |

正文保留 Icarus 主流程、全部16段源码摘录和11张图；原41个围栏逐字保留为正文34个、[工具补充](../../../assets/08-arista-fpga-draft/ADVANCED-TOOLS.md)7个。补充页完整收录 YoWASP 安装、两项综合及 XSim 备用命令；重复的参考表移至本页。Linux 验证图从工具准备移到⑥，术语在首次需要处解释；实现、图片、工具版本和验证状态不变。

检查及数量口径见 [顺稿核验索引](../ch08-arista-fpga-readable-20260917.json)。没有重跑核心仿真或综合，没有执行 XSim/Vivado 和真机操作。

## 本轮交叉核验

1. 源码 → 正文：16 段原始摘录去除整体缩进后逐字相同，CSV 与真实库解释一致。
2. 协议 → 源码：逐项核对字段偏移、长度、大端拼接和补空格；短帧/VLAN/选项等不冒充本课固定包型。
3. 代码 → 行为：22 帧功能测试与两个故意破坏逻辑的反例；验证字节保持、一次额度和寄存器边界。Yosys 对过滤与控制寄存器分别执行通用综合，生成两份网表并通过结构检查。
4. 图 → 代码：MAC 后的队列、单缓冲收/发阶段、控制与数据分开；跨域在硬件适配，不由 Python 执行。
5. 命令 → 厂商源码：生命周期、CSV、Makefile 和真实 MOS 部署逐项对照；不创造通用 FPGA 烧写命令。
6. 课堂 → 环境：全为展示卡，没有绿色执行入口；效果图为设定三帧输入后的推导，不承诺现有网页产生 GAP。

详细输出、源文件摘要、图形和格式检查见 [机器核验索引](../ch08-arista-fpga-draft-20260917.json)。

## 尚未拥有的证据

没有完整许可 FDK/MAC IP 的板级适配结果，本机已有 Icarus 与 Yosys 结果；没有 XSim/Vivado 报告，没有生成或加载 `.bit/.swix`，没有 MOS CLI 实机输出、端口抓包或时延测量。本课肯定陈述的是有出处的机制和已经核验的功能；没有把这些缺失证据写成“保证拿来就能运行”。

## 工具与协议入口汇总

| 来源 | 对应内容 |
| --- | --- |
| [Arista 7130 Developer](https://www.arista.com/en/products/7130-developer) | FPGA、管理 API 与开发包的职责 |
| [OpenFDK 固定提交](https://github.com/aristanetworks/openfdk/tree/13a7aac5b0aaba1ed7bbeb04dd71c5b3bded6d9d) | nullverilog 工程、Makefile、MOS Python 与寄存器库 |
| [Vivado 2023.1 安装与许可](https://docs.amd.com/r/2023.1-English/ug973-vivado-release-notes-install-license) | 工具来源、安装和许可要求 |
| [Vivado 2023.1 逻辑仿真](https://docs.amd.com/r/2023.1-English/ug900-vivado-logic-simulation) | xvlog、xelab、xsim 的职责 |
| [Vivado 综合](https://docs.amd.com/r/2023.1-English/ug901-vivado-synthesis) | SystemVerilog、寄存器与组合逻辑 |
| [Vivado 实现](https://docs.amd.com/r/2023.1-English/ug904-vivado-implementation) | 布局布线与实现结果 |
| [MoldUDP64](https://nasdaqtrader.com/content/technicalsupport/specifications/dataproducts/moldudp64.pdf) / [ITCH 5.0](https://www.nasdaqtrader.com/content/technicalsupport/specifications/dataproducts/NQTVITCHspecification.pdf) | 报文、消息长度与字段定义 |
| [Netnod 的 Arista 工程](https://github.com/Netnod/FPGA_NTP_SERVER/tree/04c89fd2f2347843246ad825ace986db7408fe89/FPGA/targets/ntps_arista) | 已公开的 MOS 安装、装载和应用通道连接实例 |

## FPGA 资源的通俗比喻（2026-09-17）

①改用“电子积木”说明既有资源与可配置连接，表格对应判断器、便签、片上内存和连接线。AMD UG574 的 LUT/Storage Elements 与 UG573 的 Block RAM Introduction 支持其资源分工；比喻不表示每个寄存器容量固定、所有缓存必为BRAM，或BRAM具有硬盘的断电保存能力。LUT规则表用于说明逻辑函数的配置，未引入新的动态重配置操作。图件、代码及验证状态不变。

依据：[LUT](https://docs.amd.com/r/en-US/ug574-ultrascale-clb/Look-Up-Table)、[寄存器](https://docs.amd.com/r/en-US/ug574-ultrascale-clb/Storage-Elements)、[Block RAM](https://docs.amd.com/r/en-US/ug573-ultrascale-memory-resources/Block-RAM-Introduction)。

同日后续按用户要求同步修改资源图00a及其PNG，保留原几何与箭头；图中文字与上方比喻一致，图册和两级摘要已更新。核验见 `refs/evidence/ch08-fpga-resource-figure-20260917.json`（项目根目录起算）；其余图和所有实现不变。

## 从软件编译理解FPGA构建（2026-09-17）

①和00b先区分SystemVerilog语言、RTL描述方式、Vivado工具和.bit配置产物，再用“选电路、安排位置、接好线路”引入综合/网表/布局/布线。GCC、C++与可执行文件仅作职责类比；.bit是配置数据，不是CPU指令。目标匹配包括FPGA器件与板级引脚、时钟，不能简化为操作系统版本。删去此处提前展开的流水化句子，④继续保留单缓冲的具体行为。

依据：[UG901输入](https://docs.amd.com/r/2023.1-English/ug901-vivado-synthesis/Setting-Synthesis-Inputs)、[目标器件](https://docs.amd.com/r/2023.1-English/ug901-vivado-synthesis/Running-Synthesis)、[UG904实现](https://docs.amd.com/r/2023.1-English/ug904-vivado-implementation)、[UG908配置文件](https://docs.amd.com/r/2023.1-English/ug908-vivado-programming-debugging/Associating-a-Programming-File-with-the-Hardware-Device)。UG908仅说明配置文件性质，本课MOS装载路线不变；未新增Vivado或真机验证。

## MOS来历与版本识别（2026-09-17）

本章选择MOS作为假设条件，不表示7130必为MOS或FPGA必须用MOS。Arista官方产品回顾说明2018年收购Metamako并引入7130；MOS生命周期页给出Metamako Operating System全称；固定OpenFDK支持表同时列MOS/EOS。安全公告0064明确用show version查MOS，输出字段Software image version，示例0.26.5不作为安装建议。

来源：https://blogs.arista.com/blog/redefining-low-latency-switching-once-again 、https://www.arista.com/en/support/product-documentation/7130-life-cycle-policy 、https://www.arista.com/en/support/advisories-notices/security-advisory/12912-security-advisory-64 。正文仅补解释与查询入口；本轮未访问任何交换机，未生成现场版本输出。
