# 第二部分维护与输出来源

### 2026-09-16 · `.101` 平铺构建失败修复

真实上线会在平铺应用目录运行全部测试，不能只在管理机仓库执行选定套件。软件准备/固定制品测试现限定真实仓库布局，管理机缺包仍报错；生命周期测试补齐客户端映像检查模拟。管理机全部 238 项、`.101` 完整构建、上线入口 11 项通过。现有 pending 分支会在原命令重试时清理中断部署并保留原日志；无需恢复快照或删除状态文件。完整平台再次上线仍待用户运行。[核验](../../refs/evidence/snapshot-restore-fix-20260916/check.json)

### 2026-09-16 · 第四章快照后的统一接续入口

恢复第四章结束的快照后，在 `.111` 重跑正文运行 ① 的原命令即可进入已有 A/B 平台的核验、软件补齐、再次核验分支；成功后进入第五章准备 A。不再给学员单列带 `--prepare-capabilities` 的第二条命令，该选项仍保留供维护使用。新增默认入口回归覆盖补齐成功/失败，确认原 RUN 与历史记录保留，失败不继续部署或报成功。完整快照实机重刷仍待运行。

使用时机是恢复第四章快照后、第五章准备 B 之前。准备 B 会停止普通行情接收器，此后默认上线命令不能通过接收器核验；不要把这个预期状态当成旧版 A/B，更不要为绕过检查直接加 `--upgrade-ab` 重建正在测试的会话。

## 源过滤读数与 IGMP 版本

①A 新增只读 `/proc/net/mcfilter` 与数据口 `ifindex`，保留 raw/mcfilter.txt、raw/data-ifindex.txt 并纳入 SHA；格式器只转换真实返回，不预填两条成功样例。Linux 5.15 `igmp_mcf_seq_show` 的 Device 仅六字符，所以按 Idx 对应完整接口名；地址按内核打印的 ntohl 值解析。INC/EXC 是接口上该源的包含/排除引用数，不是逐进程所有权或交换机剪枝结果。

NETWORK-REFERENCE 已删除“没有指定源过滤条件”，区分主机 Socket INCLUDE 与标准 SSM 232/8。历史 Querier 回执为 v2；配置计划没有显式改版本。新内核可在遇到 v2 查询器后使用兼容报告而保留 Socket 源过滤，不宣称本次现场已使用 IGMPv3。下次顺刷看①A的真实源读数、①B两组Dynamic/Et2与①C双路到包；本轮不修改交换机查询器版本。


## A/B 评估后的实现变化（本地验证）

新源码通过 IP_ADD_SOURCE_MEMBERSHIP 指定 `20.1.1.1`，①A 展开的命令增加 `--multicast-source`；历史两组成员/抓包原件保持，不能据此宣称已经实机验证新来源过滤。源过滤不改变 A/B 地址、端口或成员查看方法，也不代表源地址身份认证。接收器默认端口共用 C++ 常量，READY 新增 PID 和来源，恢复/复用核对运行映像与该进程 READY。

第 03 章三窗脚本保存各窗口前后、去重计数前后及结束状态，核对 Exchange/Feed Session 与回放轮次；跨圈提示重新运行，并沿用原模式恢复。脚本现为 56 行，正文改用一行文件入口并更新工具表。历史证据的脚本摘要仍属当时版本，不改写原清单。


## A/B 新平台与双路实测来源

本节接管下方旧平台的来源说明。用户已完成升级，①A～①C 已实测；正文摘取查询与读数，不展示采集日期和 RUN 编号（写作硬规则 §7.3.1）。

| 正文位置 | 原始来源（reports/course-runs/ 下） |
| --- | --- |
| 运行 ① 启动 | `20260915T094055Z-02-trading-platform/raw/05-verify.txt` |
| ①A 两组订阅 | `20260915T095417Z-02-igmp-join/raw/classroom.txt` 与 `raw/membership.txt` |
| ①B 两组 Dynamic / Et2 | `20260915T095418Z-02-igmp-members/raw/classroom.txt` |
| ①C 用户双路抓包 | `20260915T095834Z-02-igmp-feed/raw/packets.txt`、`raw/feed.json`、`raw/classroom.txt` |

