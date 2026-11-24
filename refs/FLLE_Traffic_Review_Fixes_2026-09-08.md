# 流量改造评估后的修复报告（2026-09-08）

本轮修复了远端静默断言、四路径模式的接收器生命周期和 DPDK 失败恢复，并按追加意见调整第一章两张图。当前平台仍是 `20260908T095222Z-02-trading-platform`，**SOFTWARE / SFC / READY**，Feed **HEALTHY**，pending/gaps 为0。没有执行 Git commit、push 或 tag。

本轮验证 RUN：`20260908T104721Z-traffic-review-fixes`。本报告承接[上一轮修改报告](FLLE_Traffic_Revision_2026-09-08.md)，不覆盖其原始证据。

## 修复后的行为

| 评估项 | 本轮处理 |
| --- | --- |
| `;` 吞掉远端断言结果 | `lab_is_quiescent` 和 `controller_stop` 回退分支均改成 `A && B`。本机停止控制器的断言也显式传播失败。回归执行实际命令串，覆盖单元 active/inactive 与端口有/无监听的四种组合；active 且无监听必须失败 |
| SOFTWARE → TRANSPORT/SFC 遗留接收器 | SFC 在读取 READY 状态、提前返回之前，先停普通行情消费者/Guardian，再停共享接收器；释放 UDP31032/42121、Unix socket 及 IGMP 订阅。第08～10章仍可通过 `feed-guardianctl.sh` 显式启用实验接收配置 |
| DPDK 停止顺序 | 先停普通行情消费者，再停 SFC 客户端，然后停接收器；之后停止旧 DPDK、释放大页并启动新 DPDK。接收器停止失败现在有 `DPDK_ACTION_FAILED stage=stop_feed_receiver` |
| DPDK 中途失败 | 保留失败阶段和原退出码。切换前属于 SOFTWARE 或存在接收器时，恢复普通 SOFTWARE 配置；原来是纯下单配置时恢复 TRANSPORT/SFC。恢复失败明确返回125；成功恢复也不把原切换报告成成功 |
| Python 控制器的二次恢复 | 脚本报告恢复后，控制器另查实际状态并验证硬门闸；已恢复的 SOFTWARE 不再被无条件 SFC 恢复覆盖。验证失败、超时等原兜底路径仍保留 |
| 陈旧参数与注释 | RTL 注释和真卡设计说明把 `--multicast-receiver` 明确归到 `flle-feed-receiver`；Guardian 消费 `feed.sock`。删除 Guardian helper 两处未使用的远端 multicast 参数及对应局部变量 |
| IGMP 输出格式 | 第三章 pruning 断言允许冒号两侧空白变化，不再依赖固定多空格 |
| 第一章配图 | 保留现有内容，Exchange 在行情/订单对照中固定左侧，Trader 固定右侧；订单请求改为右→左，回执左→右。`.2` 节点统一叫 Trader，Socket 接收器只作内部组件说明。Win2019 标题收进框内；管理命令图同步调整左右端点和箭头 |

`start` 失败清理也增加接收器停止。消费者与接收器停止 helper 显式传递失败，避免在调用方条件语境下继续执行后续步骤。

## 验证与证据

| 检查 | 实际结果 |
| --- | --- |
| `.111` 应用回归 | 183项，跳过1项（本机没有接收器ELF）；其余通过 |
| `.101 make test` | C++自测通过；Python 187项，跳过9项仅完整仓库适用的检查；其余通过。C++源码/ELF本轮未改，没有重新构建制品 |
| 网页实际切换 | SOFTWARE→SFC→DPDK→SOFTWARE 全部READY；14笔订单逐笔取得 `ORDER_EXECUTED`，买卖配对 |
| SFC 常规入口 | UDP31032/42121 无监听、`feed.sock` 消失、`/proc/net/igmp` 无目标组 |
| SFC 已READY入口 | 显式启用 Guardian/direct 后重复请求SFC，仍退出接收器和组播成员，提前返回不再跳过清理 |
| 交换机及两端抓包 | Snooping组表无目标成员；VLAN20 pruning=True、flooding=False；Exchange抓到3个目标组播包，Trader在5秒观察窗中0包。未改交换机配置 |
| 实际失败恢复 | 用独立临时脚本在 `start_dpdk_client` 绑定硬件前返回42：输出阶段标签，原退出码42，恢复SOFTWARE；接收器双UDP监听、组播成员和客户端READY恢复。临时脚本随后移除 |
| 失败分支回归 | 覆盖各停止/启动阶段、回退配置选择、回退失败125、Python保留已验证恢复及拒绝未验证恢复；这些故障分支用隔离测试，实机只注入上述一次失败 |
| 图文检查 | 两张图800/1200px渲染目视；Win2019标题右边界303/290，所在框右边界380/355。16箭头与正文编号一致，箭尖距目标框12px。48项Shell/Python/XML/Markdown检查通过；图像SHA清单同步 |

