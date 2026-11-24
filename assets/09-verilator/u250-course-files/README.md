# U250 手动加入课程源码

先把本文件夹完整放到 `C:\QYT-FPGA\flle-src`。五份 `.sv` 全在这一个目录；创建官方OpenNIC基础工程后，在Vivado GUI中加入这些代码。创建工程使用OpenNIC提供的工具，后续仿真、综合和实现均按GUI逐步操作。

## 加入三个设计模块

1. 左侧 **Add Sources → Add or create design sources → Next → Add Files**。
2. 在本目录选 `market_filter.sv`、`flle_rx_filter.sv`、`flle_rx_port.sv` 三个文件。
3. 按本次实录保留 **Copy sources into project** 勾选，三个模块复制进工程；自动扫描选项保持未勾选。
4. 截图保留文件列表、路径和 Copy sources 选项，随后点 **Finish**。
5. 设计顶层保持 `open_nic_shell`。此时还未接上接收路径，不运行综合。

| 文件 | 用途 | 加入方式 |
| --- | --- | --- |
| market_filter.sv | 行情消息判决、一次丢包额度 | 当前加入 Design Sources |
| flle_rx_filter.sv | 整帧适配、流水线校验和 | 当前加入 Design Sources |
| flle_rx_port.sv | 控制寄存器和跨时钟 IP 接线 | 当前加入 Design Sources |
| p2p_250mhz.sv | 将过滤器接入 OpenNIC 收包路径 | 下一步更换工程中的接线文件引用 |
| flle_rx_control_tb.sv | 产生输入并检查行为 | 随后加入 Simulation Sources |

## 后续接线步骤，按GUI逐步完成

在 Design Sources 展开 `open_nic_shell → box_250mhz_inst → p2p_250mhz_inst`，核对原文件来自 `C:/QYT-FPGA/plugin/p2p/p2p_250mhz.sv`。先 **Remove File from Project** 移除这份原接线文件的工程引用，保留磁盘原件；再用 **Add Sources → Add or create design sources** 加入本目录的 `p2p_250mhz.sv`，取消 Copy sources into project。该p2p直接引用flle-src；前面三个模块使用工程副本。工程内只保留一个p2p_250mhz模块定义。

确认 `p2p_250mhz_inst → … rx_filter_inst → filter_inst → core` 层次已经接入。前三个设计模块的工程副本路径可以位于 `sources_1/imports/flle-src`。若要核对版本，可打开实际引用的 `flle_rx_filter.sv`，查看 `checksum_tree` 和 `CHECKSUM`。

再用 **Add Sources → Add or create simulation sources** 加入本目录 `flle_rx_control_tb.sv`，取消 Copy sources into project，保留 Include all design sources for simulation。仿真顶层选 **flle_rx_port_tb**，设计顶层仍是 **open_nic_shell**。

上述两个顶层用途不同；测试文件名也不等于仿真顶层名。点击 Run Behavioral Simulation 后 Run All，成功时预期：

```text
U250_RX_CONTROL_SIMULATION=PASS cases=11 vendor_cdc=1 hardware=NOT_RUN
```

仿真之后进入综合、实现与报告检查。本次已完成代码接入、模块仿真、完整工程综合、实现与比特流生成；[实作图册](../../../images/course-visuals/08-u250-walkthrough/README.md)的27张截图覆盖到.bit文件属性与硬件管理器入口。

## 来源与验证

源码为已核对流水线版本的冻结副本，本次说明更新不改变RTL，也不重新运行测试。五份文件与已核对版本的SHA256逐一一致；此前本地适配器29、控制12（vendor_cdc=0）、扩展适配器102项PASS。

2026-09-19新建的 `C:/QYT-FPGA` 工程已有仿真、综合与实现的截图证据：Windows下包含AMD跨时钟IP模型的模块联合仿真11项PASS（vendor_cdc=1、25656 ns正常结束）；完整 `open_nic_shell` 工程综合成功。实现完成截图显示WNS 0.064 ns、WHS 0.010 ns，TNS/THS/TPWS为0、Failed Routes为0；本轮.bit已生成，文件属性显示43,573,574字节、修改时间2026-09-19 11:18:58。Hardware Manager仍未连接目标；完整约束/规则报告与实卡收发结果仍需对应证据。以上状态不引用旧 `C:/FPGA` 工程的结果。

`p2p_250mhz.sv` 是基于OpenNIC固定提交940907fc99fc8d73dbea0028b3a23095a660a42a的课程修改文件，保留上游版权说明，许可证见LICENSE-OpenNIC.txt。其余课程文件的来源和哈希见SOURCE-MANIFEST.json。

AMD关于外部引用与工程内副本的说明：https://docs.amd.com/r/2022.2-English/ug895-vivado-system-level-design-entry/Updating-Local-Source-Files 。本次三个设计模块复制到工程，p2p与测试台直接引用外部输入；单目录交付不等于所有文件必须采用相同引用形式。外部源码修改不会自动同步工程副本。

本README按实际截图修订；先前已交付的flle-src.zip保持原字节与历史摘要，本轮没有重新打包，也没有改变任何SV源码。
