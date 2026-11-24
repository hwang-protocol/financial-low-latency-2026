# 第 08 章现役机制图

## 2026-09-19 · 全章导航与两类设备的机制图

当前[第八章](../../../08-fpga-from-code-to-device.md)按19项任务组织为6组：认识电路与设备（2项）、准备开发工具（3项）、U250接入与构建（4项）、U250实现与验证（4项）、交换机适配与部署（5项）、行业延伸（1项）。章首总导航与第01/07章相同，写在正文 Mermaid 里；任务表和19张小导航卡采用同一组编号。设备容器和接口关系仍用原生SVG。`08-fpga-switch-real-world-cases` 现用于正文 5.1，承接旧 Arista 稿的三个公开部署案例。

| 文件 | 正文位置与说明 |
| --- | --- |
| [08-course-navigation.mmd](08-course-navigation.mmd) / [08-course-navigation.svg](08-course-navigation.svg) | 历史导出参考；学生正文总导航改回与前几章相同的章内 Mermaid |
| [08-u250-data-control.svg](08-u250-data-control.svg) | 3.2：网口报文经过过滤器和QDMA交给主机；管理命令通过跨时钟模块与寄存器进入电路 |
| [08-u250-fields.svg](08-u250-fields.svg) | 3.2：固定报文格式检查、Type/Locate/Stock提取与一次额度判断，字段偏移从以太网头起算 |
| [08-board-switch-paths.svg](08-board-switch-paths.svg) | 4.1：U250的观察位置在PCIe主机，交换机的观察位置在网络出口；数据与控制路径分开 |
| [08-switch-board-integration.svg](08-switch-board-integration.svg) | 4.2：7135V配套工程与课程模块之间的报文、控制、时钟复位三组连接，保留实际源码名 |
| [08-ug1301-alveo-card-features.png](08-ug1301-alveo-card-features.png) | 3.7：UG1301「Alveo Card Features」官方标注图，标出 Network Interface 与 Micro-USB Interface |
| [08-alveo-u250-io-bracket.png](08-alveo-u250-io-bracket.png) | 现行黑壳侧视裁切，保留图册；正文改用带标注图 |
| [08-u250-usb-jtag.svg](08-u250-usb-jtag.svg) | 线序示意保留，不进正文 |

四张机制SVG解释接口、职责和预期处理关系，不是实卡验证结果。U250的源码行为与交换机整帧缓存示例分别说明；交换机图以具备完整7135V/BVL配套工程为前提。本轮更新保留所有旧图，旧章号和既有验证记录维持历史身份。

GUI实录另见[U250操作图册](../08-u250-walkthrough/README.md)：当前27张，图22综合完成、图24实现完成、图25比特流生成成功、图26文件属性，图27展示未连接状态下的Auto Connect入口。完整规则报告与实卡验证仍按各自证据确认。

2026-09-19：原`tmp/`下十张用户安装截图已改名移入[独立安装图册](../08-vivado-install/README.md)，不再混放机制图目录；原文件名与字节摘要均有清单，PNG内容未修改。

## 2026-09-19 · 芯片、工具与设备关系

1.2 在关系图之前增加 U250 产品外观：[08-alveo-u250-card.png](08-alveo-u250-card.png)。用户原图 `image.png` 为 1200×1200，下半空白约 588px；课堂版裁到 1113×614（内容框外留 40px）。未裁原件见 [08-alveo-u250-card-source.png](08-alveo-u250-card-source.png)。这是产品外观图，不是实验室现场照片，也不改关系图里的示意图标。

新增 `08-chip-tool-device-map.svg`（1200×860）与同源PNG（1600×1147），嵌入合并第八章1.2并替换D02占位。原生图标包括芯片、PCIe板卡、交换机、开发电脑与配置文件；上部两行分别为AMD UltraScale+→AMD Alveo U250、AMD Versal HBM VH1542→Arista 7135V，下部说明AMD Vivado结合各自配套工程生成本例.bit/.pdi。硬件图标为功能示意，端口数量/外形不作为实物规格。