①C 只录 A/B 各一条报文，明确省略其余八条、统计命令与过程日志；包数为 5/5，总数 10，`HEALTHY`、`next_expected=1716790`，恢复 `MULTICAST_A`。原件保持。AI 此前也执行了同一窗口双路抓包（`20260915T095420Z-02-igmp-feed`），正文最终使用用户 17:58 这一轮。

运行 ② 尚保留 `20260915T073229Z-02-trading-platform` 的历史成交示例，紫卡已明确，不再称与新版启动同轮。准备 C 原始配置回执仍来自上午；说明按当前 `--configuration --ab --display` 打印规则列两组，未重写历史日志。实际配置是 VLAN20 范围，无需为 B 增加另一套配置。

网页总览原图 `screenshot_20260915_174342_20260915_174343_577922.png` 已原样改名归位为 `images/course-visuals/02-diagrams/02-ui-trading-terminal-ab.png`，替换正文原总览图；SHA256 `d73764618af13592515cf296cc1f1426ea3d3a66b877bcc139009861e294e8bb`。其余两张旧图只说明界面。

网页初始状态提示已通过浏览器测试并更新现役静态文件，当前状态为仅 A 路。未重新执行干净快照安装、首单或第 04 章采样。详见 [实测核验](../../refs/evidence/chapter02-ab-live-members-and-capture-20260915.json)。

## 2026-09-15：复核尾项与课堂来源分离

按 §7.3.1，正文紫卡不放采集日期与 RUN 编号，运行①只保留五段输出属于同一轮平台的总述；具体日期/路径仍以下表为准，三张旧截图的来源日期也只留在此处。展示命令和原始返回不因这次简化而改写。

AUTO 陪跑现放在首单输出后、本章小结前；限价段只有买卖双向教学例、报价变化与 IOC，字段、后台补价和重试过程不再在正文另讲。准备 C 的打印工具仅把“运行①B核对”改成“运行 ①B 核对”，正文按当前格式器回放原始 switch.txt；历史 classroom.txt 不改。该打印文件摘要已变化，前轮含它的清单通过记录仍属当时验证，不能当作本轮代码摘要。[核验](../../refs/evidence/chapter02-final-polish-20260915.json)

## 2026-09-15：评估收口与现役输出来源

九步入口统一为一行 Bash，B1/B2 同级；AUTO 陪跑移到策略后，手工正文不再重复字段和脚本内部判断。direct 在正文说明为脚本的控制器配置，原生命令仍完整展示。长工具披露四项按当前文件核对，后续脚本改行数时须同步。

下表是当前正文的来源：恢复、加组、成员、收包、首单同属 073229 平台，五份清单共 37 项通过；此记录接管下方“新恢复/首单待用户运行”的当时状态。旧 RUN 和旧教学安排留作历史。本轮无设备操作；准备 A 一处说明改为“配套内核模块”，正文注明说明按当前脚本整理，原始回执与读数不变。首单显示测试同步当前来源，其余交易逻辑和图件保持。[核验](../../refs/evidence/chapter02-audit-fixes-20260915.json)

## 2026-09-15：取消章尾重复复查

用户要求完成前面各步后直接结束，正文已删除运行③、代码和输出，并将重复验收表改为简短小结。当前九步按 3/5/1 分组，运行②是最后一项；下方曾把只读复查列为课堂步骤的记录为历史安排。`03-readonly-review.sh` 和既有日志保留作维护与审计资料，不再要求学生执行。首单、组播脚本及其检查逻辑未改。[核验](../../refs/evidence/chapter02-remove-final-review-20260915.json)

## VFIO N 含义由脚本打印

B1 脚本直接解释这个开关是否允许绕过 IOMMU、N=No 及非 N 停止。正文标题和说明按当前脚本整理，命令及 N 仍来自用户 RUN `20260915T071220Z-02-guest-iommu-prep`；新措辞只做本地输出验证，没有重跑设备，也未修改原始日志。先显示实际值再检查 N，失败时也能看到返回值。本条接管下方“保留原有说明”的历史格式记录。[核验](../../refs/evidence/chapter02-vfio-output-wording-20260915.json)

