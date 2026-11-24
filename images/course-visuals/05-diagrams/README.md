# 第 05 章课程图片集

2026-09-16：来源部署图底部改为第二章备好 Socket / Onload 打标客户端、第五章启用；其余路径与图形保持。800 / 1200px 渲染通过，800px 目视无越界。

### 2026-09-16 · 第五章独立更新 Socket／Onload 客户端

`05-source-build-deploy.svg` 保留原布局，标明原 v13 Socket 程序留存、第五章准备 B 另装 `posix-runtime/flle-posix-qos-v1/bin/flle-trader`。已在 800px 与原始 1200px 宽度目视检查，文字无溢出和遮挡；原有统一箭头几何保持。两级 SHA 同步。下方“原图字节不变”属于相应旧轮记录。

## 2026-09-16 · 四张代码路径图重绘

当前正文使用 11 张 SVG，配套说明使用 2 张；其余 49 张保留为历史图件。此清单取代下方旧日期的图数口径，不删除历史资产。

| 当前正文图 | 用途 |
|---|---|
| `05-four-path-roles.svg` | 对照接口、TCP 处理者与网卡归属；TCPDirect 明确为 ZF 用户态栈处理 TCP |
| `05-source-build-deploy.svg` | 准备 A：源码位置、编译产物与部署关系 |
| `05-kernel-socket-path.svg` | 标准 Socket 的调用、内核栈与队列 |
| `05-onload-order-path.svg` | 同一程序加载 Onload 库 |
| `05-onload-vi-ctpio.svg` | VI 资源、DMA / CTPIO 发送对比及与 Socket 代码的关系 |
| `05-tcpdirect-order-path.svg` | ZF 显式 API 与事件循环 |
| `05-guest-iommu-vfio-chain.svg` | 已有 IOMMU / VFIO 条件，移至 DPDK 段 |
| `05-dpdk-fstack-order-path.svg` | F-Stack 回调、线程交接、PMD 与队列 |
| `05-pmd-queues.svg` | PMD 的 TX/RX 队列职责与网卡 DMA 搬运 |
| `05-order-timing-windows.svg` | 两段耗时与总耗时，共三项指标 |
| `05-balanced-comparison-method.svg` | 四轮平衡顺序与统计方式 |

四张重绘图由 `assets/05-kernel-bypass/build-code-visuals.py` 生成，与 `code-reading.html` 共用函数编号。使用 1200×1400 画布、平面线条图标；蓝色发单、绿色回报，底部单独画等待、事件循环或线程交接。VFIO / IOMMU 与内核支持只在资源说明中出现，不串进逐包 TCP 处理链。

四图在 800px 正文宽度和 1200px 原尺寸均已完整目视；文本、图标、代码框及连线采样检查无重叠。深色代码框统一使用 700 粗体；顶部图标与代码框保留间距，协议栈图标与标题也已拉开。四图副标题明确相对前一路的变化，正文增加统一对照表及原码摘录。箭头统一 12×12、userSpaceOnUse、refX=0、butt 线帽，目标框前留白至少 14px。

最新评估修正 K/O/Z 顶行的取单与建连顺序，K 图区分 TCP 握手与后续 Soup 登录；O1 显示 latency 配置，O4 标明最多轮询 100 ms，O/Z 用“整包到卡后发送”说明本课行为。完整源码页同步修正 K4 / Z4 落点。总览和比较方法图统一写 Onload，计时图题为“一笔订单的三项耗时”；这六张改动图均在 800px 与原尺寸复看。DMA、VI 和来源图保持原字节。

新增 VI/CTPIO 图使用 1200×1260 画布，平面 CPU / 内存 / 网卡图标。蓝线表示发送，绿线表示回报；CTPIO 发送同样用蓝线。用“整包到卡后发送”代替模式名，以及 Socket 应用由 Onload 库内部使用 VI 和选择 CTPIO。800/1200px 已目视检查。

