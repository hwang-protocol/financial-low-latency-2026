# Vivado 2026.1 安装、工具与网口 IP 许可截图

来源：用户2026-09-18在Windows采集的原始PNG。2026-09-19先从08-diagrams/tmp归档10张，再从newDoc/images/tmp归档3张CMAC许可截图；同日再从newDoc/images归档1张官方下载页截图，共14张。保留原始像素和文件字节。来源映射与SHA256见SOURCE-MANIFEST.json及SHA256SUMS。

[第八章](../../../08-fpga-from-code-to-device.md)第2部分使用12张。新增00为AMD 2026.1官方下载页上的Stand-Alone / Vivado Lab Edition分区；正文写明本课继续在同一页下载完整Vivado。按用户最新要求，最终许可检查统一使用13-confirm-cmac-license.png，同时显示ALVEO工具许可和cmac_usplus IP许可；原09的ALVEO单独状态页保留参考，不在正文重复展示。04为许可管理器默认试用入口参考。

| 文件 | 原文件名 | 用途 | 正文位置 |
| --- | --- | --- | --- |
| [00-amd-2026-1-download-page.png](00-amd-2026-1-download-page.png) | screenshot_20260919_142159_20260919_142200_108539.png | AMD 2026.1 官方下载页上的 Lab Edition 分区 | 2.1 |
| [01-select-vivado.png](01-select-vivado.png) | screenshot_20260918_115603.png | 选择 Vivado 产品 | 2.1 |
| [02-select-alveo-components.png](02-select-alveo-components.png) | screenshot_20260918_115752.png | Alveo 器件、线缆驱动及许可管理组件 | 2.1 |
| [03-download-install-progress.png](03-download-install-progress.png) | screenshot_20260918_120154.png | 下载与安装进度 | 2.1 |
| [04-license-manager-entry-reference.png](04-license-manager-entry-reference.png) | screenshot_20260918_124954.png | 许可管理器入口；截图默认选中60天试用，仅保留参考 | 配套参考 |
| [05-select-alveo-license.png](05-select-alveo-license.png) | screenshot_20260918_125219.png | AMD Product Licensing 原网页，勾选 Alveo 许可 | 2.2 |
| [06-bind-license-host.png](06-bind-license-host.png) | screenshot_20260918_125602.png | 生成节点绑定许可，选择本机 Host ID | 2.2 |
| [07-download-generated-license.png](07-download-generated-license.png) | screenshot_20260918_125802.png | Manage Licenses 中查看生成结果并下载 | 2.2 |
| [08-load-license-file.png](08-load-license-file.png) | screenshot_20260918_125830.png | Load License → Copy License 导入许可 | 2.2 |
| [09-confirm-alveo-license.png](09-confirm-alveo-license.png) | screenshot_20260918_130045.png | 确认 ALVEO、许可条目、到期日期及版本上限 | 配套参考（最终许可状态见13） |
| [10-vivado-start-page.png](10-vivado-start-page.png) | screenshot_20260918_130210.png | Vivado 2026.1 启动界面 | 2.3 |
| [11-search-cmac-license.png](11-search-cmac-license.png) | screenshot_20260918_153917.png | 搜索并选择UltraScale+ 100G以太网免费IP许可 | 2.2 |
| [12-generate-cmac-license.png](12-generate-cmac-license.png) | screenshot_20260918_153928.png | 选择CMAC IP项目并生成节点绑定许可 | 2.2 |
| [13-confirm-cmac-license.png](13-confirm-cmac-license.png) | screenshot_20260918_154301.png | 最终许可状态同时显示ALVEO与cmac_usplus | 2.3 |

## 阅读与证据边界

- 11搜索100G Ethernet，实际勾选的是带“+”的UltraScale+ Integrated 100G Ethernet No Charge License；12显示将它加入产品列表后生成节点绑定许可。
- 13的Loaded License Tiers仍是ALVEO，新增cmac_usplus条目。它证明补充网口IP许可，不是切换Enterprise。IP:Bought是工具显示分类，前两张已明确No Charge，不解释为付费购买。
- cmac_usplus的Expiration Date显示Permanent，Version Limit为2027.09；工具条目的到期日为18-sep-2027。版本上限与到期日分开读取，不外推为所有IP或器件均已授权。
- 06、07中的机器标识和申请者字段保留原件，作为本机绑定示例；未保存或分发.lic许可文件、密钥或登录凭据。
- 02的下载量33.11 GB、磁盘需求104.91 GB是本例安装器读数；03的剩余时间为工具估计。读者按自己的版本与组件准备。
- 00 显示的是同一官方页上的 Stand-Alone / Vivado Lab Edition 分区，Windows 包约 835 MB；本课下载完整 Vivado，不以该分区作为安装包来源。
- 全部截图最大显示宽度760px，正文可点击原图；没有补造未提供的操作画面。

官方资料：AMD下载 `https://www.amd.com/en/support/downloads/adaptive-socs-and-fpgas/development-tools/2026-1.html`、[生成许可](https://docs.amd.com/r/en-US/ug973-vivado-release-notes-install-license/Create-and-Generate-a-License-Key-File)、[导入许可](https://docs.amd.com/r/en-US/ug973-vivado-release-notes-install-license/Install-Certificate-Based-Node-Locked-License-Key-File)、[CMAC许可](https://docs.amd.com/r/en-US/pg203-cmac-usplus/Licensing-and-Ordering)。