## 2026-09-15：准备 C 查询改用脚本课堂打印

正文第 7～9 条改为用户 RUN `20260915T071549Z-02-igmp-configure` 的 `raw/classroom.txt` 连续节选，不再贴交换机完整原始回执。清单 7 项 SHA 通过；完整 `switch.txt` 留在该 RUN。

## B2 一号机软件输出（2026-09-15 用户运行）

正文 B2 入口后只留版本、两个程序文件/权限、F-Stack 与 DPDK 符号及网卡 PMD。来源为 `20260915T071415Z-02-dpdk-software-prep/raw/10.1.1.1-software.txt`，同一连续窗口内只删除 python3、cd、readelf、strings 的长路径命令行，保留其原始说明和结果；短 ls/test 命令保持。图卡明确标注节选与省略范围，不作为额外手动操作。

run.env 的 EXIT_CODE=0，四项 SHA 通过。分发、lspci/支持文档及 B1 已讲过的分组/安全模式不再重复。B1/B2 用户运行均已完成，新恢复入口尚未随本轮重跑。[核验](../../refs/evidence/chapter02-host1-b2-output-20260915.json)

## 2026-09-15：准备 C 不再讲 running-config 恢复

学生正文已删除“配置影响与恢复”红卡。交换机只改 running-config、不 `write memory`、维护重启回到第 01 章初始化配置，仍按 DEC-20260721-05 执行，不再在准备 C 重复。

## B1 一号机关键输出（2026-09-15 用户运行）

正文在 B1 入口后只保留 `.1` 的启动参数、VFIO 加载命令和保护模式 N，撤掉重复主机标题，不展开分组检查。来源为 `20260915T071220Z-02-guest-iommu-prep` 的 `raw/after-boot.txt`、`raw/vfio.txt` 中一号机片段，按原始顺序拼接；仅增加段间空行，命令与返回逐行保持。八项 SHA 核对通过；分组 7 及单设备检查原文保存在该 RUN，不纳入学生节选。B2 尚待用户运行。[核验](../../refs/evidence/chapter02-host1-b1-output-20260915.json)

## 2026-09-15 后续收口：IOMMU 简讲，结果放脚本

用户明确撤下 IOMMU 图，正文不继续展开 CPU/MMU、隔离组及 VFIO 映射后端。只讲 DMA 内存保护，然后给出与 B1 对应的 GRUB_CMDLINE_LINUX、update-grub、重启、/proc/cmdline 和 modprobe vfio-pci；实际依旧一个 B1 入口，源码/检查机制未因简讲而撤除。原安全模式输出节选退出正文，启动配置块标为脚本设置内容，非实测输出。

F-Stack API 按用户要求保留四组用途。已回源固定 F-Stack lib/ff_init.c（ff_dpdk_init、ff_freebsd_init、ff_dpdk_run）及本课 dpdk_trader.cpp 的调用。B2 的“检查结果与后续用途”正文小节删除，文件名、可执行权限、版本与链接检查统一由脚本打印。

B1 显示标题与说明精简，末尾准备结果纳入 raw/result.txt 与 SHA；B2 增加两个程序的 ls -lh、test -x 与结果。B1 旧显示标签断言同步，状态机测试仍保留。本地七项软件检查、三项准备契约和 B1 契约通过；没有实机准备或交易动作。最后指令由用户执行并贴回输出。本条接管下方仍在正文展示 IOMMU 图及 B1 安全模式输出的记录。[核验](../../refs/evidence/chapter02-iommu-scope-and-output-20260915.json)

## 2026-09-15：DPDK 理论与安装集中到准备 B

正文依次讲 DPDK/传统路径、F-Stack、网卡与官方支持名单、IOMMU，再执行 B1（隔离准备）和 B2（软件安装）。源码示例从 Git 下载开始，解释 Meson/Ninja 来源并给出 DPDK、F-Stack 编译安装和客户端链接命令。课堂 B2 使用已缓存的固定软件，不在课堂等待公网下载。

