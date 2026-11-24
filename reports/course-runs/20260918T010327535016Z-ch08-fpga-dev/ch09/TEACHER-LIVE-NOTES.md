# 第09章分步演示：教师说明

2026-09-17 当前课堂约定：沿用第七章，**正常丢包后保留 GAP，由老师在网页手工恢复**。本轮真实过滤 RUN：`20260917T103243Z-10-rtl-stages`，丢弃序号与缺失序号都是 191，数量1，API拒单；审计入口 `20260917T101303Z-08-09-live-review`。

## 分步课堂运行

| 入口 | 本步行为 | 停顿状态 |
| --- | --- | --- |
| `08a-prepare-rtl-filter.sh` | 实编译、六项自测，组播 A 经模型后转本机单播；验证健康后暂停 | PREPARED |
| `08b-arm-rtl-filter.sh` | 发令额度1、短暂播放、捕获 GAP 后暂停 | GAP_CAPTURED |
| `08c-verify-rtl-filter.sh` | 核对序号/数量/拒单，再停 adapter、清控制文件、归还 direct 接收，保留 GAP | GAP_HELD |
| 网页“重新开始并清空交易” | **老师亲自点击**，新会话重建行情 | HEALTHY / OPEN |
| `08d-restore-rtl-filter.sh` | 只读验收新会话、原模式、网络与订单簿前进，不重播、不下单 | RESTORED |

`08c` 先执行 `verify`，再执行 `hold`；后者通过原有进程身份检查停止 adapter，用 `feed-guardianctl.sh direct --defer-feed-check` 归还接收路径。它不重播、不重启 Guardian，不等待旧缺口自行变健康；退出前确认 session、缺失序号、GAP、PAUSED 均保持。正常结束释放守护锁与过滤进程，网页手工重启才不会被拦住。

本次准备、发令、核对及撤出已按绿卡通过，六项自测和真实网页 GAP/禁单都已核验。手工恢复与最终只读验收的最新状态见审计报告；不能用下方旧版两笔成交记录冒充本轮验收。

## 正常阶段与维护恢复

正常讲解不设观察截止时间。`GAP_HELD` 表示过滤已撤出、缺口保留；它是守护终态，不能被定时恢复。只读验收失败保持原状态，不代替老师重播或下单。开始下一轮前要求 HEALTHY / OPEN。

单条设备动作失败或中断仍有异常回切保护。若在准备/发令中途需要提前结束，使用下面的**教师维护入口**；它可能重播，正常课堂不执行：

```text
python3 Documents/newDoc/assets/09-verilator/live-support/stage-session.py restore
```

`hold` 撤出失败记 `HOLD_FAILED`，停止自动恢复，保留日志供显式维护；不能为了报成功而清掉缺口。旧全自动维护入口、旧 RUN 后缀与共享锁名保留兼容，不属于学生顺刷入口。

共享网页检查核对现役 GAP/STALE 样式及 `orderUnavailable` 按钮保护，并明确标记 `DEPLOYED_SOURCE_AND_API`；实际浏览器截图另存于审计目录，不能把字符串检查当截图。离线回归包括当前网页保护、破坏保护的反例、阶段停顿、手工恢复、A/B/DUAL模式与重复发令限制。

## 教师恢复清单

正常流程先核对过滤程序/control已退出、direct接收归还、原模式已恢复且仍GAP/PAUSED。老师网页重启后，08d只读检查新会话HEALTHY/OPEN/PLAYING、SFC/READY/sfc、接收器与建簿程序在线、两股五档齐全且序号前进；同时核对工具口归还与临时VLAN消失。当前课堂不发送两笔恢复验证订单，按本次回执验收。

## 历史实现与实测记录（以下保留旧版行为，不替代上面的现役流程）