小型可提交证据：[traffic-review-fixes-20260908.json](evidence/traffic-review-fixes-20260908.json)。原始命令输出、故障注入脚本、部署清单和渲染证据位于 `Documents/reports/course-runs/20260908T104721Z-traffic-review-fixes/raw/`，按仓库规则不自动进入Git；小型记录保存其SHA与本轮源码身份。`.2` 控制工作区及 `.101` 源码清单已更新并验证，v13应用制品保留原字节。

## 第六章基准的结论边界

采用停止接收器方案，**本轮没有重采17,600笔**。第六章新增生命周期解释及旧v12数据身份说明。

需要补充一个事实：正式采样脚本原本就调用 `pause_exchange_at_fixed_book`，使用有期限的回放暂停租约并复核回放序号/身份；它没有在普通 PLAYING 行情条件下直接采样。接收器遗留确实是准备/切换阶段的隔离回归，但不能据此直接断言旧17,600笔采样期间存在行情RX。停止接收器也不等于网卡完全无行情——PLAYING/UNICAST仍可能向该网卡发包。正文现在区分应用接收、组播剪枝与正式固定簿面采样条件；旧数字没有被升级为当前v13性能结论。

## 保留的边界

接收器 SIGKILL 后可能遗留 `feed.sock`、AF_UNIX SNDBUF 未做负载裕度定标，本轮没有扩大修改；不自动删除未知socket。慢消费者导致缺口/拒单的既有策略保持。控制端点仍是封闭管理网内的 `.2:48606`、按 `.101` peer IP 放行，没有新增认证架构。本轮未重跑完整第08～10章过滤实验或全课快照；明确验证了其 Guardian/direct 启动与退组路径。

## 待提交文件

本轮涉及 `apps/flle-trading-lab/scripts/{transport_labctl,control-host,platform-baseline}.sh`、`flle_trading/transport_controller.py`、`tests/test_transport_controller.py`、新增 `tests/test_transport_lifecycle.py`；第03/06章、Guardian/RTL配套说明；第一章总览/通信SVG、图册README与两级SHA；四份治理文件、本报告及证据JSON。此前授权改造的其他未提交文件全部保留。

建议 commit message：`fix: preserve stop assertions and isolate transport feed lifecycle`。若分开提交图文，可用 `docs: align Exchange and Trader roles in overview diagrams`。提交由用户本人执行。

## 2026-09-08 追加复核：IGMP 两条断言的正文/资产同步

用户再次复核发现上一轮只放宽了正文 pruning 断言，实际资产仍是固定空格，Flooding 断言两边也未改。本次将 `02-compare-market-transports.sh` 和第三章正文中的两条断言统一为 `grep -Eq`，允许冒号两侧及行尾的空白变化，同时保留精确 True/False 与行尾约束。完整正文代码块与资产逐字一致，bash语法、14个实际grep正反用例、`git diff --check`通过。

验证RUN `20260908T110905Z-igmp-assertion-sync`；第三章运行②生成 `20260908T110945Z-03-market-paths`。执行的是修改后的原资产脚本；原入口会下发IGMP配置，为遵守本次“不动设备配置”，验证外壳只把该次EOS调用替换成真实 `show` 查询，其余模式切换、抓包、解码、断言及清理均由原脚本执行。没有使用缓存或伪造交换机输出。验证外壳和命令计划随RUN保存；资产原有设备初始化行为未改。

结果：UNICAST 120个单播包，MULTICAST 120个组播包，DUAL各60个、序号重合60；membership=1、duplicate_delta=1343、pending/gaps=0，`THREE_TRANSPORT_MODES_PASS`。真实EOS两条断言均命中；证据SHA验证通过；EXIT恢复原UNICAST，最终Feed HEALTHY。小型可提交记录：[igmp-assertion-sync-20260908.json](evidence/igmp-assertion-sync-20260908.json)。本轮没有重新运行无关的C++/Python应用回归或性能基准。

