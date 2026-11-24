# 第零部分教师说明

本页保存机器规格和取证入口。学生正文只保留实验所需概念、原生命令与结果读法。

## 机器规格与历史记录

以下为2026-08-19在观察机 `.101` 的历史只读记录，不代表本轮重新检查了设备。

<div style="border-left:6px solid #7e22ce;background:#f3e8ff;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#7e22ce;color:#fff;font-weight:800;">已验证现场锚点 · 教师取证</span> <span style="font-weight:700;color:#581c87;">2026-08-19 在观察机 <code>.101</code> 只读采集：4 个逻辑 CPU；单实例 L1d 48 KiB、L1i 32 KiB、L2 1280 KiB、L3 55296 KiB（约 54 MiB）；Cache Line 64 B；Page 4096 B。证据：<code>20260819T135057Z-00-cpu-cache-baseline</code>。这组字段描述的是机器规格，性能结论由后续测量给出。</span></div>

规格中的 L1d 是数据缓存、L1i 是指令缓存，KiB=1024 B、MiB=1024 KiB。逻辑 CPU 数量不等于物理核心数量。学生正文只使用缓存行64 B、普通页4 KiB；详细字段留在本页便于对照。

主题一的“1.1 缓存与主内存”另有一张个人电脑任务管理器截图：`images/course-visuals/00-diagrams/00-personal-pc-l1-l2-l3-cache.png`。该图 L1 2.4 MB、L2 40.0 MB、L3 36.0 MB，是用户个人电脑的整机汇总，用来对照三级缓存名字；不得与上方 `.101` 的 L1d/L1i/L2/L3 KiB 记录混用。学生正文用“L2 通常每核一份、L3 通常各核共享”解释这台机器加总后 L2 大于 L3；40.0 ÷ 24 只是按核心数均分整机读数，不是已核验的每核官方规格。

首次按页写入的历史样例来自 `20260825T045052Z-00-page-fault-shape`，三行输出为4096、128、128。判据仍为缺页增量与写过的页数同量级，不以这一次精确128替代一般判据。DEC-402将学生读法改为“预期接近128，不要求正好相等”，没有新增数值阈值；差异大时保留原样输出核对，没有新实验。

## 首次写入结果的核对

学生正文以两项原始字段的关系解释正常现象：写过128页，次缺页增量应接近128。2026-09-09用户反馈当前实验正常，本轮据此精简结果卡；没有收到新的原始输出，正文仍引用原有带日期的历史样例。

若增量与页数差别很大，先确认脚本是否原样复制、`touched_pages` 是否为128，再核对 `page_size`（本课机器为4096），并记录是在本课机器、其他虚拟机还是容器中运行。保留原样输出，不以换环境重试来凑出128。

`ru_minflt` 统计整个进程，包含Python自身的活动，无法把每一次增加对应到某一行代码。本实验观察首次写入与缺页计数的关系；业务延迟和不同写法的性能，由第四、第五部分另行测量。

## 配套资产

| 本地资产 | 行数 | 当前职责 |
| --- | ---: | --- |
| [01-cpu-cache-baseline.sh](01-cpu-cache-baseline.sh) | 24 | **教师 / 审计取证**：核对本页机器规格与正文采用的大小 |
| [02-page-fault-shape.sh](02-page-fault-shape.sh) | 42 | **唯一课堂实验**的远端取证与 SHA 封存版本 |

第一份脚本在 `.101` 读取规格，第二份在 `.101` 执行同一个首次写入实验；通过 `.111` 保存远端原始输出与 SHA 清单。DEC-404为课堂Python和本脚本中的同一段Python同步加入A～E中文注释，执行语句保持；两处Python逐字一致。新增代码图说明申请、计数、逐页写入与释放的顺序，没有新实验。

## 来源与维护

