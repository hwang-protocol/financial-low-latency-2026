# V80：通过 PCIe 寄存器测试同一个过滤核心

这份代码把上一层的 `market_filter.sv` 原样接到 AXI-Lite 寄存器接口。Linux 把一条 36 字节 ITCH 测试消息和序号写进去，FPGA 返回“放行/丢弃”的判决。它不从网口收包，也不向现役交易系统发包。

**已验证：本地 RTL 仿真、Verilator 检查、C 编译与命令参数保护。未验证：Vivado 构建、AMC 镜像打包、烧写和 PCIe 实机读写。** 下面的板级步骤是有对应源码的集成路线，不能称为已经上板成功。

## 文件与本地测试

| 文件 | 任务 |
| --- | --- |
| `../market_filter.sv` | 沿用本章过滤核心，不复制、不改写 |
| `market_filter_axil.sv` | 接收独立的 AXI 写地址/写数据，保存消息，触发核心，保存判决 |
| `test_market_filter_axil.sv` | 验证 AXI 握手、WSTRB、复位、额度、序号和匹配结果 |
| `build_filter.tcl` | 锁定工具与上游提交，复制基础工程，在指定位置接入本课模块 |
| `check_build.tcl` | 导出时序/资源/DRC 报告，拒绝负 slack 与严重 DRC，记录实际 Boot/PLD 路径 |
| `integrate_filter.tcl` | 用本课模块替换官方 PF1 GPIO 示例，保留原地址/时钟/复位连接 |
| `filter_mmio.c` | Linux x86-64 程序，经指定 PCIe PF1 的 BAR2 访问本课寄存器 |
| `run_local_tests.sh` / `test_mmio_guards.py` | 重跑本地检查；不访问 PCIe 硬件 |

在本目录执行；需要 Icarus Verilog、Verilator、GCC 和 Python 3：

```bash
./run_local_tests.sh /tmp/flle-v80-local-test
```

默认使用上一级的 `market_filter.sv`；需替换时，`CH09_CORE_FILE` 填单个源码文件路径。它不复用第八章表示源码目录的 `FLLE_CORE`。

本次得到 110 项 RTL 检查和 5 项 CLI 保护测试通过。Icarus 对 `always_comb` 的常量切片会提示扩大敏感列表，不影响此次行为仿真；Verilator 仅关闭未使用信号提醒：本接口不区分 AXI 保护位，核心也只读取 ITCH 的指定字段。

## 接口与地址

官方 `v80_base/scripts/config_bd.tcl` 把 PF1 BAR2 映射到内部地址 `0x020200000000`；GPIO 占用 `0x020200020000` 开始的 4 KiB。本课替换这一个 GPIO，保留它的地址，所以 Linux 使用 **PF1、BAR2、偏移 `0x20000`**。

| 本模块内偏移 | 读写 | 含义 |
| --- | --- | --- |
| `0x00` | R | APP_ID = `0x464c4c39`，识别本课寄存器测试电路 |
| `0x04` | W | 命令：1=装入一次额度，2=提交当前消息，4=清零额度；不组合命令 |
| `0x08` | R | bit0=处理忙，bit1=结果有效，bit2=丢弃 |
| `0x0c` | R | 剩余额度 |
| `0x10/0x14` | R | 放行/丢弃累计次数 |
| `0x18/0x1c` | R | 最近结果的序号低/高 32 位 |
| `0x20` | RW | Stock Locate，复位值 8095 |
| `0x24/0x28` | RW | Stock 的低/高 32 位，复位值 `NVDA` 加四空格 |
| `0x30/0x34` | RW | 待提交序号的低/高 32 位 |
| `0x40`～`0x60` | RW | 36 字节消息，9 个 32 位字，按消息先后排列 |

消息的第一个字写成数值 `0x411f9f00`，表示前四个字节 `41 1f 9f 00`。PCIe 的寄存器访问采用小端 32 位读写；消息在核心中仍按网络字节顺序排列。这两件事由 wrapper 与 C 程序分别处理。

写地址和写数据可以不同拍到达；两者齐备才执行一次。B/R 响应在对端未接收时保持稳定。WSTRB 指定哪些字节生效；命令仅在低字节有效时触发。复位清空额度、计数、结果和未完成的总线请求。写入非法地址、组合命令或处理期间写寄存器，返回 SLVERR。结果保留到下一次提交；单一控制程序读取空闲状态后，序号的高低两次读取属于同一结果。

## 固定官方基础工程

本路线采用 **AMR 3.0 / Vivado 2026.1 / Alveo V80**，不沿用已经标为 obsolete 的 AVED。