用户确认正式固定簿面暂停合同消除了前轮关于17600笔行情RX的疑问；本次不重采。待提交补充为第三章正文、`assets/03-live-traffic/02-compare-market-transports.sh`、本报告/证据和治理记录。提交建议继续分两条：代码 `fix: preserve stop assertions and isolate transport feed lifecycle`；配图 `docs: align Exchange and Trader roles in overview diagrams`。均未由AI提交。

## 2026-09-08 追加讲解：IGMP 原生命令、实际输出与完成条件

按用户“怎么打、怎么看、如何证明完成”的要求，第三章运行②新增②A/②B/②C讲解停顿：EOS配置和三个show命令逐字展开、接收器IP_ADD_MEMBERSHIP与Linux报告过程、主机ip maddr，以及从本次MULTICAST.pcap读三包的命令。每步都有执行位置、前置/影响、真实输出节选和人工判断；末尾验收表将配置启用、主机成员、交换机Dynamic/Et2及剪枝、数据口实际收包、应用连续性分别对上证据，补充异常排查和运行配置保留范围。

同位置两句旧“发送端向两个client复制/两个socket各自加组”的比喻改为统一接收器语义；更新运行②学习目标、任务地图和资源说明，仍保持本章3个导航项。完整自动脚本保留，代码块仍与资产逐字一致，EOS手工命令块与计划逐字一致。

本次仅修改文档，没有再次下发配置、部署或开启新实机RUN。输出复用 `20260908T110945Z-03-market-paths`，pcap三行由本机tcpdump实际重读；命令围栏语法、Markdown表格、HTML闭合及输出出处检查通过。维护记录见 `design/evidence/igmp-walkthrough-20260908.json`。新增未提交内容：第三章正文、本报告、治理记录及小型检查摘要。建议说明：`docs: explain IGMP setup membership and delivery verification`。

## 2026-09-08 追加修改：五个管理端口与第四章指标链

按用户确认保留独立客户端管理端口。第一章新增48121 AUTO/Guardian、48122 Socket、48123 Onload、48124 TCPDirect、48125 DPDK逐项解释，另列Exchange48120；用一次TCPDirect网页下单说明8088 JSON→48124内部命令→交易所43120 OUCH，并注明按配置启停及命令响应/成交回执的区别。

第⑧组重画为Grafana左、Prometheus中、Gateway右；保留原编号、TCP蓝色和箭头框外间隙，标明9090查询及8088/metrics抓取。查询与定期抓取是两个独立HTTP请求，返回沿原连接，避免读成每次看板刷新都触发即时抓取。Gateway节点注明第04章。

正文指标表覆盖第四章8块面板用到的全部12个指标名，逐项说明在线状态、进度、行情速率、当前/固定批次RTT、Feed状态、订单成交速率和样本数；区分Prometheus自产up与Gateway导出的组件状态，明确C++计算摘要、秒单位及原始逐单样本边界，并链接第四章与实际dashboard。

验证：对照Gateway默认端口、导出函数、Prometheus/Grafana配置和实际dashboard；12个指标名全部覆盖。两种宽度渲染目视/文字边界、16条箭头与表映射、12px间隙、XML/Markdown/bash围栏/HTML及两级图像SHA通过。没有改运行代码、部署或设备，也没有新性能实验。检查摘要`design/evidence/ports-metrics-map-20260908.json`。

本次未提交文件：第一章正文、通信SVG、章级README与两级SHA、治理记录、本报告和摘要。建议说明：`docs: clarify trader ports and map chapter 04 metrics flow`。AI未执行提交。

## 2026-09-08 最后复核：导航合同与图册地址残留

用户发现两个文字回归。本轮先实际复现 `verify-filter-course-cards.py` 的第三章任务地图/导航知识不一致错误，再将任务地图统一为导航卡的“加组、成员转发与三种交付模式”；图册README两处48606控制端点从`.111`修正为`.2`。

修复后执行 `python3 Documents/newDoc/assets/common/verify-filter-course-cards.py` 返回0：11章74张导航卡、18张执行卡、24个图片引用全部PASS。第三章完整运行②代码块仍与资产逐字一致，图册不再含`.111`的48606端点。检查原始输出和文件摘要见[navigation-readme-fix-20260908.json](evidence/navigation-readme-fix-20260908.json)。本轮只改文字和维护记录，没有修改脚本、SVG或设备配置，没有新实机实验。

本次待提交补充：第三章正文、第一章图册README、本报告、FREEZE/PIT及小型检查记录。代码与配图仍按前述两条commit说明分开整理，AI未执行commit/push/tag。此前文图检查虽覆盖语法/渲染，却漏跑仓库自身的导航合同检查；本条恢复的是该检查的真实PASS状态。