新增 PMD 图为 1200×960：三列分别为 F-Stack、PMD、网卡，上排发单、下排回报，箭头只表示处理先后；描述符与报文缓冲区分开说明，网卡 DMA 直接读写主机缓冲区。底栏用一句话区分驱动职责与 CTPIO 搬运方式。800/1200px 已检查文字、图标与连线。

配套仍使用 `05-rss-irq-receive-roles.svg`、`05-exchange-receive-placement.svg`。`05-source-build-deploy.svg` 按用户要求保留在准备 A，原图字节不变。本轮退出现役的是 `05-classroom-run-flow.svg`、`05-dataplane-mode-switch.svg`，原件继续参加 SHA 校验。以下记录仅代表各自日期的编排。

---


## 2026-09-14 · 接收队列图从入门章移入配套说明

`05-rss-irq-receive-roles.svg` 原字节复制自 `../00-diagrams/00-rss-irq-extension.svg`（1200×460），用于[收包分工说明](../../../assets/05-kernel-bypass/README.md#receive-queue-irq)，由正文准备 C 链接。图先区分 RSS 分队与中断亲和性，具体 Exchange 配置紧随其后；不增加学生配置步骤。

第 05 章运行②沿用 `05-onload-order-path.svg`，图下合入网卡、CPU 与 Onload 库的分工，不再重复添加第 00 章旧 Onload 图。正文仍引用 11 张图；配套说明引用 2 张图。

### 2026-09-12 · 比较方法图去掉额外统计脚注

用户继续指出图中“两个计时窗口的 p50 不能直接相减”难读且打断流程。已删除这条额外脚注，保留原版横向布局、轮换顺序与统计流程；该统计细节不再塞进方法图。800px/1400px 全图目视及两级 SHA 59/266 通过，未改运行脚本或操作现场。

### 2026-09-12 · 比较方法图恢复原布局

用户否定上一轮对比较方法图的重排，要求恢复原来较认可的格式，并去掉难读的“同轮内前一路到后一路的不同路径组合各一次”等措辞。已恢复原版 1400×900 横向画布、四张条件卡、4×4 表和底部四张汇总卡；原有矩形、圆形和分隔线几何逐项一致。右栏改为“让测试顺序更公平：轮流先测、后测，也轮流接在其他路径后面测”。保留平衡拉丁方名称、预热数量、暂停/恢复和四格取平均的必要说明，图下继续只留参考链接。 已在 800px 和原始 1400px 检查整图。

### 2026-09-12 · 比较方法图集中说明

用户要求比较方法由图承担，图下只留必要内容。重排 05-balanced-comparison-method.svg 为固定条件、Williams 平衡拉丁方、逐格统计三部分，补全轮内前后路径组合、暂停与恢复、每格预热/正式数量、四格分位数等权平均与不可直接相减的提醒。删除图下五段重复说明，仅保留方法及第04章参考链接。 图尺寸 1200×1100，800px 与原始尺寸已目视检查。

## 2026-09-12 · 计时窗口改用人话标签

`05-order-timing-windows.svg` 三个时刻改为进队、开始发送、收到结果；两段窗口改为进队 → 开始发送、开始发送 → 收到结果。箭头尺寸和坐标未改。

## 2026-09-12 · 程序来源图路径迁为 ch05

用户明确要求把现役四路径资产从ch06迁为ch05，取代前轮“旧包名不改”的约定。已迁移vault目录和文件名、v5构建输入解包根及v13运行包解包根，同步脚本、图文、白名单、目录与SHA。v13包仅MANIFEST和provenance内容改变，40份其他文件及8个编译产物全部保持原字节；依赖包内容也相同。旧归档内部与旧RUN原始记录保留，分析器兼容两种历史路径。 源码部署图的管理机目录、运行包文件名与虚拟机解包目录均为ch05，800/1200px整图已查看；排版和箭头坐标不变。

## 2026-09-12 · 准备 D 图只改一行说明

`05-classroom-run-flow.svg` 保持原来的四段纵向课堂顺序。只把准备 D 那一行从“沿用第二章 RUN → 锁定路径比较条件”改成“停掉 AUTO / MANUAL，换上测试客户端”。其余框、箭头和尺寸未改。

## 2026-09-12 · 源码图最终教学呈现

用户要求让图承担说明，图下尽量减少文字；同一项目客户端只突出部署时编译与课前编译，不在学生正文展开版本差异。最终图补完整运行包路径、主要源码映射、编译/部署时机、目录与Kernel/Onload共用文件；删除图下重复段落和四行功能表，仅保留包/源码链接、旧包名及沿用Exchange的短说明。准确源码差异留教师记录，未宣称两个版本源码逐字一致或全部行为相同。

## 2026-09-12 · 源码图版本说明更正

源码图两条分支明确不同版本：第02章部署时源码已有行情处理更新，第05章使用v13封存源码。公共顶部只列项目位置和主要源文件映射，不代表版本相同。800/1200px整图查看通过，箭头坐标保持。

## 2026-09-12 · 准备 C 的文件来源与收包配置

新增 `05-source-build-deploy.svg`：分开第02章首次部署时编译普通客户端与课前编译四路径运行包两条路线，写明源码、包内文件和 `.2` 部署路径；第05章复用三个封存程序。按用户追问补齐三组主要源码到程序的映射，明确 TCPDirect 共用 trader.cpp 并接入 tcpdirect_order_transport.cpp。图中 RUN_ID 是加载的部署编号占位符，不生成示例运行态。v13 沿用部分 v12 构建产物，图只表达课前完成，不声称全部在同一天编译。

新增 `05-exchange-receive-placement.svg`：用网卡、接收队列1、逻辑CPU2说明正式测量条件；128是RSS表项数，1和2是对象编号。本图移至资产 README 的教师参考；平台启动时已设置，准备与测量入口自动复核，学生无需另行配置。

两张原生SVG均在800px与1200px整图审阅。共用12×12用户坐标箭头，refX=0、3px线宽、butt线帽；尖端距目标框描边外缘至少12px，所有箭头目视通过。旧图字节不变；两级SHA更新为59/266项，47张历史资产继续保留。

## 2026-09-12 · 现役与归档清单

本目录共 60 张图：第05章引用 11 张 SVG、教师说明引用 2 张 SVG，其余 37 张 PNG 与 10 张 SVG 明确保留作历史审计，不再用于当前课堂。下方旧日期条目只记录当时编排，不作为当前引用清单。

`SHA256SUMS` 校验全部 60 张图的文件完整性，包含归档文件；正文引用检查只核对下面的现役清单。未引用但列为归档的 47 张图是已知保留项，不应报为待处理的孤立资产。恢复到正文前须按当前技术事实和制图规则重审。

| 现役 SVG | 状态 |
| --- | --- |
| `05-balanced-comparison-method.svg` | 第 05 章引用 |
| `05-classroom-run-flow.svg` | 第 05 章引用 |
| `05-dataplane-mode-switch.svg` | 第 05 章引用 |
| `05-dpdk-fstack-order-path.svg` | 第 05 章引用 |
| `05-exchange-receive-placement.svg` | 资产 README 教师参考引用 |
| `05-four-path-roles.svg` | 第 05 章引用 |
| `05-guest-iommu-vfio-chain.svg` | 第 05 章引用 |
| `05-kernel-socket-path.svg` | 第 05 章引用 |
| `05-onload-order-path.svg` | 第 05 章引用 |
| `05-order-timing-windows.svg` | 第 05 章引用 |
| `05-rss-irq-receive-roles.svg` | 资产 README 收包分工说明引用 |
| `05-source-build-deploy.svg` | 第 05 章引用 |
| `05-tcpdirect-order-path.svg` | 第 05 章引用 |

| 归档文件 | 状态 |
| --- | --- |
| `05-01-four-software-paths.png` | 历史保留，退出正文 |
| `05-02-unified-measurement-contract.png` | 历史保留，退出正文 |
| `05-03-pci-ownership-lifecycle.png` | 历史保留，退出正文 |
| `05-04-chapter-roadmap.png` | 历史保留，退出正文 |
| `05-05-bypass-responsibility-spine.png` | 历史保留，退出正文 |
| `05-06-kernel-socket-path.png` | 历史保留，退出正文 |
| `05-07-kernel-strace-model.png` | 历史保留，退出正文 |
| `05-08-kernel-evidence.png` | 历史保留，退出正文 |
| `05-09-onload-preparation.png` | 历史保留，退出正文 |
| `05-10-onload-preparation-evidence.png` | 历史保留，退出正文 |
| `05-11-onload-inventory.png` | 历史保留，退出正文 |
| `05-12-onload-inventory-evidence.png` | 历史保留，退出正文 |
| `05-13-onload-path-selection.png` | 历史保留，退出正文 |
| `05-14-onload-live-connection.png` | 历史保留，退出正文 |
| `05-15-onloaded-valid-inspection.png` | 历史保留，退出正文 |
| `05-16-libonload-loader-proof.png` | 历史保留，退出正文 |
| `05-17-kernel-vs-onload-strace.png` | 历史保留，退出正文 |
| `05-18-onload-live-evidence.png` | 历史保留，退出正文 |
| `05-19-tcpdirect-build.png` | 历史保留，退出正文 |
| `05-20-tcpdirect-build-evidence.png` | 历史保留，退出正文 |
| `05-21-tcpdirect-object-lifecycle.png` | 历史保留，退出正文 |
| `05-22-binary-identity-gate.png` | 历史保留，退出正文 |
| `05-23-elf-loadability-gate.png` | 历史保留，退出正文 |
| `05-24-hugepage-baseline-gate.png` | 历史保留，退出正文 |
| `05-25-onload-device-entry.png` | 历史保留，退出正文 |
| `05-26-tcpdirect-readiness-evidence.png` | 历史保留，退出正文 |
| `05-27-hugepage-tlb-dma.png` | 历史保留，退出正文 |
| `05-28-hugepage-lifecycle.png` | 历史保留，退出正文 |
| `05-29-hugepage-evidence.png` | 历史保留，退出正文 |
| `05-30-dpdk-data-ownership.png` | 历史保留，退出正文 |
| `05-31-pci-owner-state-machine.png` | 历史保留，退出正文 |
| `05-32-bdf-driver-netdev-ip.png` | 历史保留，退出正文 |
| `05-33-iommu-safety-gate.png` | 历史保留，退出正文 |
| `05-34-dpdk-preflight-evidence.png` | 历史保留，退出正文 |
| `05-35-dpdk-function-vs-safety.png` | 历史保留，退出正文 |
| `05-36-dpdk-evidence-chain.png` | 历史保留，退出正文 |
| `05-37-chapter-handoff.png` | 历史保留，退出正文 |
| `05-course-optimization-map.svg` | 历史保留，退出正文 |
| `05-dpdk-fstack-owner-cpu.svg` | 历史保留，退出正文 |
| `05-exit-channel.svg` | 历史保留，退出正文 |
| `05-four-gates.svg` | 历史保留，退出正文 |
| `05-four-real-order-paths.svg` | 历史保留，退出正文 |
| `05-kernel-loopback-syscall-sequence.svg` | 历史保留，退出正文 |
| `05-onload-runtime-three-piece.svg` | 历史保留，退出正文 |
| `05-sfc-vs-vfio-data-path.svg` | 历史保留，退出正文 |
| `05-tcpdirect-transport-adapter.svg` | 历史保留，退出正文 |
| `05-tcpdirect-zf-hardware-path.svg` | 历史保留，退出正文 |

## 2026-09-12 · 第五章粗扫与计时图修正

正文现引用 10 张 SVG。四张单路径图继续沿用同一版式；准备 B 中重复且较密的 `05-sfc-vs-vfio-data-path.svg` 退出正文，原文件与清单保留。下方 2026-09-02 的 11 图清单是历史编排。

`05-order-timing-windows.svg` 三个时刻现写为进队、开始发送、收到结果，对应 `queued_ns` / `send_ns` / `completed_ns`。两段窗口写为进队 → 开始发送、开始发送 → 收到结果。箭头仍是同尺寸 18×18 用户坐标头部、refX=0、4px 线宽和 butt 线帽，尖端距目标圆节点描边外缘 12px。800px 与 1400px 整图目视通过。两级 SHA 已同步。

## 2026-09-12 · 现役第05章

本目录由原第06章前移，现役图文件与链接采用新编号；下方历史条目保留原日期和验证身份。本轮未新增设备实验。

## 2026-09-07 · DEC-377 全课顺稿配图

本轮新增下列原生 SVG，图标表示角色，保留旧图文件作历史审计。正文入口以本表为准；旧日期条目记录当时状态。

| 当前图 | 回答什么 | 替换的正文图 |
| --- | --- | --- |
| `05-four-path-roles.svg` | 四种收发方式的接口、TCP 实现与网卡归属 | `05-four-gates.svg`（已退出正文） |

依据为本章现役正文与配套实现；不包含新增运行读数或硬件实测。使用自绘文件、包裹、时钟、芯片、内存、队列等矢量图标。箭头遵硬规则 §3.3.3：本组固定 12×12 用户坐标头部、refX=0、2.5 线宽、butt 线帽，尖端与目标框至少间隔 12；无箭头的比较图不强加方向。800px 与 1200px 已逐张检查，修复缺字和标题越界。


> 生成日期：2026-08-23；当前主线重构并逐图复核：2026-09-02
> 生成方式：历史图使用Codex内置`imagegen`；当前主线新增仓库原生SVG
> 使用位置：`05-openonload-tcpdirect-dpdk-kernel-bypass.md`

## 历史正文主线（2026-09-02）

旧 37 张 PNG 与未被本轮正文引用的原生 SVG 全部保留作历史审计。按 DEC-208/214/215/218/222/223，当前第六章正文使用 11 张仓库原生 SVG；其中 4 张总览图负责全章关系，4 张同版式路径图分别紧邻运行 ①～④，计时图负责统一字段边界，模式切换图解释网页按钮与 curl 的同一 API，比较方法图解释四轮平衡采样与汇总：

| 文件 | 教学任务 |
| --- | --- |
| `05-four-gates.svg` | 章首：同一笔 SoupBinTCP/OUCH 订单对应四种本机 Transport；第四条同时更换 TCP 实现与设备所有权 |
| `05-guest-iommu-vfio-chain.svg` | 准备 B：用“仓库 / DMA 叉车 / 地址围栏”串起 ESXi I/O MMU、GRUB、Guest cmdline、IOMMU group 与 VFIO；强调 group 7 的数字只是本机标签，真正门闸是组内只有 X2522；unsafe no-IOMMU 明确拒绝 |
| `05-sfc-vs-vfio-data-path.svg` | 准备 B：把四路重新归纳成两类 owner；左侧 Kernel、Onload、TCPDirect 都保留 `sfc`，右侧 DPDK 独占走 F-Stack → `net_sfc_efx` PMD → `vfio-pci + IOMMU type 1`，下方单列管理面切换链并与单笔订单热路径分开 |
| `05-classroom-run-flow.svg` | 准备 D：四段课堂顺序保持原图；准备 D 一行改为停掉 AUTO / MANUAL，换上测试客户端 |
| `05-order-timing-windows.svg` | 运行 ①～④之前：用进队、开始发送、收到结果三个时刻分开 `queue_to_send_ns` 与 `order_rtt_ns`，并用总括号说明两段之和为 `submit_to_final_ns` |
| `05-kernel-socket-path.svg` | 运行 ①：同一 OUCH 订单经 POSIX Socket、系统调用门、Linux TCP/IP、`sfc` 与 X2522 到 Exchange；底栏只保留标准易排障与热路径经过通用内核栈的取舍 |
| `05-onload-order-path.svg` | 运行 ②：同一 Trader 与 POSIX API 经 Onload 透明拦截进入用户态 TCP 和 VI/CTPIO；灰色支路明确建栈、异常和慢路径仍与 Linux 协作 |
| `05-tcpdirect-order-path.svg` | 运行 ③：显式 ZF API、主动 reactor、ZF 用户态 TCP 与 VI/CTPIO 串成主线；owner 仍为 `sfc`，线上协议不变 |
| `05-dpdk-fstack-order-path.svg` | 运行 ④：F-Stack TCP/IP、DPDK `net_sfc_efx` PMD、VFIO/IOMMU 与 X2522 独占连成主线；强调它同时更换 API、栈和 PCI owner |
| `05-dataplane-mode-switch.svg` | 运行 ④：网页按钮与课堂 curl 都走 `POST /api/data-plane`；后台是停客户端、`dpdk-devbind` 换 `sfc`/`vfio-pci`、再启动 |
| `05-balanced-comparison-method.svg` | 运行 ⑤：先固定订单与环境，再用 4×4 轮换顺序让四路各处于第 1～4 位一次；每格 100 笔预热、1000 笔正式采样，最后按路径四格等权汇总 |

37 张 PNG 全部退出正文并留盘审计。`05-four-real-order-paths.svg`、`05-tcpdirect-transport-adapter.svg`、`05-onload-runtime-three-piece.svg`、`05-tcpdirect-zf-hardware-path.svg` 与 `05-dpdk-fstack-owner-cpu.svg` 也保留为历史教学资产，但不再承担当前正文步骤。`05-31-pci-owner-state-machine.png` 是曾用于运行 ④ 的 VFIO/UIO 通用图，现由课程专用 SVG 替换；`05-kernel-loopback-syscall-sequence.svg` 也退出主线，因为真实 Kernel Socket 下单已经承担基线入口。`05-13-onload-path-selection.png` 继续退役，因为它容易把“PCI function 仍绑定 `sfc`”误读成“加速包仍逐包穿过普通 netdev 热路径”。

## 后续路径图怎样继承这张母版

`05-kernel-loopback-syscall-sequence.svg` 同时是后续路径图的视觉母版，但不要求后续实验仍是本机 loopback。复制成新文件后保持以下结构，使学员能一眼看出“哪里没有变、哪里换了”：

| SVG 分组 | 固定职责 | 后续怎样改 |
| --- | --- | --- |
| `lane-frame` | 左边调用者、中间执行路径、右边接收者的三栏位置 | 保持栏位、颜色层级和标题位置；按真实实验重命名参与者 |
| `server-listen` / `connection-setup` | 监听与建连 API、必要先后和各调用职责 | Onload 保留 socket API；TCPDirect 换成 ZF API；DPDK 换成端口/队列动作 |
| `request-path` / `ack-path` | 请求与回复真正经过的运行时和数据路径 | 只画本轮真实经过的对象；远端实验必须把物理 NIC / 线缆 / 对端放在同一抽象层级 |
| `evidence-layer` | 本轮观察到的调用账与证据边界 | 只有新 RUN 已取证后才能改数字和结论 |

派生图继续使用相同编号圆点、蓝色请求箭头、绿色回复箭头和底部证据边界。所有用 `<path>` 画出的连线都必须显式写 `fill="none"`；否则浏览器会把折线路径首尾闭合并填成黑色多边形。不能直接在 Kernel 母版上覆盖事实；应复制成新文件，让各条路径留下可审计版本。当前真实交易主线已经由 `05-four-real-order-paths.svg` 接管；后续派生图必须继续保持 SoupBinTCP/OUCH 任务和对应 Transport 的真实层级。

`05-tcpdirect-transport-adapter.svg` 保留 `normal-posix-client`、`tcpdirect-adapted-client`、`broker-view`、`replacement-seam`、`adaptation-contract` 与 `course-evidence-boundary` 分组。当前图已经对应真实 `OrderTransport` / ZF 实现和真单 RUN；后续若替换交易协议或 Transport 接口，应复制新版本，不覆盖这份已经取证的结构。

## 统一视觉与证据合同

```text
16:9 clean white classroom slide; premium flat-isometric/vector technical
illustration; crisp navy outlines; cyan data/action, purple runtime/memory,
green verified evidence/recovery, orange ownership/interpretation, red only
for a genuine unavailable/unsafe branch; large English labels readable from
a classroom screen. No logos, watermarks, fabricated IPs, ports, PIDs, BDFs,
timestamps, hashes, packet counts, timing values or speed claims.
```

| 文件范围 | 教学任务 | 硬约束 |
| --- | --- | --- |
| `06-01`～`06-05` | 四条软件路径、统一测量合同、PCI所有权、章节路线与责任迁移 | 四条路径都有CPU；OS不消失；不做未实测性能排序 |
| `06-06`～`06-18` | Kernel syscall路径、Onload准备/清单/活连接/加载器与对照证据 | `strace`时间不是网络延迟；清单和`libonload.so`不是活流量证明；`Onloaded(Valid)`只归属于观察窗口内的具体socket |
| `06-19`～`06-26` | TCPDirect固定制品、ZF对象生命周期与四道就绪门 | SHA相同只证明字节一致；ELF只证明可装载形态；设备入口不等于业务流量；RUN 4只得出就绪性结论 |
| `06-27`～`06-29` | HugePage、TLB、DMA与`0→4→0`可逆生命周期 | 大页不保证延迟收益；必须先读零基线、注册恢复动作并证明回到零 |
| `06-30`～`06-37` | DPDK轮询/mbuf/队列所有权、BDF身份、IOMMU门禁、功能证据与总复盘 | 同一PCI功能所有权互斥；Guest 现有 group 7；课堂走 VFIO 真包走并交还；UIO 历史收据不写成当前延迟 |

## 人工返修与拒收记录

- `06-01`首稿擅自补入价格、数量、时间戳和交易所等行情字段，已拒收；最终版只保留已验证的`AAPL TICK · 52 BYTES`。
- `06-04`首稿用“all checks completed”收束，错误扩大了DPDK安全结论，已拒收；最终版明确拆成`FUNCTION: OBSERVED`与`IOMMU GROUP: ABSENT · NO VFIO SAFETY PROOF`。
- `06-06`首稿把`NEIGHBOR`拼错，已拒收；最终版删去不必要的内部小字并保留正确的Kernel POSIX主路径。
- `06-26`首稿擅自生成示例IP、时间戳和RUN ID，已拒收；最终版只保留四道门禁、空白收据图标和受限结论。
- `06-13`与`06-14`明确保留unsupported socket回落内核的分支，并限制`Onloaded(Valid)`只证明当时观察到的socket。
- `06-33`～`06-36`记录的是 2026-08-23 当时“Guest 无 IOMMU group”的历史图层，已退出正文。2026-08-31 本机后来写入 Guest cmdline 并得到 group 7；快照恢复又会回到无组状态。禁止把这些旧图重新当成本轮现场。
- 内置绘图服务在`06-13`和`06-29`生成时超过首轮等待窗口；均继续等待同一内置任务完成，没有改用外部图片或脚本占位。
- 按 DEC-20260831-140 返修 `05-four-gates.svg` 与 `05-exit-channel.svg`：删去「VIP 闸口 / 护照不用换」，快速通道改为自助机自己刷、认不了的退回窗口；四张卡末行统一为「闸：海关在管 / 闸：归你」，让「办手续」和「那道闸归谁」两层在同一张图里并排可见。禁止再用插队、特权、免检一类说法。
- 按 DEC-20260831-145 保留旅客 / 单子 / 出站闸骨架，但撤回“相邻始终只换一件”的过强图题：DPDK 同时换设备所有权和实验层级，底栏明确另用一把尺子；第四卡长句拆成两行短句，避免出框。
- 按 DEC-20260831-141 再修这两张 SVG：章首图改成「填哪张单子、谁来办」对「出站闸」；当时四扇门副标写过“相邻只换一件”，该句后来已由 DEC-145/146 撤回。继续禁止把专用柜台写成专用护照。
- 按 DEC-20260831-146 逐张核对正文实际引用的 6 张图：运行 ① 从会误读成物理 NIC 已经参与的 `06-06` 换成证据边界准确的 `06-07`；Onload 正文把不存在的“虚线”改成图中真实的灰色回退支路；DPDK 状态图明确是通用图，本轮只走 VFIO；两张 SVG 分别修正 06–08 阶段标签和 DPDK 的 L2 / 所有权双重变化。
- 2026-09-02 按用户反馈新增 `05-guest-iommu-vfio-chain.svg`。它只解释已经锁定的安全门闸，不改变脚本或设备现场；开机配置链和运行时 DMA 链分层，避免把 GRUB、IOMMU、group 与 VFIO 误读成同一个东西。
- 2026-09-02 继续按用户反馈新增 `05-sfc-vs-vfio-data-path.svg`。图不再把四路表现成同级平行 API，而是先按 PCI owner 分成 `sfc` 三路与 `vfio-pci` 一路；模式切换管理链和单笔订单热路径分开，避免把界面等待时间误读成 DPDK 订单延迟。
- 2026-09-02 按用户反馈新增 `05-classroom-run-flow.svg`，替换准备 D 前的等宽字符箭头。四个框只回答“准备一次、单路四次、统一比较一次”，不重复展开准备门闸，也不写任何示例延时。
- 2026-09-02 按用户反馈新增 `05-order-timing-windows.svg`，替换三个计时字段的等宽公式。图把同一笔订单固定为三个时间点和两个相邻窗口，总括号只表达精确加法关系；不把 `queue_to_send_ns` 误画成纯队列等待。
- 2026-09-02 按用户反馈新增四张同版式单路 SVG：`05-kernel-socket-path.svg`、`05-onload-order-path.svg`、`05-tcpdirect-order-path.svg`、`05-dpdk-fstack-order-path.svg`。正文四个字符路径全部退役；每张图固定订单线程、API/栈、X2522 owner、物理链路与 Exchange 的阅读方向，使学员能逐图比较“哪里没变、哪里换了”。
- 2026-09-02 按用户反馈新增 `05-dataplane-mode-switch.svg`。它只解释已经存在的模式切换 API：网页按钮和课堂 curl 是同一入口，后台才是 `labctl` 停进程与 `dpdk-devbind` 换驱动。
- 2026-09-02 按用户反馈新增 `05-balanced-comparison-method.svg`。图把 Williams 直接翻译成四行四列的轮换顺序，并把固定条件、每格 100+1000、16 格总账、四格等权汇总与“固定簿面但不冻结进程”放在同一张图里；正文删除原六行方法表和重复长解释。

## 尺寸与投屏层级

37张历史PNG中26张为`1672×941`，9张为`1671×941`，2张为`1672×940`。2026-09-02 当时正文不再按投屏/折叠分层，只引用历史表中的 11 张；现役清单见本文开头。

全部固定摘要见同目录`SHA256SUMS`。
