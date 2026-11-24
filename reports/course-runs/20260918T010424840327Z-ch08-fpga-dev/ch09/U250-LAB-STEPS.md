# U250 台架操作单：从设备检查到一次 NVDA 过滤

> **历史 U250 / OpenNIC 路线，保留供对照。** 当前第 09 章改用 Alveo V80 / AMR 3.0.0；本页的 au250、onic、.bit 和未实现的演示工具不适用于 V80。当前工程见同目录 `v80/README.md`。


> 2026-09-07 · DESIGN / NOT HARDWARE VERIFIED · 配套第10章“走向真实硬件”

本单供开发者/教师查内部实现，学生正文只展示Shell命令。这里保留Vivado内部脚本细节；不是要求学生到多个命令解释器逐段输入。

本单用于 **U250 + 固定 OpenNIC 工程 + 独立 100G 台架**。命令已按公开源码核对，尚未在本课构建或上板。先验证官方默认收发，再验证 NVDA 插件；本仓库仍缺完整包处理插件、寄存器控制程序和 `onic` 课程配置档案。准备齐这些交付物，才能完成最后的一次过滤。

正文展示的是默认收发→加载过滤镜像→设置一次额度的状态变化，策略查询接口定义见本单第6节。

这里的“开发机”运行 Vivado；“插卡主机”安装 U250 并运行 Linux 驱动；两者可以分开，开发机用 USB-JTAG 连接卡。`.101` 不是编译前提。数据口使用独立 100G 对端，管理连接不经过待重配置的卡。

## 1. 记录卡的身份与支持条件

先按正文运行 `lspci -Dnnk`。将实际完整 BDF 记为 `FLLE_FPGA_BDF`；这个值只属于插卡主机，不用于选 JTAG 线缆。记录实卡型号/板版、FPGA 型号、供电、PCIe 插槽宽度、网口和 JTAG 线缆身份。

| 核对项 | 固定版本依据 | 不满足时怎么处理 |
| --- | --- | --- |
| 板型 | `script/board_settings/au250.tcl` 的 part 为 `xcu250-figd2104-2l-e`，board part 为 `xilinx.com:au250:part0:1.3` | 换对应板级工程，不能仅改文件名 |
| Vivado | Shell README 列出 2020.x、2021.x、2022.1；2022.2 的 QDMA 5.0 另有驱动配套提示 | 首轮选择上游列出的组合，不默认最新版兼容 |
| IP 许可 | `cmac_usplus` 免费许可仍需领取、安装并被 Vivado 识别 | 依 README 补许可、重建 IP，再继续生成镜像 |
| 数据链路 | 本版 OpenNIC 为 100G，驱动要求装载前链路就绪 | 准备匹配对端与 FEC；本课 7150 10G 链路不能原样迁入 |
| Linux | 配套驱动在 Ubuntu 18.04/20.04/22.04 的若干内核测试过 | 保存实际 `uname -r`，准备匹配内核头文件并验证驱动；不能泛称任何内核均可 |

