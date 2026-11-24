# 第08章 7135V / EOS：一级来源核对

核对日期：2026-09-17。当前正文按用户要求从旧型号改为新一代7135V；此前评估归档在 `Documents/design/evidence/ch08-modern-eos-20260917/previous-mos-source-review.md`，不再作为本章操作基线。

## 硬件、工具和镜像

| 事实 | 一级来源与核对结论 |
| --- | --- |
| 目标平台 | [7135V产品页](https://www.arista.com/en/products/7135V-Series)、[数据表](https://www.arista.com/assets/data/pdf/Datasheets/7135V-Datasheet.pdf)：DCS-7135V-48Y-4QC、Versal HBM VH1542、16GB HBM、48 SFP28/4 QSFP28、BVL；FDK Yes、VDK No，最低EOS4.36.0F |
| 设备用户指南 | [7135V指南](https://www.arista.com/en/support/toi/eos-4-36-0f/23975-dcs-7135v-48y-4qc-user-guide)的公开索引存在，正文访问要求登录；未取得专属端口映射/完整开发包 |
| LUT和寄存器 | AMD [AM005 LUT](https://docs.amd.com/r/en-US/am005-versal-clb/Look-Up-Table)、[Storage Elements](https://docs.amd.com/r/en-US/am005-versal-clb/Storage-Elements?contentId=Vm3CtC0AW~fc4D_ovUb35A)支持本章资源解释 |
| 芯片内部RAM | [AM007](https://docs.amd.com/r/en-US/am007-versal-memory/Block-RAM-Introduction)；片上RAM类比内存，不类比断电保存的硬盘；16GB HBM与此不同，本课不使用HBM |
| 当前工具来源 | [AMD 2026.1下载入口](https://www.amd.com/en/support/downloads/adaptive-socs-and-fpgas/development-tools/2026-1.html)、[当版许可](https://www.amd.com/en/products/software/adaptive-socs-and-fpgas/vivado/vivado-licensing-options.html)；版本与许可须按BVL兼容表，不能用官网下载最新版替代厂商认证 |
| VH1542器件支持 | AMD [2025.2器件表](https://docs.amd.com/r/2025.2-English/ug973-vivado-release-notes-install-license/Supported-Devices)明列XCVH1542；此项不证明BVL已认证2025.2或2026.1 |
| Versal生成PDI | [UG908](https://docs.amd.com/r/en-US/ug908-vivado-programming-debugging/Generating-the-Bitstream-or-Device-Image)、[write_device_image](https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/write_device_image)：GUI Write Device Image和Tcl均真实存在 |
| PDI内容及配套设计 | [UG1304](https://docs.amd.com/r/en-US/ug1304-versal-acap-ssdg/Creating-a-Boot-Image-PDI)、[UG1273](https://docs.amd.com/r/en-US/ug1273-versal-acap-design/Generating-the-Boot-Image-in-the-Design-Flows)：PDI可含PLM固件与配置，生成依赖器件启动/配置模块，不能说内部全无CPU代码 |

资料中的L1延时数字不作为本课性能；本课只有功能模型，未提供持续25G吞吐或实测时延。100字节/25G=32ns仅为数据串行化，不含前导码/FCS/接口/缓存。

## 公开代码能证明什么

OpenFDK在本次核对时HEAD为 **13a7aac5b0aaba1ed7bbeb04dd71c5b3bded6d9d**，不是为了保留旧MOS而固定旧环境。

| 文件 | 核对事项 |
| --- | --- |
| [resources/libapp/device.py](https://github.com/aristanetworks/openfdk/blob/13a7aac5b0aaba1ed7bbeb04dd71c5b3bded6d9d/resources/libapp/device.py) | 7135V硬件修订分支、Fpga1、bvl、VH1542、image_type=pdi；EOS load_image接受port_def，profile_state检查applied |
| [src/boards](https://github.com/aristanetworks/openfdk/tree/13a7aac5b0aaba1ed7bbeb04dd71c5b3bded6d9d/src/boards) | 没有公开BVL板级目录；nullverilog的lb2顶层不能移名当作新板支持 |
| [vivado.mk](https://github.com/aristanetworks/openfdk/blob/13a7aac5b0aaba1ed7bbeb04dd71c5b3bded6d9d/resources/vivado.mk) | 旧板构建规则不能证明BVL工具兼容或PDI生成，不使用make BOARDSTD=bvl冒充可构建 |
| [EOS示例目录](https://github.com/aristanetworks/openfdk/tree/13a7aac5b0aaba1ed7bbeb04dd71c5b3bded6d9d/examples/nullverilog/src/eos) | YAML、CLI、Daemon启停框架；本课命令与寄存器逻辑自行编写 |
| [EOSSDK agent.h](https://github.com/aristanetworks/EosSdk/blob/a66f65bb4674fefa5a9312ee1e5fd6895f2810b2/eos/agent.h#L123-L134) | CliExtension.agentRpc和on_agent_rpc的字符串请求/响应契约；一次额度不写持久配置 |
| [RegisterFile](https://github.com/aristanetworks/openfdk/blob/13a7aac5b0aaba1ed7bbeb04dd71c5b3bded6d9d/resources/libapp/register_file.py) | 名称/编号映射及自动重试；arm写绕过这一层，避免程序自动再次授予额度 |
| [app.mk](https://github.com/aristanetworks/openfdk/blob/13a7aac5b0aaba1ed7bbeb04dd71c5b3bded6d9d/resources/app.mk) | 已有PDI通过本课EXTRA_APP_FILES进入暂存目录，保留CLI注册/守护程序权限，不调用vivado.mk |

本课与公开libapp不自动重复控制写；内部PLSmbusUtil和物理总线未验证，不能声称硬件exactly-once。RPC去重也不替代实际板级写请求确认。

## 安装和端口

[官方EOS安装例](https://github.com/aristanetworks/openfdk/blob/13a7aac5b0aaba1ed7bbeb04dd71c5b3bded6d9d/examples/telemexample/quickstart.md#eos-installation)与[扩展管理](https://www.arista.com/en/um-eos/eos-managing-eos-extensions)支持copy到extension目录、extension安装、重新登录及show extensions。已安装扩展不等于FPGA已经配置。

[EOS L1命令](https://www.arista.com/en/um-eos/eos-7130-layer-1-commands)及[配置页](https://www.arista.com/en/um-eos/eos-configuring-layer-1-on-the-7130-platform)支持l1 source interface及capabilities/path查询。E_IN→P、P→E_OUT、E_OUT→E_IN是本课三条单向设计；实际端口名称和可连方向依设备读回。公开app_ports=1-68不是具体连通能力证明。没有本课7135V抓包、EOS安装或L1实测记录。

## 协议与核心继续有效

NASDAQ [MoldUDP64](https://nasdaqtrader.com/content/technicalsupport/specifications/dataproducts/moldudp64.pdf)及[ITCH5.0](https://nasdaqtrader.com/content/technicalsupport/specifications/dataproducts/NQTVITCHspecification.pdf)支持固定无VLAN/IPv4-IHL5/单条Type A的偏移：100=14+20+8+20+2+36，IPv4总长86，UDP字段66、载荷58；序号52—59，股票88—95。Locate8095只属于课程数据，不是NASDAQ永久编号。

教学接口采用valid/ready/data/keep/last语义；非尾拍keep=ff、尾拍低位连续有效是本核心约束，不是所有AXI4-Stream的通用限制。s_error是附加信号，指定Versal网口的位宽、错误和时钟接口尚需适配。

仿真核心、寄存器与缓存行为保持；新平台不自动提高它的线速。本轮重跑22帧Icarus及16项管理逻辑测试；此前Yosys通用综合沿用。没有Vivado/XSim、完整PDI/SWIX或真机证据。经典Enyx/德交所/Netnod案例保留原部署事实，不转写为7135V案例。

## 2026-09-18 · 工具与文件顺序说明

本轮核对 AMD UG908 的器件镜像生成说明、Arista OpenFDK README 的 Introduction/Structure、固定13a7aac5的 `resources/app.mk` 与 EOS 扩展安装手册。FDK包含硬件资料、库、示例、IP核与构建工具；PDI是Vivado构建结果，SWIX是EOS扩展安装格式。公开FDK资料用于核对职责，不证明完整BVL工程已取得。

正文按“写SV源码→Icarus功能仿真→接入FDK板卡工程→Vivado生成PDI→连同Python管理源码打成SWIX→EOS安装→命令启动Python→装载与运行”解释。本课 `package_eos.mk` 读取已有PDI并收集Python文件，`eos/filter_control.py` 调用 `load_image`；新增一行SV摘录逐字来自 `nvda_match.sv`。既有31段代码块及实现保持，未重跑仿真、打包或上板。

来源：[AMD UG908](https://docs.amd.com/r/en-US/ug908-vivado-programming-debugging/Generating-the-Bitstream-or-Device-Image)、[Arista FDK](https://github.com/aristanetworks/openfdk#introduction)、[固定app.mk](https://github.com/aristanetworks/openfdk/blob/13a7aac5b0aaba1ed7bbeb04dd71c5b3bded6d9d/resources/app.mk)、[EOS扩展安装](https://www.arista.com/en/um-eos/eos-managing-eos-extensions)。AMD UG901固定2026.1的单页入口本轮访问失败，未以此声称取得该页；工具职责由上述资料和既有本地源码核对。核验：`Documents/design/evidence/ch08-tool-flow-20260918.json`。

## 2026-09-18 · 八步导航与正文对齐

本轮合并编译比喻和工具流程，按准备环境、编写源码、仿真验证、接入板卡工程、构建PDI、打包SWIX、安装装载与接线、验证过滤八步组织。FDK先用于板卡适配，Icarus负责本地仿真；PDI与Python在SWIX打包时汇合，EOS安装后由管理程序装载。沿用上轮已核对来源和现有实现，没有新增外部技术结论或重查仓库HEAD。31段既有代码保持，未执行仿真、Vivado、打包或上板。核验：`Documents/design/evidence/ch08-eight-step-navigation-20260918.json`。
