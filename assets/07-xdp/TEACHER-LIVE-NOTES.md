# 第07章运行④/⑤：教师维护与网页手动恢复说明

## 2026-09-17 · 现役入口编号修正与共享锁兼容

准备A、运行①②③的四个现役脚本已改为生成 `07-xdp-*` 新目录；运行③的调试路径改成 `/flle/ch07`，Clang打印完整实际参数，`查 C / 查 BPF / 查 ELF` 标题补空格。现役运行④本来就使用 `07-xdp-drop`，无需改RUN身份。下方“仍沿用08”的顺稿记录是本轮修复前的历史状态。

原绿色入口已实跑：准备A `20260917T081424Z-07-xdp-toolchain-prep-NJQcpB`（复用现有版本，无安装），① `20260917T081349Z-07-xdp-readiness`，② `20260917T081317Z-07-xdp-bounds`，③ `20260917T081347Z-07-xdp-build`，均退出0、摘要通过。新对象SHA为 `26930b08…dd1f0e3`，与旧对象的 `xdp / .maps / .relxdp / license` 段逐字一致；变化仅为调试路径相关内容。正文运行③的历史分区读数仍有效，未改历史归档或假装本轮又做了丢包。

运行④及备用重启共同调用 `acquire_filter_lock`：先持有中性锁 `/var/tmp/flle-market-filter.lock`，再持有兼容锁 `/var/tmp/flle-ch08-10.lock`。两者均非阻塞获取，退出释放；不得删除或重命名已有锁文件。兼容锁确保仍用旧名的同跳板机P4/RTL/交易重置以及旧XDP进程与新入口互斥，不能把它视为漏改编号。23项丢包/恢复前台回归（含3项新旧锁互斥）及6项准备卡回归通过；本轮未新挂载或注入丢包。

明确列为RETIRED的旧桥接、SPAN、固定输出脚本继续保持历史RUN名和路径，不进入绿色卡链，也不因为这次命名修复重新成为可用实验。第08/09章代码与实验仍暂停。证据：`refs/evidence/ch07-entrypoint-numbering-20260917/check.json`。

用户随后要求“先看结构，再运行打印源码”：现有安全检查/过滤流程图及解释已放到运行②绿卡紧前，随后是脚本入口和真实源码摘录。图字节和其余讲解保持。

## 2026-09-17 · 适度顺稿与输出来源

本次只调整第07章阅读顺序与展示：环境图前移、准备A先图后词、收包比喻归运行①；运行②先查看源码，再解释动作/字段/map/策略，map说明先于BLOCK。三张源码到内核的步骤高亮图继续保留。运行③实际编译并检查对象，运行④从相同源码重新编译后挂载；⑤以HEALTHY/OPEN和订单簿恢复更新验收，不增加试单。五段实跑输出原文不变。

准备A、运行①由正文内联代码改为调用现有 `00-xdp-toolchain-prep.sh`、`01-xdp-hook-readiness.sh`；修改前已逐字核对两份内联代码与资产相同。未改脚本、C程序或图片字节，未操作设备。终端“接收程序 ONLINE”来自 `wait-feed-state.py` 输出的 `trader_auto`，此轮对应 `feed-guardianctl.sh` 启动/复用的只建簿Guardian；网络收包与feed完整性仍由共用接收器提供。

移出学生主线的准备/只读检查来源仍保留：

| 输出 | 原始记录 |
| --- | --- |
| 准备A版本检查 | `reports/course-runs/20260907T151613Z-08-xdp-toolchain-prep-gI3q0t/raw/result.txt` |
| 运行①接口检查 | `reports/course-runs/20260905T111619Z-08-xdp-readiness/raw/result.txt` |
| 运行②带行号源码 | `reports/course-runs/20260905T112542Z-08-xdp-bounds/raw/result.txt` |

`00/01/03/04` 现有脚本生成的RUN标签仍沿用 `08-xdp-*`，运行③调试路径映射仍为 `/flle/ch08`；它们是章节前移后的内部命名遗留，不改变过滤目标或步骤执行。本次顺稿不重命名运行记录或修改脚本。正文与流程图展示核心Clang参数，并明确省略调试路径归一化选项；后续若清理命名，应单独核对脚本测试和产物摘要，不改历史RUN。`查C / 查BPF / 查ELF` 也是现有脚本的打印标题，本次正文版本节选只保留实际命令与版本，原始日志未修字。

