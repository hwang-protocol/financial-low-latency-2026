# 把接收过滤模块接入当前 Windows OpenNIC 工程

> 历史工程接入与替换记录。2026-09-19 起本轮干净复走使用[单目录完整包](../u250-clean/START-HERE.md)，下面的旧目录替换步骤不用于新工程。

## 已接入工程的本次更新：只替换两份文件

当前用户已经完成首次接入。无需重复 Add Sources，只覆盖工程实际引用的两份文件：

| 新版文件 | Windows目标文件 |
| --- | --- |
| [flle_rx_filter.sv](flle_rx_filter.sv) | `C:\FPGA\build\au250\open_nic_shell\open_nic_shell.srcs\sources_1\imports\flle-sim\flle_rx_filter.sv` |
| [flle_rx_control_tb.sv](flle_rx_control_tb.sv) | `C:\FPGA\build\au250\open_nic_shell\open_nic_shell.srcs\sim_1\imports\flle-integration\flle_rx_control_tb.sv` |

可先把原件复制到备份目录；关闭这两个编辑标签，再用新版替换目标文件，防止旧编辑内容覆盖新版。允许直接下载到目标目录，保留原名，无需经过中转目录。随后仍以 flle_rx_port_tb 运行行为仿真/Run All，预期11项vendor_cdc=1；通过后重新综合和实现，查看新Timing/DRC/Methodology。

两拍及以上帧增加九拍校验等待（250 MHz下36 ns）；本地原适配器29项、控制12项、扩展102项通过，但新Windows结果与时序尚未验证。详见[修复证据](../../../refs/evidence/ch09-u250-checksum-pipeline-20260918/README.md)。以下首次接入说明供以后干净工程复走使用，当前不要重复执行。

2026-09-18 · 首版 Windows 联合仿真与综合通过，实现时序失败；当前流水线修复候选已通过本地功能验证，待 Windows 重测。

用户已把原 `C:\FPGA\plugin\p2p\p2p_250mhz.sv` 复制到另一目录备份。原核心 `market_filter.sv` 保留；接下来使用下面四份文件。无需创建新工程或运行新脚本。

| 文件 | 来源和用途 | 加入位置 |
| --- | --- | --- |
| [p2p_250mhz.sv](p2p_250mhz.sv) | 基于固定 OpenNIC 源码修改的接线文件，保留上游版权 | 替换已有文件，不再添加同名副本 |
| [flle_rx_filter.sv](flle_rx_filter.sv) | 已测整帧适配器的更新版，增加自动超时清额度 | 更新 Design Sources 中已有文件 |
| [flle_rx_port.sv](flle_rx_port.sv) | 助手编写的控制寄存器和接线外壳，复用工程现有跨时钟 IP | Design Sources |
| [flle_rx_control_tb.sv](flle_rx_control_tb.sv) | 助手编写的新增测试台，含本地测试与真实 AMD IP 联合测试两个顶层 | Simulation Sources |

接收方向现在是：网口 → 原 packet_adapter → p2p 中的 rx_filter_inst → flle_rx_filter → PCIe QDMA。原 market_filter 位于 flle_rx_filter 内部。发送方向继续使用官方 tx_ppl_inst。

## 人工更新文件

1. 在文件资源管理器创建 `C:\FPGA\flle-integration`，下载上表四份文件放进去；这是存放本次文件的位置。
2. 关闭 Vivado 中原 `p2p_250mhz.sv` 的编辑标签，避免编辑器中未保存的旧内容覆盖新文件。把下载的同名文件复制到 `C:\FPGA\plugin\p2p`，确认替换。桌面备份不动。
3. 更新工程内的适配器副本：用文本编辑器打开新下载的 `flle_rx_filter.sv`，全选并复制代码。在 Vivado 的 **Design Sources** 中双击已有 `flle_rx_filter`，在右侧源码编辑区全选、粘贴、保存。确认新源码参数列表包含 `ARM_TIMEOUT_CYCLES`。这一步直接更新工程实际引用的文件，避免只覆盖下载目录却没有更新工程副本。
4. **Add Sources → Add or create design sources → Add Files**，只加入新文件 `flle_rx_port.sv`，勾选 Copy sources into project，Finish。设计顶层保持 **open_nic_shell**。
5. **Simulation Sources** 中，旧测试台下面可能仍引用先前导入的 `sim_1/imports/flle-sim/flle_rx_filter.sv` 和 `market_filter.sv`。查看文件属性确认路径后，仅移除这两份仿真专用副本的工程引用（Remove File from Project，不勾选删除磁盘文件）。保留 `flle_rx_filter_tb.sv` 和 Design Sources 内的两份硬件源码。这样两个测试台都使用同一份设计源码，不会一边测试旧版、一边综合新版。若属性显示已经引用 `sources_1` 中的设计文件，就不移除。
6. **Add Sources → Add or create simulation sources → Add Files**，加入 `flle_rx_control_tb.sv`。保留 Include all design sources for simulation。在 Simulation Sources 中选择 **flle_rx_port_tb → Set as Top**，注意不是 flle_rx_control_tb，也不是原 flle_rx_filter_tb。