- AMR 发布标签：`alveo_v80_gen5x8_26.1_20260609`，提交 `bb929d3ea60e67f952c59fde8514383f8648d60a`。
- 硬件工程：`Xilinx/amr_vivado_designs`，提交 `4b7d244758c683ec4c45f357e65511c25cff8f38`。
- 该硬件工程设置器件 `xcv80-lsva4737-2MHP-e-S`，板卡选择 `*:v80:*`，需要对应的 Vivado 2026.1 设备/板卡文件与许可。
- 完整固件构建还调用 `sdtgen`、`empyro`、`bootgen` 和 `$XILINX_VITIS/data/embeddedsw`。仅装 GCC 或 Vivado Lab Edition 不足以构建整套镜像。按 AMR 3.0 的开发环境准备对应版本的 AMD 工具；官方 V80 构建说明列出 64 GB 系统内存要求。

在 Ubuntu 开发机还需安装 `git build-essential cmake python3 lsb-release dpkg-dev pciutils unzip wget netcat-openbsd file` 和当前内核对应的 `linux-headers-$(uname -r)`。固定 AMR 总构建会编译 `ami.ko` 后再打包，开发机没有插卡也需要内核头文件；生成包不等于安装驱动。首次 JTAG 工具另需 `nc`（由 netcat-openbsd 提供）和 `file`。

```bash
git clone https://github.com/Xilinx/amr_vivado_designs.git
git -C amr_vivado_designs checkout 4b7d244758c683ec4c45f357e65511c25cff8f38
git clone --branch alveo_v80_gen5x8_26.1_20260609 https://github.com/Xilinx/amr.git
```

`build_filter.tcl` 在新目录复制官方 `v80_base`，保留器件、XDC、CPM/NoC 等配置，在 `config_bd.tcl` 之后插入本课模块。它拒绝错误的 Vivado 版本、其他硬件提交、被改动的基础工程和已存在的输出目录。

完成 AMD 工具环境初始化后，用实际绝对路径执行：

```bash
vivado -mode batch -source /绝对路径/v80/build_filter.tcl \
  -tclargs /绝对路径/amr_vivado_designs /绝对路径/build/flle_v80
```

上游脚本会运行 `write_device_image` 并导出 `build/flle_v80/project/v80_base.xsa`。**本课尚未运行 Vivado；必须检查模块接口推断、地址映射、DRC、时序和镜像产物，不能只凭 Tcl 文本宣称构建通过。** 这次替换沿用官方分段配置：启动镜像负责管理底座，PLD 镜像包含本课测试电路，两者必须配套。不能把 PLD 当成可加载到任意底座的文件。

## 从硬件设计到可启动镜像

在固定版本的 AMR 根目录，将本次 XSA 交给官方脚本：

```bash
./build.sh -xsa /绝对路径/build/flle_v80/project/v80_base.xsa -profile v80
```

提供 `-xsa` 后，上游脚本复用该硬件设计，再构建 AMC 固件与 AMI 软件。主要固件输出在调用目录的 `build_amc/`：`amc.elf`、`amr_ospi.bin`、`amr_ospi_fpt.bin`。其中：

- `amr_ospi.bin`：启动部分与 AMC 固件，用于已有兼容 AMR 分区表的启动分区更新；烧写它不等于本课 PL 电路已经加载。
- `*_pld.pdi`：同次 Vivado 实现生成的 PL 镜像，包含本课电路。构建脚本的 `project/flle_reports/artifacts.txt` 记录实际路径；不要凭空填写文件名。
- `amr_ospi_fpt.bin`：包含分区表的初始化镜像；不能当普通应用镜像随便写入某个分区。
- `pdi_program`：官方还提供运行时装载功能，但 PL 镜像要匹配当前底座的 Parent UUID。本课不通过跳过 UUID 检查来替代正确构建。

AMI 驱动、libami、ami_tool 的软件版本要和卡上 AMC 匹配；按同版 AMR 官方步骤安装。软件包构建有其 Linux/内核头文件与打包依赖，不能把“本地 C 程序已编译”当作这一步已完成。

## 有独立 V80 台架后的部署顺序

以下操作尚未执行。先确保卡已经按 AMR 3.0 的安装/恢复文档初始化，已有兼容 FPT 和可用回退镜像，再部署自定义启动镜像。

1. `ami_tool overview`、`lspci -Dnn -d 10ee:` 和 `ami_tool mfg_info -d "$PF0"` 核对同一块物理卡。PF0 的 ID 是 `10ee:50b4`；同槽 PF1 是 `10ee:50b5`。AMI 的 BDF 接口按 bus/device/function 定位；本路线限定 PCI domain `0000`，不把多 domain 下相同 BDF 当作已消歧。
2. 用 `ami_tool cfgmem_info -d "$PF0" -t primary` 读回当前分区表。变量 `BOOT_PART` 必须来自该输出中的、经确认可用的非活动启动分区；不能凭教材固定写 0 或 1。保留当前已验证启动镜像。
3. 将本次 `amr_ospi.bin` 传到台架主机，使用官方命令：

```bash
sudo ami_tool cfgmem_program -d "$PF0" -t primary \
  -i /绝对路径/amr_ospi.bin -p "$BOOT_PART" -q
sudo ami_tool device_boot -d "$PF0" -p "$BOOT_PART"
```

