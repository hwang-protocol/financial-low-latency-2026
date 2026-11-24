# U250：从干净目录创建工程，一次走完

本次文件包：`flle-u250-clean-20260919`。把整个文件夹放到 Windows 的 **`C:\FPGA-clean`**，本轮所有输入和生成结果都放在这里。保留原来的 `C:\FPGA` 工程及其结果。已有 Vivado、U250 器件支持和许可继续使用，准备一个空的新目录即可。

这是课程预先集成的 OpenNIC 源码包：官方基础源码来自固定提交 `940907fc99fc8d73dbea0028b3a23095a660a42a`，官方建工程脚本保持原样；课程代码已经放到该脚本会读取的位置，接收路径也已接好。解压后先读本文件；根目录的上游 `README.md` 留作出处与背景。

**本轮只做一次新的完整构建。** 若失败，保留本次日志和关键截图，结束重试并整理文章。当前包沿用经过本地功能测试的校验和流水线候选，没有在这轮继续改 RTL；Windows 完整工程、时序和硬件结果仍须分别确认。

## 顺序与截图

| 步骤 | 做什么、完成时看什么 | 关键截图 |
| --- | --- | --- |
| 1. 放好文件 | 解压整个包，确认下面的目录结构 | 无需截图 |
| 2. 创建 Project | 在 Vivado 运行官方 `script/build.tcl`；出现 U250 / `open_nic_shell` 工程 | S05：Project Summary，保留窗口标题中的新路径 |
| 3. 核对代码、加入测试台 | 设计源码已由官方脚本载入；只添加一次 `sim` 中的测试文件 | S06：过滤模块层次和新版源码路径 |
| 4. 仿真 | 以 `flle_rx_port_tb` 运行到测试台结束 | S07：最终 PASS 行和仿真顶层，失败则保留首条错误 |
| 5. 综合 | Run Synthesis，把描述转换成电路网表 | S08：综合完成及网表里的过滤模块 |
| 6. 实现与检查 | Run Implementation，完成布局布线后检查 Timing / DRC / Methodology | S09：本次 Timing Summary，真实显示通过或失败 |
| 7. 生成文件 | Generate Bitstream；查看本次 `.bit` 的名字、时间与目录 | S10a：生成完成；S10b：文件资源管理器里的 `.bit` |
| 8. 装载入口 | Open Hardware Manager；有实卡才连接和配置 | S11：当前硬件连接状态；无卡就停在这里 |

正常过程先收这 **8 张关键图**。下载、许可、安装使用已有图片，不重复安装。报告中的详细错误只在需要保留失败原因时补图。

## 1. 一次放好整个目录

解压后的关键位置应为：

```text
C:\FPGA-clean\
├─ START-HERE.md
├─ SOURCE-MANIFEST.json
├─ SHA256SUMS
├─ LICENSE.txt
├─ board_files\                  官方板卡信息
├─ constr\                       官方引脚、时钟等约束
├─ script\build.tcl               原版官方建工程入口
├─ plugin\p2p\p2p_250mhz.sv      已接好过滤模块的接线代码
├─ src\market_filter.sv           行情判决核心
├─ src\flle_rx_filter.sv          新版流水线整帧适配器
├─ src\flle_rx_port.sv            寄存器、跨时钟 IP 与过滤器接线
└─ sim\flle_rx_control_tb.sv       本轮唯一需要手动添加的测试台
```

包内还保留了官方基础模块和其他板卡资料。整包复制即可；本轮不从其他目录拿文件，也不覆盖旧工程。开始前这个目录中应没有 `build`；该目录由创建工程步骤生成。

## 2. 从 Vivado 创建完整 Project

关闭旧工程，回到 Vivado 欢迎界面。这里用 OpenNIC 官方提供的入口创建完整工程，其中包含网口、PCIe、时钟、复位和约束。

打开 **Window → Tcl Console**，在底部输入区依次输入：

```tcl
cd C:/FPGA-clean/script
set argv {-board au250 -synth_ip 0 -impl 0}
set argc [llength $argv]
```

第一行指定工作目录；第二行把 U250 和“稍后手动综合、实现”的选项交给官方工具；第三行给出参数数量。这是调用官方脚本所需的参数，不需要另写启动脚本。

然后点 **Tools → Run Tcl Script**，选择 **`C:\FPGA-clean\script\build.tcl`**。

这一阶段会创建工程、生成 IP 文件和读入源码，可能需要数分钟以上；`-synth_ip 0 -impl 0` 将综合和实现留给后续 GUI 步骤。等待工程创建结束。若脚本报错，保留第一条错误并停在这里。

工程生成后的入口是：

```text
C:\FPGA-clean\build\au250\open_nic_shell\open_nic_shell.xpr
```

检查 **Project Summary**：Top module 为 `open_nic_shell`，器件为 `xcu250-figd2104-2l-e`，板卡为 Alveo U250。截 **S05**。此时还没有完成仿真、综合或实现。

## 3. 确认本轮代码，然后只加入测试台

官方脚本会读入 `src` 中的三份课程设计源码，并使用包内已经接好的 `plugin\p2p\p2p_250mhz.sv`。无需再添加这些设计文件。

在 **Design Sources** 中找到 `flle_rx_filter`，打开其源码，核对两件事：

