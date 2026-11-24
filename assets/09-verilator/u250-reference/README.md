# U250 参考工程：从官方下载开始

本阶段任务：在已有过滤核心仿真和综合的基础上，取得 U250 的板卡基础工程，认识其文件，再通过 Vivado 继续集成开发。

## 第一步：下载官方工程

有 Alveo U250 时，先打开 [OpenNIC 项目总页](https://github.com/Xilinx/open-nic)。官方说明硬件源码在 [OpenNIC Shell](https://github.com/Xilinx/open-nic-shell)；该仓库 README 的支持板卡列表包含 U250。

为使教师和学员拿到同一份文件，本次使用固定提交的官方压缩包：

```text
https://github.com/Xilinx/open-nic-shell/archive/940907fc99fc8d73dbea0028b3a23095a660a42a.zip
```

这是 GitHub 按仓库和提交生成的源码归档。仓库页的 Code → Download ZIP 下载的是当前看到的分支或提交；后续日期可能拿到不同内容，因此本课写死上面这条地址。

本次用户把压缩包内的仓库内容直接放入 `C:/FPGA/`，因此 `README.md` 位于 `C:/FPGA/README.md`，构建脚本位于 `C:/FPGA/script/build.tcl`。下面的操作均以这个实际目录为准。

### 下载链接怎么找到，为什么能用于 U250

查找顺序是官方仓库 → README 的支持板卡和用途 → 板卡设置文件 → 固定源码版本 → 下载压缩包。[固定版本 README](https://github.com/Xilinx/open-nic-shell/blob/940907fc99fc8d73dbea0028b3a23095a660a42a/README.md) 明确列出 Alveo U250，并说明工程提供以太网、PCIe 及用户 RTL 接口，符合本课接入行情过滤逻辑的用途。

进一步核对 `script/board_settings/au250.tcl`：器件为 `xcu250-figd2104-2l-e`，板卡定义为 `xilinx.com:au250:part0:1.3`；仓库还提供 `board_files/Xilinx/au250/1.3/` 和 `constr/au250/`。这是选择 U250 的具体依据。压缩包支持多种板卡，运行时通过 `-board au250` 选择 U250。

浏览器打开上面的 `github.com/.../archive/<提交>.zip` 后，可能跳到 `codeload.github.com` 的同内容下载地址。`Xilinx/open-nic-shell` 指仓库，末尾 40 位是提交编号，不是 U250 型号。本次选择固定提交是为了复现相同源码，不表示该提交已经通过 Vivado 2026.1 的完整构建验证。

## 第二步：先认清下载到了什么

| 文件或目录 | 谁提供的 | 作用 |
| --- | --- | --- |
| `README.md` | 官方仓库 | 工程架构、支持板卡、构建参数和版本说明 |
| `board_files/Xilinx/au250/1.3/` | 官方仓库 | U250 的板卡定义和接口预设 |
| `constr/au250/` | 官方仓库 | 引脚、时序和其他板级约束 |
| `src/` | 官方仓库 | 网口、PCIe、时钟复位和用户逻辑接口等基础 RTL |
| `plugin/p2p/` | 官方仓库 | 默认数据通路示例，可参考它理解用户模块怎样接入 |
| `script/board_settings/au250.tcl` | 官方仓库 | U250 器件型号与板卡定义选择 |
| `script/build.tcl` | 官方仓库 | 按板卡及参数创建 IP、加入源码和约束，生成 Vivado 工程；其他参数可继续构建 |

这些基础文件已经在下载包中，不要求学员自己从零编写。

## 第三步：理解它如何交给 Vivado

下载包没有现成的 `.xpr` 工程文件。官方采用 `script/build.tcl` 生成工程：Vivado 执行这个 Tcl 文件，读取源码、板卡定义和约束，再产生可打开的 `.xpr`。

Vivado 图形界面提供 **Tools → Run Tcl Script** 入口。但运行前仍需明确脚本的工作目录、板卡和构建参数，不能把“点开任意 Tcl”写成已验证操作。这个版本的脚本使用相对目录，要求从 `script/` 工作目录执行；它还通过 `argc/argv` 读取参数。后续现场步骤应逐项说明这些设置及结果，不添加不透明的课程启动器。

2026-09-18 用户在新的 Vivado 2026.1 窗口中完成以下操作，并提供工程已打开的截图：

1. 打开 **Window → Tcl Console**；展开控制台后，点击日志下面的输入行。
2. 输入以下三行并执行：

   ```tcl
   cd C:/FPGA/script
   set argv {-board au250 -synth_ip 0 -impl 0}
   set argc [llength $argv]
   ```

   第一行设置官方脚本所需的工作目录。第二行指定 U250、推迟 IP 综合并关闭自动实现。第三行统计参数列表元素，返回 `6`，即三个选项名和三个值。这三行是本课说明的调用设置，`build.tcl` 本身来自官方包；没有额外启动器。脚本仍会创建 IP 和生成所需文件。
3. 点击 **Tools → Run Tcl Script**，选择 `C:/FPGA/script/build.tcl`，点击 **OK**。
4. 截图显示生成并打开 `C:/FPGA/build/au250/open_nic_shell/open_nic_shell.xpr`；顶层为 `open_nic_shell`，Project part 显示 Alveo U250，Board part 为 `xilinx.com:au250:part0:1.3`。`synth_1` 和 `impl_1` 均为 **Not started**。

这证明用户端已生成并打开参考工程；完整生成日志尚未收回，不能据此声明所有 IP 无告警或综合、实现通过。后续先综合官方基础工程，核实当前工具版本下能否完成，再进行本课过滤模块集成。

## 官方文件、工具模块和本课代码的关系

| 内容 | 来源 | 在本阶段的用途 |
| --- | --- | --- |
| OpenNIC 基础工程及板卡文件 | 上述官方下载包 | 提供真实板卡的基础连接 |
| CMAC、QDMA 等 IP | 用户安装的 Vivado | 按工程参数创建网口和 PCIe 模块；不随本课重新分发工具或许可证 |
| `market_filter.sv` | 本课已有源码 | 实现行情过滤判决，已在独立工程仿真和综合 |
| `market_filter_sim_tb.sv` | 本课编写的测试台 | 给过滤核心送测试输入并核对输出，已完成用户端 14 项仿真 |
| 后续适配代码 | 本课待开发 | 把完整报文、过滤判决和配置接口接起来；尚未交付 |

当前工程的下一开发目标是板级集成；下载基础工程不等于过滤逻辑已接好。改动时应逐个指出修改文件、增加的连接以及修改原因。

用户目录截图确认 Vivado 2026.1、CMAC 3.1 Rev.26、QDMA 5.1 Rev.4；官方 README 列出的构建版本是 2020.x、2021.x 和 2022.1。当前工程创建已由用户截图确认；IP 参数和端口兼容、授权、综合、布局布线及时序仍需按实际结果核验，不能提前写成通过。

维护机另缓存了同一版本的官方 tar.gz，来源/摘要见 `artifacts/ch09-u250-reference-source.json`（仓库根目录下）。缓存用于恢复与源码核对，不取代学员的官方下载步骤。ZIP 和 tar.gz 压缩包的摘要不同。