接线正确且刷新层次后应能展开：

```text
open_nic_shell
└─ box_250mhz_inst
   └─ p2p_250mhz_inst
      └─ … / rx_filter_inst : flle_rx_port
         ├─ control_cdc_inst : axi_lite_clock_converter
         ├─ control_inst : flle_rx_regs
         └─ filter_inst : flle_rx_filter
            └─ core : market_filter
```

中间 generate 层名称由工具显示为准。此时右侧仍打开的旧 Implemented Design 图不代表新代码已经实现。

## 先验证实际跨时钟 IP，再综合

点击 **Run Simulation → Run Behavioral Simulation → Run All**。测试台将控制时钟和报文时钟分开驱动，通过工程内真正的 AMD AXI-Lite Clock Converter 发授权、撤销和读回命令。测试使用缩短的超时周期，测试台最终预期输出：

```text
U250_RX_CONTROL_SIMULATION=PASS cases=11 vendor_cdc=1 hardware=NOT_RUN
```

首版 Windows 截图已确认此结果，结束于24856 ns；当前修正版需重新验证。`vendor_cdc=0` 表示只测同一时钟域的自有逻辑，不能代替这次联合测试。若测试卡住或报错，保留首条失败消息；不要修改测试预期或屏蔽超时。

联合测试通过后再核查设计层次并 Run Synthesis。之后仍需要处理 CMAC XCI 过期原因、原基线时钟告警，运行 Implementation、查看 Timing/DRC 并生成 bitstream；首版综合已通过，实现WNS=-1.943 ns；当前修正版尚待完整重建。不要使用 Force up-to-date 把旧结果当新版。

## 控制接口约定

仅支持当前 `NUM_QDMA=1`，接口数量可为 1 或 2；每个接口独立拥有一次额度与计数。多 QDMA 分支保留上游代码以便比较，不属于本次交付范围，仿真参数检查拒绝该配置。

管理访问经已有 `axi_lite_clock_converter` 从 axil_aclk 进入 axis_aclk；所有寄存器、状态采样和过滤判决均位于 axis_aclk。修改版 p2p 调用上游 `generic_reset(NUM_INPUT_CLK=2)`，为两个时钟域生成复位。上游固定配置为 AXI4LITE / DATA_WIDTH=32 / ACLK_ASYNC=1 / SYNCHRONIZATION_STAGES=2。参考 [AMD 时钟转换说明](https://docs.amd.com/r/en-US/pg059-axi-interconnect/Clock-Conversion)，不自行添加 false path 来隐藏原工程时钟警告。

上游地址表为 PCIe BAR2 内 250 MHz 用户区，端口 i 的 ingress 基址为 `0x40000 + i*0x100`；由固定源码地址映射推导，尚未实卡读回。下表偏移相对于该 ingress 基址。地址映射和访问工具必须与最终镜像一起验证，当前不要求用户在 Windows 发 PCIe 寄存器命令。

| 偏移 | 内容 |
| --- | --- |
| 0x00 | 只读标识 0x464C4C45（FLLE） |
| 0x04 | 寄存器接口版本 0x00010000 |
| 0x08 | 写 1 授予一次额度，写 0 撤销；读为 0 |
| 0x0C | 状态：bit0 有额度，bit1 命令待生效，bit2 当前处于帧边界 |
| 0x10 | 剩余额度 |
| 0x14 / 0x18 | 完整放行帧数 / 策略丢弃帧数；32 位计数回绕，复位清零 |
| 0x1C / 0x20 | 最近一次丢弃的 64 位 Mold 序号：先读低 32 位获取快照，再读高 32 位；同一端口由单个读取者串行访问 |
| 0x24 | 超时周期数：默认 1,250,000,000，即 250 MHz 下 5 秒 |
| 0x28 / 0x2C | 源 IPv4 20.1.1.1 / 组播 IPv4 233.74.125.32 |
| 0x30 / 0x34 | 目的端口 31032 / Locate 8095 |
| 0x38 / 0x3C | 股票字符 NVDA / 四个空格 |

主机只进行对齐的 32 位访问；OpenNIC 用户接口没有传入字节写掩码。非法命令值、未实现地址、非对齐地址和对只读寄存器的写入返回 SLVERR。AXI 写地址和数据可以先后到达，写响应需等命令在帧边界生效；正在接收未完报文或输出被阻塞时，写响应会等待。读响应的数据在背压下保持稳定。

复位零额度。授权不会累加，每次写 1 重新授予一次额度并重新计时。计时从实际生效开始，自动清零不等待帧边界，超时同拍禁止产生新的丢弃判决；已判决丢弃的报文不恢复。缺失帧尾导致在途命令一直等待的行为尚无独立总线超时恢复设计。

本版本仍是教学构建候选：没有证明 250 MHz 时序或持续 100G 吞吐，没有主机控制程序、Mold session 审计和真卡测试；不能直接视为生产网卡交付。已验证的原核心没有改写。