实际查询 `.2` 的 `lspci -nnk -s 0000:03:00.0` 返回控制器 `[1924:0b03]`、X2522 板卡 `[1924:8028]`、驱动 `sfc`。支持依据来自 DPDK 21.11.9 的 Solarflare PMD 文档 §49.6；文档名单和本机查询分开标识。IOMMU 的重点是限制设备 DMA 读写；普通 DMA 不以它为前提，本课 VFIO 隔离方式和组 7 门槛要求先启用它。

B2 使用 v13 固定包，`flle-trader-dpdk` 内已静态链接 F-Stack 和 DPDK；B2 核对 `ff_init`、`rte_eal_init`、`net_sfc_efx` 和共享库依赖。这是软件检查，不是 PMD 实际收发验证。包中 DPDK 来自 Ubuntu 21.11.9 构建库；源码 Meson 示例说明另一路构建方式，不宣称生成了逐字节相同的现役程序。F-Stack 固定源码自带 DPDK 24.11.6，课程改用外部 21.11.9 并应用仓库兼容补丁。

软件目录为 `/opt/flle/prepared-runtime/<运行包SHA256>`；B2 校验后原子发布，两端重复运行核验复用。`transport_labctl.sh` 在 preflight/deploy 先核对两端软件，缺失则提示 B2；会话恢复从本机已准备目录复制文件，不再 scp 或解压 DPDK 运行包。交易会话原目录、文件摘要、应用二进制与后续切换逻辑保持。

七项新本地测试覆盖真实包安装/复用、失败拒绝与留证、隔离门槛及控制器会话恢复；B1 契约、课堂输出与原准备契约另行通过。固定源码摘要和补丁适用性已核对；源码构建示例未做本轮完整编译。B1/B2、新恢复流程未代用户在设备上执行，实机安装输出待用户运行后录入；下方 2026-09-10 顺刷保持历史身份。[本轮核验](../../refs/evidence/chapter02-dpdk-preparation-20260915.json)

## 本轮顺稿范围

最新输出标签收口：首单结果的 order_id 明确解释为 client_order_id，网页对照也写客户端编号；first_trade.py 的原始打印字段不改。准备 C 格式器与正文统一使用“第 N 条命令”，①A只保留配置/范围两行解释及完整原生命令。本轮只改显示文字，9 项 IGMP 与 5 项课堂输出回归通过；准备 C 示例与新格式器离线读取下表原始 switch.txt 的输出有序逐行一致。没有设备操作，不能把新版标题说成旧终端当时已打印，历史清单不改写。

首单时序图按实际编号来源修正：MANUAL 的 queue_order 分配 UserRefNum 并入队，控制返回 client_order_id；Exchange 接受后另分配 order_reference。图中先标本地分配，再保留返回/发送并行，交易所受理和成交分成两条回报。正文“受理编号”改为客户端编号，说明拒绝分支及拿号不等于受理。依据 trader.cpp 的 allocate_user_ref / queue_order / ORDER 分支、exchange.cpp 的 process_order 路径和已核阅 Nasdaq OUCH 5.0 规范；只改 Mermaid 与解释，不改协议或程序。800px 与 871px 原尺寸渲染目视通过，见 `refs/evidence/chapter02-order-id-clarity-20260910.json`。

评估收口：章尾检查统一为“运行③：复查平台与组播状态”，同步学习目标、Mermaid、任务地图、导航卡和绿卡。正文移除修复/更新/补跑等维护过程措辞，保留正向证据范围。EOS 命令用“第 1～9 条”讲解，历史终端圈号保持原样。复查示例只留原始 trader-auto、Dynamic/Et2 与当前健康三行，完整输出仍为下表原件；本轮未修改脚本或重跑设备。原生命令展示和终端打印保留，避免违背用户此前要求。

正文按“准备环境 → 启动系统 → 确认组播 → 首笔模拟交易与只读复查”展开。2026-09-10 经用户批准修复接收缓冲并重部署，完整顺刷已通过；维护 RUN 为 `20260910T043407Z-02-feed-buffer-fix`，平台为 `20260910T043800Z-02-trading-platform`。Nasdaq 案例和协议范围保留在延伸阅读，旧样例与本次新结果的来源分别列在下表。