本轮文档核验：`refs/evidence/ch07-reading-flow-20260917.json`。正文移出的[用户空间/内核/硬件分层图](../../images/course-visuals/07-diagrams/07-ppt-s04-kernel-layers.png)保留作教师补充；实验环境图继续在章首。

## 跨章比较补充

第07章在XDP入口执行软件过滤，第08章把同一任务接入FPGA电路。两者都要核对目标字段、一次额度和恢复；U250先以仿真与构建结果为证据，再单独验证实卡。

进一步阅读：[第08章：FPGA——从过滤代码到板卡与交换机](../../08-fpga-from-code-to-device.md)。[旧三章执行位置图](../../images/course-visuals/07-diagrams/07-09-execution-comparison.svg)保留为历史参考，图中章号不再代表现役目录。

## 2026-09-17 · A/B 模式兼容与重刷接续

终端展示由 `live-support/format-xdp-result.py` 按真实字段生成：接口仅摘原生接口/程序两行，行情转为中文字段表，丢包对账列出双方序号。完整JSON和原始对账仍存raw，原断言与pipefail保留。最初以用户 `20260917T073502.386920713Z-07-xdp-drop` 的记录（Sequence643）核对格式器。

正文当前样例更新为用户随后实跑 `20260917T074307.428975746Z-07-xdp-drop`：程序40，会话0612260007，基线下一条期望113；缺口646→647→648，丢1包且Sequence=647、Locate=8095，卸载后GAP/PAUSED。正文保留挂载与初始策略、健康基线、缺口、对账、最终状态五段。31项归档SHA通过，格式器回放与正文逐行对应；初始 `policy_id=7 mode=allow remaining=0 ttl_seconds=0` 来自用户同轮终端粘贴，原脚本未把该行单独落盘。下方626截图属于历史轮次。本次仅扩充文章，未改脚本或重新触发丢包；核验见 `refs/evidence/ch07-expanded-live-output-20260917.json`。

运行④接受 `MULTICAST_A / MULTICAST_B / DUAL`，并保留 `MULTICAST / UNICAST` 旧模式兼容；实际过滤固定选择 A，C 规则仍匹配 `233.74.125.32:31032`。正常④继续停在 GAP_HELD，不自动恢复；教师完整恢复入口可还原保存的原模式。失败现在打印阶段及对应日志末尾。

`.111` 保留但目标机重建时，旧丢包指针可能属于另一平台。入口先核对新平台控制器身份、健康行情与接收口无过滤，再将旧指针归档到原 RUN 的 `platform-replaced-*` 子目录；原 run.env/state.env/证据不改，不将旧实验标为恢复成功。当前平台仍有 GAP、身份不符或未知过滤程序时保留指针并停止；同平台重复运行继续等待网页人工恢复。跨平台的完整服务重启仍禁止。

原绿色入口实跑 `20260917T073039.110571425Z-07-xdp-drop` 退出0：旧平台记录自动归档，Native XDP/JIT 挂载成功，恰好丢1包，Sequence 与 Feed next_expected 均647；XDP已卸载，现场保留 GAP/PAUSED。证据索引：`refs/evidence/ch07-09-multicast-compat-20260917/check.json`。

运行④只注入一次丢包并保留网页故障；运行⑤由用户在网页点击“重新开始并清空交易”。2026-09-14 用户已实跑④：Sequence与next_expected均626，丢包1，同Session保持GAP/PAUSED，本次XDP已卸载；30项归档SHA通过。用户先后提供缺口和手动恢复截图：红条消失，回放第7轮暂停→第8轮播放，订单簿恢复。随后只读查询确认恢复会话0612260008为HEALTHY/OPEN，并通过现役恢复条件及接收口交接检查；未验证恢复后的成交。[证据](../../refs/evidence/chapter07-drop-held-live-20260914.json) · [原终端记录](../../refs/evidence/chapter07-drop-held-live-20260914.txt)

原终端记录保留当时打印的重启脚本提示。当前入口已修正重复运行的门禁，并改为提示网页手动恢复；原实跑归档的8份源码曾与修改前一致，其中编排和运行态辅助现已更新，不能把原丢包证据当成新版本重复运行的设备实测。连续3轮使用本地API/SSH替身验证，16项测试通过；当前设备只验证了只读的恢复检查。[重复运行修复核验](../../refs/evidence/chapter07-repeat-after-web-recovery-20260914.json)

## 当前课堂步骤