2026-09-17 兼容更新：第09章准备/动作入口接受 A/B/DUAL 原模式，实验选择 `MULTICAST_A`，adapter仍接收 `233.74.125.32:31032`，统一接收器退出 A/B 订阅以免副本绕过。核验器接受 A 的新名称及旧别名、拒绝 B/DUAL；恢复保留原模式和播放状态。隔离阶段测试、十组模式/播放组合的真实恢复函数回归通过，未重新执行本章实机四步；下方真实回执保持原值。核验见 `Documents/design/evidence/ch07-09-multicast-compat-20260917/check.json`。

2026-09-07 · DEC-387 · 当前完整实跑 `20260907T152509Z-10-rtl-stages`：四步全部通过，三次120秒课堂停顿，RESTORED/last_exit_code=0，无补救cleanup。初始额度0、策略丢0；RTL丢220=Feed缺220、gap1/API400；恢复0612260010、HEALTHY/OPEN、两笔成交、AAPL1→1。正文四段逐字来自本RUN，GAP网页另有实际截图（总RUN142544Z/browser/10-rtl-gap.png）。输入为第二章144050Z平台，未补编译业务应用或替换GUI；130101Z/051442Z及后文记录均为历史。


> 历史记录：2026-09-07 · DEC-376 · 当时最终版四步在051442Z一次完整通过，含真实课堂停顿；正文四个输出块逐字采用本次display回执。045433Z保留为修复过程证据，024814Z保留为旧完整流程证据。


## 历史分步课堂运行

用户要求按准备、发令、核对、恢复逐步贴命令。现役课堂入口为 `08a-prepare-rtl-filter.sh`、`08b-arm-rtl-filter.sh`、`08c-verify-rtl-filter.sh`、`08d-restore-rtl-filter.sh`，每个只进入一个前台阶段；旧 `08-rtl-filter-live.sh` 兼容文件名只进入准备，不再自动跑完整流程。

| 阶段 | 做什么，停在哪里 | 正常完成状态 |
| --- | --- | --- |
| prepare | .2 构建与六项内部自测；默认额度0启动adapter，接真实行情，确认无策略丢包、HEALTHY后暂停重放 | PREPARED |
| arm | 核对同一正常会话与进程；向控制文件写block，确认程序已消费；立即RESUME，在5秒额度有效期内触发丢包，捕获GAP后PAUSE | GAP_CAPTURED |
| verify | 读当前暂停会话与日志，对照丢弃序号/缺失序号/数量1，并检查拒单与GUI合同；不再给额度或恢复 | VERIFIED |
| restore | 停止本RUN进程、清控制文件，恢复原发送/接收方式，重放恢复HEALTHY，检查两笔成交与持仓；恢复原播放方式 | RESTORED |

`stage-session.py`（281 行）负责持久状态、顺序、共享锁、独立恢复守护和退出状态；`stage-actions.sh`（141 行）执行本步的SSH/API/构建与恢复；`stage-output.py`（136 行）验证回执再生成摘要；`remote-control.py`（119 行）部署在本次.2目录，校验PID/启动时刻/boot ID/完整可执行路径后操作本RUN进程。以上均在 `live-support/`。每步入口依赖这些教师运行工具，原理图与正文给出当前小步的作用，不把几个标题放在一条自动全流程入口上。