| 官方入口 | 本章只取什么 |
| --- | --- |
| [Linux Memory Management](https://docs.kernel.org/admin-guide/mm/index.html) | 程序申请的内存怎样由操作系统管理 |
| [Linux Page Tables](https://docs.kernel.org/mm/page_tables.html) | 程序给出的地址怎样对应到实际存储位置 |
| [Linux NAPI](https://docs.kernel.org/networking/napi.html) | 网卡发出通知后，系统怎样接着处理报文 |
| [Intel Optimization Reference Manual](https://www.intel.com/content/www/us/en/content-details/671488/intel-64-and-ia-32-architectures-optimization-reference-manual-volume-1.html) | 数据放在哪里、怎样访问，会影响等待多久 |
| [SI prefixes (BIPM)](https://www.bipm.org/en/measurement-units/si-prefixes) | 毫秒、微秒、纳秒的含义与换算 |

时间单位表在第 04 章读计时字段的位置。第 00 章当前按四个等待点、10 个步骤编排：内核边界 1 项，取数据 / 准备内存 / CPU 调度 / 如何收包各 2 项，一页总结 1 项。一张任务表与 10 张导航卡逐项对应，沿用 DEC-401/402 的中性靛蓝分组和绿色当前标签；2026-09-14 的四主题安排取代旧七步分组。

主题三只讲等待执行、执行中暂停与上下文切换；逻辑 CPU 编号和 CPU 亲和性不在入门正文展开，具体配置留到第 04 章。上方历史机器规格继续保留供教师核对。

## 收包概念的讲解顺序（2026-09-14 更新）

第 00 章只建立普通收包的交接链和四个等待点；第 01 章对应真机设备与抓包，第 05 章再讲旁路及收包分工。按用户要求，Onload 图文与 RSS / 中断亲和性高级延伸退出入门正文，接管 DEC-411～413 对这两部分的布局安排。

| 概念 | 当前处理 |
| --- | --- |
| 中断、NAPI与驱动poll、网络栈、套接字接收队列 | 主题四的“4.2 通知与应用读取”，沿普通路径五箭头①～⑤讲解 |
| 接收队列、RSS、多个通知入口与中断亲和性 | 移至[第 05 章收包分工说明](../05-kernel-bypass/README.md#receive-queue-irq)，由准备 C 链接；图与两行解释集中在配置说明前 |
| RX Buffer、RX Descriptor、DMA | 主题四的“4.1 缓冲区与 DMA”先说明存放与搬运职责，再进入通知与读取；总结只回顾 |
| 准备内存 | B标记为申请/首次访问阶段；供网卡DMA使用的缓冲区先准备好，避免把CPU按需缺页画成网卡写入时发生 |
| OpenOnload | 网卡、CPU、库和业务代码的分工合入第 05 章运行②，沿用该处路径图；本章不再展开 |
| softirq、MSI-X的机制细节 | 此处不展开，需用时再查官方文档 |

主题四的“4.2 通知与应用读取”使用 `00-receive-kitchen-flow.svg` 普通收包主图。`00-rss-irq-extension.svg` 原字节复制为第 05 章配套图 `05-rss-irq-receive-roles.svg`；本目录的原件与 `00-onload-hardware-software.svg`、`00-kernel-vs-onload-receive.svg` 留作历史资产。一页总结使用已有 `00-packet-memory-notification.svg`，①～⑤区分数据/通知/处理关系，A～D与正文四个等待点逐行对应。A～D有重叠影响，不构成四项独立可相加的延迟；概要图不描述所有缓存与DMA一致性细节或精确复制次数。

Onload 与队列扩展已移入[第 05 章](../../05-openonload-tcpdirect-dpdk-kernel-bypass.md)。第 00 章理解检查现按取数据、准备内存、CPU 调度、如何收包各设一题；实验代码、运行命令与历史输出保持。下方 DEC-412～414 为当时图文安排的历史记录。

- [Linux NAPI](https://docs.kernel.org/networking/napi.html)：中断通知后安排NAPI，驱动poll处理已到报文。
- [Linux 网络扩展](https://docs.kernel.org/networking/scaling.html)：队列、RSS和中断分工。
- [Linux DMA指南](https://docs.kernel.org/core-api/dma-api-howto.html)：驱动先准备设备可访问的内存。
- [AMD Onload透明接入](https://docs.amd.com/r/en-US/ug1586-onload-user/Onload-Transparency)：库接手受支持的套接字调用，未加速调用交给内核。

用户追加用词要求：正文首次用“套接字（Socket）”，后续用Socket；主图标为“Socket接收队列”和“通过Socket读取”，不再只用中文译名。

## OpenOnload硬件与软件分工补图（DEC-412）

用户继续询问为何旁路仅留文字，并怀疑协议处理应位于网卡。本轮新增 `00-onload-hardware-software.svg`：左为网卡硬件收发、队列分发与DMA；右为CPU执行的软件，普通路径内核处理协议，Onload受支持路径由应用内的库处理，再经Socket交给业务代码。内核/驱动资源管理与未加速路径保留。两箭头①资源配合、②数据交付，独立于普通收包图及RSS高级延伸图；不恢复八步流程或启动命令。

按AMD Onload Transparency与OpenOnload项目README核对：协议栈由用户态共享库实现，另有支持内核模块。图中进程框表示执行归属，箭头是处理关系；报文字节仍落在主机内存中。未画成网卡上的完整TCP卸载，也未承诺所有协议工作都只在用户态、零中断或零内核参与。正文正向解释分工，不写成对读者私下疑问的反驳。

## 中英文标签与Socket说明补正（DEC-413）

用户最终要求图中重要概念用中文（英文），故三图使用中断（IRQ）、批量收包（NAPI）、套接字（Socket）；正文仍可沿用已引入的Socket简称。Onload图内核/库两处均展示Socket接口实现，业务侧为调用；这是实现职责的位置对照，不表示普通应用缺少用户态Socket调用入口。正文取消旁路段与对应两行表的额外加粗，压缩重复比喻，保留资源管理职责。

[AMD VNIC](https://docs.amd.com/r/en-US/ug1586-onload-user/Virtual-Network-Interface-VNIC)说明硬件过滤/RSS分流及隔离收发资源；[AMD CTPIO](https://docs.amd.com/r/en-US/ug1586-onload-user/CTPIO)说明X2发送数据经PCIe直达端口、绕过常规发送数据路径的能力。DMA/分流是硬件分工，受支持协议主要由CPU上的库处理；第零部分只加一行硬件分工，CTPIO具体机制留第六部分。本轮没有检测某个实时连接是否使用CTPIO，也没有新增性能归因。

## 总结图编号顺序（DEC-414）

用户指出IRQ⑤容易被读为最后发生。现总结图按①DMA写入、②中断通知、③④取数处理、⑤应用读取编号，图内及正文阅读提示同步。只对常见中断驱动收包路径作此引导，不表示NAPI主动轮询也必须先收到IRQ。A～D等待位置保持。