2026-09-14 撤下只打印固定标签的 Python 步骤，运行编号调整为①入口检查、②查看 C 源码与过滤规则、③编译、④丢包并保留现场、⑤网页手动恢复。过滤条件表与配图归入②；脚本文件名保留原路径，与课堂编号分别维护，下方带日期的历史复核沿用当时编号。

## 运行③编译输出来源（2026-09-17）

正文 ELF 节选更新为用户执行 `04-xdp-build.sh` 的 RUN `20260917T071738Z-08-xdp-build`，原件为 `reports/course-runs/20260917T071738Z-08-xdp-build/raw/build.txt`。保留命令、文件格式、列标题与 `xdp / .maps / .BTF` 三行，只去行尾空白；编号与大小保持原值。三项归档 SHA 核对通过，源码摘要为 `7780bccc…dd7f54cd4`，对象摘要为 `03c12c4d…68042a0`。此记录只证明该次编译产物，不证明挂载或丢包实验完成；本轮编辑没有重新执行编译或操作设备。

## 编排与前置条件

运行④入口为 [05-xdp-inline-live.sh](05-xdp-inline-live.sh)，调用 [run-xdp-receiver-live.sh](live-support/run-xdp-receiver-live.sh)。它核对 `.2 ens64np1` 的 sfc、IP 与无其他过滤程序，使用已部署平台，编译并挂载本次 XDP，以零额度确认健康，再开放一次 DROP。

前置为第06章交还 `SFC / READY / sfc`、准备A工具齐全、8088和SSH可用、无其他过滤实验。运行③仍是独立编译观察，不是④的硬性前置。当前行情接收使用普通Linux socket；不外推到Onload、TCPDirect或DPDK接收路径。

运行④观察到GAP后发 `REPLAY|PAUSE`，暂停没有到期时间，避免行情自动循环后新Session清除缺口。读取XDP计数和审计序号，与Feed对账；随后只卸载本次程序，核对同Session、同缺失序号、`GAP / INHIBITED_FEED_GAP / PAUSED`，以 `result=GAP_HELD` 结束。它不再调用拒单测试、网页合同检查或恢复后的试单，不自动重放、不重启服务。

程序结束后没有维持实验的后台编排。正常完成已卸载XDP，暂停与行情缺口由现有服务保存，教师可停下来讲解。若外部操作恢复/重启回放或换了平台，故障现场也会改变；观察期间保持配置。

## 运行态与网页手动恢复

运行④实际开始才生成 `*-07-xdp-drop` RUN。取证目录为 `reports/course-runs/$RUN_ID/`，小型状态在 `reports/run-state/07-xdp-drop.env`，记录实验RUN、原平台RUN、原行情模式和阶段。正常结束为GAP_HELD。

运行⑤使用网页现有按钮“重新开始并清空交易”：前端请求 `POST /api/replay`，带 `action=RESTART, clear_trades=true`。网关清理模拟交易，从新Session重新回放；它不会完整停起交易所、网关等全部服务，也不自动恢复丢包前的行情模式。“继续”仅RESUME，不能补回缺失报文。正常丢包结束已经卸载本次XDP，用户自行决定何时点击按钮。

网页按钮不写第07章运行态。用户再次执行④时，`acknowledge_recovery` 先加载旧记录并核对同一平台身份，再调用只读的 `check_recovery_ready`：原阶段须为GAP_HELD，当前必须是不同于旧缺口的新Session、接收端Session一致、HEALTHY/OPEN、pending=0且已接收行情，同时通过现有接收口交接检查。它不重放、不卸载、不重启服务；缺口尚在、API不可用或交接失败时保留旧状态并拒绝再丢包。

核对通过后，恢复快照、交接输出、辅助源码及SHA另存于原RUN的 `recovery-observed-<时刻>/`，原始取证清单不变。随后把原RUN记为COMPLETE，再生成本次新RUN、建立健康基线并只丢一次。每轮都在GAP_HELD停下，等待用户再次点击网页恢复；没有自动恢复计时器。异常退出阶段仍需按下方排障说明检查，不把残留挂载当作已完成恢复。

实验期间持有过滤锁和部署锁，正常结束释放；两次实验之间没有后台编排或自动恢复计时器。

## 教师备用：排障时完整重启

[06-restart-trading-service.sh](06-restart-trading-service.sh) 只用于需要完整服务重启的异常排障；正常的网页恢复与重复实验不调用它。它读取保存的平台身份，只清理本次残留挂载，拒绝其他过滤程序，再执行 `transport_labctl.sh stop`、`baseline`，恢复原行情模式并从新Session重放。它会停起交易所、接收器、客户端、控制器和网页后台，清空进程内的模拟交易状态；不会重新构建或部署程序。

