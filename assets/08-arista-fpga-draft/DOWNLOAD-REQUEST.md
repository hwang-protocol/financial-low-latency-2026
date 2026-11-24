# 第八章 FPGA 开发材料：下载 URL 与协助清单

核对日期：2026-09-18。用途：转发给协助获取开发材料的同事。

目标设备：**Arista DCS-7135V-48Y-4QC**；板级标识：**BVL**；目标芯片：**AMD Versal HBM VH1542**。

请先取得 Arista 完整开发包的版本说明，再按其中要求准备 Vivado。下面给出的 AMD 文件链接对应 **2026.1**，用于明确下载入口；课程最终采用开发包指定的版本。

## 1. Arista：取得 BVL 完整 FPGA 开发包

官方软件下载门户：

```text
https://www.arista.com/en/support/software-download
```

这是[OpenFDK官方README](https://github.com/aristanetworks/openfdk/blob/13a7aac5b0aaba1ed7bbeb04dd71c5b3bded6d9d/README.md)给出的通用门户入口，**尚未核实7135V / BVL完整包在其中的具体目录、文件名或下载链接**。2026-09-18用户确认协助者进入门户后未找到指定材料，截图未显示7130/7135V或FDK条目；仅凭截图不能确定是账号授权范围还是材料分发入口的原因。

**现在请先向Arista支持或供应商确认包名、获取入口和授权条件。** 可联系 `support@arista.com`（[7135V数据表末页](https://www.arista.com/assets/data/pdf/Datasheets/7135V-Datasheet.pdf#page=10)）；OpenFDK源码还列有维护联系地址 `fdk-support@arista.com`（[device.py文件头](https://github.com/aristanetworks/openfdk/blob/13a7aac5b0aaba1ed7bbeb04dd71c5b3bded6d9d/resources/libapp/device.py#L1-L7)）。本清单只提供联系信息，未替用户发送邮件。

型号核对：数据表第5页的 **FPGA** 一行写明 **AMD Versal HBM VH1542**，**FPGA Development Kit (FDK)** 一行为 **Yes**。这确认硬件型号及FDK支持；实际下载所需的是该板卡的开发工程。截图中的EOS、EOS SDK、AI Agent和编辑器插件，各有自己的用途，不能据其存在判断已取得BVL板级工程。

需要取得：

- 7135V / BVL 的完整 FPGA 开发包（FDK），包括板级参考工程和构建说明。
- 配套 EOS、Vivado 的版本要求，以及精确器件型号、引脚和时钟约束。
- 网口模块（IP）的依赖与许可要求，以及所需 Vivado 许可说明。
- 生成 `.pdi`、打包 EOS 扩展 `.swix`、装载和寄存器访问的示例或文档。

**收到文件后，先核对完整文件名及README中的支持板卡、EOS/Vivado版本；确认包含7135V / BVL工程后，再准备构建环境。**

## 2. AMD：下载 Vivado Linux 开发工具

官方版本选择与下载页面：

```text
https://www.amd.com/en/support/downloads/adaptive-socs-and-fpgas/development-tools/2026-1.html
```

打开后，在页面顶部选择开发包要求的版本，找到 **AMD Unified Installer**。以下两种方式任选一种；开发工具选择 **Vivado Design Suite**。

### 方式 A：Linux 在线安装器

下载项：**AMD Unified Installer for FPGAs & Adaptive SoCs 2026.1: Linux Self Extracting Web Installer**。

大小约 **394.17 MB**。它负责继续下载选中的工具及器件组件，也可用“Download Only”准备离线安装材料。

具体下载入口：

```text
https://account.amd.com/en/forms/downloads/xef.html?filename=FPGAs_AdaptiveSoCs_Unified_SDI_2026.1_0616_1700_Lin64.bin
```

对应文件名：`FPGAs_AdaptiveSoCs_Unified_SDI_2026.1_0616_1700_Lin64.bin`。

### 方式 B：完整离线安装包

下载项：**AMD Unified Installer for FPGAs & Adaptive SoCs 2026.1 SFD**。

大小约 **98.28 GB**，适合课前下载后带到开发机安装。

具体下载入口：

```text
https://account.amd.com/en/forms/downloads/xef.html?filename=FPGAs_AdaptiveSoCs_Unified_SDI_2026.1_0616_1700.tar
```

对应文件名：`FPGAs_AdaptiveSoCs_Unified_SDI_2026.1_0616_1700.tar`。

这两个地址都是官方的账号下载入口，需要在浏览器中完成 AMD 登录。若直接打开提示会话失效，请从上面的官方下载页面登录后点击对应下载项。本次仅核对下载条目和入口，尚未下载文件。

## 3. 器件支持与许可

**器件支持组件**在 Vivado 安装器中选择，按 BVL 开发包要求安装目标 VH1542 所需的 Versal 支持。

**许可说明**见 AMD 官方页面：

```text
https://www.amd.com/en/products/software/adaptive-socs-and-fpgas/vivado/vivado-licensing-options.html
```

2026.1 的官方表将 Versal 支持列在 **PRO、ENTERPRISE、GOLD** 档。请结合最终工具版本核对许可；网口 IP 的授权条件另按开发包说明处理。用于构建电路的是完整 Vivado Design Suite；Lab Edition 用于器件装载和调试。

## 可直接转发的需求

> 麻烦帮忙取得 Arista DCS-7135V-48Y-4QC 对应的 BVL 完整 FPGA 开发包（FDK），目标芯片为 AMD Versal HBM VH1542。需要板级参考工程、构建说明、EOS/Vivado 版本要求，以及网口 IP 和工具许可说明。我们准备在 Linux 开发机上，从 SystemVerilog 源码构建 `.pdi`，后续打包为 EOS 的 `.swix` 并装载到交换机。我们在软件下载门户中未看到对应条目，请先确认该开发包的提供方式、具体文件名、下载入口及所需账号/合同/许可条件，再提供README和版本说明；确定配套版本后，再准备对应的Vivado安装材料。