`-q` 让烧写与重启分开；第二条命令才切到新镜像。重启后重新枚举卡，不复用未经核对的旧 BDF。首次初始化、升级 FPT 和 JTAG 恢复按官方专门流程做，不包含在这两行中。

4. 从本次 Vivado 输出的 `project/flle_reports/artifacts.txt` 取出唯一 PLD 路径，将该文件一起传到台架。停止所有 PF1 访问，再用重新枚举得到的 PF0 装载：

```bash
sudo ami_tool pdi_program -d "$PF0" -i "$FLLE_PLD"
```

`FLLE_PLD` 必须指向与刚才启动镜像来自同次构建的实际 PLD 文件。核对工具显示的 Current UUID 与 Parent UUID；不一致就停止，重新核对构建配套关系，不能关闭检查。此步成功之后才查本课 APP_ID。运行时装入的 PL 在断电后不会凭这条命令自动恢复，本课台架每次重新启动后重复此装载步骤。

5. 确认 PF1 未绑定其他驱动、资源已分配且已启用。Linux 的 `enable` 文件是引用计数；确需启用独立测试 PF1 时才向它写 `1`，不能循环累加。课程工具检查这些条件，遇到未启用或已被驱动占用的 PF1 会退出，不自动解绑或启用。
6. 编译本课工具，然后使用重新枚举得到的**完整小写 BDF**（`dddd:bb:dd.1`）填写 `PF1`：

```bash
gcc -std=c11 -Wall -Wextra -Werror -O2 filter_mmio.c -o flle-v80-mmio
sudo ./flle-v80-mmio --device "$PF1" show
sudo ./flle-v80-mmio --device "$PF1" --write submit 646
sudo ./flle-v80-mmio --device "$PF1" --write arm
sudo ./flle-v80-mmio --device "$PF1" --write submit 647
sudo ./flle-v80-mmio --device "$PF1" --write submit 648
```

工具只映射 BAR2 中本课的 4 KiB；写寄存器前核对 APP_ID，并要求显式 `--write`。同一资源使用合作式文件锁，防止本工具的多个实例同时操作；它不会排除绕过该锁的其他程序，同时只运行一个控制程序。没有运行中的提交时，预期 646 放行、647 丢弃、648 放行，累计计数相对开始增加 2/1。这里的“丢弃”是核心返回一个判决，网口没有收到或丢掉任何行情。

**AMI 管理 PF0；本课工具访问 PF1。** 固定 AMR 驱动支持表不含 PF1 的 `50b5`，所以不能把 `ami_tool -d PF1 bar_rd/bar_wr` 写成默认可用的寄存器访问方式。`filter_mmio.c` 使用 Linux 文档公开的 `resourceN` mmap 接口；实际台架还需验证平台允许映射和访问，当前本地测试没有覆盖真实 PCIe。

## 官方依据与仍缺少的网口工程

- [AMR 3.0 发布与版本表](https://xilinx.github.io/amr-docs/docs/3.0.0/AMR-release-information.html)
- [V80 完整构建与部署](https://xilinx.github.io/amr-docs/docs/3.0.0/getting-started/build_v80.html)
- [固定硬件工程 config_bd.tcl](https://github.com/Xilinx/amr_vivado_designs/blob/4b7d244758c683ec4c45f357e65511c25cff8f38/alveo_v80/platforms/v80_base/scripts/config_bd.tcl)：PF1 GPIO、BAR2 与地址映射。
- [固定硬件工程 main.tcl](https://github.com/Xilinx/amr_vivado_designs/blob/4b7d244758c683ec4c45f357e65511c25cff8f38/alveo_v80/platforms/v80_base/scripts/main.tcl)：器件、XDC、分段配置和 XSA 导出。
- [固定 AMI PCI ID 支持表](https://github.com/Xilinx/amr/blob/bb929d3ea60e67f952c59fde8514383f8648d60a/sw/AMI/driver/ami_pcie.c)及 [probe](https://github.com/Xilinx/amr/blob/bb929d3ea60e67f952c59fde8514383f8648d60a/sw/AMI/driver/ami_top.c)。
- [AMD 2026.1 分段配置](https://docs.amd.com/r/en-US/ug1273-versal-acap-design/Segmented-Configuration)：`write_device_image` 将启动部分与 PL 分成两个 PDI。
- [Linux PCI sysfs](https://www.kernel.org/doc/html/latest/PCI/sysfs-pci.html)：身份、enable 和 resourceN 的公开接口。

该 V80 基础工程未实例化 Ethernet，QSFP 与参考时钟端口仍为注释。仓库的 `eth_10g` 例程属于 VE2302，不是 V80。要做真正的网口行情过滤，还需 V80 对应的 MAC/PCS、收发器/时钟、报文解析与缓冲、以及通往主机的数据通道；本目录没有把这些缺失部分伪装成已经实现的 NIC。
