# EOS 管理示例：7135V / BVL

这份代码负责装载镜像、查看状态和发出一次丢包额度。过滤 RTL 已有本地测试；本目录的管理逻辑也通过本地测试，尚未在 EOS 或 7135V 上运行。

## 文件分工

| 文件 | 做什么 |
| --- | --- |
| `FlleFilter.yaml` | 声明本课的命令和后台程序，交给 EOS 注册 |
| `FlleFilterCli.py` | 处理命令；启停写入配置，一次额度通过临时 RPC 发出 |
| `FlleFilterDaemon.py` | EOSSDK 后台程序；由 EOS 的 `arista-python` 启动，找到 BVL FPGA，装载 PDI，发布状态 |
| `filter_control.py` | 等待镜像就绪、核对应用 ID、读写寄存器 |
| `filter_rpc.py` | 拒绝过期请求、旧启动会话和重复执行 |
| `../package_eos.mk` | 把现成 PDI、管理代码和配套库打成 EOS 扩展包 |
| `../test_eos_control.py` | 使用真实 OpenFDK CSV 解析器和模拟硬件测试管理逻辑 |

EOS 管理骨架来自 Arista OpenFDK `nullverilog/src/eos`，固定提交 `13a7aac5b0aaba1ed7bbeb04dd71c5b3bded6d9d`。RPC 调用依据 [EOS SDK 官方接口](https://github.com/aristanetworks/EosSdk/blob/a66f65bb4674fefa5a9312ee1e5fd6895f2810b2/eos/agent.h#L123-L134)。命令名与过滤逻辑由本课编写。

## 准备好板级工程后打包

先由配套 BVL FDK 工程生成、检查真实 `.pdi`，同时提供与该镜像实际 MAC/PHY 匹配的端口定义 JSON。该步骤还需要相应许可和板级适配；公开 OpenFDK 的旧 `vivado.mk` 不能构建 BVL 镜像。

进入本资产目录，使用已经核对过的具体 EOS 版本打包：

```bash
cd Documents/newDoc/assets/08-arista-fpga-draft
make -f package_eos.mk \
  ARISTA_FDK_DIR="$BVL_FDK_DIR" \
  PDI_FILE="$BVL_PDI_FILE" \
  PORT_DEF_FILE="$BVL_PORT_DEF_FILE" \
  EOS_VERSION="$BVL_EOS_VERSION"
```

四个变量分别指向配套 FDK 目录、真实 PDI、端口 JSON 和已核对的 EOS 版本。前三项使用绝对路径；`EOS_VERSION` 必填，不能把最低支持版本当成所有机器的实际版本。

完整 SWIX 打包使用对应 FDK 规定、并验证过的 Linux 打包环境。上游 `app.mk` 调用 `rpmbuild -ba`，其 spec 要求 RPM 数据库中的 `python3-devel`；Ubuntu 用 apt 安装 `python3-dev` 不等于满足这项依赖。不要用 `--nodeps` 绕过检查。本次只验证了文件暂存及 tar 清单，尚未验证 RPM / SWIX 构建环境。

预期产物是 `flle_filter-0.2.0.swix`。这个 Makefile **只打包，不综合 RTL**；填入版本号只限定安装目标，也不等于该组合已经通过设备测试。

同一打包目录支持再次运行；模板只清理本应用暂存目录内、目标匹配的 CLI 符号链接，再重建打包清单，不删除设备或其他应用的文件。

安装后，文件位于 `/opt/apps/flle_filter/`；镜像固定为 `fpga/flle_filter-bvl.pdi`，端口定义为 `fpga/flle_filter-bvl-ports.json`，寄存器映射为 `fpga/flle_filter_registers.csv`。

## 安装与操作

把 SWIX 复制到设备的 `/mnt/flash/` 后，在 EOS 中执行：

```text
copy flash:flle_filter-0.2.0.swix extension:
extension flle_filter-0.2.0.swix
```

扩展注册会结束当前 CLI 会话，重新登录后检查 `show extensions`。这是 [OpenFDK 官方安装流程](https://github.com/aristanetworks/openfdk/blob/13a7aac5b0aaba1ed7bbeb04dd71c5b3bded6d9d/examples/telemexample/quickstart.md#eos-installation)。然后启动本课应用：

```text
configure terminal
flle_filter
   no disabled
end
show flle_filter status
show flle_filter counters
```

只有 `Running: Yes` 才接受控制命令。进入 `flle_filter` 子模式后，`arm once` 授予一次额度，`disarm` 撤销额度，`disabled` 停止应用。停止前先恢复隔离台架的外部旁路。

`arm once` 不写入 running-config；重启应用始终从关闭过滤开始。镜像装载与额度操作是两件事，授予额度不会重新构建或装载 PDI。

## 本地验证与保证范围

完成正文1.3后，在`.101`执行；固定公开测试依赖已随源码复制，完整测试日志由正文3.3保存。

```bash
source /opt/flle-ch08-dev/current.env
"$FLLE_DEV/venv/bin/python" -B "$FLLE_CORE/test_eos_control.py" \
  "$FLLE_CORE/test-support/openfdk"
```

本地测试检查就绪条件、ID 校验、额度操作、重启、重复/过期 RPC、错误返回和序号读数，并调用真实上游 `StatusAccessor` / `status_as_dict` 核对 CLI 状态接口。它们不执行 EOSSDK，也不验证实际 I²C、时钟跨域或 FPGA 装载。

控制写绕过 `RegisterFile.write_reg` 的自动重试，只调用一次 `communicator.write_reg`。公开 OpenFDK 的 `RegisterAccessor → EosRegAccess → PLSmbusUtil.write` 路径未再写显式重试；EOS 内部的 `PLSmbusUtil` 与硬件总线仍须上板验证。因此，这里保证的是**本课软件不自动重复请求**，不是已经证明物理总线绝不重发。

一次写回执丢失后，程序报告结果未知并停止接受控制，不自行再次授予额度。此时仍能运行不访问硬件的 `show flle_filter status`；先恢复外部旁路，再在应用子模式执行 `disabled` / `no disabled`，不要重发 `arm once`。多项活动计数是逐次采样；仅在额度关闭且读前后丢包计数不变时输出完整序号。
