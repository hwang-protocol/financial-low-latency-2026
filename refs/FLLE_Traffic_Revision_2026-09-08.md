# 流量、控制器与课程配图修改报告（2026-09-08）

后续评估修复与最新验证见[流量改造评估修复报告](FLLE_Traffic_Review_Fixes_2026-09-08.md)。本页保留上一轮证据身份。

已完成文档、配图、代码和受影响路径的实机验收。当前平台为 **SOFTWARE / SFC / READY**，行情 **HEALTHY**，pending/gaps 均为0。没有执行 Git commit、push 或 tag。

## 按讨论意见完成的修改

| 项目 | 修改后的行为 | 主要文件 |
| --- | --- | --- |
| 移除 `.111` 控制服务依赖 | Windows Server 2019 浏览器访问 `.101:8088`；后台调用 **`.2:48606/TCP`**；Python 服务在 `.2` 本机执行切换。`.111` 保留部署、SSH 和证据职责 | `apps/flle-trading-lab/scripts/control-host.sh`、`transport_labctl.sh`、`prepare-control-host.sh`、`flle_trading/transport_controller.py` |
| 统一行情接收 | 一个 `flle-feed-receiver` 普通 Socket 进程接收组播和单播，通过 Unix SOCK_SEQPACKET 向 AUTO/MANUAL 分发完整报文；保留原网络接收时间戳 | `src/feed_receiver.cpp`、`src/feed_ipc.hpp`、`src/trader.cpp`、`src/exchange.cpp` |
| 统一业务端点 | 组播 **`233.74.125.32:31032/UDP`**；单播 **`20.1.1.2:42121/UDP`**；订单仍为 **`20.1.1.1:43120/TCP`**。删除42122～42125的额外行情发送目标；各进程管理端口48121～48125保留 | 第01、02、03章及启动、抓包、过滤脚本 |
| 真实交易所案例 | 第二章解释 Nasdaq INET Nordic A/B 地址、IGMP、PIM-SM/RP 建树与行情逐段传播。本地源保持20.1.1.1，复用真实组与目的端口；没有配置 PIM/RP/组播路由 | [第二章](../02-host-native-trading-system-baseline.md) |
| IGMP 现场验证 | VLAN20 Snooping + Querier20.1.1.254；`.2`接收器加入组，交换机看到动态Et2，pruning=True、VLAN flooding=False；Et2对应接口收到真实行情 | `assets/03-live-traffic/market-igmp-enable.plan`、`02-compare-market-transports.sh` |
| LANZ 工作原理 | 说明 length、streaming、no shutdown；`.101`主动连接`.253:50001`，交换机沿同一TCP连接推protobuf；8089发布JSON，8088页面的JavaScript每500ms fetch并呈现 | [第七章](../06-arista-cut-through-ptp-time.md) |
| 图与通信表 | 第一章补Windows2019、`.2`控制服务、单一行情入口；保留真实AMD/Broadcom/Arista logo、TCP蓝/UDP橙及16条通信说明。第二章增加真实组播传播图，并同步03、08、10相关图 | [第一章总览](../images/course-visuals/01-diagrams/01-physical-topology-host-owned.svg)、[通信图](../images/course-visuals/01-diagrams/01-traffic-flows-and-ports.svg)、[真实案例图](../images/course-visuals/02-diagrams/02-nasdaq-multicast-routing.svg) |

`.1/.2 → .101:46120/UDP` 按讨论保留：`.1`上报重放/交易所状态，`.2`上报客户端交易事件。LANZ服务架构保持，只补齐解释。Onload、TCPDirect、DPDK仍是下单技术，不为它们另造行情接收器。DPDK独占数据口期间，普通Socket行情接收停止；返回普通交易时重启。

## 验证结果

总任务 RUN：`20260908T090619Z-traffic-revision`；最终平台 RUN：`20260908T095222Z-02-trading-platform`。

