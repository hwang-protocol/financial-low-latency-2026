# 第00章课程图片集

2026-09-19：现役课程合并为00～08，`00-wait-sources-network-host.svg` 中原08/P4与09/FPGA改为同属08的U250板卡、交换机两条路线，布局与图标保持；下方旧章号为历史记录。

## 2026-09-14 · 四个等待点与十步导航

正文以取数据、准备内存、CPU 调度、如何收包为四个主题，基础分工和总结置于两端。现有图片按这个顺序使用：缓存层级、个人电脑缓存读数与局部性图归主题一；地址翻译与首次写入图归主题二；线程状态图归主题三；普通收包图归主题四；A～D 综合图用于最后回顾。RX Buffer / Descriptor / DMA 的三行说明从总结前移至“4.1 缓冲区与 DMA”，再看“4.2 通知与应用读取”的主图。

本轮不新增或修改图文件，12 处图片路径与顺序保持；下方旧节号只记录当时布局，当前定位以正文四主题标题和锚点为准。个人电脑截图的并行排版调整保留。

## 2026-09-14 · Onload 与队列扩展退出入门正文

第 00 章收包部分只保留普通收包与四个等待点两张主图；正文图片由 14 张减为 12 张。`00-onload-hardware-software.svg` 退出正文，分工说明合入第 05 章运行②现有路径图下；`00-rss-irq-extension.svg` 原字节复制到 `../05-diagrams/05-rss-irq-receive-roles.svg`，供第 05 章收包配置配套说明引用。两份旧文件保留历史，不再按下方旧日期条目恢复到第 00 章。

## 2026-09-14 · 开场三图：链路、全课路线、四个等待点

开场两段各补教学 SVG，全部为线稿卡片风格，与 `00-memory-workbench.svg` 同一套图标。

| 当前图 | 画布 | 回答什么 |
| --- | --- | --- |
| `00-business-reaction-chain.svg` | 1200×880 | 一次下单反应经过的五段职责顺序 |
| `00-wait-sources-network-host.svg` | 1200×880 | 五段分别由哪一章处理：网络段列第 06～09 章，主机段列第 04、05 章，第 01～03 章为基础 |
| `00-kitchen-four-waits.svg` | 1200×760 | 四个等待点分别在等什么，每格先技术说法、再厨房说法 |

按用户两轮反馈修正：厨房图先从场景插画改为四格卡片；随后第二张图不再写成“路径、拥塞、丢包”，改为对齐后续章节的真实知识点——第 06 章固定转发 / 出口排队 / PTP 对时，第 07～09 章 XDP、P4、FPGA，第 04 章队列交棒、忙轮询与 CPU 隔离（缓存与内存本身属本章），第 05 章四条出站路径。按用户要求不谈丢包。四个等待点的措辞同步改准：缓存里没有这份数据、第一次访问才真正备好、就绪后还没轮到、报文到了程序还没读到。

章号只说明各段在哪里展开，不表示优化顺序；三图均不含耗时或性能结论，未改实验与脚本。

## 2026-09-14 · 个人电脑三级缓存截图

用户提供个人电脑任务管理器处理器页截图，原文件 `newDoc/image.png` 已改名为 `00-personal-pc-l1-l2-l3-cache.png`（632×256 PNG），放进本目录并嵌入第2节层级表之后。图回答“真实机器上的 L1/L2/L3 容量长什么样”，与厨房存储层级图分工：后者讲位置关系，前者给整机汇总数字。

界面读数：L1 2.4 MB、L2 40.0 MB、L3 36.0 MB，24 核心 / 24 逻辑处理器。L2 大于 L3 是这台个人电脑的事实，不能写成缓存层级定律，也不能当成 `.101` 实验机规格。2026-09-14 正文改为图左短表右、两栏等高；用整机加总解释 L2 大于 L3，40.0 ÷ 24 只作均分读数。未改图字节。

## 2026-09-09 · DEC-414 总结图按处理顺序编号