依据：[AMD U250器件说明](https://docs.amd.com/r/en-US/ug1301-getting-started-guide-alveo-accelerator-cards/Card-Features)、[Arista 7135V产品页](https://www.arista.com/en/products/7135v-series)。800/1200px目视、字体和文字边界检查通过；三条箭头统一12×12、尾部锚定、3px butt线帽，尖端距目标框12px。保留旧09章产品图，未修改其内容或引入新硬件验证结论。核验记录见 `refs/evidence/ch08-chip-tool-device-map-20260919.json`。

## 2026-09-17 · RTL 代码与寄存器连线对照

新增 `08-rtl-register-wiring.svg`（1200×1080）及同源 PNG（1600×1440），置于章首两段 SystemVerilog 示例之前。上半部画 A 比较后保存 `a_ok_q`，同时保存 `b_q`，下一拍比较 B 并保存合并结果；下半部移除这两组中间寄存器，两个当前输入的比较结果直接连接合并逻辑，保留 `hit` 寄存器。图中①②与正文代码对应。

这是 RTL 数据连接示意，省略共同的时钟线；综合可能合并逻辑，不代表芯片布局或固定资源数量。示例源码和既有功能仿真结果保持，未运行 Vivado 或装载硬件。12 条箭头统一 12×12 尾部锚定 marker、3px butt 线帽、12px 目标框外间隙。Chromium 配 Noto Sans CJK SC 渲染，800/1200px 整图审阅、文字边界与 XML 检查通过。核验见 `refs/evidence/ch08-rtl-wiring-20260917.json`。

## 2026-09-17 · FPGA 交换机的三个真实应用

同日按用户反馈补充：nxLink 面板明确“专用微波 / 光纤冗余 / 报文仲裁与去重”，正文旁加紫色小知识卡，解释微波争取低时延、光纤保障连续性以及双路复制/接收去重。依据 Euronext 与 nxLink 原始说明，几何与九条箭头不变；SVG/PNG 重新渲染审阅。

新增 `08-fpga-switch-real-world-cases.svg`（1200×1380）及同源 PNG（1600×1840），放在章末 Netnod 工程之后。蓝/橙/绿三个面板分别画 Enyx nxLink 无线/光纤仲裁、德交所 MetaWatch 监测副本、Netnod 普通 NTP 请求与回复。正文简短说明用途，附 Arista 原始部署案例与 Netnod 源码入口。

这是公开资料的机制归纳，没有把 7130 的 L1 转发时延当作 FPGA 应用时延，也没有把 BMv2 产物当作这些应用的硬件镜像。九条箭头统一 12×12 尾部锚定 marker、3px butt 线帽、12px 目标框外间隙。800/1200px 整图审阅、文字边界与 XML 检查通过；保留所有旧图与实验代码。核验见 `refs/evidence/ch08-09-fpga-cases-20260917.json`。

## 迁移范围（2026-09-19）

本目录仅保留 FPGA 配套图；旧 P4/BMv2 教学图及其操作说明未迁入。现役引用以根目录第 08 章为准。

## Vivado乐高操作导航

`08-vivado-building-blocks.svg`：原生SVG，八步对应3.2—3.8（3.6分配置与观察两步），网表为综合产物。正文地图与职责表、七节导航卡互相对应；实卡装载与联调保持条件边界。

## 2026-09-19 交换机前端简化

08-switch-board-integration.svg 已从第08章前端讲解撤下，文件保留供追溯；正文按用户要求仅保留工程来源、源码职责及构建打包概要。

## 交换机打包概览

`08-switch-packaging-overview.svg` 用三列解释输入文件、厂商app.mk/RPM/manifest、swi-tools/SWIX。第08章4.3.2以此图替代详细准备步骤；命令保留在MANUAL-PACKAGING.md。