- 执行位置：跳板机；构建与过滤在 `.2`，GUI/API 仍为 `.101:8088`。前置为第二章完整平台已在线、前序实验已恢复、.2工具准备通过、原路径归还，以及.11/7150管理检查可用。新控制器不改变RTL、adapter或5秒策略有效期。
- 同一次实验：只在prepare实际开始时生成`…-10-rtl-stages`，指针是`Documents/reports/run-state/ch10-rtl-stages.json`，状态是RUN目录的`session.json`，记录原模式/播放状态、阶段、守护身份、期限与`last_exit_code`。不靠跨Shell环境变量或手填示例RUN接续。
- 停止条件：正常步骤完成后前台退出，后台持有共享`/var/tmp/flle-ch08-10.lock`。PREPARED/GAP_CAPTURED/VERIFIED是正常讲解停顿，不设截止时间；继续时核对进程、会话与暂停状态。前台动作仍有执行超时，异常中断遗留的执行中阶段也保留恢复期限；异常只执行cleanup，不自动进入arm/verify，也不发送恢复验证订单。该守护依赖跳板机存活与管理网络，不能抵御整机掉电或长期失联。
- 顺序与重复：arm仅接受PREPARED，因此不会重复发令；verify可在GAP_CAPTURED/VERIFIED重复读取同一暂停现场。restore可提前结束任何未完成阶段；成功后的重复restore只报告结束，不再次下单。守护丢失时禁止继续发令；恢复可在重新取得全局锁后接管。前一实验未结束时禁止创建新prepare。
- 失败：前置所有权检查通过后才写`armed`标记，之后失败/中断尝试cleanup；恢复不成功记RESTORE_REQUIRED，不能冒充结束。恢复验证订单失败时只恢复网络，不自动重发订单；保留失败回执与RESTORE_REQUIRED，须核对订单及持仓后由教师处理；此时重试恢复入口只恢复网络，不重发验证订单。信号、超时与设备错误使入口非零退出，成功为0；每步状态保存本次退出状态。
- 中途关掉终端后，直接贴运行④恢复；不要重新贴运行①或再次发令。prepare单次执行上限420秒，其余阶段150秒；这与正常讲解不限时是两回事。
- 发令摘要显示`control_consumed=block`，表示adapter已读取指令；额度日志`adapter_arm remaining_drops=1 ttl_ms=5000`保存在本次`raw/adapter-armed.log`，不冒充终端摘要。
- 文件发令：控制辅助程序做的核心动作仍是把`block`加换行写到`/var/tmp/flle-market-filter.cmd`；先核对进程身份，用独占创建避免覆盖未消费指令，并等待文件被adapter读取删除。辅助程序的成功返回仅说明已消费；丢弃次数与序号还必须由日志核对。
- 证据：各步原始文件在同一RUN的`raw/`，完整阶段日志按尝试时间另存，重复查询前把已有短回执保存在`raw/history/`，源码及二进制分别在`source/`、`artifacts/`；每步更新含session.json的SHA256SUMS。远端本RUN文件保留用于审计，正常恢复只停止进程、清控制文件，不宣称删除了远端构建目录。
- 验证范围：最终版08a→08b→08c→08d在20260907T051442Z-10-rtl-stages一次通过，中途未改源码；前三步后各停顿约133/101/102秒，接续时会话/行情状态一致。正常等待无固定期限的逻辑另有超出旧期限的隔离测试；有限现场停顿不能证明无限时长或跨重启接续。

## 历史051442Z四步实测与当时正文回执

本次目录：`Documents/reports/course-runs/20260907T051442Z-10-rtl-stages/`。四个前台入口均退出0；全程使用同一套最终源码，无临时补救。前三步后暂停供讲解，分别约133/101/102秒后继续，未提前恢复或重复发令。

- prepare：六项自测通过；session0612260125、next_expected193、额度0、策略丢包0、HEALTHY/OPEN。
- arm：终端实际显示control_consumed=block，完成短暂重放后再次暂停。
- verify：DROP194=next_expected194、gap1、API400/FEED_NOT_HEALTHY，保留同一暂停会话。
- restore：session0612260126、HEALTHY/OPEN、UNICAST/PLAYING；两笔ORDER_EXECUTED、AAPL10→10，adapter/control清除、交接检查通过。

本次清单共184项，逐项验证通过；SHA256SUMS文件摘要为`19ced284f2663607bf8d05d5d75d2ff870822a6bf8053146af7e4cef405e2bb3`。阶段动作日志约27.13/1.64/0.59/23.09秒，另计上述课堂停顿。

正文四个输出块分别逐字取`raw/prepare-display.txt`、`arm-display.txt`、`verify-display.txt`、`restore-display.txt`，保留四行头、零丢包计数及末尾停顿/恢复提示；开头的运行中进度提示不属于这些摘要文件。构建、原始日志、订单、接续快照及按阶段封存的源代码在同一目录，核对摘要不能替代读取原始证据。