`00-packet-memory-notification.svg` 的旧⑤IRQ改②；原②取数据、③执行代码时读取、④应用读取依次改③④⑤。①DMA与A～D等待不变，箭头ID/可见编号/描述、图内阅读提示及正文alt/图注同步。说明常见中断驱动路线，不把IRQ作为所有轮询路径的必需前置。

1200×1370与全部几何保持；800/1200、32文字边界、五箭头角色对应和两端12px、15表/HTML、74卡及SHA29/214通过，无实验。报告 `refs/FLLE_Receive_Order_2026-09-09.md`。

## 2026-09-09 · DEC-413 Socket实现对照与中英文图名

`00-onload-hardware-software.svg`在内核与Onload库两处标出“套接字（Socket）接口实现”，业务侧标“套接字调用”；库框加高至145px，应用/CPU外围框相应延长，独立两箭头及画布保持。图注说明接口背后的收发处理位置，不把普通路径的用户态调用入口省略为“程序直接身处内核”。

`00-receive-kitchen-flow.svg`及`00-packet-memory-notification.svg`把通知标为“中断（IRQ）”、本路径的NAPI职责标为“批量收包（NAPI）”；主图队列标为“套接字（Socket）接收队列”。三图800/1200目视、77文字边界、12箭头固定12×12头部与两端12px通过，15表/HTML、74卡及SHA29/214通过。其他图字节保持，无实验。报告 `refs/FLLE_Socket_Labels_2026-09-09.md`。

## 2026-09-09 · DEC-412 OpenOnload硬件与软件分工

新增 `00-onload-hardware-software.svg`（1200×920），在第5节旁路段独立展示：左网卡硬件收发/队列/DMA，右CPU执行的软件；普通路径内核协议栈作为位置参照，Onload库与Socket业务代码位于同一应用进程框。独立①直接使用分配的网卡资源、②交付，正文两行对应。底部说明主机内存、内核/驱动的资源管理和未加速收发。

这是分工位置图，不复用DEC-410八步对照，也不改变独立RSS扩展及等待点图。箭头表达处理关系，不省掉主机内存或暗示网卡承担完整TCP协议栈。800/1200目视、18文字边界、两箭头两端12px及固定12×12头部、15表/HTML、74卡、SHA29/214通过。全文10图，无实验。报告 `refs/FLLE_Onload_Hardware_Software_2026-09-09.md`。

## 2026-09-09 · DEC-411 普通收包、独立高级延伸与四等待点

| 当前图 | 画布 | 用途与编号 |
| --- | --- | --- |
| `00-receive-kitchen-flow.svg` | 1200×1140 | 第5节普通收包厨房角色；①～⑤对应主表 |
| `00-rss-irq-extension.svg` | 1200×460 | 第5节高级延伸；RSS分队与通知分工，独立①②对应两行表 |
| `00-packet-memory-notification.svg` | 1200×1370 | 第6节总结，①～⑤处理关系，A～D四等待点 |

`00-kernel-vs-onload-receive.svg`自本轮退出正文并保留历史；下方DEC-410为当时对照版记录。旧00-17/00-20 PNG亦保持历史。第5节主图保留网卡、缓冲区、中断铃、NAPI/驱动poll验收、网络栈、Socket备菜台和应用主厨；高级延伸分开显示，不把⑥⑦接续进主图。第6节补清单与DMA、缓存、CPU内核/应用与行情解析，A～D逐行对应正文；内存B属于申请/首次访问阶段，收包缓冲区先备好。

三图均原生平面图标，无外链位图；最小字号21px在800课堂宽度约14px。各图编号独立，所有箭头12×12头部、3px线宽、两端12px间隙；A～D用彩色标记及无箭头引线/括线表示观察范围。800/1200目视、71文字边界、12箭头、14表/HTML、74卡及SHA28/213通过，无实验。报告 `refs/FLLE_Receive_Waits_Flow_2026-09-09.md`。

## 2026-09-09 · DEC-410 普通收包与OpenOnload过程对照