| 验证 | 结果 |
| --- | --- |
| 构建与制品 | 7个应用输出在两条隔离构建路径逐字一致，C++自测通过。v13源码/运行包/provenance/厂商输入摘要及source→ELF映射通过 |
| Python回归 | `.111`：173项、1项跳过（本机没有接收器ELF）；`.101`：177项、9项仅完整仓库适用的检查跳过。真实接收器4项全部通过，覆盖完整报文分发、单一绑定、断开连接与慢接收者 |
| 控制器归属 | `.2`实际监听10.1.1.2:48606；`.111`该端口无监听。控制脚本与依赖已分发到`.2`，本机子进程不继承设备切换锁 |
| 网页控制链 | 从`.101`网页使用的API依次执行DPDK、SFC、BASELINE，均READY；最终验收逐笔等待回执，**14/14 ORDER_EXECUTED**，各手工客户端测试净持仓归零 |
| 行情三模式 | UNICAST抓120包全部单播；MULTICAST抓120包全部组播；DUAL抓60+60，两路60个序号重合、duplicate增长，membership=1、pending/gaps=0 |
| 最新行情解码 | `20260908T102234Z-03-live-market`：200个真实组播包，MoldUDP64/ITCH解码通过 |
| IGMP | 查询器20.1.1.254、动态成员Et2、剪枝生效且VLAN泛洪关闭。主机实际收到该组31032流量；没有配置组播路由 |
| XDP | `20260908T100656Z-08-xdp-receiver-live`：一次目标丢包→缺口→拒绝下单→恢复健康，恢复后2笔成交 |
| P4 | `20260908T101323Z-09-p4-drop-live`：四阶段通过，丢包序号与缺口对账；恢复VLAN20、健康行情与两笔成交 |
| RTL | `20260908T101639Z-10-rtl-stages`：6项模型自测、一次丢弃201/缺失201、缺口1、拒单；恢复后两笔成交且净持仓不变 |
| 文档与图 | 800/1200px渲染审图、SVG/XML、源目的编号与16行表、47项静态检查、206项中央图像SHA、11章74张导航卡检查通过 |

小型可提交验收记录：[traffic-revision-20260908.json](evidence/traffic-revision-20260908.json)。详细原始输出在本机 `Documents/reports/course-runs/20260908T090619Z-traffic-revision/`，按仓库既有规则不自动进入Git；报告与小型记录保留RUN身份、关键结果和证据摘要。

## 本轮发现并修复的问题

1. 控制器移到`.2`后，后台接收器/客户端继承设备锁fd8，导致下一次切换等待。修复为本机子shell关闭fd8，由前台控制操作持锁；增加真实后台进程锁释放回归，并重新部署验收。失败平台`20260908T092516Z`已停止，日志保留。
2. P4控制表还用旧组地址的十六进制值`ef140114`，识别到NVDA但策略不命中。修正为`e94a7d20`，同步源码、表项、示例和测试；失败RUN`20260908T100942Z`已自动回滚，重跑通过。
3. 原交换机虽然显示Snooping Enabled和Et2成员，但没有Querier，剪枝未生效。增加VLAN20二层查询器后，pruning=True、Flooding=False。
4. 最初网页接口探测只检查请求已接受，部分即时盘口限价随后因价格变化被PX拒绝；最终验收改用课程已有的可成交测试限价，并逐笔核对Executed，保留两次记录，不把Accepted当成交。

## 证据范围与后续

本轮完成功能和受影响路径回归，**没有重跑00～10完整快照课程，也没有重新采集17600笔四路径性能基准**。旧v12包、历史抓包和性能数字保留原始身份；第三章旧Packet Details图明确标为历史样例。统一接收引入本机IPC，后续处理时间包含分发开销，旧Feed延迟不代表新架构性能。LANZ本轮补文档并回源核对代码，未重新制造拥塞。

Nasdaq案例的真实参数来自[官方INET Nordic生产接入表v4.0](https://www.nasdaq.com/docs/2025/09/09/Connectivity-Guideline-INET-PROD-20250909-v4.0.pdf)：A源159.79.85.1、组233.74.125.32、UDP31032、RP159.79.85.252。中间设备按[标准PIM-SM机制](https://www.rfc-editor.org/rfc/rfc7761.html)解释，未公开的接口IP、客户端IP和源UDP端口不编造。本地只复现二层交付。

全部修改仍在工作区。待提交内容包括课程01/02/03/06/07/08/09/10、配图与SHA、应用/实验脚本与测试、v13制品登记、治理文件和本报告。建议 commit message：`refactor: move control to trader and unify market feed delivery`。提交与推送由用户本人完成。