## 展示输出与页面来源

| 内容 | 原始来源 |
| --- | --- |
| 准备 A 一号机安装与授权输出 | 用户运行 `20260915T050423Z-02-onload-runtime-prep` 的 `raw/10.1.1.1-runtime.txt`；从“查 Onload 版本”连续取至功能名称说明末尾，保留七段检查及脚本说明，设备标识/序列号脱敏、去行尾空格；六项 SHA 核验通过。正文按用户要求仅展示 .1，替代此前 .2 的旧安装示例 |
| 准备 B1 旧安全模式节选（已撤下） | `20260907T143627Z-02-guest-iommu-prep`；两端 N，历史配置并重启约 19 秒 |
| DPDK 网卡型号 | 2026-09-15 只读 SSH 查询 `.2` 的 `LC_ALL=C lspci -nnk -s 0000:03:00.0`；原返回保存在本轮核验 JSON，正文两行标题/读法是教学标注 |
| 准备 C 第 7～9 条查询 | 用户运行 `20260915T071549Z-02-igmp-configure/raw/classroom.txt` 第 7～9 条连续窗口；7 项 SHA 通过。当前正文用格式器回放原始 `switch.txt`，仅将成员说明的编号空格统一；查询读数保持原件。完整 `switch.txt` 与旧课堂打印留在同一 RUN。历史 `20260910T040553Z` 仍为当时空成员表证据 |
| 运行 ① 在线检查 | `20260915T073229Z-02-trading-platform/raw/restore.txt` 末尾四项 ONLINE、文件 PASS、TRADING_LAB_READY 与四条说明；9 项 SHA 通过。未把未保存在该 raw 的脚本尾部能力提示拼入实际输出 |
| 三张网页截图 | `20260829T023952Z-02-trading-baseline`；日期保留本表；正文只说明历史截图用于介绍界面，交易读数不混入 09-15 输出 |
| 运行 ①A 完整原生命令 | `20260915T073755Z-02-igmp-join/raw/classroom.txt`；展开命令指向 073229 平台，正文仅折行；主机组成员节选同一课堂输出，清单 5/5 通过 |
| 运行 ①B 交换机成员 | `20260915T073819Z-02-igmp-members/raw/classroom.txt`；VLAN20 / 233.74.125.32 / Dynamic / Et2，清单7/7通过 |
| 运行 ①C 五包与恢复 | `20260915T073920Z-02-igmp-feed/raw/classroom.txt` 与 `packets.txt`；源端口44557、五包、HEALTHY / next_expected=687059、恢复 UNICAST。清单10/10通过 |
| 首笔交易课堂打印 | `20260915T073229Z-02-trading-platform/raw/first-trade-classroom.txt` 从“① 查下单前的平台状态”至末尾连续节选；原值在 first-trade.txt。SELL AAPL1，订单2100000003，限价287.37、成交292.36、持仓变化-1、RTT131201ns；首单清单6/6通过 |
| 最终复查节选 | 已退出正文；`20260910T044832Z-02-readonly-review/raw/classroom.txt` 仅保留为历史维护证据 |

上述 RUN 原件在 `reports/course-runs/`。下述为 2026-09-10 的历史顺刷过程（不是本轮09-15）：当时没有恢复快照，停止旧平台后依次准备 A/B/C、构建部署、加组、成员、抓包、首单与复查，准备 B 按需重启了两端。脚本仍保存完整日志及摘要；持久摘要见 `refs/evidence/chapter02-feed-gap-fix-20260910.json`。

#### 后续为什么必须复用它

| 后续变量 | 仍然不变的业务基线 | 届时比较什么 |
| --- | --- | --- |
| CPU、内存、队列与亲和性 | 同一 MANUAL 客户端，AUTO 保持独立负载 | 热路径分布与尾部是否变化 |
| eBPF/XDP | 同一真实 ITCH 行情 | 更早观察或筛选后，应用责任怎样变化 |
| OpenOnload/TCPDirect | 同一订单会话与成交闭环 | 缩短内核网络路径后的差异 |
| DPDK/Kernel Bypass | 同一订单协议、下单意图与成交闭环 | 订单路径上的驱动所有权与轮询模型差异 |
| 交换机与组播优化 | 同一 AAPL/NVDA Feed | 转发、复制、排队与恢复行为的差异 |

