# U250 接收接口：复用过滤核心的整帧仿真

接收接口适配模块用于验证 OpenNIC 格式的数据如何交给已有核心判断，并执行整包放行或丢弃。原有核心测试仍有效；`market_filter.sv` 没有修改。2026-09-18 已补充 OpenNIC 接线候选和控制接口，见 [人工接入步骤](INTEGRATION.md)；首版Windows联合仿真及综合通过，实现WNS=-1.943 ns。当前已改为校验和流水线候选，本地29/12/102项通过，修正版Windows仿真及新实现时序待确认。

## 文件来源与用途

| 文件 | 来源 | 用途 |
| --- | --- | --- |
| [market_filter.sv](../market_filter.sv) | 本课已有代码，本轮原样复用 | 根据 ITCH 类型、Locate、股票代码及剩余额度作判决 |
| [flle_rx_filter.sv](flle_rx_filter.sv) | 本轮由助手编写的 SystemVerilog 硬件源码 | 接收 512 位数据流，暂存前两拍，解析报文，调用原核心，整包放行或丢弃 |
| [flle_rx_filter_tb.sv](flle_rx_filter_tb.sv) | 本轮由助手编写的 SystemVerilog 仿真源码 | 产生输入报文、配置和背压，逐拍比较输出数据、tkeep、tlast、tuser，核对额度和计数 |