| 当前图 | 正文用途 | 原图状态 |
| --- | --- | --- |
| `00-kernel-vs-onload-receive.svg`（1600×1660） | 第5节上下对照普通路径与Onload；八编号箭头 | `00-17-nic-interrupt-napi.png`退出正文，保留历史 |
| `00-packet-memory-notification.svg`（1200×690） | 第6节分清内存落点、通知与CPU处理；三编号箭头 | `00-20-os-hot-path-summary.png`退出正文，保留历史 |

对照图保留主内存缓冲区、中断通知、驱动批量取包、协议处理、套接字接收队列、应用线程，以及Onload库加载、进程归属和内核支持。普通路径①②③④、Onload⑤⑥⑦、支持路径⑧，与正文短表逐项对应。平面网卡/内存/协议层/程序/铃/CPU图标均为原生矢量，无外链或位图。蓝绿区分普通与Onload处理路线，橙线为通知，灰虚线为支持关系；本图不按TCP/UDP分别着色。

箭头表达处理关系，不给出精确时序或复制次数；支持范围按本课X2522与官方Onload文档，不表示无内存、无内核、无中断或无调度等待。800/1200目视、57文字边界、11箭头两端12px与固定12×12头部、12表/HTML、74卡及两级SHA26/211通过。报告 `refs/FLLE_Network_Bypass_Basics_2026-09-09.md`，未执行实验。下方日期条目记录旧图当时状态。

## 2026-09-09 · DEC-409 全图统一平面风格

用户指出立体机箱与平面面板视角混用，明确要求统一平面构图。现役 `00-scheduler-thread-states.svg` 保持1200×940及五箭头布局，候选架、调度面板、两个处理器、暂停区全部改为正视纯色图形，统一描边与圆角；无透视侧面、渐变、阴影、滤镜或位图。主次关系和图后五行短表保持，图注/alt同步。

800/1200整图目视、22文字边界、五箭头两端12px、13表/HTML、74卡及SHA24/209通过。报告 `refs/FLLE_Scheduler_Flat_2026-09-09.md`；下方DEC-408为前版立体设计记录。

## 2026-09-09 · DEC-408 参照原PNG恢复立体构图

用户希望参照原 `00-14-scheduler-core-selection.png` 的质感与构图，并压缩图后文字。现役 `00-scheduler-thread-states.svg` 原位重画为1200×940：左侧候选架和彩色线程标牌，中间带齿轮、指示灯和金属边框的选择机构，右侧两块立体处理器；下方等待区保持次要。全部为原生SVG路径、渐变和阴影，不嵌入PNG。

①选择、②③执行为主线；左侧明确已准备好但还要等执行机会。④暂停、⑤条件满足后回到可运行候选为补充。中间机械机构比喻内核调度功能，不是设备清单；图形不承诺固定优先级、精确队列实现或快照式线程身份。五箭头与五行短表对应，图后解释区汉字数370→192。800/1200目视、21文字边界、五箭头两端12px、13表/HTML、74卡和SHA24/209通过。报告 `refs/FLLE_Scheduler_Illustration_2026-09-09.md`。

## 2026-09-09 · DEC-407 突出开始执行之前的调度等待

用户明确主次：线程已有工作且具备运行条件后，仍可能等待CPU执行；执行中等数据为次要补充。现役 `00-scheduler-thread-states.svg` 原位改为1200×920：已准备好的线程→调度器→处理器，①选中、②执行；橙色提示CPU可能正执行其他线程，括线标出准备好到开始执行的调度等待。底部用两句补充阻塞后再继续。取消DEC-406的上下两排身份切换和四时刻重复图。

四种原生图形为时钟、线程卡、选择清单、处理器；全中文，两个箭头统一12×12头部、3px线宽、两端12px间隙。800/1200整图、19文字边界、13表/HTML、74卡与SHA24/209通过。下方历史条目保留当时版本身份。报告 `refs/FLLE_Scheduler_Wait_2026-09-09.md`。

## 2026-09-09 · DEC-406 调度图改为连续执行故事