第二部分只建立**功能控制组**，不拿本章的一次 `order_rtt_ns` 宣布性能。第四部分会先固定测量点、负载、环境和统计口径，再把后续优化与这一应用的普通 Linux profile 做公平 A/B。

### 源代码与恢复入口

完整应用在 [`apps/flle-trading-lab/`](../../apps/flle-trading-lab/)；学生不需要先读完几千行代码才能把系统拉起来。先按职责找到入口，第三部分再沿真实报文深入。

| 路径 | 负责什么 | 是否进入热路径 |
| --- | --- | --- |
| `src/exchange.cpp` | 历史回放、行情发布、订单连接、纸面撮合 | 是，C++ |
| `src/feed_receiver.cpp` / `src/feed_ipc.hpp` | 用普通 UDP Socket 统一接收行情，保留整包与接收时间，经 Unix Socket 分发给本机 Trader | 是，C++ |
| `src/trader.cpp` | 同一二进制按 `AUTO/MANUAL` 角色启动为两个进程；各自拥有 Feed、风控、订单 ID 和订单会话 | 是，C++ |
| `src/nasdaq_protocol.hpp` | ITCH/MoldUDP64/OUCH/SoupBinTCP 课程子集编解码 | 是，C++ |
| `src/itch_book.hpp` | 从 ITCH 订单事件维护 AAPL/NVDA 订单簿 | 是，C++ |
| `src/book_checkpoint.cpp` | 从 09:30 前增量生成真实开盘订单簿检查点 | 部署工具 |
| `flle_trading/gateway.py` | 汇总旁路状态，提供 HTTP/SSE 与控制 API | 否，Python |
| `web/` | 浏览器行情、价格走势、盘口、策略、订单与成交界面 | 否，HTML/CSS/JS |
| `scripts/transport_labctl.sh` | 完整平台部署、普通交易与路径测试配置切换、验签和停止 | 编排工具 |
| `tests/first_trade.py` | 走和网页同一条 `/api/order` 接口，提交一笔手动 IOC，再按订单 ID 核对回执 | 课堂下单脚本 |
| `tests/latency_regression.py` | 在固定条件下采样 120 笔手动 IOC，断言订单 RTT 的 P99 低于 10 ms 上限 | 工程回归工具 |

行情制品已保存在管理机，恢复脚本核验后直接分发。完整源码目录和制品重建方法见 [Trading Lab 说明](../../apps/flle-trading-lab/README.md)；课堂上先看各服务是否启动，再核对首笔成交。

## 本地配套资产

运行①的 `stage` 在原始关键行之后另行打印字段说明，不修改命令原始日志；五阶段解释材料/工具、构建来源、部署产物、启动与核验，复用分支也解释在线和文件字段。末尾区分当前SOFTWARE配置、已备齐能力与DPDK按需接管；5组课堂输出回归覆盖各阶段失败、复用和原始日志保留。Unix Socket解释对照 `feed_receiver.cpp`、`feed_ipc.hpp`、`trader.cpp` 的AF_UNIX调用，放在同机行情分发首次使用处。

运行①A对照 `control-host.sh` 的 start_feed_receiver 和 `feed_receiver.cpp` 的 udp/main。正文直接列完整二进制路径及全部相关参数，不以 .sh 包装命令或变量替代原生命令；23 行入口同步打印当次路径和展开的默认值，标为等效启动配置，不声称控制器实际显式传入了所有默认值。direct 映射为 --multicast-receiver 1，C++ 调用 setsockopt/IP_ADD_MEMBERSHIP；不把进程复用检查当作实际收包证明。

