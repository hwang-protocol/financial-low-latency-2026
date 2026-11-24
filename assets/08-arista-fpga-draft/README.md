# 第08章 Arista FPGA 推演稿配套

状态：DRAFT · 2026-09-18。现役正文：[第08章：FPGA——从过滤代码到板卡与交换机](../../08-fpga-from-code-to-device.md)。旧交换机稿与原 P4 正文不在本仓库；课堂以现役第08章为准。

本目录保留完整交换机参考实现和旧实验入口；下文涉及离线脚本、绿卡与 `.101` 的执行说明对应归档稿。现役第08章使用本目录源码解释交换机适配，课堂操作以正式正文为准。

本目录提供真实 SystemVerilog 核心、测试环境和按 Arista EOS API 编写的管理示例（7135V / BVL / PDI）。课堂第1、3步的绿卡在可恢复快照的 `.101` 安装工具、编译、仿真和通用综合；`.111` 只保留与分发材料、回收结果。核心和管理代码可离线测试，完整板级应用尚未构建或验证。

## 文件分工

| 文件 | 行数 | 职责 |
| --- | ---: | --- |
| [nvda_match.sv](nvda_match.sv) | 38 | 固定封装匹配与 64 位序号提取；不校验 IP/UDP checksum。 |
| [drop_once.sv](drop_once.sv) | 33 | 一次额度、控制优先级、丢包计数和序号锁存。 |
| [frame_filter.sv](frame_filter.sv) | 116 | 完整帧缓存、错误处置、裁决、按 valid/ready 输出。 |
| [control_regs.sv](control_regs.sv) | 36 | 同步于报文时钟的寄存器读写与一拍命令脉冲。 |
| [flle_filter_registers.csv](flle_filter_registers.csv) | 10 | FDK RegisterFile 的名称/编号映射。 |
| `eos/` | — | EOS 管理代码及说明：启停、PDI 装载、临时 RPC、计数查询；未在 EOS 上运行。 |
| `packaging/app-settings.mk` | — | 现役课程的声明式应用清单，直接配合厂商 app.mk；无自写执行步骤。 |
| `package_eos.mk` | — | 旧打包辅助入口，保留追溯，现役正文不再调用。 |
| `test_eos_control.py` | — | 本地管理逻辑测试，真实上游 CSV 解析器配模拟硬件。 |
| `test-support/openfdk/` | — | 固定公开提交的三份测试依赖及许可，不是完整BVL开发包。 |
| `classroom/` | — | 与正文绿卡逐字相同的短操作入口：分发、安装、编译、运行、综合和收回结果。 |
| [filter_tb.sv](filter_tb.sv) | 149 | 22 帧功能用例、逐字节比对、错误与额度/寄存器检查。 |
| [simulate.sh](simulate.sh) | 15 | 在临时目录调用 Icarus，结束自动删除本地构建产物。 |

## 本地复核

维护者在安装 Icarus Verilog 的开发机、仓库根目录执行：

```bash
bash assets/08-arista-fpga-draft/simulate.sh
```

核验版本为 Icarus Verilog 11.0。脚本接受 `IVERILOG` / `VVP` 指定工具路径；非标准解包安装还可用 `IVERILOG_IVL_DIR` 指定内部工具目录。这些不是课堂设备依赖。

实际 stdout：

```text
cases=22 forwarded=17 policy_drop=2 error_discard=3
byte_preservation=PASS one_shot=PASS backpressure=PASS registers=PASS
functional_simulation=PASS hardware_implementation=NOT_RUN
```

计数为 22 帧，不是穷举所有输入。测试分别覆盖禁丢、非目标不消耗额度、连续目标、各类字段不匹配、输出等待时稳定、MAC 错误标志、非法 keep、2048/2049 字节边界、输入间隔、撤销额度、disarm 优先和 64 位序号读回。输入是人工构造的核心接口数据，未提供有效 IP checksum/FCS；本课核心不负责这两层校验。

另外用独立副本故意破坏两处逻辑：丢弃后不清额度、转发首字节变化。两个反例均被测试拒绝。采用真实上游 `register_file.py`，配内存读写后端，检查了 CSV 名称/编号、只读保护和高低 32 位拼接；没有将本地结果当作 EOS 或 FPGA 通信验证。

Icarus 对 `always_comb` 内常量切片给出保守敏感集合提示；结果与 stderr 一并记入证据，不把提示抹掉。证据：[本轮核验索引](../../refs/evidence/ch08-arista-fpga-draft-20260917.json)。

## 从 .101 快照开始的课堂路线

`.101` 的起点为本课Ubuntu22.04/amd64基础快照，具备管理SSH、Python3/venv、tar和基础库；Icarus、pip和YoWASP由正文绿卡离线安装。缓存保留在 `.111`，详见[缓存清单与来源](../../artifacts/ch08-fpga-dev-cache.md)。不要把这份缓存当作任意空白发行版的完整依赖闭包。

全部绿色卡在 `.111` 执行，由脚本自动SSH到 `.101`：1.1分发并准备共享工具，1.2检查，1.3安装；3.1—3.5分别编译、仿真、管理测试和通用综合。每一步停下供讲解，日志与失败退出码自动保留。入口和路径说明见[classroom/README.md](classroom/README.md)。

