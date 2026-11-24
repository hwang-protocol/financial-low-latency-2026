# 第10章机制图与保留参考图

> 更新：2026-09-07 · DEC-374 · 分步课堂与文件发令

面向网络工程师：图先讲位置、流向与职责，正文就近解释系统和硬件术语。新增 SVG 是教学机制图/硬件设计图，不是实测截图。

| 文件 | 用途与边界 |
| --- | --- |
| `10-rtl-verilator-fpga-overview.svg` | 现用章首：SystemVerilog/RTL设计分成CPU模型与FPGA配置两路；1200×1020 |
| `10-07-ready-valid-truth-table.png` | 历史参考：正文改用中文图标版SVG |
| `10-ready-valid-handoff.svg` | 现用：上方C++原始报文路径，下方模型读副本/三个接收条件/内部丢包变量，判决返回C++；1200×1450 |
| `10-one-shot-filter-control.svg` | 现用：脚本启动进程/写控制文件，C++读取block给模型一次额度，下方展示丢一次后放行；1200×1020 |
| `10-filter-result-check.svg` | 现用运行③：发送端、过滤程序和接收程序，核对丢弃/缺失序号；1200×650，数字为解释示意 |
| `10-08-four-cycle-handshake.png` | 保留参考，正文未引用：通用停顿握手 |
| `10-18-fifo-depth-four.png` | 保留历史参考，正文未引用；当前 market_filter 没有 FIFO |
| `10-rtl-filter-circuit.svg` | 现用：两份C++来源→一个程序→收包/模型调用/转发，底部放大比较与状态；1200×1510 |
| `10-real-nic-data-path.svg` | 现用：100G发包机→U250缓存/RTL→QDMA→接收主机，另画丢弃与主机配置；1200×870，NVDA过滤设计 |
| `10-build-program-boot.svg` | 工程补充参考，正文改用实际构建/JTAG命令：构建、临时配置与Flash启动 |
| `10-packet-before-verdict.svg` | 工程补充参考，正文未引用：字段到齐前缓存，随后整包裁决 |
| `10-simulator-versus-real-card.svg` | 保留教师参考，正文未引用：XDP / 软件模型 / 真卡的位置与订阅对照；不代替现役收发/判决职责说明 |

本目录封存 12 张图；正文实际引用 6 张，均为 SVG。新增 SVG 均以 1200 px 与 800 px 渲染并目视复核。摘要见本目录及上级 `SHA256SUMS`。

原 DEC-275 删除的失真旧协议/接口/RUN 图不恢复；本轮不删除既有图片。旧 README 的“当前 RTL 深度为四”已纠正：那是退役 market_pipeline，不是现役 market_filter。


## DEC-360：与第09章统一课堂风格，保持NVDA任务（2026-09-06）

