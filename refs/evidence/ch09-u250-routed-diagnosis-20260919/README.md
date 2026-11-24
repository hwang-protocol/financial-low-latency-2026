# U250 当前实现时序诊断

2026-09-19；证据为用户上传的 Windows Vivado 路由后时序报告，以及仓库内新旧适配器源码。只读取报告与源码，未启动仿真、综合、实现或设备操作，未修改 RTL/约束。

## 已确认结果

报告生成于 **2026-09-18 23:35:31**（原文未写时区），Vivado 2026.1 build 6511674，工程 `open_nic_shell`，状态 `Routed`。WNS **-1.723 ns**，TNS **-864.191 ns**，Setup失败端点 **3996**；Hold和脉宽失败端点均为0。它与用户最新Design Runs数值相符，但不足以确定构建实际用了哪一版源码。

报告使用 `-max_paths 10`，全文件57928行，提取506条详细路径，其中30条违反时序；这30条是报告选出的样本，不能当作全部3996个失败端点。

| 路径类别 | 最差裕量 | 报告中的关键证据 | 判断 |
| --- | --- | --- | --- |
| 250 MHz过滤路径 | -1.723 ns | `filter_inst/data1_reg[232]/C` → `filter_inst/core/m_mold_seq_reg[2]/CE`；4 ns周期内数据延迟5.558 ns，19层逻辑含9个CARRY8；经过 `core/fold_sum_return[14]` | 旧式组合校验和长链仍出现在这次实现中，应先核查源码副本与综合网表来源 |
| QDMA控制到数据通路 | -0.322 ns | `reg_qconf_reg[0]` → QDMA `gb_array_reg[100][2]/CE`；时钟125 MHz到250 MHz，10层逻辑 | 另有基础工程中的失败路径，不能承诺更新过滤器就使整板全部通过 |
| 322 MHz网络通路复位分发 | -0.179 ns | 复位同步寄存器 → `tx_slice_1_inst` 数据寄存器同步复位R引脚；扇出3502，布线延迟3.038 ns | 存在高扇出复位布线问题，不能把它直接设为false path |

组统计：axis_aclk_0同钟2985端点、TNS -771.570 ns；txoutclk_out[0]同钟1011端点、TNS -92.621 ns。QDMA 125→250 MHz跨钟组另列99端点、TNS -9.722 ns；跨钟计数可能与其他组共享终点，不能相加得到4095。

## 为什么首先怀疑构建来源

旧版适配器 `flle_rx_filter.before.sv` 用组合 `fold_sum` 函数完成校验和。仓库修正版 `u250-gui/flle_rx_filter.sv` 已移除该函数，增加 `checksum_tree`、`checksum_fold1/2` 与寄存的 `profile_ok`，使校验和计算由寄存器隔开。当前报告的最差路径仍从报文缓存直接穿过多级进位链和 `fold_sum_return` 到核心使能，与预期分段结构不符。

**推断：这次构建很可能仍使用了旧的设计源副本，或使用了旧综合/检查点结果。尚不能仅凭报告判定是用户替换位置、编辑器覆盖、缓存复用还是其他构建来源问题。** 全报告没有新寄存器标记只能作为旁证，因为报告只列有限路径，名字也可能经综合优化改变。

工程此前同时存在 `sources_1/imports/flle-sim` 和 `sim_1/imports/flle-sim` 等目录。仿真与综合可能引用不同副本；测试台收尾等待也从12改到32拍，所以11项PASS和仿真结束时间变化不能单独证明适配器流水线已经进入综合。AMD说明：Copy Sources into Project生成工程内副本，修改原始文件不会自动更新该副本。[AMD 更新本地源文件](https://docs.amd.com/r/2022.2-English/ug895-vivado-system-level-design-entry/Updating-Local-Source-Files)

下一步只取得并核查Windows工程内实际设计文件：`C:/FPGA/build/au250/open_nic_shell/open_nic_shell.srcs/sources_1/imports/flle-sim/flle_rx_filter.sv`。这个位置来自前次源码属性截图；若工程引用已改变，再以当前工程文件清单为准。若文件已是新版，再查`.xpr`的文件引用、synth_1日志/产物时间与实现所用检查点。确认来源前不要求重跑，不再盲目新增流水线。

报告还列出TIMING-3/4/6/27五个Critical Warning，涉及主时钟定义和关系；附带说明这些来自最近一次methodology运行，可能过期。需要具体对象级报告才可处理，当前不能由摘要归因为Vivado版本不兼容，也不应放宽周期或屏蔽时序检查。[AMD TIMING-4说明](https://docs.amd.com/r/2021.2-English/ug906-vivado-design-analysis/TIMING-4-Invalid-Primary-Clock-Redefinition-on-a-Clock-Tree)

## 保留范围与删除

按用户“看完把它删了”的要求，删除上传的 `Documents/newDoc/open_nic_shell_timing_summary_routed.rpt`，不另存完整副本。保留本摘要、结构化统计和三条典型路径摘录，以便后续定位且避免用户反复截图。

- 原报告：7608683字节，SHA256 `55e1cddf43eb733eeb1703744a8f25884e590781800a95df1cbd5cfae31416d0`。
- [结构化统计与来源指纹](summary.json)：含报告行号、失败样本和新旧源码SHA256。
- [过滤路径摘录](filter_checksum-excerpt.txt)：原报告从2843行开始。
- [QDMA路径摘录](qdma_control-excerpt.txt)：原报告从20989行开始。
- [网络复位路径摘录](network_reset-excerpt.txt)：原报告从15468行开始。

当前结论是“实现未通过，构建源码来源待核实”，不能写成“新流水线已验证无效”或“替换文件后保证通过”。硬件仍为NOT_RUN。