从头重做时，直接恢复 `.101` 快照并从1.1开始，脚本自动新建工作目录和分发材料。每步结果已自动回存；连续学习第九章则保留环境。正文仅保留两处短源码，完整讲解在[选读附录](RTL-WALKTHROUGH.md)。

`.101`的22帧仿真、16项管理测试、两项通用综合与自动SSH入口核验见 `refs/evidence/ch08-auto-ssh-and-deployment-focus-20260918.json`（仓库根目录起算）。通用网表仍无VH1542映射、布线和时序结果，PDI/SWIX及真机未验证。[工具补充](ADVANCED-TOOLS.md)保留XSim和板级打包前提。

## 板级接入合同

这里的顶层接口是教学核心接口，不是声称所有厂商 MAC 都使用相同接口。真机工程必须完成以下连接：

| 接入层 | 明确要求 |
| --- | --- |
| RX MAC/PCS | 帧字节不含前导码与 FCS；最早字节在低 8 位；错误随当前帧标记；适配 Ethernet IP 的真实接口 |
| 接收队列 | 在 RX MAC 与核心之间；支持核心暂不接收时缓存；队列溢出按整帧处置并单独计数；不能靠 s_ready 停止线缆来流 |
| 流接口 | 每拍最多 8 字节；本核心要求非末拍 keep=ff，末拍 keep 非零且从最低位连续有效；上升沿 valid && ready 才交付；valid=1、ready=0 时保持 valid 及数据/边界/错误标记。s_error 是本课附加信号，不是 AXIS 必选脚 |
| 时钟/复位 | 核心同步高有效复位；解除复位与核心时钟同步；不同域之间采用有确认的请求和一致的读回，不直接跨域传单拍命令 |
| 寄存器 | 本课编号是 word index；板级总线负责对应到编号，不凭 byte address 猜偏移；每次已接收写事务只给一拍 wr_en |
| TX MAC/PCS | 保证完整帧、正确字节顺序、FCS 和帧间隔；匹配所选 IP 的时钟/流控要求 |
| BVL 工程 | 由对应7135V的完整FDK提供实际顶层、器件启动模块与约束；连接四份RTL，提供PDI及匹配端口定义，EOS包包含管理代码/CSV/libapp |

单缓冲核心最多保存 2048 字节（不含 FCS）。更大帧、错误标志或非法 keep 按错误丢弃，不消费策略额度；其他完整帧按原字节放行。接收与发送分阶段，**此实现没有持续 25G 线速保证**；有限队列只能吸收短时突发。RTL 数组没有承诺映射成 BRAM，资源和时序需看 Vivado 结果。

`app_id=0x464c4c45` 是本课标识，不是 Arista 通用寄存器。命令写 1 arm、写 2 disarm，写 3 按 disarm 优先；反复 arm 设置同一个一位额度，不累加。控制与裁决同拍时先处理控制，本帧不消耗额度；无复位/命令/命中时保持状态。计数器为 32 位回绕值，最后序号为 64 位。

本目录未交付 MAC/PCS IP、板级 top/XDC/CDC 适配或可装载 `.pdi/.swix`。正文构建卡的前提是这些适配已完成。取得设备和完整开发材料后，还须走 XSim、Vivado 综合/实现/DRC/CDC/时序、原样转发、一次丢弃、错误与突发验证。所有结果到时另行登记，不能把本轮功能仿真升级为上板结论。

## 2026-09-17 新平台迁移验证

主线为 DCS-7135V-48Y-4QC / VH1542 / BVL / EOS。四份核心RTL、CSV与测试环境保持，重新执行Icarus：22帧、17转发、2策略丢弃、3错误丢弃，全部检查通过。此前Yosys通用综合证据继续有效，本轮未重跑。

EOS管理逻辑的16项本地测试通过：等待装载状态、标识校验、启动禁丢、临时额度、重启、重复与过期请求、写回执丢失、稳定序号读取。测试使用真实OpenFDK寄存器/状态解析代码和本课CLI处理函数，设备及命令上下文为模拟对象；没有执行EOS系统或EOSSDK。具体命令和文件职责见 `eos/README.md`。

打包规则已用真实GNU Make验证暂存清单与权限；输入明确是测试占位文件，未生成真实PDI、RPM或SWIX。完整BVL工程、授权网口IP和对应Vivado版本仍需厂商交付；本机未取得该包，未运行Vivado/XSim或7135V实机验证。

本轮记录在 `refs/evidence/ch08-modern-eos-20260917.json`。不要把应用管理框架支持新设备解释为完整板级设计已经完成，也不要把通用网表当作PDI。

## 来源与许可

逐项依据在 `SOURCE-REVIEW.md`。EOS生命周期与CLI接入基于Arista OpenFDK EOS示例，保留BSD-3-Clause许可和版权说明；临时RPC依据EOS SDK公开接口。本课未复制或再分发闭源BVL工程/IP。经典案例仍按原部署年代讲解，不当作7135V部署证据。