| 资产 | 用途 |
| --- | --- |
| `assets/02-trading-baseline/00a-runtime-prep.sh` | 准备 A：一次备齐运行依赖 |
| `assets/02-trading-baseline/00b-iommu-prep.sh` | 准备 B1：按需配置并重启以启用网卡隔离 |
| `assets/02-trading-baseline/00b-dpdk-software-prep.sh` | 准备 B2：两端软件安装、版本/链接/隔离检查与格式化输出 |
| `assets/02-trading-baseline/test-dpdk-software-prep.py` | 本地真实固定包检查及恢复入口测试，SSH 编排使用替身 |
| `assets/02-trading-baseline/test-iommu-prep.py` | 教师离线回归：隔离组、双端准备与失败回滚 |
| `assets/02-trading-baseline/test-preparation-contracts.py` | 教师离线回归：重复准备、失败留证与首单就绪条件 |
| `assets/02-trading-baseline/01-restore-trading-lab.sh` | 运行 ① 完整学生入口；仓库根执行 `bash assets/02-trading-baseline/01-restore-trading-lab.sh` |
| `assets/02-trading-baseline/02-first-trade.sh` | 运行 ② 完整学生入口；仓库根执行 `bash assets/02-trading-baseline/02-first-trade.sh` |
| `apps/flle-trading-lab/scripts/labctl.sh` | 预置应用的安全编排、验签与精确停止 |
| `apps/flle-trading-lab/tests/first_trade.py` | 按订单 ID 核对在线 IOC、持仓增量与统一记录 |
| `images/course-visuals/02-diagrams/02-trading-lab-runtime.svg` | 运行架构、热路径与观察路径 |
| `images/course-visuals/02-diagrams/02-nasdaq-multicast-routing.svg` | Nasdaq 真实组播端点、PIM 建树与接入层复制的机制示意 |
| `images/course-visuals/02-diagrams/02-build-start-trade.svg` | 构建、启动与首笔交易流程 |
| `images/course-visuals/02-diagrams/02-ui-replay-book-order.png` | 网页：回放、盘口与手工下单 |
| `images/course-visuals/02-diagrams/02-ui-trend-latency.png` | 网页：价格走势、延时基线与策略 |
| `images/course-visuals/02-diagrams/02-ui-blotter-path.png` | 网页：统一交易记录与系统路径 |
| `images/course-visuals/02-diagrams/02-ui-first-trade-receipt.png` | 网页：运行 ② 同一笔手动单回执 |


## 本地 IGMP 从第三部分前移

用户要求先准备好组播环境，再下首单。第二部分新增准备 C（配置）、运行①A（加组/主机查询）、①B（交换机表）、①C（实际收包）。第三部分删重复配置讲解及执行，三模式脚本改为 show + VLAN20/成员检查。早期本地回放曾使用 `20260908T124946Z-03-market-paths` 的历史材料；现在①A～①C已有完整实跑，正文五包已更新为上表新来源，准备 C 仍保留用户原空表，不用后续有成员的结果覆盖它。

### 原第三部分来源

删除的旧讲解保存在[快照开刷前的第三部分原文](../../reports/course-runs/20260908T122503Z-00-10-snapshot-replay/source-before/03-live-trading-traffic-and-protocols.md)。此处只保留来源，不再复制旧绿色卡片。

## 复评后的验证边界

完整九项顺刷通过，持续观察 519.97 秒到 next_expected=1002609，末次健康检查为 1036667 / HEALTHY / OPEN；两路 UDP Socket drops 和系统 RcvbufErrors 为 0。默认逐 Socket 请求 4 MiB，实际 rb=8388608；全局 rmem_default/rmem_max 仍为 212992。构建器运行 193 项测试，184 通过、9 项因缺 Documents 跳过；这 9 项已在 .111 单独通过。IGMP 9 项替身回归覆盖预存 GAP、健康等待失败及恢复失败；复查仅 GET 当前状态，不再重复首单文本。桌面和移动网页只读检查通过，能看到本单回执。

这不是孤立变量性能 A/B，也不是完整 6.5 小时回放验收。旧运行为何没有触发，缺少当时负载/调度证据，仍未确定。课堂配置/成员展示使用 `--display`，第三部分自动前置检查继续使用默认严格模式；不扩展为第三部分或全课程新版本通过。