核对HEALTHY/OPEN、平台和过滤交接通过后记COMPLETE；失败保留RESTART_FAILED及 `restart-<时刻>/` 日志，排障后可重试。平台RUN变化时拒绝执行，不能用旧记录重启新平台。第二章部署入口可能复用已有服务，不等同于此完整停起操作。

## map 与程序身份

股票匹配条件在 C 程序中固定为 Type A、Locate 8095 和完整 `NVDA    `。`policy.target_stock_locate` 虽被控制脚本写入，现役 C 程序并不读取它，不能用它说明已实现动态换股票。重复运行修复只改编排及状态检查，C过滤条件保持。

`policy` 保存开关、有效期与一次性额度，`drop_audit` 记录被丢序号，`counters` 按 CPU 计数，读取时求和。额度用原子比较交换从 1 改为 0，只有一个 CPU 能成功；配置在未开放额度时完成，并不提供任意多字段更新的原子事务。

由接收接口的 attachment 找到 program ID，再从该程序的 `map_ids` 找 map；策略写入、计数读取和卸载均限定本次程序，不能拿其它程序的计数替代。相关参考图：[共享额度](../../images/course-visuals/07-diagrams/07-maps-and-one-shot.svg)、[接口与program/map身份](../../images/course-visuals/07-diagrams/07-17-netdev-program-map-chain.png)。

| 关键操作 | 教学上看什么 |
| --- | --- |
| `ip link set dev ens64np1 xdpdrv obj … sec xdp` | `xdpdrv` 明确要求驱动入口，不自动退到 generic |
| `ip -details link show dev ens64np1` | `prog/xdp id … jited` 证明挂载位置和 JIT |
| `set-xdp-policy.py block 1 5 "$PROG_ID"` | 清审计后武装一次、5 秒期限，只写本次程序的 map |
| `xdp-session.py dump drop_audit` | 按 program 的 `map_ids` 找到审计表，读取被丢 Sequence |

以上是脚本内动作的解释，不需要另行逐条执行。XDP与历史P4、RTL软件过滤入口共用同一跳板机文件锁，只防止该机同时运行多层过滤；不能阻止另一台跳板机操作，课堂统一入口。

## 异常与恢复边界

一次丢包额度和5秒有效期保持不变。远端180秒看门狗只按接口和program ID卸载本次XDP，不重放行情、不补回缺失消息。正常④结束时也已卸载；这个看门狗不是课堂恢复计时器。

④失败或被中断时，若已尝试武装则尽力暂停回放，并仅卸载本次程序；无论在哪一步失败，都不会自动重放、恢复原行情模式或重启业务。状态记为NEEDS_MANUAL_RESTART。SSH/API不可用时，暂停或卸载可能失败，不能仅凭trap运行过就宣称故障已稳定保留或设备已清理。

恢复检查若提示取证目录、`run.env` 或 `state-held.json` 缺失，应按提示路径检查或从原备份恢复文件；文件为空、无法解析或缺少会话也会单独提示。网页重新开始不能修复这些取证文件。只有当前行情尚未恢复时，才提示点击网页按钮；各类失败均保留原运行态。

恢复连通后查看本次 `raw/cleanup.txt`、`state.env`，再选择网页恢复或教师备用重启入口。若有不属于本次实验的XDP或其他过滤程序，先核对其归属；不要强卸。备用重启失败时看对应restart目录；修正问题后重试，仍沿用原实验与平台身份。

## 历史结果与详细输出

[旧脚本步骤图](../../images/course-visuals/07-diagrams/07-live-steps-and-evidence.png)描述旧版七步自动丢包与恢复，只用于追溯历史；学生正文已换成“丢包→停下来观察→网页手动恢复”的流程图。

2026-09-13 归档复核：正文运行③/④仍展示 2026-09-05 的源码/编译输出，源码摘要应为 `65ba5111…a59530acc5e7b7`；运行⑤也保留同日 Sequence 756 的结果。现役源码摘要为 `7780bccc…dd7f54cd4`，对应 2026-09-08 更新后的流量地址。`20260908T132538Z-08-xdp-receiver-live` 已封存同一份现役源码，记录丢包 1、Sequence/next_expected 均 586、拒单及恢复通过；45 项归档摘要复核一致。本轮没有重跑设备，不把这组读数拼入旧输出。

