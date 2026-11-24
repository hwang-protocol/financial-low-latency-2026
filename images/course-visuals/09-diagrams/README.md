# 第 09 章机制图与保留参考图

## 2026-09-18 · 第08/09章共享 .101 开发机

`09-branch-navigation.svg`（1200×1880）及同源 PNG（1600×2507）在顶部补充第08章 1.1—1.3 的共享准备：`.111` 保存源码与缓存，`.101` 开发。共同第2步为绿色“2 在 .101 编译与自测”；A 路真实行情实验继续在 `.2` 执行。B3注明寄存器仿真可在 `.101` 做，B6区分本地 C 工具测试与需要真卡的 PCIe 读写；B 路保留紫色真卡路线、未上板和 B7 待适配边界。

共同1—2、A1—A5、B1—B7共14步不变。800/1200px整图目视、15个箭头尖端放大检查通过；800/1200/1600px字体及文字边界检查通过。15根箭头仍为12×12尾参考 marker，尖端距目标框12px。本次只核验图件，不增加设备、快照恢复或上卡验证结论。核验：`refs/evidence/ch09-shared-development-navigation-20260918.json`。下方旧条目按各自日期和版本理解。

## 2026-09-18 · 共同代码后的仿真 / 真卡双分支导航

`09-branch-navigation.svg`（1200×1780）及同源 PNG（1600×2373）作为全章主流程图：共同1—2之后分成A1—A5与B1—B7。正文按共同→左路→右路讲解，14个标题和导航卡逐项对应，卡内可跳转并返回总图。A5明确网页手工恢复后执行运行④验收；B路未上板，B7网口通路用虚线标为待适配。

15根箭头统一12×12尾参考marker，尖端距目标框12px；800/1200px整图目视、800/1200/1600px字体与文字边界检查通过。旧`09-rtl-verilator-fpga-overview`、`09-v80-build-load`退出正文重复总览，源文件与PNG保留参考。其余机制图仍按各节职责使用，正文共9图。核验：`refs/evidence/ch09-branch-navigation-20260918.json`。下方旧条目按各自日期和版本理解。

## 2026-09-18 · AMD产品与V80双镜像路线

当前第09章使用 V80 / AMR3.0.0 / Vivado+Vitis2026.1。新增三图、重绘一图，SVG及同源1600px PNG配套：

| 文件 | 内容与尺寸 |
| --- | --- |
| `09-amd-product-map` | 芯片/卡/工具分层、UL与V80、其他厂商；1200×820 |
| `09-rtl-verilator-fpga-overview` | 同一RTL的CPU模拟与V80 Boot/PL路线；1200×830 |
| `09-v80-register-path` | PF0管理、PF1 BAR2寄存器、同核心判决及未交付网口范围；1200×1090 |
| `09-v80-build-load` | Vivado→XSA→启动bin→Boot→匹配PLD→读判决；1200×1220 |

四图统一12×12箭头、尾部锚定、目标框外12px间隙，800/1200px整图与文字边界检查通过。图为设计/机制示意，不是上板证据。旧U250数据路径图仅在历史配套页保留；下方“现用”描述按原日期理解。本轮核验见 `refs/evidence/ch09-v80-local-20260918.json`。


## 2026-09-18 · 章首图摘要补齐

保留工作区现有章首SVG/PNG；从SVG独立渲染的1600px PNG与现有PNG逐字节一致。800/1200px整图目视、三宽度字体和文字边界检查通过；同步图册尺寸及两级摘要，登记现有同源PNG。本轮仅核对图件一致性，不重新核验V80外部规格或提升上板状态。核验：`refs/evidence/ch09-overview-manifest-20260918.json`。

## 2026-09-17 · FPGA 网卡的三个真实应用

新增 `09-fpga-nic-real-world-cases.svg`（1200×1380）及同源 PNG（1600×1840），放在章末真卡操作讲解之后。三个面板分别展示 nxFeed 在 FPGA 网卡上处理行情并经 PCIe 交付本机策略、Algo-Logic 用带网口的 Alveo U50 完成行情到订单的处理、Azure 2018 论文中的 FPGA SmartNIC 网络卸载。

