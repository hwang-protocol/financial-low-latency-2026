# 第08章工具补充：通用综合与 XSim

[返回正文](../../08-arista-fpga-market-filter-draft.md)。正文保留 Icarus 的安装、编译与运行；本页逐步展开第二条验证路线和打包依赖，所有命令仍是紫色展示。

开始前，沿用正文②设置的 `FLLE_DEV=/opt/flle-fpga-tools` 和 `FLLE_CORE=/financial-low-latency/Documents/newDoc/assets/08-arista-fpga-draft`，在同一 Linux 终端操作。另开终端时，先重新执行正文②的定位命令。工具与源码目录必须已存在，Python 3、curl 可用。

本页的 YoWASP 安装与两项综合已在本机完成；XSim 和完整 FDK 构建未执行。通用网表描述逻辑连接，不能直接装进7135V。

## 安装 YoWASP Yosys

### 建立独立 Python 环境

YoWASP 将 Yosys 打包为 WebAssembly 程序，由 Python 环境启动；Python 管理代码不会因此编入 FPGA。[YoWASP](https://yowasp.org/)、[发行包](https://pypi.org/project/yowasp-yosys/)

用 `venv --without-pip` 建独立环境，绕过系统缺少 ensurepip 的问题；随后从 PyPA 取得引导程序，安装 pip。

<div style="border-left:6px solid #7e22ce;background:#f3e8ff;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#7e22ce;color:#fff;font-weight:800;">仅供展示 · Linux 创建工具环境并安装 pip</span> <span style="font-weight:700;color:#581c87;">下载文件保存在工具目录；随后明确使用虚拟环境内的 Python 执行。</span></div>

```bash
python3 -m venv --without-pip "$FLLE_DEV/venv"
curl -fL https://bootstrap.pypa.io/get-pip.py -o "$FLLE_DEV/get-pip.py"
"$FLLE_DEV/venv/bin/python" "$FLLE_DEV/get-pip.py" 'pip==25.2'
```

三行依次建环境、下载安装程序、在环境内安装 pip，系统 Python 包保持独立。[pip 官方入口](https://pip.pypa.io/en/stable/installation/)

### 安装并检查 Yosys

配套 `local-tools-requirements.txt` 锁定 `yowasp-yosys==0.69.0.0.post1233` 和依赖，pip 从 PyPI 下载。

<div style="border-left:6px solid #7e22ce;background:#f3e8ff;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#7e22ce;color:#fff;font-weight:800;">仅供展示 · Linux 安装固定版本综合工具</span> <span style="font-weight:700;color:#581c87;">同一独立环境内安装依赖，再调用 yowasp-yosys 查看版本。首次启动会准备运行缓存。</span></div>

```bash
"$FLLE_DEV/venv/bin/python" -m pip install   --index-url https://pypi.org/simple -r "$FLLE_CORE/local-tools-requirements.txt"
"$FLLE_DEV/venv/bin/yowasp-yosys" -V
```

本机读回 Yosys 0.69；下面用它生成通用网表。

## 把 RTL 综合成通用网表

Yosys 将 RTL 转为逻辑单元及连接，输出 JSON 网表；综合不加入测试环境 `filter_tb.sv`。

本例让 YoWASP 从工作目录访问文件：复制四份 RTL，输入和输出均用相对路径。

<div style="border-left:6px solid #7e22ce;background:#f3e8ff;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#7e22ce;color:#fff;font-weight:800;">仅供展示 · Linux 准备综合目录</span> <span style="font-weight:700;color:#581c87;">复制的是构建输入；源文件名保持，生成网表不会覆盖仓库源码。</span></div>

```bash
mkdir -p "$FLLE_DEV/work/core-synthesis"
cp "$FLLE_CORE/nvda_match.sv" "$FLLE_CORE/drop_once.sv"   "$FLLE_CORE/frame_filter.sv" "$FLLE_CORE/control_regs.sv"   "$FLLE_DEV/work/core-synthesis/"
cd "$FLLE_DEV/work/core-synthesis"
```

<div style="border-left:6px solid #7e22ce;background:#f3e8ff;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#7e22ce;color:#fff;font-weight:800;">仅供展示 · Linux 综合过滤数据通路</span> <span style="font-weight:700;color:#581c87;">顶层 frame_filter 会实例化 matcher 与一次额度逻辑；完整日志写入文件。</span></div>

```bash
"$FLLE_DEV/venv/bin/yowasp-yosys" -Q -T -p '
  read_verilog -sv nvda_match.sv drop_once.sv frame_filter.sv;
  synth -top frame_filter -noabc;
  check -assert;
  stat;
  write_json frame-filter-netlist.json
' > frame-filter-synthesis.log 2>&1
```

| 命令 | 对这份源码做什么 |
| --- | --- |
| `read_verilog -sv` | 读取 SystemVerilog 模块 |
| `synth -top frame_filter -noabc` | 以过滤器为顶层执行通用综合；不调用 ABC 门级映射步骤 |
| `check -assert` | 检查连接等结构问题；发现问题就返回失败 |
| `stat` | 打印综合后模块、连线与逻辑单元统计 |
| `write_json` | 将逻辑网表写成文件；这个 JSON 不是 FPGA 配置镜像 |

`-Q -T` 省略横幅与结束统计，`-p` 执行命令串，`> ... 2>&1` 保存完整日志，保留失败状态。

控制寄存器是独立模块，再以它为顶层检查一次：

<div style="border-left:6px solid #7e22ce;background:#f3e8ff;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#7e22ce;color:#fff;font-weight:800;">仅供展示 · Linux 综合控制寄存器</span> <span style="font-weight:700;color:#581c87;">与过滤数据通路分开生成第二份网表；板级工程最终把两者接在一起。</span></div>

```bash
"$FLLE_DEV/venv/bin/yowasp-yosys" -Q -T -p '
  read_verilog -sv control_regs.sv;
  synth -top control_regs -noabc;
  check -assert;
  stat;
  write_json control-regs-netlist.json
' > control-regs-synthesis.log 2>&1
```

<div style="border-left:6px solid #7e22ce;background:#f3e8ff;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#7e22ce;color:#fff;font-weight:800;">仅供展示 · Linux 查看综合结果</span> <span style="font-weight:700;color:#581c87;">读取刚才生成的日志，查看结构检查，并确认两份网表已经写出。</span></div>

```bash
rg 'Found and reported|ERROR|Warning' *-synthesis.log
ls -lh frame-filter-netlist.json control-regs-netlist.json
```

两次综合退出0，均报 `Found and reported 0 problems.`，两份网表已生成。它们尚无 VH1542 的映射、布线和时序结果，通用单元数不等于 FPGA LUT 用量。

## 用 XSim 运行同一测试

XSim 中 `xvlog` 编译、`xelab` 展开顶层、`xsim` 运行；本轮未执行这组命令。[AMD 批处理仿真](https://docs.amd.com/r/2026.1-English/ug900-vivado-logic-simulation/Running-the-Vivado-Simulator-in-Batch-Mode)

<div style="border-left:6px solid #7e22ce;background:#f3e8ff;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#7e22ce;color:#fff;font-weight:800;">仅供展示 · Vivado 开发环境中的 XSim 命令</span> <span style="font-weight:700;color:#581c87;">先加载正文②介绍的 settings64.sh；本轮未执行 XSim，已执行的是 Icarus 与 Yosys。</span></div>

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
