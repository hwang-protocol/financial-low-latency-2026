# 第08章工具补充：XSim 与板级打包前提

[返回正文](../../08-fpga-from-code-to-device.md)。Icarus与YoWASP离线安装、仿真和通用综合已移到正文第1/3步的真实绿卡；不再要求在`.111`创建开发环境。固定包和来源见[离线缓存说明](../../artifacts/ch08-fpga-dev-cache.md)。

后续需要Vivado时，在`.101`开发终端加载本轮`/opt/flle-ch08-dev/current.env`及实际Vivado安装目录的`settings64.sh`；下列命令以已取得匹配BVL开发包、安装对应工具为前提，仍是紫色展示。

## 用 XSim 运行同一测试

XSim 中 `xvlog` 编译、`xelab` 展开顶层、`xsim` 运行；本轮未执行这组命令。[AMD 批处理仿真](https://docs.amd.com/r/2026.1-English/ug900-vivado-logic-simulation/Running-the-Vivado-Simulator-in-Batch-Mode)

<div style="border-left:6px solid #7e22ce;background:#f3e8ff;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#7e22ce;color:#fff;font-weight:800;">仅供展示 · Vivado 开发环境中的 XSim 命令</span> <span style="font-weight:700;color:#581c87;">先加载正文第1步介绍的 settings64.sh；本轮未执行 XSim，已执行的是 Icarus 与 Yosys。</span></div>

```bash
mkdir -p "$FLLE_DEV/work/xsim"
cd "$FLLE_DEV/work/xsim"
xvlog -sv "$FLLE_CORE/nvda_match.sv" "$FLLE_CORE/drop_once.sv"   "$FLLE_CORE/frame_filter.sv" "$FLLE_CORE/control_regs.sv"   "$FLLE_CORE/filter_tb.sv"
xelab filter_tb -s filter_sim
xsim filter_sim -runall
```

## FDK 构建与打包工具

完整SWIX打包使用配套FDK规定的Linux环境；前面的Ubuntu本地仿真环境不等于已配好打包环境。系统工具来自该发行版软件包源，Python依赖按FDK规则安装：

| 工具 | FDK 中的用途 |
| --- | --- |
| GNU Make、Bash、`jq` | 执行构建规则，读取 JSON 源文件清单 |
| `rpmbuild` | 将镜像、管理代码和依赖打成 RPM |
| Python 3、venv、pip | 建立隔离的打包环境，安装构建规则指定的 Python 依赖 |
| `switools` | 根据 FDK 打包规则生成 `.swix` |

本课 `package_eos.mk` 引用公开 `app.mk` 的打包规则（含 `switools==1.2` 等依赖）；这是软件打包，不能用于 BVL 硬件构建。具体用法见同目录 `eos/README.md`，与交付的 BVL 包核对后使用。[app.mk](https://github.com/aristanetworks/openfdk/blob/13a7aac5b0aaba1ed7bbeb04dd71c5b3bded6d9d/resources/app.mk)

公开 `rpm.spec` 还要求 RPM 数据库中的 `python3-devel`。Ubuntu 的 `python3-dev` 是另一套包管理记录，不能只装同类 apt 包就声称满足该构建条件。本轮验证到文件暂存；RPM/SWIX 完整构建未执行，不用 `--nodeps` 跳过要求。