## 暂停现场的恢复修复

20260907T045433Z-10-rtl-stages：运行①六项自测和默认放行通过；运行②/③保留session0612260123、DROP198=next_expected198、缺口1、API400。运行④先停adapter，再调用Guardian工具；旧工具会等待已收到行情，但重放仍PAUSED且RESTART在它之后，导致超时。它还把超时状态重定向到/dev/null，完整日志因而为空。

现使用`feed-guardianctl.sh direct --defer-feed-check`先确认接收进程就绪，然后RESTART，再严格核对新会话HEALTHY与实际序号。prepare的接收程序设置同样先不等包，再启动adapter和重放。该选项只推迟收包验证，不能作为行情已恢复的证据；其他调用者不传选项时仍执行原有严格验证，失败会打印最后状态。阶段脚本也记录失败行号和状态码。

修复后同一RUN的恢复成功：session0612260124、HEALTHY/OPEN、UNICAST/PLAYING；两笔ORDER_EXECUTED，AAPL10→10，adapter/control清除，handoff通过。失败回执和修复后的回执分开保留。课堂停顿无限等待的后续变更仅做隔离测试，没有重发block或重复恢复验证订单。

## 分步入口的离线检查记录

2026-09-07：`live-support/test-stages.py` 用临时目录和模拟动作运行真实阶段控制器/守护进程，覆盖四步独立退出、共享锁跨步骤保留、越序拒绝、重复arm拒绝、重复verify和幂等恢复、失败与空闲恢复、守护丢失接管。合成回执测试拒绝序号不一致、额外DROP、会话变化、未暂停和持仓不平；进程测试只操作测试创建的sleep子进程，验证身份不符拒绝、已匹配进程停止、未消费指令不覆盖，以及正确写入block并等待消费。恢复订单验证失败后再次恢复只调用cleanup，未再次调用发送订单的restore动作。

两项共享检查器通过：第十章5执行卡/8模拟卡/6图，输出检查13个脚本的58个printf块及4个新阶段摘要头。CommonMark实际解析正文28代码块/21加粗，Bash与Python语法、本地链接、两层图片摘要及diff通过；控制SVG在800/1200px审图，几何/箭头与修改前一致。原RTL/adapter、旧104行完整流程、硬件命令与04/08/09章正文未改。以上没有执行SSH/API或新现场RUN，不等于新分步实测。

## 历史教学调整与旧完整流程

DEC-368（2026-09-07）：运行①改“用真实行情验证过滤程序”，前文RTL/额度/block接真实行情；先讲接收少消息为何能验证过滤，再定义Feed/GAP。学生图由跨章位置比较换成发送/过滤/接收对账示意，维护接线移本文件独立节。原命令、原始输出、运行态与历史证据不改，图中101/102/103不能用作现场参数；实际读数仍按本次日志核对。

DEC-366（2026-09-07）：原Ready/Valid图明确上方手写C++接收/保存/按判决发送原始报文，下方生成模型读取消息副本、返回判决并保存剩余额度与累计丢包数。ready的定义是准备好接收；源码assign按cfg_load_valid直接算ready，只有判决/额度等保存状态在上升沿更新。向学生解释cfg_load_valid时说“设置或清零丢包额度”，不只说“写配置”。八箭头遵DEC-365，围栏/源码/运行态不变，无新实验。

DEC-364（2026-09-07）：第二组改“控制接收与丢包”，同步大导航、任务地图和两张导航卡。原Ready/Valid图先画消息与状态的归属，再画clk的0→1更新点，最后画首条命中、清valid、第二条命中的额度变化。讲清每次武装给一次额度，一个模型依次处理，并非多个CPU通知；remaining_drops是剩余可丢数，drop_count是已丢数。RTL节选前补SystemVerilog紫卡，解释外层always_ff/posedge与生成模型的关系；代码和运行流程不变，无新实测。

