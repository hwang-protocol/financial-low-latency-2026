# U250 新工程 GUI 操作截图

用户于2026-09-19交付；前21张来自 `newDoc/images/tmp`，随后两张来自 `newDoc/images`，实现完成、比特流生成、文件属性、硬件管理器及电路观察图再从 `newDoc/images/tmp` 归档。31张原图按归档次序命名，像素和文件字节不变。全部嵌入[第八章](../../../08-fpga-from-code-to-device.md)，最大显示宽度760px，点击可查看原图。完整旧名映射与摘要见SOURCE-MANIFEST.json及SHA256SUMS。

| 原文件时间后缀 | 当前文件 | 内容 | 正文位置 |
| --- | --- | --- | --- |
| screenshot_20260919_085718.png | [01-extract-opennic.png](01-extract-opennic.png) | 官方源码解压到QYT-FPGA | 3.1 |
| screenshot_20260919_090020.png | [02-open-tcl-console.png](02-open-tcl-console.png) | 打开Tcl Console菜单 | 3.1 |
| screenshot_20260919_090035.png | [03-enter-project-parameters.png](03-enter-project-parameters.png) | 在控制台底部输入工程参数 | 3.1 |
| screenshot_20260919_090042.png | [04-confirm-project-parameters.png](04-confirm-project-parameters.png) | 执行参数设置并返回6 | 3.1 |
| screenshot_20260919_090059.png | [05-run-official-project-script.png](05-run-official-project-script.png) | Tools菜单运行官方Tcl脚本 | 3.1 |
| screenshot_20260919_090342.png | [06-base-project-ready.png](06-base-project-ready.png) | U250基础工程创建完成且构建未开始 | 3.1 |
| screenshot_20260919_091218.png | [07-open-add-sources.png](07-open-add-sources.png) | File菜单添加源码 | 3.2.4 |
| screenshot_20260919_091232.png | [08-select-design-sources.png](08-select-design-sources.png) | 选择添加设计源码 | 3.2.4 |
| screenshot_20260919_091336.png | [09-import-three-design-files.png](09-import-three-design-files.png) | 一次加入三个模块并复制到工程 | 3.2.4 |
| screenshot_20260919_091434.png | [10-filter-hierarchy-before-wiring.png](10-filter-hierarchy-before-wiring.png) | 过滤模块已加入但尚未接入顶层 | 3.2.4 |
| screenshot_20260919_092008.png | [11-remove-original-p2p-reference.png](11-remove-original-p2p-reference.png) | 移除原p2p接线文件工程引用 | 3.2.4 |
| screenshot_20260919_092111.png | [12-add-course-p2p-source.png](12-add-course-p2p-source.png) | 再次选择添加设计源码以加入课程p2p | 3.2.4 |
| screenshot_20260919_092130.png | [13-reference-course-p2p.png](13-reference-course-p2p.png) | 加入课程p2p且不复制到工程 | 3.2.4 |
| screenshot_20260919_092212.png | [14-check-course-p2p-path.png](14-check-course-p2p-path.png) | 打开课程p2p核对实际路径 | 3.2.4 |
| screenshot_20260919_092607.png | [15-select-simulation-sources.png](15-select-simulation-sources.png) | 选择添加仿真源码 | 3.3 |
| screenshot_20260919_092639.png | [16-add-control-testbench.png](16-add-control-testbench.png) | 加入控制测试台并包含设计源 | 3.3 |
| screenshot_20260919_093108.png | [17-set-simulation-top.png](17-set-simulation-top.png) | 设置flle_rx_port_tb为仿真顶层 | 3.3 |
| screenshot_20260919_093155.png | [18-run-behavioral-simulation.png](18-run-behavioral-simulation.png) | 启动行为仿真 | 3.3 |
| screenshot_20260919_093346.png | [19-run-all-simulation.png](19-run-all-simulation.png) | 从Run菜单运行完整测试 | 3.3 |
| screenshot_20260919_093355.png | [20-simulation-pass.png](20-simulation-pass.png) | 11项含AMD CDC模型的联合仿真通过 | 3.3 |
| screenshot_20260919_093520.png | [21-launch-synthesis.png](21-launch-synthesis.png) | 综合启动窗口及本机并行任务数 | 3.4 |
| screenshot_20260919_100626_20260919_101022_572525.png | [22-synthesis-complete.png](22-synthesis-complete.png) | 新工程综合完成，准备进入实现 | 3.4 |
| screenshot_20260919_101000_20260919_101031_870257.png | [23-launch-implementation.png](23-launch-implementation.png) | 综合完成后启动实现的Launch Runs窗口 | 3.5 |
| screenshot_20260919_110925_20260919_111111_646929.png | [24-implementation-complete.png](24-implementation-complete.png) | 新工程实现完成及主要时序汇总指标 | 3.5 |
| screenshot_20260919_111928_20260919_112836_827566.png | [25-bitstream-complete.png](25-bitstream-complete.png) | 比特流生成成功，选择打开硬件管理器 | 3.6 |
| screenshot_20260919_112801_20260919_112843_751839.png | [26-bitstream-file-properties.png](26-bitstream-file-properties.png) | 本轮open_nic_shell.bit文件位置、大小与修改时间 | 3.6 |
| screenshot_20260919_112825_20260919_112849_891637.png | [27-hardware-manager-auto-connect.png](27-hardware-manager-auto-connect.png) | 硬件管理器Auto Connect入口，当前未打开硬件目标 | 3.7 |