用户反馈DEC-405的角色/状态环仍未讲清“做一半、先等待、之后接着做”，并要求替换卡通图标。当前 `00-scheduler-thread-states.svg` 改为1200×900四个连续时刻，三条编号箭头：①甲等待数据，处理器执行乙；②数据到达，甲可运行，此例处理器仍执行乙；③再次选中甲，从暂停处继续。上半部始终追踪甲的进度，下半部是同一个逻辑处理器的甲/乙/乙/甲四种时刻。

图标改为带位置书签的执行记录与金属处理器，删除主厨头像、任务单堆和排班台。三根箭头均12×12固定头部、3px线宽，两端距框12px。图下三行表对应箭头。800/1200预览、31处文字边界、13表/HTML、74卡和SHA24/209通过。下方DEC-405条目为前版设计记录，旧PNG仍保留历史。报告 `refs/FLLE_Scheduler_Continuation_2026-09-09.md`。

## 2026-09-09 · DEC-405 中文线程调度图

正文第4节改用 `00-scheduler-thread-states.svg`（1200×1000），旧 `00-14-scheduler-core-selection.png` 保留历史并退出正文。四种原生矢量图标：任务单、排班台、主厨与处理器、时钟。所有可见标签为中文，五条编号箭头说明选择、执行、等待、唤醒及仍可运行线程被切换后的去向。排班台为内核调度功能的比喻，不是独立硬件；图只展示一个执行位置和常见状态转换，不刻画全部调度策略或退出状态。

图注、下方三状态表与逻辑CPU编号句同步，正文仍八图。800/1200预览、20处文字边界、五箭头端点12px间隙及两级SHA通过。报告 `refs/FLLE_Scheduler_Diagram_2026-09-09.md`；无实机操作。

## 2026-09-09 · DEC-404 首次写入代码图

新增 `00-page-write-code-walkthrough.svg`，1200×1690，放在唯一实验的完整代码前。左列摘录代码，右列说明内存/计数变化；箭头按A～E标明申请、读取before、逐页写入、读取after、输出与释放。C步复用上一图的内核/账本图标，明确引用上一图⑤处理缺页、⑥重试。图内省略部分代码参数和表达式，完整脚本紧随其后；计数器图标不填入假读数。

正文及 `assets/00-basics/02-page-fault-shape.sh` 的Python同步加入A～E中文注释，代码语法树保持。正文现为八图，原有七图继续使用。五根箭头固定12×12头部、refX=0、userSpaceOnUse，3px线宽、butt线帽，源/目的边缘均留12px；1200/800预览、61文字边界及正文代码预览见 `refs/FLLE_Page_Write_Code_Diagram_2026-09-09.md`。无实机实验。

## 2026-09-09 · DEC-403 编号地址翻译图

当前正文用 `00-address-translation-numbered.svg` 替换 `00-03-tlb-translation.png`。原PNG保留作历史资产；下方2026-08条目描述旧版，不再作为当前正文入口。新图为1200×1270原生SVG，重画原图紫色记录柜、蓝色账本、主内存柜和内核工作站的立体风格，六种图标均为SVG路径/形状，无外链字体或位图。

七条箭头与正文七行表一一对应：①查询TLB，②按结果访问内存，③未命中查页表，④取得并缓存翻译结果，⑤内核处理缺页，⑥修复后重试，⑦报告无法恢复的访问。图左给出从①开始的常见路线；绿色④表示记录取得与保存，实际读写会利用缓存，图不刻画CPU流水线内部时序。页表作为主内存中的结构单独展示，不冒充独立硬件。图中⑤展开查页表时的处理分支，图表不是完整硬件异常状态机。

次缺页/主缺页合入正文⑤行；普通页4KiB、缓存行64B及大页另以短段承接首次写入实验。所有箭头头部固定12×12、refX=0、userSpaceOnUse；线宽3、butt线帽，尖端距目标框12px。1200/800px预览及编号/端点/文字边界核对见 `refs/FLLE_Address_Translation_Diagram_2026-09-09.md`。未执行实机实验。