统一任务是过滤现有交易系统中的NVDA Type A行情：Locate8095、Stock为NVDA加四个空格、额度1。当前模型丢行情后，Feed Guardian检出缺口并阻断下单；没有实现按证券解析/丢弃OUCH订单包。

现役正文先讲字段、一次额度与文件发令，再按准备工具、运行①准备、②发令、③核对、④恢复推进。①的自测不需要行情；接流验收后暂停，教师自行决定何时贴下一张卡。课堂入口与停顿/异常恢复合同见本文件“分步课堂运行”。

历史一键长流程保留在`live-support/run-rtl-filter-live.sh`（104行），不作为现役课堂入口；现役分步流程读取第二章平台运行态、market_filter.sv与mold_filter_adapter.cpp；.2构建、自测并运行模型；跳板机只上传源码、取回证据副本。前后仍用bridge交接门只读检查.11与7150，不能因本章模型不经过它们而移除管理依赖。失败时EXIT trap尝试清策略/恢复原模式、停止adapter并恢复direct Guardian；按当次完整回执确认恢复结果。

## 控制指令与输入边界

分步入口与图对应：运行①在.2启动mold_filter_adapter；老师讲完后，运行②通过remote-control.py写入控制文件。进程里的C++读取block并调用load_remaining给模型一次额度。正文的printf是该写文件动作的Shell表达；两个阶段之间有课堂停顿，发令不重启过滤进程。

本节承接从学生正文移出的实现细节；课堂先按三阶段图理解过滤行为，定位源码或解释日志时再核对以下项目。

| 来源与名字 | 具体作用 |
| --- | --- |
| live脚本的`FLLE_FILTER_MODE=allow` | 以默认放行启动adapter，模型实际丢包额度为0 |
| live脚本的`FLLE_REMAINING_DROPS=1` | 预备一次丢包数量；启动时不因此直接丢包 |
| adapter读取的`block`指令 | 调用load_remaining给模型装入1，并开始本次有效期 |
| adapter读取的`allow`指令 | 给模型装入0，撤销丢包机会 |
| 模型输入`cfg_load_valid` / `cfg_load_drops` | 表示本次额度设置有效及要写入的数量；设置时s_ready为0，优先保存额度 |
| RTL的复位与内部状态 | 复位清零额度、计数和判决；命中且有额度时消耗一次额度，输出丢弃判决 |
| adapter的`POLICY_TTL` | 用steady_clock设定5秒有效期；收到block后重新计时，过期时调用load_remaining清零；不是RTL内部硬件定时器 |

adapter通过socket订阅固定组播和端口，recvfrom来源核对20.1.1.1；仅Message Count=1、总长符合、内层长36字节且Type A的消息被复制给模型。其它收到的报文直接转发，包括来源不匹配、短报文和多消息包；这里仅指该 socket 实际收到的报文。现役重放一包一条消息，多消息Mold包整包放行，不做拆分过滤；本课模型不是通用ITCH parser。历史字节样本只用于字段核对，不是现役live输入。

来源：`live-support/run-rtl-filter-live.sh`的启动/发令段，`mold_filter_adapter.cpp`的run_adapter/load_remaining与POLICY_TTL，`market_filter.sv`的assign/always_ff。整理只改变文档位置，未执行任何控制指令，也未修改超时值或输入条件。

## 运行接线与维护前提

以下保留旧完整流程的接线依据；当前四阶段入口、暂停点和恢复行为以上面的“分步课堂运行”为准。

运行①的学生入口为`08-rtl-filter-live.sh`，内部exec完整`live-support/run-rtl-filter-live.sh`（104 行）。输入仍为第06章已保存运行态及本章market_filter.sv/mold_filter_adapter.cpp；必须已有可工作的行情/交易系统，目标.2工具准备完成。主线用中文任务解释本次做什么，具体维护依赖在此核对。

