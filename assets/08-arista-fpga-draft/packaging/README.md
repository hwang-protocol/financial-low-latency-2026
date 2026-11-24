# 分步调用官方打包工具

课堂入口：[第08章4.3](../../../08-fpga-from-code-to-device.md#step-4-3)。

本目录只交付 `app-settings.mk` 声明式应用清单，以及 `__init__.py` 应用包标识文件。按正文复制到准备目录：前者放 `app/`，后者放 `app/src/`。业务与管理源码、PDI、端口 JSON、寄存器表按正文目录准备。

`make` 依次读取课程清单和未经修改的厂商 `resources/app.mk`。文件复制、权限设置、CLI 注册链接、源码归档、RPM 制作和 manifest 生成使用厂商规则；清单自身没有 recipe、`$(shell ...)` 或部署步骤。先只生成 RPM 与 manifest，再由操作者单独执行 `swi-tools create`，最后上传并通过 EOS 安装、启用。

清单按公开 OpenFDK 3.2.0 固定提交 `13a7aac5b0aaba1ed7bbeb04dd71c5b3bded6d9d` 的结构准备。它列入该版本 `libapp` 下 Python、PCIe 库、调谐 CSV 和时钟配置，共58份文件；完整 BVL FDK 若调整目录，应依交付版本核对文件清单。`RPMBUILD` 仅给原生 `rpmbuild` 补充厂商 spec 需要的摘要字段，spec 保持原样。`DRIVER_REGS` 置空，因为寄存器 CSV 已显式放入 `src/fpga/`。

这份文件包含应用清单和必要的构建设置，并非只有文件名变量：`.SECONDEXPANSION` 支持厂商规则中 `$$(@D)` 等延后展开的依赖；`override RPMBUILD` 避免后读的厂商赋值覆盖摘要参数。保留两项是为了直接使用原样 `app.mk` 与 `rpm.spec`，不增加课程执行步骤。本轮顺稿保持设置文件原样，未重新打包。

本轮仅检查声明格式、文件覆盖及官方规则的 `make -n` 文件准备计划，未执行 RPM/SWIX 构建或设备操作。完整 BVL FDK、板级适配、支持的 Linux/EOS 版本及实际镜像仍是执行前提。旧 `../package_eos.mk` 不属于现役主线，保留追溯。

来源：[官方应用规则](https://github.com/aristanetworks/openfdk/blob/13a7aac5b0aaba1ed7bbeb04dd71c5b3bded6d9d/resources/app.mk)、[官方 SWIX 工具](https://github.com/aristanetworks/swi-tools)。
