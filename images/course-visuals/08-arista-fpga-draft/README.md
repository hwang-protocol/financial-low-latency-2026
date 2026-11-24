# 第08章 FPGA 交换机推演稿图册

2026-09-17：为独立备选稿新增十张原生 SVG，PNG 为同源兼容显示版。图中数据流、逻辑资源与功能分区是教学示意，不是器件布局或现场截图。正文还复用原 `08-diagrams/08-fpga-switch-real-world-cases` 行业案例图；旧图保持。

| 文件（SVG / PNG 同名） | 尺寸（SVG） | 本图回答什么 |
| --- | --- | --- |
| [00a-fpga-resources.svg](00a-fpga-resources.svg) | 1200×920 | 用判断器、便签、片上内存和连接线解释 FPGA 资源 |
| [00b-configure-circuit.svg](00b-configure-circuit.svg) | 1200×940 | 保留参考：编译比喻已并入图02，正文不再重复引用 |
| [01-packet-path.svg](01-packet-path.svg) | 1200×940 | 第7步接线与检查：三接口归属、三个报文方向及连接条件/路径/无额度试通；7135V映射待核对 |
| [02-tools-and-sources.svg](02-tools-and-sources.svg) | 1200×1310 | 全章八步导航：准备→源码→仿真→板卡工程→PDI→SWIX→装载接线→验证；配软件开发比喻 |
| [02b-linux-build-checks.svg](02b-linux-build-checks.svg) | 1200×1800 | 3.1—3.5：测试台发额度检验电路、Python向模拟设备发令、真机寄存器控制链路，以及同一份源码的通用综合 |
| [02c-board-integration.svg](02c-board-integration.svg) | 1200×1820 | 4.1—4.4：加入源码、接三组接口、核对工程，交付第5步的完整工程输入 |
| [02d-pdi-build.svg](02d-pdi-build.svg) | 1200×1450 | 5.1—5.5：综合及检查、实现及检查、输出PDI，各阶段产物和问题处理 |
| [03-fields-and-comparators.svg](03-fields-and-comparators.svg) | 1200×990 | 源码选读附录：帧偏移、字节序和字段比较 |
| [04-buffer-and-drop.svg](04-buffer-and-drop.svg) | 1200×950 | 单缓冲接收/裁决/发送与一次额度 |
| [05-register-control.svg](05-register-control.svg) | 1200×850 | 源码选读附录：EOS临时RPC / Python控制如何访问硬件寄存器 |
| [06-build-upload-load.svg](06-build-upload-load.svg) | 1200×1070 | 保留参考：总览已并入图02，具体操作见正文第5—7步 |
| [07-observe-filter.svg](07-observe-filter.svg) | 1200×840 | 保留参考：三帧输入、两帧输出与计数对应；第8步已改为简短命令说明，正文不再引用 |

## 检查与更新

十图均在 800px 正文宽度和 1200px 原尺寸查看；用带 Noto Sans CJK SC 的 Chromium 131 检查字体加载、文字出框和横向溢出，PNG 输出宽度 1600px。箭头统一为 12×12 用户坐标单位，尾部锚点 refX=0/refY=6、3px butt 线宽，尖端在目标框外留 12px；原始 SVG 为修改源。

SVG 变更后，使用具备上述字体的浏览器按宽度渲染，按 viewBox 等比例设置画布高度；复核 800/1200px 的字、线、目标关系，再生成 1600px PNG。PNG 不能独立改字。同步本目录与上层 SHA256SUMS；核验结果存入 [本轮索引](../../../refs/evidence/ch08-arista-fpga-draft-20260917.json)。

图 00a/00b 根据 AMD Versal AM005/AM007 与 Vivado 文档解释资源和构建机制；图 01/06 按 OpenFDK/EOS 应用接口解释假设路径；图 03/04/05 对应本课完整 RTL/Python；图 07 中 S、3/2/1 是设定输入后的示例，不是当前网页或抓包结果。详细来源：[逐项核对](../../../assets/08-arista-fpga-draft/SOURCE-REVIEW.md)。

2026-09-17 评估修订：图01改为隔离台架发包/收包端；图02强调网口IP授权；图02b区分本地验证与缺失板级适配；图06前置完整许可和三组连接；图07明确逐帧低速推演。五图保持原几何与箭头规格，重新渲染并检查800/1200px，PNG宽1600px。证据：[本轮复核](../../../refs/evidence/ch08-arista-fpga-review-20260917.json)。