| screenshot_20260919_122913_20260919_123756_529083.png | [28-implemented-device-layout.png](28-implemented-device-layout.png) | U250实现后器件布局与过滤器网表层次 | 3.6 |
| screenshot_20260919_123114_20260919_123807_996078.png | [29-open-core-schematic.png](29-open-core-schematic.png) | 从core右键菜单打开Schematic | 3.6 |
| screenshot_20260919_123131_20260919_123816_102148.png | [30-market-filter-connections.png](30-market-filter-connections.png) | market_filter模块层次与信号连接 | 3.6 |
| screenshot_20260919_123728_20260919_123828_180856.png | [31-market-filter-expanded-logic.png](31-market-filter-expanded-logic.png) | 展开market_filter底层逻辑单元及连线 | 3.6 |

## 实录状态

图15在正文中按1930:1049裁切显示，隐藏Vivado窗口下方露出的资源管理器和桌面；原始PNG及点击查看原图保持不变。

三个设计文件导入时Copy勾选，使用工程副本；p2p与测试台未勾选，直接引用交付目录。图11记录移除原p2p的工程引用并保留磁盘原件，随后加入课程接线文件。图10是接线前的并列层次，用于说明“加入模块”与“接上主工程”的区别。

| 阶段 | 本次QYT-FPGA工程的证据与状态 |
| --- | --- |
| 模块仿真 | 图20显示11项PASS、vendor_cdc=1、hardware=NOT_RUN，25656 ns正常结束；包含AMD跨时钟IP模型 |
| 完整工程综合 | 图22显示Synthesis successfully completed，synth_1为synth_design Complete! |
| 实现 | 图24显示Implementation successfully completed和route_design Complete；WNS 0.064 ns、WHS 0.010 ns，TNS/THS/TPWS为0、Failed Routes为0 |
| 配置文件 | 图25生成成功；图26显示本轮.bit为43,573,574字节，修改时间2026-09-19 11:18:58 |
| 硬件管理器 | 图27打开Auto Connect菜单，仍为unconnected；未证明发现器件或上板编程 |
| 电路观察 | 图28为器件布局全景，图29为Schematic入口，图30为模块连接，图31展开core并显示Leaf Cells (323)、LUT5及Site。正文3.6说明全景斑驳色块主要是OpenNIC收发包链路占用的资源格子，market_filter在全景上几乎看不出来；不能把全部着色资源都归属过滤核心 |
| 完整报告与实卡 | 图24的Methodology仍有5 CW、100 Wa；完整约束/规则报告及实卡收发仍需各自证据 |

## 当前覆盖范围

31张图覆盖创建工程、代码接入、模块仿真、综合、实现、比特流生成、文件属性、电路观察与硬件管理器入口。新增28—31四图来自 `C:/QYT-FPGA` 本轮工程，嵌入3.6配置生成之后，正文图号为3-27—3-30；原27号硬件管理器图片的正文图号顺延为3-31。原图像素与字节保持不变。

图27显示尚未连接硬件目标，不能作为实卡装载成功的证据。真实板卡编程、报文与计数验收仍需现场确认；本轮没有取得.bit二进制内容或其SHA256。

## 课程模块层级补图

`screenshot_20260919_150021_20260919_150333_993704.png` → [`32-course-module-hierarchy.png`](32-course-module-hierarchy.png)：用于3.2.1，原图保持不变，正文以780px最大宽度展示，点击查看原图；下方表格仅解释六个关键模块。

### 六模块标注版

`32-course-module-hierarchy-annotated.png` 由内置 imagegen 图片编辑生成，正文显示此标注版，链接仍指向未修改的原始截图。提示要求：保留界面、文字与布局，给 p2p_250mhz、flle_rx_port、axi_lite_clock_converter、flle_rx_regs、flle_rx_filter、market_filter 六行加同色橙色细框，无填充、无箭头、无新增文字。已目视核对六框与模块对应；生成标注版与原图尺寸不同，不作为逐像素原始证据。

### 仿真入口截图裁剪显示版

`15-select-simulation-sources-cropped.png`：使用内置imagegen从原截图制作裁剪编辑版，提示仅保留Vivado窗口（原坐标0,0至2220,1206），去除底部文件管理器和桌面，不拉伸、不新增标注。生成尺寸[1702, 924]，属于生成式编辑衍生图，不声称逐像素无损裁剪。原始2220×1472截图保持不变，SHA256与初始记录一致。正文使用独立图片及width:100%;height:auto，去除原aspect-ratio遮罩。