前两例明确为公开商用方案，Azure 为公开部署案例并限定历史架构；不补造具名交易客户、生产部署规模或性能数字。八条箭头统一 12×12 尾部锚定 marker、3px butt 线帽、12px 目标框外间隙；800/1200px 整图审阅、文字边界与 XML 检查通过。保留旧图、软件仿真与真卡未实测边界；原始出处与核验见 `refs/evidence/ch08-09-fpga-cases-20260917.json`。

## 2026-09-12 · 现役第09章

本目录由原第10章前移，现役图文件与链接采用新编号；下方历史条目保留原日期和验证身份。本轮未新增设备实验。

## 2026-09-10 · 当前共图：六类型各一条

本章过滤位置直接嵌入 `../03-diagrams/03-itch-type-strips.svg`（1200×1350），与第3/8/9/10章完全同源。六种类型各一条，字段在条内横向分格；本章只匹配A行，图卡已明确。旧 `03-market-packet-fields.svg` 不再被本章引用，下方登记为上一版历史。800/1200px及桌面/手机实际嵌入核验通过；本目录图片字节不变，共图由03-diagrams及总目录SHA登记，不升级实机结论。

## 2026-09-10 · 过滤位置直接嵌入共用字段图

本章在讲解过滤字段处直接显示 `../03-diagrams/03-market-packet-fields.svg`（现为1200×1624），与第三、八、九、十章引用同一文件，不维护副本，也不只留跳转链接。Type/Locate/Stock 黄色标记与本章源码一致；是否丢包和额度仍由本章规则说明。共图800/1200px及桌面/手机嵌入验收见03-diagrams最新条目。本目录原图字节不变；共图SHA由03-diagrams与总清单登记，不提高本章实机验证等级。下方不同尺寸或“仅链接”的描述为历史状态。

## 2026-09-08 · DEC-393 统一流量与端口

本轮更新：`09-simulator-versus-real-card.svg`。控制器归属 `.2`，行情由一个普通 Socket 接收后本机分发；组播 `233.74.125.32:31032`、单播 `.2:42121`。生产案例仅用官方公开端点，中间路由器为机制示意。本地无 PIM/RP 配置。800/1200px 渲染检查；历史抓包与旧性能图保留原始字节及其出处。


> 更新：2026-09-07 · DEC-374 · 分步课堂与文件发令

面向网络工程师：图先讲位置、流向与职责，正文就近解释系统和硬件术语。新增 SVG 是教学机制图/硬件设计图，不是实测截图。

| 文件 | 用途与边界 |
| --- | --- |
| `09-rtl-verilator-fpga-overview.svg` / `.png` | 现用章首：RTL分别进入CPU模型与V80配置路线；SVG 1200×830，PNG 1600×1107；上卡待验证 |
| `09-07-ready-valid-truth-table.png` | 历史参考：正文改用中文图标版SVG |
| `09-ready-valid-handoff.svg` | 现用：上方C++原始报文路径，下方模型读副本/三个接收条件/内部丢包变量，判决返回C++；1200×1450 |
| `09-one-shot-filter-control.svg` | 现用：脚本启动进程/写控制文件，C++读取block给模型一次额度，下方展示丢一次后放行；1200×1020 |
| `09-filter-result-check.svg` | 现用运行③：发送端、过滤程序和接收程序，核对丢弃/缺失序号；1200×650，数字为解释示意 |
| `09-08-four-cycle-handshake.png` | 保留参考，正文未引用：通用停顿握手 |
| `09-18-fifo-depth-four.png` | 保留历史参考，正文未引用；当前 market_filter 没有 FIFO |
| `09-rtl-filter-circuit.svg` | 现用：两份C++来源→一个程序→收包/模型调用/转发，底部放大比较与状态；1200×1510 |
| `09-real-nic-data-path.svg` | 现用：100G发包机→U250缓存/RTL→QDMA→接收主机，另画丢弃与主机配置；1200×870，NVDA过滤设计 |
| `09-build-program-boot.svg` | 工程补充参考，正文改用实际构建/JTAG命令：构建、临时配置与Flash启动 |
| `09-packet-before-verdict.svg` | 工程补充参考，正文未引用：字段到齐前缓存，随后整包裁决 |
| `09-simulator-versus-real-card.svg` | 保留教师参考，正文未引用：XDP / 软件模型 / 真卡的位置与订阅对照；不代替现役收发/判决职责说明 |