- 脚本在跳板机执行，借管理连接操作.2；前后check-filter-handoff.sh bridge仍检查.11与7150是否归还网口与VLAN20。开始前要确认已退出前一轮过滤实验、原网络路径恢复且.11/EOS只读管理可用。它们是复现实验的前提，不是本次RTL的报文处理路径。
- GUI/API沿用第二章一次部署的`http://10.1.1.101:8088`；编译、自测、过滤进程与Guardian接收均在.2。脚本调用API控制.1的行情重放并读取观察结果，没有迁移GUI。
- 让Guardian临时退出原组播，只收本机42121；adapter订阅233.74.125.32:31032，将放行报文的UDP载荷原样转发至42121。这样被丢弃的消息不会经原组播再补给Guardian。日志中Exchange=MULTICAST/Guardian=UNICAST正是当前软件接线，不要求真FPGA也改成UNICAST。
- 初始内部自测以`--selftest`运行，无须.1先发送行情；通过后启动adapter并接入真实重放。`rtl_selftest`证明确定性输入下的规则，后续`rtl_drop`与Feed缺口才是实际交付的对账；两者不能互相代替。
- 入口创建当次RUN目录，完整回执在`Documents/reports/course-runs/<本次RUN>/raw/`；记录源码与制品，前后检查及完整编排保留于同目录。EXIT/INT/TERM时尝试恢复，不把trap存在当成恢复成功证据。
- 收尾核对：控制文件和adapter进程消失，Guardian回到direct profile，行情恢复实验前模式；新Session为HEALTHY，两笔Socket/SoupBinTCP/OUCH验证订单成交，AAPL持仓前后相等。必要时查看feed-guardian-restored.txt和恢复订单原始回执。

原[XDP、软件模型与真卡位置参考图](../../images/course-visuals/09-diagrams/09-simulator-versus-real-card.svg)撤出学生运行①，保留用于教师比较实现位置；它不代替正文对手写C++收发与生成模型判决职责的准确划分。学生运行图仅说明丢弃/缺失序号如何核对，101/102/103为解释用示意，不能写入RUN或作为实测结果。

## 历史自动恢复清单

学生正文只交代“行情与交易恢复、临时过滤退出”。完整实验的维护收尾还要检查：行情恢复本次原模式（本次为 UNICAST），Feed Guardian 为 direct / HEALTHY，交易 profile 为 SFC/READY/sfc；`.2` 无本课 XDP、adapter/control 残留，`.11` 无 XDP/BMv2，7150 无 VLAN100/200，相关接口归还 VLAN20。以本次 run.env、handoff-after、Guardian 恢复文件和两笔订单原始回执核对，不能用上次记录证明当前机器状态。

## 实际打印与历史依据

`live-support/classroom-output.py`（40行）从命令输出中提取课堂字段：构建过程只显示rtl_selftest行，Feed、拒单、界面检查和恢复订单按短字段显示。每个管道先由tee保存完整原文，再调用格式器；没有修改JSON文件或后续断言的输入。缺失/损坏字段直接报错，不补默认成功值。新运行将把格式器源码一并封存。

DEC-373时的正文样例曾取自 `Documents/reports/course-runs/20260907T024814Z-10-rtl-filter-live/`，现已由上面的051442Z四份摘要接管；以下保留旧证据说明。旧样例按“自测→丢包对账→恢复”摘录，非逐行完整终端转录。`source/` 中的 RTL、adapter、主流程、格式器与对应保留源码逐字一致；旧104行完整流程仍保留，课堂已不调用。用归档格式器读取归档 raw，核对正文自测/Feed/拒单/成交字段，adapter 四行日志也一致。