依据：[固定板配置](https://github.com/Xilinx/open-nic-shell/blob/940907fc99fc8d73dbea0028b3a23095a660a42a/script/board_settings/au250.tcl)、[Shell README](https://github.com/Xilinx/open-nic-shell/blob/940907fc99fc8d73dbea0028b3a23095a660a42a/README.md)、[Driver README](https://github.com/Xilinx/open-nic-driver/blob/3de226996ff5bacf8c4bdcec5318725e39c80b23/README.md)。

## 2. 取得工程，先生成默认收发镜像

在**开发机新建的工作目录**中取源码，保留固定版本。以下目录不应覆盖已有工程；Vivado 环境脚本路径按安装位置替换。Git checkout 仅选择上游版本，不向课程仓库提交内容。

<div style="border-left:6px solid #15803d;background:#dcfce7;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#15803d;color:#fff;font-weight:800;">命令<span style="color:#fde047;background:#166534;border-radius:4px;padding:0 4px;">(模拟)</span> · 源码与工具准备（Bash）</span> <span style="font-weight:700;color:#14532d;">开发机；固定版本下载、环境加载与版本查看。本课未执行下载后的 Vivado 构建。</span></div>

```bash
FLLE_HW_ROOT="$PWD/flle-u250-lab"
mkdir "$FLLE_HW_ROOT"
cd "$FLLE_HW_ROOT"
git clone https://github.com/Xilinx/open-nic-shell.git
git -C open-nic-shell checkout --detach 940907fc99fc8d73dbea0028b3a23095a660a42a
source /填写实际安装目录/Vivado/2022.1/settings64.sh
vivado -version
cd "$FLLE_HW_ROOT/open-nic-shell/script"
```

在同一 Bash 会话运行正文的默认构建命令：`-board au250 -tag pass_lab -impl 1`。首次使用 `pass_lab` 标签；重做时换新标签，避免把旧构建当新结果。Shell 随带 `board_files`；若需外部板文件，用 `-board_repo` 指向已核对并记录版本的板仓库。

完成后，在同一会话记录输出路径和摘要。

<div style="border-left:6px solid #15803d;background:#dcfce7;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#15803d;color:#fff;font-weight:800;">命令<span style="color:#fde047;background:#166534;border-radius:4px;padding:0 4px;">(模拟)</span> · 定位构建产物（Bash）</span> <span style="font-weight:700;color:#14532d;">开发机；仅在 Vivado 构建完成后执行。文件存在只证明有产物，还需检查实现报告。</span></div>

```bash
FLLE_PASS_BUILD="$FLLE_HW_ROOT/open-nic-shell/build/au250_pass_lab/open_nic_shell"
FLLE_PASS_BIT="$FLLE_PASS_BUILD/open_nic_shell.runs/impl_1/open_nic_shell.bit"
sha256sum "$FLLE_PASS_BIT"
```

打开 `$FLLE_PASS_BUILD/open_nic_shell.xpr`，查看 **Implementation → Open Implemented Design → Report Timing Summary / Report DRC**。确认实现完成、无阻断问题、必要时钟与路径有约束，setup/hold 检查通过；保存完整报告。生成文件本身不能证明时序合格。[构建参数与产物目录依据](https://github.com/Xilinx/open-nic-shell/blob/940907fc99fc8d73dbea0028b3a23095a660a42a/script/build.tcl)

## 3. 补齐 NVDA 插件，再编译过滤镜像

这一步是当前仓库的工程缺口。开发者应先交付以下内容，学员上机时应拿到完整工程，不能要求学员猜寄存器地址或现场拼网卡接口。

| 交付物 | 必须完成的行为 |
| --- | --- |
| 包处理外壳与 `market_filter.sv` | 缓存原帧；校验源/目的地址、端口与长度；给核心送字段和序号；裁决后整包放行/丢弃；非目标有序通过 |
| 插件接线与时序约束 | 接到 OpenNIC 的 250 MHz 接收用户区；另一用户区保留默认连接；配置跨时钟交接正确 |
| 寄存器地址表与主机控制工具 | 显示版本/生效条件；设置一次额度、清零额度、读取剩余次数与丢弃记录；地址和宽度与镜像一致 |
| 硬件超时和审计 | 替代 C++ 的超时撤销；保存丢弃会话/序号，策略丢包与错误/溢出分开计数 |
| 插件仿真与构建记录 | 测首个目标丢弃、后续目标通过、非目标通过、连续包、停顿和复位；保存源码版本、报告与 `.bit` 摘要 |

控制工具至少要提供“查看当前状态”“设置一次额度”“撤销额度”“读取丢弃记录”四个实际入口，并配命令输出示例。**这些入口应由实现后的工具给出；当前不虚构一个已存在的 `fpga-ctl` 命令。**

完整插件的目录约定来自 [OpenNIC User Plugin Integration](https://github.com/Xilinx/open-nic-shell/blob/940907fc99fc8d73dbea0028b3a23095a660a42a/README.md#user-plugin-integration)。`FLLE_PLUGIN` 指向开发者交付的目录，不能指向只有 `market_filter.sv` 的当前资产目录。

<div style="border-left:6px solid #15803d;background:#dcfce7;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#15803d;color:#fff;font-weight:800;">命令<span style="color:#fde047;background:#166534;border-radius:4px;padding:0 4px;">(模拟)</span> · 过滤插件构建（Bash）</span> <span style="font-weight:700;color:#14532d;">开发机、已有完整插件后；在子 shell 中检查缺文件即退出，再构建。此检查不代替功能仿真或检查实际接线。</span></div>

```bash
(
  set -e
  FLLE_PLUGIN='/填写已实现的NVDA插件绝对目录'
  for flle_freq in 250mhz 322mhz; do
    for flle_file in \
      "build_box_${flle_freq}.tcl" \
      "box_${flle_freq}/user_plugin_${flle_freq}_inst.vh" \
      "box_${flle_freq}/box_${flle_freq}_address_map_inst.vh" \
      "box_${flle_freq}/box_${flle_freq}_address_map.v" \
      "box_${flle_freq}/box_${flle_freq}_axi_crossbar.tcl"; do
      test -f "$FLLE_PLUGIN/$flle_file"
    done
  done
  cd "$FLLE_HW_ROOT/open-nic-shell/script"
  vivado -mode batch -source build.tcl -tclargs \
    -board au250 -tag nvda_lab -user_plugin "$FLLE_PLUGIN" \
    -bitstream_userid 0xF1100001 -impl 1
)
```

插件实现时，在已完整接线的 `build_box_250mhz.tcl` 中加入 `read_verilog -sv rtl/market_filter.sv` 与 `read_verilog -sv rtl/nvda_packet_wrapper.sv`。这是开发者配置的内部构建入口，正文不再展示这两行；不能用它们覆盖完整脚本，核心必须由外壳实例化并连接。

该次镜像应在 `build/au250_nvda_lab/open_nic_shell/open_nic_shell.runs/impl_1/open_nic_shell.bit`。检查时序/DRC，并在实现后的层次中确认 `market_filter` 实例及其有效连接；核对可读镜像版本与本次构建记录。**官方 `build.tcl` 在用户区目录或构建脚本缺失时会退回默认插件；“成功生成 .bit”不证明包含 NVDA 策略。**

默认镜像和过滤镜像各自按下面的装载/收发流程验证。首次先装默认镜像；只有默认收发通过，才换过滤镜像。

## 4. 指定实卡并通过 JTAG 加载

**先完成插卡主机维护准备。** 完整镜像包含 PCIe 电路，重配置会使其链路消失。停止该卡数据业务，释放所有相关 PCIe 功能的驱动或虚拟机占用，保留独立管理/JTAG/带外控制。首次装载后，上游要求暖重启（重启主机但不断电），使 PCIe 重新枚举；不能冷断电后仍期待 JTAG 临时镜像保留。

上游提示某些 Dell/iDRAC 主机可能因链路消失强制重启，已加载 `onic` 时重扫也可能挂住内核。台架维护步骤必须适配实际主板；[完整工程说明](HARDWARE-NOTES.md)保留了 `setup_device.sh` 的适用范围与恢复要求。这里不自动改 PCIe 桥寄存器或调用未经台架适配的重扫脚本。

下面在**开发机 Vivado Hardware Manager 的 Tcl Console** 操作。先连接本机 `hw_server`，只列出 JTAG 目标。

<div style="border-left:6px solid #15803d;background:#dcfce7;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#15803d;color:#fff;font-weight:800;">命令<span style="color:#fde047;background:#166534;border-radius:4px;padding:0 4px;">(模拟)</span> · 列出 JTAG 目标（Tcl）</span> <span style="font-weight:700;color:#14532d;">开发机已连接 U250 的 USB-JTAG；此块只连接和枚举，不编程。</span></div>

```tcl
open_hw_manager
connect_hw_server -url localhost:3121
get_hw_targets
```

将输出中对应实卡线缆的**完整目标名**填入下一块；核对唯一匹配后打开，再列器件。若服务器连接已打开，不重复执行上一块。

<div style="border-left:6px solid #15803d;background:#dcfce7;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#15803d;color:#fff;font-weight:800;">命令<span style="color:#fde047;background:#166534;border-radius:4px;padding:0 4px;">(模拟)</span> · 选择线缆、列出芯片（Tcl）</span> <span style="font-weight:700;color:#14532d;">与上一块同一 Vivado 会话；按线缆身份选择，不默认选第一张卡。</span></div>

```tcl
set flle_target_name {填写 get_hw_targets 返回的完整目标名}
set flle_targets [get_hw_targets $flle_target_name]
if {[llength $flle_targets] != 1} {error "必须唯一匹配实卡 JTAG 目标"}
current_hw_target $flle_targets
open_hw_target
get_hw_devices
```

把当前目标下的 U250 器件名填入；确认 `PART` 是 U250 系列，实际封装/速级还需与铭牌及构建工程核对。只看到器件系列不等于完整板型匹配。

<div style="border-left:6px solid #15803d;background:#dcfce7;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#15803d;color:#fff;font-weight:800;">命令<span style="color:#fde047;background:#166534;border-radius:4px;padding:0 4px;">(模拟)</span> · 选择芯片并编程（Tcl）</span> <span style="font-weight:700;color:#14532d;">同一已完成维护准备的会话；第一次使用默认镜像的绝对路径，第二次换已验证的 NVDA 镜像。</span></div>

```tcl
set flle_device_name {填写 get_hw_devices 返回的 U250 器件名}
set flle_devices [get_hw_devices $flle_device_name]
if {[llength $flle_devices] != 1} {error "必须唯一匹配 U250 器件"}
set flle_device [lindex $flle_devices 0]
current_hw_device $flle_device
report_property $flle_device
if {![string match -nocase "xcu250*" [get_property PART $flle_device]]} {
  error "器件不是 U250，停止装载"
}
set flle_bit {/本次构建的绝对路径/open_nic_shell.bit}
if {![file isfile $flle_bit]} {error "镜像文件不存在"}
set_property PROGRAM.FILE $flle_bit $flle_device
program_hw_devices $flle_device
refresh_hw_device $flle_device
get_property REGISTER.IR.BIT5_DONE $flle_device
get_property REGISTER.USERCODE $flle_device
report_property $flle_device
```

保留编程日志，查看完成状态和刷新后的配置状态。过滤镜像的 DONE 应为 1，USERCODE 应与构建参数 `0xF1100001` 一致（示例标记，真实构建逐次登记）；默认镜像未指定标记时不能照这个值验收。`PROGRAM.FILE` 是指定的本地文件路径，本身不是板上镜像身份读回；USERCODE 是 JTAG 读回的镜像标记，不是密码学校验；NVDA 镜像还要通过插件控制接口读回生效策略与状态。带 ILA 时加载同次构建的 `.ltx`，才能正确解释探针。

命令依据：[选择硬件目标](https://docs.amd.com/r/2022.2-English/ug835-vivado-tcl-commands/current_hw_target)、[program_hw_devices](https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/program_hw_devices)、[OpenNIC 装载说明](https://github.com/Xilinx/open-nic-shell/blob/940907fc99fc8d73dbea0028b3a23095a660a42a/README.md#programming-fpga)。本单不用该提交的 `program_fpga.sh` 作直接入口：它调用的 Tcl 引用 `$hw_device`，而所读取的 `au250.tcl` 没有定义该变量；应先适配，不能承诺原样可用。

如需断电后自动加载，在临时配置、过滤和回退验收后，按[Flash 用户镜像步骤](HARDWARE-NOTES.md#u250-flash)生成 `.mcs` 并 Program / Verify。不要覆盖恢复区；Flash 操作和 JTAG 临时装载不是同一步。

## 5. 让 Linux 认出新网口并确认收发

在**插卡 Linux 主机**恢复枚举并记录本次 BDF。准备匹配当前内核的开发文件，再取固定驱动、构建。若启用 Secure Boot，模块签名/加载条件须按该主机配置处理，不能把加载拒绝当 FPGA 策略问题。

<div style="border-left:6px solid #15803d;background:#dcfce7;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#15803d;color:#fff;font-weight:800;">命令<span style="color:#fde047;background:#166534;border-radius:4px;padding:0 4px;">(模拟)</span> · 驱动构建与加载（Bash）</span> <span style="font-weight:700;color:#14532d;">插卡主机的新工作目录；100G 对端已连接、FEC 已匹配、没有已有 onic 模块占用，再执行 insmod。此命令会改变驱动状态，本课未执行。</span></div>

```bash
uname -r
git clone https://github.com/Xilinx/open-nic-driver.git
git -C open-nic-driver checkout --detach 3de226996ff5bacf8c4bdcec5318725e39c80b23
cd open-nic-driver
make
sudo insmod onic.ko
sudo dmesg --ctime | tail -n 60
lspci -Dnnk
```

若台架需要 RS-FEC，按驱动 README 和两端实际配置明确选择 `RS_FEC_ENABLED`，不要在不清楚对端的情况下套用默认值。然后执行正文的 BDF→网口检查与 `ethtool` 命令。成功标准是驱动/BDF/网口对上、链路与计数合理，并且实际报文到达主机；该固定驱动的链路变化检测有限，不能只靠 `Link detected` 一项。

默认镜像验证只需先用台架自己的地址收发；迁入课程行情时，再按 `HARDWARE-NOTES.md` 的接收端迁移表处理数据地址、组播订阅与控制器。当前课程配置检查 `SFC/READY/sfc`，需要新增 `onic` 配置档案；不能直接执行原软件 live 脚本来宣称真卡验收。

## 6. 管理工具怎样读回策略状态（待实现接口）

正文不再用模拟抓包演示，改为拟设计的 `flle-fpga show --device <BDF>` 与 `flle-fpga arm --device <BDF> --drops 1`。这入口是本课给插件定义的管理接口，目前没有对应可执行文件；它们不是 OpenNIC 或 Vivado 内置命令。前文“不虚构已存在的控制CLI”的边界仍成立。

| 状态 | show 应显示什么 | 实现依据 |
| --- | --- | --- |
| 已有默认 OpenNIC | opennic-pass、过滤器 NOT_PRESENT、PASS_THROUGH | 先识别已知默认镜像；不能对它盲读用户插件寄存器 |
| 本章镜像已加载 | opennic-nvda、本次 Build ID、PRESENT、规则、READY、额度0 | 插件初始化预置 Type A、Locate 8095、Stock NVDA加四空格；复位清零额度和审计 |
| arm 已确认，尚未命中 | ARMED、额度1、计数未增加 | 主机写入一次额度，等待板上确认，show重新读取当前状态 |
| 一次丢弃后 | 额度0、丢弃计数加1 | 核心在接受匹配消息时扣减额度；原子快照关联状态与计数 |

`READY` / `ARMED` 是管理工具对策略状态的中文解释对应标签，不是核心里的 `s_ready` 信号，也不是现有RTL的寄存器名。前者表示过滤规则就绪但额度为0，后者表示有一次可用额度。其实现必须从实际寄存器值推导，不能只读取本地文件或复述刚发出的写请求。

实施管理工具时，先核设备所有权、镜像身份及寄存器映射版本。未知镜像或读取失败应报错/UNKNOWN，不能默认打印“已加载”。默认OpenNIC没有过滤插件，工具应通过适配过的已知镜像识别流程返回NOT_PRESENT，不访问不存在的策略地址。控制接口必须为镜像身份、模块存在性、实际条件、额度与审计提供可读状态。

正文的 `Build ID: 0xF1100001` 假设插件向PCIe控制接口暴露与JTAG USERCODE一致的构建标记；OpenNIC参数写USERCODE不意味着它自动出现在任意BAR地址。需要在插件中显式接入该标记并随每次构建同步。ARMED与READY为当前快照：有匹配流量时，arm后立刻show可能已见额度0和计数加1。

现役核心支持外部cfg_locate/cfg_stock及cfg_load_drops，包处理外壳仍须实现启动条件、控制总线、配置确认/跨时钟处理、超时撤销与一致状态读取。本轮只定义教学接口，不实现命令或寄存器地址表。完整功能与恢复验收要求仍见 [硬件工程说明](HARDWARE-NOTES.md)；真实设备到手后再按实际台架取证，本段不再编造抓包文件和序号结果。

## 7. Shell加载入口的实现合同（待实现）

正文新增模拟命令 `flle-fpga load --device <BDF> --bit <文件>`。它与show/arm一样是拟设计接口，目前没有可执行文件，不是上游现成命令。学生只在Linux Shell调用它；工具内部调用Vivado，再由Vivado执行Tcl完成编程和状态读取。不是Tcl去执行Shell脚本。

- 设备配置档案须登记BDF、实卡身份与JTAG线缆/器件的一一对应；BDF本身不能选中JTAG目标。目标未知、不唯一或器件/镜像不符时停止，不能默认第一张卡。
- 调用前停流、释放相关驱动/VM占用并保留独立管理。load按第4节的既定台架维护流程调用Vivado、指定.bit和program_hw_devices；不能自动把PCIe重扫视为所有主机均安全。
- 装载无错误后，刷新并读取DONE、USERCODE。工具将实际读回整理成正文的Configuration/Build ID；值不符或读取失败就返回失败，不打印模拟成功。
- JTAG确认完成与Linux网口恢复是两个步骤。重枚举后的BDF可能变化，show/arm必须核对恢复后的身份；此接口不将DONE当作可收发或策略功能验证。
- 正文为了缩短路径，把构建产物复制为 `/work/flle-u250-lab/nvda-filter.bit`，内容保持同一镜像；应在构建报告通过后复制和登记摘要。插件配置为读取固定rtl路径，复制market_filter.sv后再构建，无需学生手写read_verilog。

本节仅描述应实现的封装，不新增load脚本、装载回执或硬件验证结论。