- 实际文件路径是 **`C:\FPGA-clean\src\flle_rx_filter.sv`**。
- 搜索 **`checksum_tree`** 能找到寄存加法树，状态列表含 **`CHECKSUM`**。这个版本已移除旧的 `fold_sum` 组合函数。

应能沿 Sources 展开下面的层次；中间 generate 层名称以工具显示为准：

```text
open_nic_shell
└─ box_250mhz_inst
   └─ p2p_250mhz_inst
      └─ … rx_filter_inst : flle_rx_port
         ├─ control_cdc_inst : axi_lite_clock_converter
         ├─ control_inst : flle_rx_regs
         └─ filter_inst : flle_rx_filter
            └─ core : market_filter
```

截 **S06**，优先同时保留模块层次和打开文件的完整路径。源码身份确认后，本轮保持包内文件不变。

再点 **Add Sources → Add or create simulation sources → Add Files**，只选择 **`C:\FPGA-clean\sim\flle_rx_control_tb.sv`**。取消 **Copy sources into project**，保留 **Include all design sources for simulation**，点 Finish。

在 **Simulation Sources** 中右键 **`flle_rx_port_tb` → Set as Top**。它定义在 `flle_rx_control_tb.sv` 中，文件名和顶层模块名不同。设计顶层始终保持 `open_nic_shell`；测试台只属于仿真源集。

## 4. 仿真

点 **Run Simulation → Run Behavioral Simulation**，打开后点 **Run All**，直到测试台自行 `$finish`。成功时预期出现：

```text
U250_RX_CONTROL_SIMULATION=PASS cases=11 vendor_cdc=1 hardware=NOT_RUN
```

截 **S07**。`vendor_cdc=1` 表示使用真实 AMD 跨时钟 IP 的仿真模型；`hardware=NOT_RUN` 表示尚未上板。若出现 `$fatal`、编译失败或超时，保存首条错误，结束本轮后续构建。

## 5. 综合

关闭仿真，点 **Run Synthesis**。这一步综合完整 U250 工程，可能需要数分钟以上。完成后选择 **Open Synthesized Design**，确认网表中包含 `rx_filter_inst` / `filter_inst`，截 **S08**。仅仿真测试台通过不能证明整板已通过综合。

## 6. 实现与检查

点 **Run Implementation**，这是本轮主要等待阶段；此前同规模工程等待很久，本次也不能承诺具体分钟数。完成后选 **Open Implemented Design**，查看 **Report Timing Summary、Report DRC、Report Methodology**。截 **S09**，保留本次 Setup / Hold / Pulse Width 的结果和失败端点数。

若仍为 **Failed Timing**，按用户约定保存结果，不修改 RTL/约束，也不再重跑。若布局布线本身完成，可以沿用用户已授权的流程体验，尝试下一步导出一次；文档明确标注“文件已生成，时序未通过”。若流程报错而未完成，或 DRC 阻止生成，保留错误后结束本轮。

## 7. 生成并找到文件

点 **Generate Bitstream**。若提示必须重新综合或实现，先停下核对原因，不确认额外长时间重建。正常接续现有实现结果时，会运行 `write_bitstream`。

成功后截 **S10a**，并在文件资源管理器打开：

```text
C:\FPGA-clean\build\au250\open_nic_shell\open_nic_shell.runs\impl_1
```

找到 **`open_nic_shell.bit`**，显示文件名、修改时间和大小，截 **S10b**。保留同目录的本次报告与日志。生成 `.bit` 本身不代表时序已经达标。

## 8. 打开硬件装载入口

点 **Open Hardware Manager**。当前没有实卡，截图如实显示未连接状态，截 **S11**，本轮离线操作到此结束。

将来有已正确供电并连接 USB-JTAG 的真实 U250，才使用 **Open Target → Auto Connect → 选中器件 → Program Device → 选择 `.bit`**。上板须使用已完成时序和规则检查的对应构建；JTAG 配置后还需验证主机驱动、网络收包及过滤计数。实卡装载、硬件验收和掉电后从 Flash 启动均未在本轮执行。

## 文件来源与验证边界

- [OpenNIC 固定版本](https://github.com/Xilinx/open-nic-shell/tree/940907fc99fc8d73dbea0028b3a23095a660a42a)：保留上游源码、版权和 `LICENSE.txt`。所有官方 Tcl 脚本保持原始字节；课程修改的上游文件仅 `plugin/p2p/p2p_250mhz.sv`，该文件头部注明了修改身份。
- 官方 `script/build.tcl` 的根目录源码读取段会载入本包 `src/*.sv`；`sim` 独立放测试台，避免把测试台当作板级设计。
- `SOURCE-MANIFEST.json` 列出固定来源、课程文件哈希和验证状态；`SHA256SUMS` 固定整包输入。课程代码是已有候选的冻结副本，不把新版标记等同于时序承诺。
- 旧工程已生成 `.bit`，但其时序未通过，且报告仍呈旧校验和组合路径；具体旧副本/旧综合来源未证实。此次新目录消除旧导入副本混用的机会，实际结果以新日志为准。
- 官方固定版本原说明早于 Vivado 2026.1。当前包尚未完成 Windows 2026.1 的整板验证；本地仿真不覆盖厂商 IP、布局布线、持续线速或硬件验收。