- 准备 A：`20260907T023201Z-10-verilator-toolchain-prep`，目标 `.2`，EXIT_CODE=0，APT 新增/升级均 0；3 项清单核验通过。清单 SHA-256：`c5b7dadf3ffdda392d19878bbd299293414ee53b87b364883ab69f3d21499443`。
- 完整接流：六项自测 PASS；`rtl_drop sequence=579` 与 `feed-gap.json` 的 `next_expected=579` 相等；drop_count/gap_size 均 1；缺口 Session `0612260119`；订单 API 400 / FEED_NOT_HEALTHY。
- 恢复：Session `0612260122` / HEALTHY / OPEN，两笔 ORDER_EXECUTED，AAPL 10→10；handoff-after 显示 adapter 进程不存在、控制文件不存在、原网口与交换机状态归还。
- 完整 RUN 36 项清单核验通过，清单 SHA-256：`5f7416d5d2ec3ba75f8a978bbdfee0a16d7e12add967bf653d7adf0984d339c1`。二进制 SHA-256：`7cadf97da4e0f6f78dfdb2decd8c522dd1407d623bbf9446df27c278f525d1a3`。
- 证据限制：live 的 `run.env` 没有 EXIT_CODE，目录未封存完整终端末尾 PASS 行。此处依据原始业务/恢复回执、清单与封存流程核验完成情况，不能声称读到了缺失的退出码；清单存在本身也不等于成功。本轮不修改已实测脚本或补造归档值。

此记录接管 DEC-361 当时“新位置完整 live 待验证”的状态；旧运行仍按原日期保留，不改写为新实验。本轮只是核验已经存在的回执，未创建 RUN、控制发包或重新下单。原始 RUN 目录默认被 Git 忽略；跨快照事实以本文件与 PINS 的路径、摘要和范围为准，原始证据的另行保存由用户管理。

DEC-360 曾把旧流程构建主机正确显示为 Low-Latency-Ops（.101）。DEC-361 按用户要求迁移实际编译到 .2，当前标题为 vm-2522-02；不是改标题冒充迁移。旧 .101 准备/构建记录保留原日期与内容，退役的 01/08-itch-pipeline 脚本也保持历史身份。`.101:8088` 仍为现有 GUI/API；此次没有迁移控制服务。

## 真卡部分的范围

U250/OpenNIC假设仍完成同一条NVDA过滤任务。正文保留四步与关键图：独立100G台架、DMA前过滤、待补packet wrapper/控制接口、Vivado构建、JTAG/Flash装载与业务验收。详细板级条件移入[HARDWARE-NOTES.md](HARDWARE-NOTES.md)。本课没有完成该wrapper、BAR地址映射、硬件超时、构建镜像或板上验证；不得把教学模拟输出登记为加载/线速成功证据。

## DEC-360 历史验证（2026-09-06）

- 两项共享检查器：`verify-filter-course-cards.py`与`verify-filter-output-labels.py`；第10仍为2绿卡/6图/7导航。
- 用8份历史输出覆盖全部格式器分支；空输入、缺字段和无效JSON均非零退出。隔离的tee管道验证完整raw字节保留，正文5段摘录与实际printf/格式器逐字一致。
- 归一化去掉打印与来源封存变更后，主流程与修改前相同；RTL、adapter与工具准备源码未改。未重新编译模型或执行现场实验。
- SystemVerilog关键行回源、标题与导航、Markdown加粗/图框/相对链接、SVG/XML/800px审图与图片摘要检查。

用户逐节审阅时优先看：开场是否分清语言/模型/芯片；握手比喻是否直观；一次完整自动运行的课堂节奏是否合适；真卡四步是否需要展开某条命令。运行时序若要拆成独立脚本，需要另做持久运行态和恢复验证，不能只把文档拆卡。

## DEC-361：角色总图与目标机编译（2026-09-07）