## 2026-09-07 · DEC-377 全课顺稿配图

本轮新增下列原生 SVG，图标表示角色，保留旧图文件作历史审计。正文入口以本表为准；旧日期条目记录当时状态。

| 当前图 | 回答什么 | 替换的正文图 |
| --- | --- | --- |
| `00-memory-workbench.svg` | CPU、缓存与主内存的取数关系 | `00-02-memory-hierarchy.png`（已退出正文） |

依据为本章现役正文与配套实现；不包含新增运行读数或硬件实测。使用自绘文件、包裹、时钟、芯片、内存、队列等矢量图标。箭头遵硬规则 §3.3.3：本组固定 12×12 用户坐标头部、refX=0、2.5 线宽、butt 线帽，尖端与目标框至少间隔 12；无箭头的比较图不强加方向。800px 与 1200px 已逐张检查，修复缺字和标题越界。


> 生成日期：2026-08-22；技术修订：2026-08-25
> 生成方式：Codex内置`imagegen`，用途分类`scientific-educational`  
> 使用位置：`00-cpu-cache-memory-os-basics.md`  
> 边界：图片用于解释角色、路径、分支和证据归属；实际数值、命令结果与结论仍以正文原始输出为准。

## 统一Prompt合同

```text
Use case: scientific-educational
Asset type: 16:9 classroom diagram for a Chinese financial low-latency engineering course
Style: clean white classroom slide; premium flat-isometric technical illustration;
crisp vector-like edges; restrained 3D depth; recognizable hardware, terminals,
memory pages and evidence files; deep navy outlines; cyan normal/data path;
orange handoff or DMA; red interrupt/fault; purple memory/control; green PASS/recovery;
large readable English labels; generous whitespace.
Constraints: exact arrow direction and ownership boundary; no logos; no watermark;
no unverified performance numbers; no fake counters or hashes; no direct NIC-to-app leap.
```

每张图在统一合同上追加下列主题和精确约束：

| 文件 | Prompt主题 | 必须保持的逻辑 |
| --- | --- | --- |
| `00-01-kernel-boundary.png` | Application、System Call、Kernel、Hardware四层 | 应用不能直接连接硬件；请求向下、结果向上。2026-09-14 正文对照表已按这四层从上往下排列，驱动写在内核层内；本文件字节未改 |
| `00-02-memory-hierarchy.png` | Registers→L1→L2→L3/LLC→RAM→可选Disk慢路径 | 层级表示距离，不暗示每次访问逐层串行 |
| `00-03-tlb-translation.png` | TLB HIT/MISS、Page Table与Page Fault分支 | HIT绕过页表；只有Page Not Ready进入Fault |
| `00-04-chapter-roadmap.png` | CPU/Cache→Locality→Page/TLB→Scheduler→IRQ/NAPI→Hot Path | 恰好六站，顺序固定 |
| `00-05-cache-hierarchy.png` | L1i/L1d、L2、共享L3/LLC与RAM剖面 | L1i和L1d分离后汇入L2；不虚构容量 |
| `00-06-cache-observation-flow.png` | lscpu、Page Size、Cache sysfs和只读边界 | 只观察层级，不生成性能结论 |
| `00-07-cache-evidence-pipeline.png` | Jump Host→SSH→.101→raw result→SHA | RUN目录属于跳板机；SHA最后生成 |
| `00-08-locality-patterns.png` | Compact与Scattered字段布局对照 | 两侧字段相同；分别占1条与4条Line |
| `00-09-cache-line-model.png` | Offset÷64→Unique Line IDs→Count | `0/8/16/24`得到1条，`0/64/128/192`得到4条；模型不是计时 |
| `00-10-cache-line-evidence.png` | .101 Python模型与结果证据链 | 不在图中填充虚构结果或SHA |
| `00-11-virtual-memory-page-fault.png` | Virtual Address→Page Table→Physical Page→CPU Cache | Not Ready才进入Kernel Page Fault，随后安装映射 |
| `00-12-page-touch-experiment.png` | page_size→before→allocate→每页1 byte→after→delta | before/after显示窗留空，不冒充实测值 |
| `00-13-page-fault-evidence.png` | .101 Python进程内bytearray与page touch取证 | bytearray、触碰和delta都属于远端进程 |
| `00-14-scheduler-core-selection.png` | Runnable、Scheduler、Running CPU与Blocked状态 | 只有Running线程才转入Blocked；Ready后回Runnable，再经Scheduler选择 |
| `00-15-scheduler-observation.png` | PSR、Allowed CPU Set、Context Switches | 三类字段分开解释；不修改Affinity |
| `00-16-scheduler-evidence.png` | 三类调度字段的远端取证链 | 三分支到raw result才汇合，SHA最后生成 |
| `00-17-nic-interrupt-napi.png` | NIC→CPU→Kernel IRQ→softirq/NAPI→Socket→App | 不暗示每包一次中断，不允许NIC直连App |
| `00-18-interrupt-counter-reading.png` | `/proc/interrupts`与`/proc/softirqs`读表 | 先认CPU列再找行；不填虚构counter |
| `00-19-interrupt-evidence.png` | 两份proc输出的远端采集和验签 | 两来源独立读取，进入raw后再SHA |
| `00-20-os-hot-path-summary.png` | NIC、主机RX descriptors、DMA/RAM、CPU内IRQ/NAPI、Cache与App | NIC读descriptor后直接DMA写buffer；IRQ独立通知CPU；NAPI是CPU内的软件阶段；步骤可重叠 |