本目录封存 12 张图；正文实际引用 6 张，均为 SVG。新增 SVG 均以 1200 px 与 800 px 渲染并目视复核。摘要见本目录及上级 `SHA256SUMS`。

原 DEC-275 删除的失真旧协议/接口/RUN 图不恢复；本轮不删除既有图片。旧 README 的“当前 RTL 深度为四”已纠正：那是退役 market_pipeline，不是现役 market_filter。


## DEC-360：与第09章统一课堂风格，保持NVDA任务（2026-09-06）

- Ready/Valid旧PNG撤正文留档；新SVG以三行表示无数据、接收方忙、双方就绪，在时钟沿才接受一次。当前market_filter的`s_ready = !cfg_load_valid`是本课依据，图注明正常工作周期，不把输出画成AXI4-Stream整帧接口。
- 原真卡路径SVG重画网口/包/芯片/主机图标：比较Type/Locate/Stock，有额度才丢一次；绿色PASS经QDMA，红色DROP终止，紫色虚线从主机配置到FPGA。为使箭头不跨丢弃框，DROP支路位于过滤模块正下方；所有模块分组是设计示意，不是物理布局或已生成网表。
- 配置地址、wrapper与硬件期限仍待实现；U250/OpenNIC使用独立100G台架，`.1/.2角色`表示迁移同一业务，不暗示现有10G网口能够直接接该shell。现役10章仍为CPU上的模型，统一任务是NVDA行情过滤及下单保护，不引入其它业务案例。
- 只读核对：[Verilator overview](https://verilator.org/guide/latest/overview.html)、[固定OpenNIC Shell README](https://github.com/Xilinx/open-nic-shell/blob/940907fc99fc8d73dbea0028b3a23095a660a42a/README.md)、[build.tcl](https://github.com/Xilinx/open-nic-shell/blob/940907fc99fc8d73dbea0028b3a23095a660a42a/script/build.tcl)、[固定驱动README](https://github.com/Xilinx/open-nic-driver/blob/3de226996ff5bacf8c4bdcec5318725e39c80b23/README.md)。现役源为`assets/09-verilator/market_filter.sv`与`mold_filter_adapter.cpp`。AMD PG085网页本次读取失败，握手图按本地RTL与C++tick/输入接口核对；不记录该网页为本轮读取成功。
- 原生SVG经resvg0.47、Noto Sans CJK SC Regular/Bold在800px渲染并目视；XML、正文相对引用与双层SHA通过。未使用生成图片工具，没有设备操作、综合、上板或新的物理RUN。

## DEC-361：开场只讲身份与产物（2026-09-07）

总图说明语言、设计描述、工具与芯片的关系，不画网包路径。原 `09-simulator-versus-real-card.svg` 移到运行①，替换该处重复的 Mermaid；`09-build-program-boot.svg` 保留于硬件节，进一步解释装载方式。既有SVG/PNG字节不改。

来源于本轮复核的[Verilator overview](https://verilator.org/guide/latest/overview.html)、[AMD FPGA Architecture](https://docs.amd.com/r/en-US/ug1291-viv/FPGA-Architecture)与[Vivado流程](https://www.amd.com/en/developer/resources/vivado.html)。模型+适配程序+运行库经C++编译器生成CPU程序；板级设计经综合布局布线生成bitstream，二者没有直接装载箭头。图中`.2`编译/自测见教师说明中的09-07新RUN；硬件仍设计未实测。

使用resvg 0.47.0、显式Noto Sans CJK SC Regular/Bold，以800和1200px渲染核对；文字不溢框，箭头不穿文字。字体通过`--use-font-file`加载；临时工具路径不作为课程运行依赖。

## DEC-363：把两部分代码画进原字段图（2026-09-07）

按用户指定更新原`09-rtl-filter-circuit.svg`，不新增第二张字段图。上层分别画SystemVerilog→Verilator→生成C++和手写mold_filter_adapter.cpp，两路汇入C++编译器/运行库，得到一个mold_filter_adapter；中层以同一Linux进程包住手写收包、生成模型、手写结果处理，①和③明确来自同一份代码；下层放大正常接收时的Type/Locate/Stock与模拟时钟沿判决。紫色只表示由RTL生成，蓝色表示手写代码，不表示独立进程或CPU并行线程。格式不符报文的直接转发已注明。

调用依据：`mold_filter_adapter.cpp`的drive_itch填写dut.s_itch和s_mold_seq，tick设置clk并调用eval，clock_filter读取drop_valid，run_adapter负责recvfrom/sendto；规则来自market_filter.sv。章节引用路径、7幅SVG/10个图片文件/6项导航不变。800/1200px显式Noto字体渲染复核，正文仅保留两段图后解释；没有修改源码或进行新实测。

## DEC-364：接收条件、时钟与额度分开解释（2026-09-07）

同轮视觉微调：用户认为时钟上升沿箭头过大；两处改用固定12px开放箭头，线宽5→2.5px，避免marker随线宽放大。800/1200px重新渲染目视，内容与布局保持。

最终箭头统一：用户指出上述局部修正留下三种尺寸。全图五条箭头线现共用一个固定18×18px实心三角marker与2.5px线宽（包括周期双向箭头的两端），只保留颜色/方向差异；取消时钟专用marker。此条接管上面的12px开放箭头方案。800/1200px按整图复核。

DEC-365尖端修正：统一marker仍保留18×18px，但参考点从尖端refX=18移到尾部refX=0，线条按箭头长度缩短，线帽butt，解决尖端露线造成的平头。消息与ready的尖端分别在x728/x447，目标框边x740/x435，间隙均12px；时钟尖端y654和周期尖端x315/x695保持。800/1200px整图、尖端放大目视及XML/几何/摘要检查。适用硬规则第3.3.3节，内容和图数不变。

按用户反馈重画原Ready/Valid图，替代抽象包裹交接。上层标明同一程序中的手写收包代码、一个生成模型对象、消息/valid与ready方向，并把remaining_drops画在模型内；中层用0/1波形、两个上升沿和一周期解释“一拍”；下层按首条命中、清valid后的空输入、第二条命中列出同一额度1→0→0和判决。正常工作、额度已配置且不再配置的示例边界写在图中，不能解读为一次CPU通知所有副本，或时钟每变化一次就有一条消息。

依据本地market_filter.sv的s_ready、always_ff与额度分支，以及mold_filter_adapter.cpp的run_adapter单对象、tick、clock_filter。第09对照只取保存并消费额度这一共同思路，不推断多CPU实现。原生SVG用resvg0.47/Noto Sans CJK SC在800/1200px渲染目视；XML、引用、正文代码不变、卡片和双层SHA静态检查。没有新的仿真、设备或性能实验；原路径及图片数量保持。

## DEC-366：原始报文路径与模型判决分开画（2026-09-07）

同轮s_valid来源补充：用户要求明确它来自上方手写C++。新增一条蓝色正交线，从上方缓冲区步骤下沿沿左侧直接连接模型的s_valid输入框；标签写“C++设置s_valid=1”，输入框注明来源。将s_valid从泛化输入标签中分离；模型左边界扩到x55为连线留槽，箭头尖端x98距输入框x110仍12px。现为九条箭头，共用DEC-365样式；800/1200px复核。

原Ready/Valid图改为上方蓝色C++收包/缓冲区/发送或丢弃，下方紫色生成模型：蓝色向下只送36字节消息副本、序号与控制输入，紫色向上只返回判决。模型内并列valid、ready、clk三个条件，汇合为上升沿接受消息，再更新内部remaining_drops/drop_count；清楚标注变量由market_filter.sv定义。格式旁路与当前软件仿真范围在图脚说明。

用户追问“正在写配置”含义，主图以“模型准备好接收”解释ready，只用小注说明设置额度时暂不接收；正文再将cfg_load_valid解释为设置/清零额度的指示。不能把ready画成每到时钟沿才更新，现役assign直接计算它；不能将“不转发原报文”画成模型不读取消息数据。依据现役run_adapter缓冲区/send_copy、drive_itch复制、clock_filter/tick和market_filter.sv；未修改源码或运行状态。

八条箭头线共用固定18×18px尾部锚定marker、2.5px butt线帽，各目标尖端间隙12px。800/1200px整图与局部放大目视、XML/几何、正文围栏与源码不变、卡片、双层摘要及diff静态核对。图片数/路径、7SVG/6导航/2绿卡保持，无新实测。

## DEC-367：用三阶段图讲发令后的过滤行为（2026-09-07）

同轮操作入口补正：用户指出“启动/发令”没有说明对象和方式；纯文字补图仍不足。现图上层明确脚本、.2上的控制文件和mold_filter_adapter三个对象，连线①启动进程、②写block、③收发代码读取文件、④给模型设置一次额度；下层保留原三阶段行为。正文展示实际printf写控制文件的一行并标注运行①自动执行，无手动停步或重新启动。图扩至1200×1020，九条同尺寸箭头、尾部锚定/12px框外间隙，800/1200px整图复核。来源为live脚本第55/64行和adapter的CONTROL_PATH/控制循环；没有执行指令。

用户明确以FPGA过滤/流量控制及模拟演示为主，不希望机制节先铺变量、超时、协议字段；确认继续使用NVDA行情案例。新增09-one-shot-filter-control.svg，三个状态栏展示启动放行、指令有效期间丢第一条匹配消息、机会用完后放行。图注限定NVDA为前文匹配规则，未命中指令的自动撤销只留一句；变量/5秒实现/来源与格式旁路移教师说明“控制指令与输入边界”。原Ready/Valid及其它图保持。

依据现役live脚本allow启动/block发令，adapter的load_remaining与POLICY_TTL，以及RTL的额度消耗。图为行为示意，不是新实测截图；未修改代码或执行实验。五条箭头共用固定18×18px、refX=0、2.5px butt线帽，所有目标留12px间隙；800/1200px整图及原尺寸尖端目视、XML/几何/引用/卡片/围栏不变/双层摘要/diff核对。现8SVG/11图片文件/6导航/2绿卡，中央192项/局部12项摘要。

## DEC-368：运行图只回答怎样证明过滤生效（2026-09-07）

原XDP/软件/真卡对比图撤正文，保留教师参考；新增09-filter-result-check.svg，画.1发送行情、.2过滤程序、同机行情接收程序，通过同一丢弃/缺失序号核对一次过滤。101/102/103是讲解示意，非历史或新RUN读数；图注限定102匹配且有额度，原始回执505保持。标题和正文先定义行情接收程序与GAP，再进入观察，不复述前面模型内部或跨章实现位置。

依据现役run-rtl-filter-live.sh/adapter发送路径与wait-feed-state对账；报文由整个过滤程序处理，模型仅提供判决。正文补四阶段自动运行与前文规则/指令的对应，管理连接、订阅端口、跨章交接和恢复参数归教师“运行接线与维护前提”。两条箭头共用18×18px尾部锚定marker，2.5px线宽、12px框外间隙；800/1200px目视与XML/引用/导航/卡片/原代码输出不变/双层SHA/diff核对。正文8SVG/6导航/2绿卡、目录12图、中央193/局部13摘要，无新实验。

## DEC-369：真卡操作优先（2026-09-07）

用户更关注设备检查、构建装载、状态和真实过滤。正文保留10-real-nic-data-path，其余两张硬件图继续在HARDWARE-NOTES引用；正文用命令与验收替代重复机制图。无图文件改动或新增渲染，本轮核对引用/摘要；正文6SVG、目录12图片、193/13项摘要。完整步骤见U250-LAB-STEPS，固定源码依据和上板缺口见HARDWARE-NOTES末节；真卡仍未实测。

## DEC-374：分步课堂（2026-09-07）

过滤控制图将原“运行①脚本”改为分步脚本，明确运行①启动、运行②写block；内部读文件/装入额度不再编号，避免与四张运行卡混淆。图的几何与箭头保持原样，800/1200px重新审图；结果对账图用于运行③。正文六幅SVG不变。