2026-09-17 图文同步：00a改为“电子积木”比喻，LUT做判断、寄存器像便签、片上RAM像内存，互连接起各单元；去掉图中的“输入位”“时钟边沿采样”等先行术语。原几何与三条箭头不变，800/1200px目视和800/1200/1600px字体/边界检查通过，1600px PNG已重生成。证据：`refs/evidence/ch08-fpga-resource-figure-20260917.json`（项目根目录起算）。

2026-09-17 构建图通俗化：00b在SystemVerilog下标明RTL代码，用GCC与程序文件类比工具和产物；Vivado内部先写“把代码变成电路、安排位置、接好线路”。正文随后解释综合、网表、布局、布线，注明目标芯片和板卡要求。原几何与5条箭头保持；800/1200px目视、800/1200/1600px字体及边界检查通过，同源PNG已更新。证据：`refs/evidence/ch08-fpga-build-analogy-20260917.json`。

2026-09-17 新平台迁移：00b/01/02/02b/05/06共六图更新为7135V、BVL、PDI和EOS。保留原几何和箭头；PDI包含器件启动与配置，控制命令为本课临时RPC。E入/E出/P是读图代号。六图同源PNG重生成并复看800/1200px，三宽度字体/边界检查通过。证据 `refs/evidence/ch08-modern-eos-20260917.json`。

2026-09-18 图04速率标注修正：`04-buffer-and-drop.svg` 脚注的“持续 10G 线速”改为“持续 25G 线速”，与7135V正文一致；继续保留“不宣称”的功能验证边界。同源PNG已重新生成，800/1200px整图目视及800/1200/1600px字体、边界检查通过；原布局与箭头保持。核验：`refs/evidence/ch08-buffer-rate-label-20260918.json`。

2026-09-18 工具图重排：按开发与使用顺序替换原三列来源图，FDK作为配套材料进入板卡工程，SystemVerilog与Python分路、在打包时汇合。明确PDI为构建结果、SWIX为安装包，命令启动Python后才装载镜像；核心仿真使用Icarus。SVG 1200×1370，同源PNG 1600×1827。十条箭头统一12×12、尾部锚定、3px butt线帽与12px目标框外间隙；800/1200px目视及三宽度字体/边界检查通过。正文图卡、alt及说明同步，真机仍未验证。证据：`refs/evidence/ch08-tool-flow-20260918.json`。

同轮术语修正：PDI用途改写为芯片启动与配置；Versal在正文硬件介绍处先定义为AMD芯片系列，VH1542为具体型号，工具图不再用未解释的系列名代替“芯片”。

2026-09-18 八步总导航：图02合并00b的编译比喻及原工具流程，明确开发机第1—6步与交换机台架第7—8步。图下八行说明、八个正文标题与导航卡使用同一编号；正文删除旧Mermaid及00b/06重复图引用，保留原图字节，正文共9图。图02 SVG 1200×1310、PNG 1600×1747；7条箭头及800/1200px目视、三宽度字体/边界检查通过。31段既有代码保持。核验：`refs/evidence/ch08-eight-step-navigation-20260918.json`。

2026-09-18 开发机绿卡：图02指明`.101`开发位置，第3步包含Icarus仿真与Yosys通用综合；脚注区分1—3可实作、4—6缺BVL材料和7—8需真机。几何/7箭头保持，SVG/PNG同步；800/1200px审图及三宽度字体/边界检查通过。正文绿卡在`.101`真实验证，核验 `refs/evidence/ch08-vm101-green-cards-20260918.json`。

2026-09-18 操作流程优先：正文仅保留两处短SV示例，图03/05随详细代码讲解移至源码选读附录，正文共7图；图02八步导航及全部图字节不变。自动SSH与文档核验见 `refs/evidence/ch08-auto-ssh-and-deployment-focus-20260918.json`。

2026-09-18 接口图文同步：图01去掉E入/E出/P代号，改用Ethernet1、Ethernet2与内部Application1/1，正反向说明和正文表格/命令一致；图顶及脚注保留通用命名示例、7135V映射和镜像通道待实机核对。两侧框扩宽容纳名字，5条箭头保留12×12尾部锚定、3px线宽、12px框外间隙。同源PNG1600×1013，800/1200px目视及三宽度字体/边界检查通过。证据 `refs/evidence/ch08-interface-figure-sync-20260918.json`。