## 生成后人工校正

- `00-05`首稿把`AAPL DATA`拼错，最终版定点修复。
- `00-07`首稿把大小写敏感的`lscpu`画成`Lscpu`；最终图改用不冒充命令的`CPU INFO`，精确命令留在正文。
- `00-11`首稿加入人物和多余图例，最终版重画为纯设备与映射路径。
- `00-12`首稿在before/after表盘填了`000000`，最终版清空显示窗，避免被误认作实测值。
- `00-20`首稿把RX queue画进NIC并写出不严谨的RAM边界；最终版重画为主机内存中的RX descriptors与packet buffer，明确DMA数据路径和IRQ/NAPI控制路径。
- `00-14`在2026-08-25复核时发现红色箭头把Runnable直接连到Blocked；终稿改成`Runnable → Scheduler → Running → Blocked/Sleeping → Runnable`状态环。
- `00-20`在2026-08-25复核时仍把DMA写入画成经过descriptor，并把NAPI画成独立硬件；终稿拆成NIC读descriptor、NIC直接DMA写buffer、IRQ独立通知、CPU内NAPI与应用解析五个阶段。
- 生成过程中内置服务有两次网络失败；未切换到需要API key的CLI，失败请求未作为最终资产。

20张最终PNG均为`1672×941`，完整摘要见同目录`SHA256SUMS`。

## 当前正文选图（2026-08-25深审）

第00章当前引用七张：`00-01`内核边界、`00-02`存储层级、`00-08`局部性、`00-03`地址翻译、`00-14`调度、`00-17`收包通知顺序、`00-20`结案全景。每节一张，职责不重复。

`00-20`与`00-17`的分工必须在近邻caption中写清：`00-17`讲**常见中断驱动路径的通知顺序**（IRQ → softirq/NAPI → Socket → App Thread），`00-20`讲**对象与数据落点**（NIC读RX Descriptor、DMA直接写RAM中的Packet Buffer、CPU经Cache读取），并同时展示独立的通知路径。`00-20`不覆盖TLB与Scheduler，因此只放在第6节“一页结案”，由同节四类等待点表补齐这两项；不得把它当成全章路线图，章首认知路线仍由可审计的Mermaid承担。

本轮只替换`00-14`与`00-20`两张存在语义错误的图片；其余18张图片字节不变，终稿摘要同步到`SHA256SUMS`。