- 章首用一张图区分 SystemVerilog 语言 / RTL 电路描述、Verilator 的 C++ 软件模型、FPGA 配置硬件。按用户要求采用总图开场；原收包位置对照图移到运行①，替换重复的接流 Mermaid。硬件装载图留在行业延伸，展开 bitstream 的 JTAG/Flash 去向。正文现为2绿卡/7SVG/7导航，图目录10图。
- 准备A只在 `.2` 安装固定 Verilator 4.038-1；实测 `20260907T003012Z-10-verilator-toolchain-prep`，APT 新增1包/升级0包/删除0包，g++/make已有，EXIT_CODE=0。原始版本及安装全文见该RUN的raw/result.txt；准备卡和asset逐字同步。最终准备卡用子shell隔离EXIT trap，`20260907T003435Z-10-verilator-toolchain-prep`按source方式再次实跑rc0，APT新增/升级/删除均0，调用者shell继续执行。
- 独立构建 `20260907T003217Z-10-rtl-target-build` 直接提取现役live脚本的mkdir→上传源码→构建/自测→取回证据→目标机内复制段，在 `.2` 执行。6/6自测通过；目标机复制后的可执行文件再次selftest通过，字节比较一致。产物SHA-256=`7cadf97da4e0f6f78dfdb2decd8c522dd1407d623bbf9446df27c278f525d1a3`；运行与远端清理均rc0。验证入口、源码、工具版本、raw与产物留在该RUN，run-state/10-rtl-target-build.env记录范围。
- 该独立验证仅调用 `--selftest`，在adapter打开socket前返回；未运行接流段、切换Guardian/行情、武装丢包或下单。在该次独立验证结束时，新位置的完整live流程仍待运行；09-05读数不能标为09-07全流程PASS。后续024814Z完整接流记录现已回源核验，见上面的“实际打印与历史依据”。
- 编译器装在目标机是本课程的部署选择，不是Verilator硬性要求。真卡仍需完整板级工程、Vivado、配置文件和上板验收，不能把CPU可执行文件装进FPGA逻辑。
- 原始RUN目录与run-state默认被Git忽略；需要跨远程快照保留原始证据时由用户显式纳入。小型事实、范围、路径与摘要已写回治理记录，不依赖/tmp或会话记忆。

## DEC-362：删除独立输入分类节，改用具体内容标题（2026-09-07）

用户无法理解“推演”与“真实输入与自测”为什么要单独存在。删除旧A节点，B/C/D改为“按字段识别 NVDA 行情”“接收一条消息，只丢一次”“启动后放行，发令后丢包”；导航减为6项，四组/两绿卡/七幅SVG不变。原适配程序检查与旁路边界移到放行节，历史字节样本留资产表，自测说明归运行①。字段节先讲规则，明确展示代码是SystemVerilog，并解释取位、assign、比较符号与定宽常量；后一个代码块同样标清语言和寄存器更新。正文旧“.101自测”残句随自测段迁移一并修正。所有非Mermaid代码/输出围栏和脚本、RTL/adapter、图片字节均保持本轮修改前内容；本轮无设备操作或新RUN。

## DEC-373：按学习依赖顺稿与复用方法（2026-09-07）

正文沿认出目标、一次额度、启动与文件发令、实际结果、硬件迁移展开。先定义 Type A/Locate/额度，再看字段代码；明确 20 字节 Mold 包头之后还有 2 字节消息长度，才到 36 字节 ITCH，未照抄评估中遗漏长度的简化。握手图放在展开文字前，ready 组合变化与时钟沿保存状态分开。硬件仍用 Shell，解释源码/产物两次复制及后续引用，并补固定版本首次装载暖重启；插件和管理工具仍未实现。

写作方法保存在仓库 `.agents/skills/flle-course-flow/SKILL.md`，AGENTS 已链接：什么时候解释、什么时候画图、怎样接续上下文、怎么讲命令与证据。正文六图各自负责总览、构建与运行、交付与状态、文件发令、结果对账、真卡路径；本轮图文件未改。维护状态移到本文件，理解检查只考正文出现的内容。

收尾检查：skill-creator quick_validate通过；两项课程检查器通过（2执行卡、8模拟卡、6图；13脚本68输出块）。CommonMark正文解析22代码块、20加粗，本地链接与Shell语法通过；两处RTL节选回源、所有Bash/SystemVerilog围栏与修改前逐字一致。归档格式器的自测/Feed/拒单/订单四组及adapter日志第五组均与正文吻合；git diff确认运行源码、SVG与归档未改。