- Ready/Valid旧PNG撤正文留档；新SVG以三行表示无数据、接收方忙、双方就绪，在时钟沿才接受一次。当前market_filter的`s_ready = !cfg_load_valid`是本课依据，图注明正常工作周期，不把输出画成AXI4-Stream整帧接口。
- 原真卡路径SVG重画网口/包/芯片/主机图标：比较Type/Locate/Stock，有额度才丢一次；绿色PASS经QDMA，红色DROP终止，紫色虚线从主机配置到FPGA。为使箭头不跨丢弃框，DROP支路位于过滤模块正下方；所有模块分组是设计示意，不是物理布局或已生成网表。
- 配置地址、wrapper与硬件期限仍待实现；U250/OpenNIC使用独立100G台架，`.1/.2角色`表示迁移同一业务，不暗示现有10G网口能够直接接该shell。现役10章仍为CPU上的模型，统一任务是NVDA行情过滤及下单保护，不引入其它业务案例。
- 只读核对：[Verilator overview](https://verilator.org/guide/latest/overview.html)、[固定OpenNIC Shell README](https://github.com/Xilinx/open-nic-shell/blob/940907fc99fc8d73dbea0028b3a23095a660a42a/README.md)、[build.tcl](https://github.com/Xilinx/open-nic-shell/blob/940907fc99fc8d73dbea0028b3a23095a660a42a/script/build.tcl)、[固定驱动README](https://github.com/Xilinx/open-nic-driver/blob/3de226996ff5bacf8c4bdcec5318725e39c80b23/README.md)。现役源为`assets/10-verilator/market_filter.sv`与`mold_filter_adapter.cpp`。AMD PG085网页本次读取失败，握手图按本地RTL与C++tick/输入接口核对；不记录该网页为本轮读取成功。
- 原生SVG经resvg0.47、Noto Sans CJK SC Regular/Bold在800px渲染并目视；XML、正文相对引用与双层SHA通过。未使用生成图片工具，没有设备操作、综合、上板或新的物理RUN。

## DEC-361：开场只讲身份与产物（2026-09-07）

总图说明语言、设计描述、工具与芯片的关系，不画网包路径。原 `10-simulator-versus-real-card.svg` 移到运行①，替换该处重复的 Mermaid；`10-build-program-boot.svg` 保留于硬件节，进一步解释装载方式。既有SVG/PNG字节不改。

来源于本轮复核的[Verilator overview](https://verilator.org/guide/latest/overview.html)、[AMD FPGA Architecture](https://docs.amd.com/r/en-US/ug1291-viv/FPGA-Architecture)与[Vivado流程](https://www.amd.com/en/developer/resources/vivado.html)。模型+适配程序+运行库经C++编译器生成CPU程序；板级设计经综合布局布线生成bitstream，二者没有直接装载箭头。图中`.2`编译/自测见教师说明中的09-07新RUN；硬件仍设计未实测。

使用resvg 0.47.0、显式Noto Sans CJK SC Regular/Bold，以800和1200px渲染核对；文字不溢框，箭头不穿文字。字体通过`--use-font-file`加载；临时工具路径不作为课程运行依赖。

## DEC-363：把两部分代码画进原字段图（2026-09-07）

按用户指定更新原`10-rtl-filter-circuit.svg`，不新增第二张字段图。上层分别画SystemVerilog→Verilator→生成C++和手写mold_filter_adapter.cpp，两路汇入C++编译器/运行库，得到一个mold_filter_adapter；中层以同一Linux进程包住手写收包、生成模型、手写结果处理，①和③明确来自同一份代码；下层放大正常接收时的Type/Locate/Stock与模拟时钟沿判决。紫色只表示由RTL生成，蓝色表示手写代码，不表示独立进程或CPU并行线程。格式不符报文的直接转发已注明。

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

用户明确以FPGA过滤/流量控制及模拟演示为主，不希望机制节先铺变量、超时、协议字段；确认继续使用NVDA行情案例。新增10-one-shot-filter-control.svg，三个状态栏展示启动放行、指令有效期间丢第一条匹配消息、机会用完后放行。图注限定NVDA为前文匹配规则，未命中指令的自动撤销只留一句；变量/5秒实现/来源与格式旁路移教师说明“控制指令与输入边界”。原Ready/Valid及其它图保持。

依据现役live脚本allow启动/block发令，adapter的load_remaining与POLICY_TTL，以及RTL的额度消耗。图为行为示意，不是新实测截图；未修改代码或执行实验。五条箭头共用固定18×18px、refX=0、2.5px butt线帽，所有目标留12px间隙；800/1200px整图及原尺寸尖端目视、XML/几何/引用/卡片/围栏不变/双层摘要/diff核对。现8SVG/11图片文件/6导航/2绿卡，中央192项/局部12项摘要。

## DEC-368：运行图只回答怎样证明过滤生效（2026-09-07）

原XDP/软件/真卡对比图撤正文，保留教师参考；新增10-filter-result-check.svg，画.1发送行情、.2过滤程序、同机行情接收程序，通过同一丢弃/缺失序号核对一次过滤。101/102/103是讲解示意，非历史或新RUN读数；图注限定102匹配且有额度，原始回执505保持。标题和正文先定义行情接收程序与GAP，再进入观察，不复述前面模型内部或跨章实现位置。

依据现役run-rtl-filter-live.sh/adapter发送路径与wait-feed-state对账；报文由整个过滤程序处理，模型仅提供判决。正文补四阶段自动运行与前文规则/指令的对应，管理连接、订阅端口、跨章交接和恢复参数归教师“运行接线与维护前提”。两条箭头共用18×18px尾部锚定marker，2.5px线宽、12px框外间隙；800/1200px目视与XML/引用/导航/卡片/原代码输出不变/双层SHA/diff核对。正文8SVG/6导航/2绿卡、目录12图、中央193/局部13摘要，无新实验。

## DEC-369：真卡操作优先（2026-09-07）

用户更关注设备检查、构建装载、状态和真实过滤。正文保留10-real-nic-data-path，其余两张硬件图继续在HARDWARE-NOTES引用；正文用命令与验收替代重复机制图。无图文件改动或新增渲染，本轮核对引用/摘要；正文6SVG、目录12图片、193/13项摘要。完整步骤见U250-LAB-STEPS，固定源码依据和上板缺口见HARDWARE-NOTES末节；真卡仍未实测。

## DEC-374：分步课堂（2026-09-07）

过滤控制图将原“运行①脚本”改为分步脚本，明确运行①启动、运行②写block；内部读文件/装入额度不再编号，避免与四张运行卡混淆。图的几何与箭头保持原样，800/1200px重新审图；结果对账图用于运行③。正文六幅SVG不变。
