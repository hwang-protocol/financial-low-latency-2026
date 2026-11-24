# U250 校验和流水线修复候选

## 后续 Windows 结果（用户截图）

2026-09-19 已取得23:35:31生成的原始routed报告：最差路径仍包含旧版fold_sum组合链（19层、9个CARRY8），与本地新版寄存分段结构不符。因此此前Windows仿真/综合截图不能证明本次整板构建使用了修正版。先核查工程内实际设计源及综合来源，不直接再改RTL或重跑。另有QDMA和网络复位分发违例，详见 [路由报告诊断](../ch09-u250-routed-diagnosis-20260919/README.md)。上传原rpt按用户要求分析后删除，仅保留小型摘要与路径摘录。

2026-09-19 当前open_nic_shell工程的Design Runs显示impl_1 `route_design Complete, Failed Timing!`：WNS **-1.723 ns**、TNS **-864.191 ns**、WHS **0.009 ns**、THS **0.000 ns**。与下文旧实现 -1.943/-242.947 数值不同，当前仍未达到时序要求；本次最差路径、失败端点数、报告时间及Windows源码哈希尚未回收，不能直接把旧Path 81当作本次根因。下方“待新实现”描述为先前阶段记录。本次未启动新实验或改代码。

随后用户截图确认修复后整工程综合完成：synth_1 为 synth_design Complete，顶层open_nic_shell，impl_1 Not started。尚待新实现时序与规则报告；综合原始日志未归档。

2026-09-18 用户确认替换适配器和控制测试台并重启行为仿真，最新截图顶层 flle_rx_port_tb，输出 `U250_RX_CONTROL_SIMULATION=PASS cases=11 vendor_cdc=1 hardware=NOT_RUN`，正常结束于 **25656 ns**。这更新下文开发结束时的Windows待测状态；修复后的综合、实现、时序及实卡仍待验证。截图原文件、编译日志与Windows源文件哈希尚未收回。右上Failed Timing仍对应先前实现。

2026-09-18；本地 RUN_ID：`20260918T131841Z-u250-checksum-pipeline`。

用户 Windows Vivado 2026.1 的 Path 81 截图：`filter_inst/data1_reg[216]/C` → `filter_inst/core/m_mold_seq_reg[15]/CE`（其他条目为序号寄存器不同位），同属 axis_aclk_0。Requirement 4.000 ns，Data Path Delay 5.784 ns，其中 logic 1.989 ns、route 3.795 ns；18 个逻辑层级，包含 8 个 CARRY8；Slack -1.943 ns，skew -0.053 ns，uncertainty 0.046 ns。整工程 Setup WNS -1.943 ns、TNS -242.947 ns、457 个失败端点。截图尚由用户保存，未归档原始 Windows 报告。

旧适配器在同一组合路径内累加 IP/UDP 校验和、折叠进位并产生 profile_ok，直接控制核心输入有效信号。这与截图路径一致，是本次修复目标；尚无完整逐单元报告，不能断言它解释全部 457 个失败端点或所有 methodology 告警。

## 修改及代价

- `flle_rx_filter.sv`：IP/UDP 各使用六级寄存加法树，再用两级寄存处理进位折叠，最后寄存 profile_ok。前两拍报文保持稳定，CHECKSUM 状态等待九拍后进入原 CHECK 状态。
- 每个两拍及以上帧相对旧版增加九个时钟周期，在 250 MHz 下为 36 ns；增加寄存资源并降低此串行处理适配器的包速率。不宣称线速。单拍旁路流程不变。
- `flle_rx_control_tb.sv`：packet 任务固定收尾等待从 12 拍增至 32 拍，适应新增阶段；计分板、报文内容/计数/额度断言及总超时保留。
- `flle_rx_filter_tb.sv`：默认仍为原 29 项；可选 EXTRA_PIPELINE_TESTS 增加校验和数据变化、坏校验和不消耗额度、流水线各阶段复位后新报文等测试，总计 102 项。
- `market_filter.sv`、P2P 接线、控制寄存器接口及既有时钟约束未改。旧适配器保存在本目录 `flle_rx_filter.before.sv`。

流水线将组合运算分摊到多个周期，以增加延迟换取更短的周期内路径；参见 [AMD Pipelining Considerations](https://docs.amd.com/r/en-US/ug949-vivado-design-methodology/Pipelining-Considerations)。实际时序必须由新布局布线报告确认。

## 本地验证

Icarus SystemVerilog 仿真最终结果：原适配器 29 项 PASS，控制逻辑 12 项 PASS（vendor_cdc=0），扩展适配器 102 项 PASS。Verilator RTL 检查和单 QDMA 的 p2p 接口检查退出 0；接口检查使用已有 IP 声明替身，不验证 AMD IP 行为。

前两次开发候选失败日志保留：校验和树跨生成层的输出连接在仿真中保持 X，导致适配器超时和控制计分板未清空；改为显式命名的各级数组连接后通过。未通过屏蔽断言或取消总超时获取 PASS。

本目录 logs 保存全部开发日志，SHA256SUMS 固定最终源码。当前只有 Linux 功能验证，尚无修正版 Windows XSim、综合、实现、时序、bitstream 或实卡结果。旧版 Windows 11 项 vendor_cdc=1 PASS 不自动覆盖本候选。
