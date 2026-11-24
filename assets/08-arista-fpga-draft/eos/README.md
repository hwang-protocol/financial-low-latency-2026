# EOS 管理示例：7135V / BVL

这份代码负责装载镜像、查看状态和发出一次丢包额度。过滤 RTL 已有本地测试；本目录的管理逻辑也通过本地测试，尚未在 EOS 或 7135V 上运行。

正式课程的获取材料、打包、上传、EOS 装载与逐帧验收步骤见[第08章4.2～4.5](../../../08-fpga-from-code-to-device.md#step-4-2)。

## 文件分工

| 文件 | 做什么 |
| --- | --- |
| `FlleFilter.yaml` | 声明本课的命令和后台程序，交给 EOS 注册 |
| `FlleFilterCli.py` | 处理命令；启停写入配置，一次额度通过临时 RPC 发出 |
| `FlleFilterDaemon.py` | EOSSDK 后台程序；由 EOS 的 `arista-python` 启动，找到 BVL FPGA，装载 PDI，发布状态 |
| `filter_control.py` | 等待镜像就绪、核对应用 ID、读写寄存器 |
| `filter_rpc.py` | 拒绝过期请求、旧启动会话和重复执行 |
| `../packaging/app-settings.mk` | 声明应用文件与名称；与厂商 app.mk 一起读取，分步制作 RPM 和 SWIX |
| `../package_eos.mk` | 旧打包辅助入口，仅保留追溯 |
| `../test_eos_control.py` | 使用真实 OpenFDK CSV 解析器和模拟硬件测试管理逻辑 |

EOS 管理骨架来自 Arista OpenFDK `nullverilog/src/eos`，固定提交 `13a7aac5b0aaba1ed7bbeb04dd71c5b3bded6d9d`。RPC 调用依据 [EOS SDK 官方接口](https://github.com/aristanetworks/EosSdk/blob/a66f65bb4674fefa5a9312ee1e5fd6895f2810b2/eos/agent.h#L123-L134)。命令名与过滤逻辑由本课编写。

## 准备好板级工程后打包

现役课程使用[声明式应用清单](../packaging/app-settings.mk)，直接调用完整 FDK 原有的 `resources/app.mk` 和 `resources/rpm.spec`，先生成 RPM 与 manifest，再手动运行 Arista `swi-tools create` 生成 SWIX。目录、下载入口、每条命令及产物见[第08章4.3](../../../08-fpga-from-code-to-device.md#step-4-3)。清单适用公开 OpenFDK 3.2.0 接口；完整 BVL FDK 的版本兼容、板级适配、PDI、RPM/SWIX 与 EOS 装载仍需在实际环境中核对。

`../package_eos.mk` 是此前的课程打包辅助入口，包含自写的文件暂存与清理步骤，保留供追溯；现役正文不再调用它。不得将它标为厂商原生工具。

完整打包需使用 FDK 规定的 Linux 环境。官方 spec 要求 RPM 数据库中的 `python3-devel`；Ubuntu 用 apt 安装 `python3-dev` 不等于满足这项依赖，不用 `--nodeps` 绕过。新清单只检查了声明、文件覆盖和 `make -n` 计划，没有执行 RPM/SWIX 构建。

安装后文件位于 `/opt/apps/flle_filter/`；镜像为 `fpga/flle_filter-bvl.pdi`，端口定义为 `fpga/flle_filter-bvl-ports.json`，寄存器映射为 `fpga/flle_filter_registers.csv`。这些是应用约定路径，按匹配镜像与完整 FDK 验证。

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

以下是归档旧稿配套的本地逻辑验证入口，依赖旧稿1.3建立的 `.111` / `.101` 环境；不属于现役第08章的 GUI 操作主线。保留用于追溯既有测试，日志由原流程收回。

```bash
bash /qyt-fll/assets/08-arista-fpga-draft/classroom/3.3-management.sh
```

本地测试检查就绪条件、ID 校验、额度操作、重启、重复/过期 RPC、错误返回和序号读数，并调用真实上游 `StatusAccessor` / `status_as_dict` 核对 CLI 状态接口。它们不执行 EOSSDK，也不验证实际 I²C、时钟跨域或 FPGA 装载。

控制写绕过 `RegisterFile.write_reg` 的自动重试，只调用一次 `communicator.write_reg`。公开 OpenFDK 的 `RegisterAccessor → EosRegAccess → PLSmbusUtil.write` 路径未再写显式重试；EOS 内部的 `PLSmbusUtil` 与硬件总线仍须上板验证。因此，这里保证的是**本课软件不自动重复请求**，不是已经证明物理总线绝不重发。

一次写回执丢失后，程序报告结果未知并停止接受控制，不自行再次授予额度。此时仍能运行不访问硬件的 `show flle_filter status`；先恢复外部旁路，再在应用子模式执行 `disabled` / `no disabled`，不要重发 `arm once`。多项活动计数是逐次采样；仅在额度关闭且读前后丢包计数不变时输出完整序号。