以下注释来自旧版自动恢复脚本打印模板，读数取自历史 RUN `20260905T084150Z-08-xdp-receiver-live`，不是学员当前执行结果。完整记录在 `reports/course-runs/20260905T084150Z-08-xdp-receiver-live/raw/`；756 只是该次序号，不能写进策略。

```text
vm-2522-02 / verify
===== 查行情缺口 =====
[Feed] 对: GAP / gap_size=1 / 闸门关闭  证: 策略执行后接收器自己发现序号缺失
$ python3 "$COMMON/wait-feed-state.py" "$API/api/state" GAP --timeout 12
{"session":"0612260105","market_mode":"MULTICAST","trader_auto":"ONLINE","feed":{"session":"0612260105","next_expected":756,"last_delivered":755,"first_pending":757,"highest_received":876,"pending":120,"duplicates":0,"gaps":0,"gap_size":1,"gap_age_ms":43,"path":"MULTICAST","integrity":"GAP","trading_gate":"INHIBITED_FEED_GAP"}}

vm-2522-02 / verify
===== 查缺口期间拒单 =====
[订单 API] 对: HTTP 400 / FEED_NOT_HEALTHY  证: 行情不完整时交易闸门确实拒绝下单
$ python3 "$COMMON/assert-feed-order-gate.py" "$API"
{"http_status":400,"error":"FEED_NOT_HEALTHY"}

vm-2522-02 / verify
===== 查界面与 GAP 状态合同 =====
[GUI] 对: 红条、灰簿、按钮合同通过  证: 页面源与 live 状态一致；不是浏览器截图
$ python3 "$COMMON/assert-feed-gap-ui.py" "$API" "$OUT/raw"
{"result":"PASS","live_feed_integrity":"GAP","banner_dom":true,"book_gray_css":true,"manual_order_disabled":true,"transport_orders_disabled":true}

vm-2522-02 / verify
===== 查被丢序号与 Feed 对账 =====
[XDP audit] 对: 恰好一包 / Locate 8095 / Sequence 等于 next_expected  证: 计数与行情缺口指向同一条消息
$ python3 - <counters.json> <drop-audit.json> <feed-gap.json>
xdp_drop_packets=1 sequence=756 locate=8095

vm-2522-02 / verify
===== 查恢复后两笔订单 =====
[OUCH] 对: 两笔成交 / AAPL 净持仓不变  证: 业务恢复覆盖真实协议下单与回执
$ python3 "$COMMON/prove-trading-recovered.py" "$API" "$OUT/raw/post-restore-orders"
{"result":"PASS","feed":{"session":"0612260108","next_expected":17526,"last_delivered":17525,"first_pending":0,"highest_received":17525,"pending":0,"duplicates":0,"gaps":0,"gap_size":0,"gap_age_ms":0,"path":"UNICAST","integrity":"HEALTHY","trading_gate":"OPEN"},"orders":[{"label":"reduce-risk","client_order_id":2108000000,"side":"SELL","result":"ORDER_EXECUTED","order_rtt_ns":50591},{"label":"restore-position","client_order_id":2108000001,"side":"BUY","result":"ORDER_EXECUTED","order_rtt_ns":48140}],"position_AAPL":[0,0]}
```

网页状态检查读取线上HTML/JS/CSS并对照GAP状态，不是浏览器截图。旧版执行后很快自动恢复，人工可能来不及看到红条；这正是后来把丢包与人工恢复分开的原因。当前用户网页截图见页首；历史合同检查不代替截图。

## DUAL 去重扩展的既有边界

这段环境边界从行业入门正文迁来，未更改既有设计或验证状态：

现役 `udp-multicast-ab-v1` 的 `DUAL` 为 A `233.74.125.32:31032` 与 B `233.74.125.33:31033` 两路组播。两路仍来自同一 Exchange 和 Et1，不是独立故障域。旧版“组播31032 + 单播42121”的去重扩展只适用于旧平台，不能解释现役 DUAL。

本章聚焦 `allow-all → NVDA Type A DROP → 保留 Feed GAP → 人工观察 → 网页手动恢复`。因此实验只发 A；B 副本补洞属于另一项观察，不与本次“丢一包必出现缺口”的演示混用。

## AF_XDP 补充概念