这些 `.sv` 是硬件逻辑及测试台源码；测试台只用于仿真。源码核对使用的官方文件是 [OpenNIC p2p_250mhz.sv，固定提交 940907fc](https://github.com/Xilinx/open-nic-shell/blob/940907fc99fc8d73dbea0028b3a23095a660a42a/plugin/p2p/p2p_250mhz.sv)。Windows 原文件路径为 `C:\FPGA\plugin\p2p\p2p_250mhz.sv`；本目录同名文件为保留上游版权说明的修改版，用户已完成首次替换与接入，本次流水线修复无需再次修改P2P。

## 为什么还有适配代码

原核心的输入是已经提取好的 36 字节 ITCH 消息和 MoldUDP64 序号，输出只是放行/丢弃判决。OpenNIC 的接收口提供含 Ethernet、IPv4、UDP、MoldUDP64 头的整帧，以及有效字节、帧尾、元数据和握手信号。适配模块负责保存这些内容、提取核心输入，并按判决处理原帧。

现有官方 `p2p_250mhz` 在单 QDMA 分支中通过 `rx_ppl_inst` 将 `s_axis_adap_rx_250mhz_*` 接到 `m_axis_qdma_c2h_*`。这是后续待适配的接收方向；直接添加 `.sv` 文件不会自动建立实例和信号连接。

## 本模块的明确范围

- 数据接口为 512 位（每拍 64 字节）、64 位 `tkeep`、1 位 `tlast`、48 位 `tuser`，帧首字节位于 `tdata[7:0]`。数据不含以太网 FCS。
- 匹配范围：无 VLAN、IPv4 IHL=5、无分片、UDP，源 IP `20.1.1.1`、目的 IP `233.74.125.32`、目的端口 `31032`；一条 36 字节 ITCH 消息；帧长恰好 100 字节。IP/UDP/Mold 长度必须一致。检查 IPv4 头校验和及非零 UDP 校验和；IPv4 的零 UDP 校验和可通过。源端口、MAC 和 Mold session 不作为匹配条件。
- 原核心识别类型 `A`、Locate `8095`、股票代码 `NVDA` 加四空格。通过参数可改变过滤目标，默认值与现有核心测试相同。
- 复位后零额度。`cfg_valid && cfg_ready` 时接收命令：`cfg_arm=1` 装入一次额度，`cfg_arm=0` 清零。配置只能在帧边界接收；发送端必须保持命令直到握手。新增参数 `ARM_TIMEOUT_CYCLES`，默认 0 保持原独立测试行为；接线外壳设为 1,250,000,000，在 250 MHz 下为 5 秒。到期清额度优先于同拍新判决，不必等报文结束；已作出的丢弃判决不会撤销。
- 不在匹配范围内的帧全部原样通过，包括 VLAN、多消息、坏校验和及不规则 `tkeep`。这是策略适配器，不是错误帧清洗器。目标帧在判决之前不会向下游输出任何一拍。
- 前两拍暂存后按原顺序回放；更长的非目标帧后续直接握手转发。数据和元数据在背压期间保持稳定。复位会中止尚未转发完的帧并清空计数和额度。
- `passed_frames` 统计完整转发到下游的帧，`dropped_frames` 统计策略丢弃帧，`last_drop_sequence` 记录最近一次策略丢弃的序号。
- 这份教学适配器会在报文之间产生处理停顿；未验证 100 Gb/s 连续接收能力、250 MHz 时序或前级缓存溢出。不能以本次仿真宣称线速可用。
- 本模块端口同属 `clk` 域，复位必须与此时钟同步释放。新增 `flle_rx_port.sv` 通过已有 AMD AXI-Lite Clock Converter 接入管理时钟域；修改版 p2p 使用已有 generic_reset 为两个时钟域生成复位。上述接线仍需 Windows 实际 IP 模型与板级报告验证，现有时钟警告尚未定位。

## 用户下一步：只用 Vivado 界面运行仿真

以下流程已由用户在 Windows Vivado 2026.1 执行，2026-09-18 控制台截图确认 29 项 PASS、1648 ns 正常结束。截图为原先未加超时参数的适配版本；本节保留为复现步骤。

1. 用文件资源管理器新建 `C:\FPGA\flle-sim`，把上表三份 `.sv` 放进去。保留已完成原核心仿真的旧工程和官方源文件。
2. 在 `open_nic_shell` 工程中点 **Add Sources → Add or create simulation sources → Next → Add Files**，选择这三份文件。它们全部先放入仿真源集，尚不修改板级综合的顶层或接线。
3. 若向导提供 **Copy sources into project**，勾选后点 **Finish**。后续修改应打开 Sources 中显示的工程内副本，避免编辑外部旧副本而以为工程已更新。
4. 在 **Sources → Simulation Sources** 中找到 `flle_rx_filter_tb`，右键 **Set as Top**。这是仿真顶层；设计顶层仍是 `open_nic_shell`。
5. 点 **Run Simulation → Run Behavioral Simulation**。若打开后仿真按默认时长暂停，点击仿真工具栏 **Run All**，直到测试台自行 `$finish`。
6. 在仿真输出中确认最终出现 `U250_RX_ADAPTER_SIMULATION=PASS cases=29 hardware=NOT_RUN`。输出中任意 `$fatal` 均须先排查。波形可观察 `remaining_drops`、`dropped_frames`、`passed_frames` 及输入输出握手。

此步骤让用户在本机复核新增连接逻辑。尚不能用它证明 OpenNIC 完整镜像已接入过滤功能；通过以后才安排设计源添加及实例接线。

## 已执行的开发验证

本机 Linux RUN `20260918T093350Z-u250-rx-adapter`：Icarus 编译/仿真退出 0，29 项检查通过；Verilator 4.038 对可综合模块 lint 退出 0。原始输出、命令和摘要见 [归档记录](../../../refs/evidence/ch09-u250-rx-adapter-20260918/README.md)，运行态另存 reports/run-state 的同名 RUN。Icarus 提示常量切片使 `always_comb` 敏感列表扩大，不是本次仿真失败。

新增接线版本的本地 RUN `20260918T101540Z-u250-integration`：原 29 项回归通过，控制接口 12 项通过，RTL 与端口结构检查通过。详见 [接线验证记录](../../../refs/evidence/ch09-u250-integration-20260918/README.md)。后续用户 Windows Vivado 2026.1 截图确认真实 IP 联合测试顶层 `flle_rx_port_tb` 输出 `U250_RX_CONTROL_SIMULATION=PASS cases=11 vendor_cdc=1 hardware=NOT_RUN`，正常结束于 24856 ns；原始日志/图片待收回。该结果独立于 Linux 声明替身检查。尚未对过滤后的整套 OpenNIC 确认综合/实现、PCIe 或真卡网络实验通过。CMAC `.xci` 过期状态及官方 TIMING-3/4/6/27 警告仍待处理。
