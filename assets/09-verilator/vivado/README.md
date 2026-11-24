# 第九章：把同一份过滤核心放进 Vivado 仿真

当前目标：在电脑上观察“无额度放行、发一次额度、首条匹配丢弃、下一条继续放行”。
工程使用用户已选择的 U250 器件 `xcu250-figd2104-2L-e`。

## 1. 取得文件

在 `.111` 构建可分发 ZIP：

```bash
python3 /qyt-fll/assets/09-verilator/vivado/package.py
```

它复制第九章现有源码并生成摘要，不修改过滤核心。输出路径会打印到终端。
在 Windows PowerShell 执行以下命令，把 ZIP 下载到“下载”目录：

```powershell
scp root@10.1.1.111:/qyt-fll/artifacts/blobs/ch09-vivado/flle-ch09-vivado.zip "$env:USERPROFILE/Downloads/"
```

解压到 `C:/FPGA/src/`，得到 `C:/FPGA/src/flle-ch09-vivado/`。

| 文件 | 职责 | 使用位置 |
| --- | --- | --- |
| `market_filter.sv` | 比较 ITCH 类型 A、locate 8095、NVDA 字段，并消耗丢弃额度 | Vivado Design Sources；Verilator 输入 |
| `market_filter_sim_tb.sv` | 产生时钟、行情和额度，自动检查结果 | Vivado Simulation Sources |
| `mold_filter_adapter.cpp` | 调用 RTL 模型；内部自测，以及 Linux 行情收发 | Linux / Verilator |
| `market_filter_tb.cpp` | 独立检查 14 项 RTL 行为 | Linux / Verilator |
| `offline-selftest.sh` | 编译并运行上述两项 Linux 测试，保存日志 | Linux 开发机 |

`market_filter.sv` 的输入是已提取的 36 字节 ITCH 消息，输出是放行/丢弃判决。
Linux adapter 根据判决转发或丢弃完整报文。Windows 仿真由 SV 测试台直接提供消息。

## 2. 在当前 Vivado 工程加入电路

点击 **Add Sources → Add or create design sources → Add Files**，只选
`market_filter.sv`。勾选 **Copy sources into project**，点击 **Finish**。
在 **Design Sources** 下确认顶层为 `market_filter`；需要时右键 **Set as Top**。

## 3. 加入测试台

再次点击 **Add Sources → Add or create simulation sources → Add Files**，选择
`market_filter_sim_tb.sv`，复制进工程后完成。在 **Simulation Sources / sim_1**
下将 `market_filter_sim_tb` 设为顶层。两份文件的类型均应为 **SystemVerilog**。

## 4. 运行并读结果

点击 **Run Simulation → Run Behavioral Simulation**。若只运行到设定时长，点击
**Run All**，让测试执行到 `$finish`。测试总时长小于 1 微秒。

预期控制台末尾：

```text
RTL_GUI_SIMULATION=PASS cases=14 hardware=NOT_RUN
```

波形重点看 `cfg_load_valid`、`cfg_load_drops`、`remaining_drops`、`s_mold_seq`、
`m_valid`、`drop_valid`、`pass_count`、`drop_count`。用 **Zoom Fit** 展开全程。

| 本段动作 | 预期结果 |
| --- | --- |
| 额度 0，送匹配消息 | `m_valid=1`，放行 |
| 写入一次额度，同时保持待处理消息 | `s_ready=0`，本周期只接收配置 |
| 配置结束，处理序号 200 | `drop_valid=1`，额度归零 |
| 再送序号 201 | `m_valid=1`，继续放行 |
| 补额度后送类型、编号、股票或填充不匹配的消息 | 放行，保留额度给下一条匹配消息 |
| 撤销额度或复位 | 后续匹配消息继续放行 |

计数在测试后半段的复位检查中清零；逐条 `CASE_PASS` 是各检查点的结果。
保存模拟器的日志；Vivado XSim 实跑结果以本机输出为准。

## 5. 同一源码在虚拟机运行

解压后的 Linux 开发机需要 Verilator、g++、make，运行：

```bash
bash offline-selftest.sh
```

脚本输出六项 adapter 自测及 14 项独立 RTL 回归，完整日志写到最后打印的目录。
这一步验证软件模型中的过滤行为。第九章 A1—A5 再将 adapter 接入课程行情链路，
由真实报文的出口、缺口及恢复状态验收；接流执行位置沿用第九章 `.2`，由 `.111`
脚本控制。

## 6. 转向 FPGA 卡和交换机

共用层是策略核心 `market_filter.sv`。板级工程提供网口收发、报文解析与缓存、
时钟复位和寄存器控制接口，接到核心的消息输入与判决输出。
U250 路线接 OpenNIC 并生成对应镜像；7135V 路线接完整 BVL 工程并生成 PDI。
构建在开发机完成，装载和物理网口实测需要相应硬件。

第八章当前使用独立的整帧核心 `frame_filter.sv`；两章策略相近，接口与实现层次不同。
本包保留第九章核心原样，为后续复用提供明确入口；跨板适配及上板仍需完成。

验证边界：随包 SV 测试台先用 Icarus 检查；这与 Windows Vivado/XSim 实跑分别记录。
本包是过滤逻辑与软件仿真材料，不包含可直接装载的 U250/BVL 板级工程。

官方界面说明：[AMD UG900 仿真指南](https://docs.amd.com/r/en-US/ug900-vivado-logic-simulation)。