2026-09-18 图02b重画为3.1—3.6完整故事：报文如信封，Python如操作员，控制寄存器接口如面板，Yosys网表如接线图。区分Python独立管理测试与硬件面板综合，综合重新读取.sv，归档为选做。SVG1200×1540/PNG1600×2053；五条箭头表示操作顺序，统一12×12尾部锚点、3px butt线宽、12px目标间隙。800/1200px整图目视及三宽度边界检查通过。证据refs/evidence/ch08-local-story-and-output-20260918.json（项目根目录起算）。

2026-09-18 文件名具体化：图02b的输入改用frame_filter.sv等（电路描述/过滤电路）、filter_tb.sv（测试台）、control_regs.sv（控制面板）；正文分别列出3.1的五份源码和3.4的三份源码。删除“电路.sv/测试台.sv/过滤模块.sv”伪文件名。首行卡片加高40px，保持字号与五箭头规格，SVG1200×1580/PNG1600×2107；800/1200px目视、三宽度边界通过。证据refs/evidence/ch08-diagram-real-filenames-20260918.json。

2026-09-18 仿真与发令关系重画：3.1列真实四份RTL与测试台，filter.vvp为输出；3.2自行发额度并实际验证2帧策略丢弃，3.3独立向FakeHardware测试Python发令。新增真机Python→control_regs→drop_once链路，明确额度在drop_once中；两条虚线从同一批源码指向3.4/3.5，板级工程继续使用.sv。正文及图撤下3.6，日志仍自动回存。SVG1200×1800/PNG1600×2400，6箭头（含2虚线）统一12×12/3px/12px目标间隙；800/1200审图、三宽度检查通过。证据refs/evidence/ch08-simulation-control-relationship-20260918.json。

2026-09-18 教学表述收口：用正向流程说明源码、两类独立测试、两份JSON逻辑接线表及Vivado生成PDI；构建在开发机完成，装载和实测连接真机。图02b保留Python→control_regs→drop_once授额链路。

2026-09-18 新增第4、5步局部流程图02c/02d，与正文4.1—4.4、5.1—5.5对应。前者交付适配后的BVL工程；后者区分构建与检查，write_device_image仅对应5.5输出。均为待取得完整BVL材料后的流程示意；无厂商顶层端口伪代码或模拟实测输出。02c为1200×1820/PNG1600×2427、8箭头；02d为1200×1450/PNG1600×1933、4箭头。统一12×12尾部锚定、3px线宽、目标间隙12px；800/1200目视与三宽度字体边界检查通过。来源：本课frame_filter.sv/control_regs.sv及正文链接的AMD UG1273/UG901/UG904/UG835。核验见refs/evidence/ch08-board-integration-and-pdi-flow-20260918.json。


## 官方界面截图（第4—5步）

2026-09-18按用户要求新增[官方Vivado截图目录](official-vivado/README.md)：4.1添加源码、4.3模块层级，5.1综合状态、5.2逻辑连接图、5.3实现进度、5.4时序汇总、5.5镜像设置，共7张官方PNG。来源为AMD 2026.1手册，部分图片沿用旧UI；原始像素保持，正文标明官方示例工程/读数并附来源链接。截图是外部参考，不适用本课原生SVG同源渲染规则。资产URL、原始文件名、尺寸及摘要见[sources.json](official-vivado/sources.json)。

2026-09-18 第08章5.5改为图形界面导出：正文与图02d统一为点击Write Device Image生成PDI，移除Tcl命令。镜像实际文件名按工程设置，打包时统一为flle_filter-bvl.pdi。02d同源PNG重新渲染，800/1200目视及三宽度边界检查通过。

2026-09-18 图01移至第7步接线命令前，原接口角色表与配置流向表合入图；①②③对应三条配置，明确前面板口与内部Application1/1。下方汇总连接条件、路径和无额度试通检查，含FEC匹配及板级错误计数。SVG1200×940/PNG1600×1253，5箭头保留12×12/3px/12px间隙，800/1200目视及三宽度字体边界检查通过。证据refs/evidence/ch08-wiring-diagram-and-checks-20260918.json。

## 2026-09-19 交换机前端简化

04-buffer-and-drop.png、05-register-control.png 已从第08章前端讲解撤下，文件保留供追溯；正文按用户要求仅保留工程来源、源码职责及构建打包概要。

2026-09-19：00a-fpga-resources.svg 底部改为正面解释配置的两句话，同步重新渲染PNG；800px显示检查无截断。