[同一类包的两种接收方式](../../images/course-visuals/07-diagrams/07-af-xdp-explained.png)：普通UDP应用拿到行情载荷，AF_XDP应用拿到完整帧并自行解析网络协议头。原“生产接收器”指实盘行情接收程序，使用AF_XDP并非必要条件；本课没有启用AF_XDP或验证其性能/零拷贝。[Linux AF_XDP文档](https://docs.kernel.org/networking/af_xdp.html)。

## 真实应用案例的来源边界

2026-09-17：按用户要求，现役行业图改为同一SVG内三个纵向面板：EPAM/Deltix在上，原Cloudflare/Meta居中和下方；正文以图为主，不展开三段长案例。原文件 `07-xdp-real-world-cases.svg` 直接重画，同源PNG用于正文显示，点击可打开SVG。图中A123仅作配对示意，无实测性能数字。

新增金融案例依据[EPAM官方仓库](https://github.com/epam/ebpf-fix-latency-tool)及[Deltix官方入口](https://ember.deltixlab.com/docs/tools/latency-tool/)：TC入/出站提取FIX Tag11及时间戳，用户态配对请求与首个响应。不能称作XDP挂点、最终成交时延或本课测得的性能；旧libpcap工具的tick-to-order功能不可移植为新eBPF工具的既有能力。源码审计及本课安装兼容性未验证，未新增运行卡。LMAX不纳入正文。详细来源边界见[案例核对记录](../../refs/FLLE_Ch07_eBPF_Trading_Cases_2026-09-17.md)。

DEC-347按用户明确要求把行业主线改为应用场景，AF_XDP图留作补充。Cloudflare L4Drop与Meta Katran是XDP案例，不能混称为AF_XDP部署。图为公开历史案例简化，不宣称复现厂商当前全量架构或性能。

- [Cloudflare L4Drop，2018-11-28](https://blog.cloudflare.com/l4drop-xdp-ebpf-based-ddos-mitigations/)说明把检测系统产生的规则编译为eBPF；文章明确解释为何当时不把这些任意匹配规则全部存入map。不能恢复旧文“两个案例都是policy写map”的概括。
- [Cloudflare边缘防护，2021-03-18](https://blog.cloudflare.com/deep-dive-cloudflare-autonomous-edge-ddos-protection/)说明L4Drop执行既有攻击规则并采样，未丢包继续到Unimog及后续处理；未命中某规则不等于证明流量正常。
- [Meta Katran，2018-05-22](https://engineering.fb.com/2018/05/22/open-source/open-sourcing-katran-a-scalable-network-load-balancer/)及[项目拓扑说明](https://github.com/facebookincubator/katran#l4-load-balancing-network-topology)说明为VIP流量选择后端、按连接维持映射，并封装转发；主图只画入方向，不展开IP-in-IP与直接回包。未把Katran画成HTTP业务处理或每包随机分配。

来源于2026-09-05在线复核；本课故意丢合法行情属于故障注入，不等于生产中常态过滤某只股票。

## 源码中的局部重复检查

运行 ② 重点展示第 140～147 行：先检查声明长度为 36，再证明整条消息可读。C 第 152 行的 `itch + 3` 和第 159 行的 `stock + 8` 已被第 144 行整体检查覆盖，保留它们是为了就近读懂字段访问条件，不代表必须逐字段重复检查；源码未改。

<a id="retired-assets"></a>

## 历史资产：仅供查阅

以下均为 `RETIRED / HISTORICAL`，不是本章运行入口。保留原路径供旧报告追溯；学生正文的资产表只列现役程序。

| 文件（相对本目录） | 历史用途 |
| --- | --- |
| `02-xdp-action-model.sh`、`xdp_action_model.py` | 旧预填动作打印；不解析报文、不验证 C 程序，已退出课堂步骤 |
| `04-xdp-counter-receipt.sh`、`05-xdp-verified-evidence.sh` | 旧计数回执与已验证输出展示 |
| `05-xdp-span-live.sh`、`live-support/run-xdp-span-live.sh` | 旧 SPAN 副本实验 |
| `analyze_mold_pcap.py` | 旧副本实验的 pcap 解析 |
| `xdp-span-show.plan`、`xdp-span-apply.plan`、`xdp-span-restore.plan` | 旧 SPAN 查询、设置与恢复计划 |
| `flle_xdp_a1_exact.c` | 旧 ICMP 过滤程序 |
| `xdp-lifecycle-native-20260820.txt`、`xdp-map-native-20260820.txt`、`xdp-standard-cli-native-20260820.txt` | 旧 ICMP 生命周期、map 与 CLI 记录 |
