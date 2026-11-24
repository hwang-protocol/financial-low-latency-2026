# 第08运行⑤：教师维护与异常恢复说明

[脚本步骤与输出对照图](../../images/course-visuals/07-diagrams/07-live-steps-and-evidence.png)概括正常执行顺序；第5步说明丢包与缺口如何互证。

学生正文只需执行一条入口并观察丢包、缺口和恢复。本文件供教师排障查阅，不是额外的学生运行步骤；正文修改不等于重新执行丢包实验。

## 编排与前置条件

完整编排在 [run-xdp-receiver-live.sh](live-support/run-xdp-receiver-live.sh)，当前 115 行。它核对源码后在 `.2` 编译并封存实际加载对象，再通过 [xdp-session.py](live-support/xdp-session.py) 管理挂载与看门狗；运行 ④ 是可单独观察的编译步骤，不是⑤的硬性前置。输入为现役源码、第06章保存的交易 RUN 和当前行情模式，输出保存在本次 `Documents/reports/course-runs/$RUN_ID/{raw,source,artifacts}`。

| 前置门 | 必须看到 |
| --- | --- |
| 第07章交接 | `SFC / READY / sfc`，8088 可用 |
| `.2` 接收口 | `ens64np1 / UP / 20.1.1.2`，无旧 XDP、无 RTL adapter |
| 工具 | 准备 A 已完成；⑤会重新编译 |
| 实验互斥 | 没有另一章的过滤实验同时执行 |

当前行情消费者走普通 Linux socket，结论不外推到 Onload、TCPDirect、DPDK 接收路径。实验仅在 `.2 ens64np1` 加载 native XDP，不改交换机、IP 或网卡驱动；保留原交易 RUN。

脚本临时使用 MULTICAST，先以零额度检查行情健康，再开放一次 DROP；读取被丢 Sequence 与 Feed 的 `next_expected` 对账，验证拒单，清策略后重放新 Session。最后卸载本次程序，恢复原模式并验证两笔订单成交，AAPL净持仓不变。

## map 与程序身份

`policy` 共享规则与一次性额度，`drop_audit` 记录被丢序号，`counters` 按 CPU 计数，读取时求和。额度用原子比较交换从 1 改为 0，只有一个 CPU 能成功；配置在未开放额度时完成，并不提供任意多字段更新的原子事务。

由接收接口的 attachment 找到 program ID，再从该程序的 `map_ids` 找 map；策略写入、计数读取和卸载均限定本次程序，不能拿其它程序的计数替代。相关参考图：[共享额度](../../images/course-visuals/07-diagrams/07-maps-and-one-shot.svg)、[接口与program/map身份](../../images/course-visuals/07-diagrams/07-17-netdev-program-map-chain.png)。

| 关键操作 | 教学上看什么 |
| --- | --- |
| `ip link set dev ens64np1 xdpdrv obj … sec xdp` | `xdpdrv` 明确要求驱动入口，不自动退到 generic |
| `ip -details link show dev ens64np1` | `prog/xdp id … jited` 证明挂载位置和 JIT |
| `set-xdp-policy.py block 1 5 "$PROG_ID"` | 清审计后武装一次、5 秒期限，只写本次程序的 map |
| `xdp-session.py dump drop_audit` | 按 program 的 `map_ids` 找到审计表，读取被丢 Sequence |

以上是脚本内动作的解释，不需要另行逐条执行。第08～10章共用同一跳板机文件锁，只防止该机同时运行多层过滤；不能阻止另一台跳板机操作，课堂统一入口。

## 自动清理的边界

实验故意制造行情缺口，期间订单闸门拒单。策略5秒到期后停止丢包；正常结束与失败trap都会尝试卸载本次程序、恢复原模式并重放。清理步骤可能受连通性影响，报错不能直接认定已恢复。

远端180秒看门狗按接口与program ID卸载，不碰其它程序；它只能停止过滤，不能补回已丢行情。只有恢复检查通过才能继续下一章。

### 恢复断言

`.2 ens64np1` 无本次 `prog/xdp`，仍为 `sfc / UP / 20.1.1.2`；行情模式回到实验前，Feed 为 `HEALTHY`。不关闭交易数据口，不改交换机。

**异常时的教师恢复路径：**若 SSH 断开，180 秒看门狗只能撤掉本次 XDP，不能补回已丢行情。重新连通后，先确认实验已停止且 `.2` 无本次挂载；仍有未知程序时停下核对，不强卸。

下表仅供异常恢复，不是正常绿卡。先从本次记录查出原模式，再替换命令里的 `<原模式>`；不能把占位符原样执行。

| 顺序（仅异常恢复） | 具体入口 | 应看到什么 |
| --- | --- | --- |
| 找回原模式 | 读取本次 RUN 的 `raw/state-before.json` 中 `market_mode`，不要照抄示例 RUN | 明确实验前模式；文件缺失则先核对现场记录 |
| 恢复发送模式 | 跳板机：`curl -fsS -X POST -H 'Content-Type: application/json' -d '{"market_mode":"<原模式>"}' http://10.1.1.101:8088/api/market` | 行情模式与记录一致 |
| 恢复直接订阅 | 跳板机：`bash Documents/newDoc/assets/common/feed-guardianctl.sh direct` | Guardian 恢复直接订阅 |
| 重建完整订单簿 | 跳板机：`curl -fsS -X POST -H 'Content-Type: application/json' -d '{"action":"RESTART"}' http://10.1.1.101:8088/api/replay` | 启动新 Session，重新建簿 |
| 检查恢复结果 | 跳板机：`curl -fsS http://10.1.1.101:8088/api/state` | 新 Session、Feed `HEALTHY`、闸门 `OPEN`；未达到就不继续第09章 |

## 历史结果与详细输出

以下注释来自当前脚本打印模板，读数取自历史 RUN `20260905T084150Z-08-xdp-receiver-live`，不是学员当前执行结果。完整记录在 `Documents/reports/course-runs/20260905T084150Z-08-xdp-receiver-live/raw/`；756 只是该次序号，不能写进策略。

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

网页状态检查读取线上HTML/JS/CSS并对照GAP状态，不是浏览器截图。正常执行恢复很快，人工不一定来得及看到网页红条；以本次终端及保存的map/Feed/订单结果为准。

## DUAL 去重扩展的既有边界

这段环境边界从行业入门正文迁来，未更改既有设计或验证状态：

当前 `DUAL` 来自同一 Exchange 和 Et1，不是独立故障域。去重扩展只取组播 `42120` 与单播 `42121`，以 Session + Sequence 为 key，并排除 `42122–42125`；它只能证明 first-valid/duplicate，不能证明 Feed A/B 高可用。

本章聚焦 `allow-all → NVDA Type A DROP → Feed GAP → Replay Restart`。DUAL 去重留作扩展，因为当前五个单播副本共享同一发送进程与故障域，不能形成可信的 Feed A/B 故障切换证据。

## AF_XDP 补充概念

[同一类包的两种接收方式](../../images/course-visuals/07-diagrams/07-af-xdp-explained.png)：普通UDP应用拿到行情载荷，AF_XDP应用拿到完整帧并自行解析网络协议头。原“生产接收器”指实盘行情接收程序，使用AF_XDP并非必要条件；本课没有启用AF_XDP或验证其性能/零拷贝。[Linux AF_XDP文档](https://docs.kernel.org/networking/af_xdp.html)。

## 真实应用案例的来源边界

DEC-347按用户明确要求把行业主线改为应用场景，AF_XDP图留作补充。Cloudflare L4Drop与Meta Katran是XDP案例，不能混称为AF_XDP部署。图为公开历史案例简化，不宣称复现厂商当前全量架构或性能。

- [Cloudflare L4Drop，2018-11-28](https://blog.cloudflare.com/l4drop-xdp-ebpf-based-ddos-mitigations/)说明把检测系统产生的规则编译为eBPF；文章明确解释为何当时不把这些任意匹配规则全部存入map。不能恢复旧文“两个案例都是policy写map”的概括。
- [Cloudflare边缘防护，2021-03-18](https://blog.cloudflare.com/deep-dive-cloudflare-autonomous-edge-ddos-protection/)说明L4Drop执行既有攻击规则并采样，未丢包继续到Unimog及后续处理；未命中某规则不等于证明流量正常。
- [Meta Katran，2018-05-22](https://engineering.fb.com/2018/05/22/open-source/open-sourcing-katran-a-scalable-network-load-balancer/)及[项目拓扑说明](https://github.com/facebookincubator/katran#l4-load-balancing-network-topology)说明为VIP流量选择后端、按连接维持映射，并封装转发；主图只画入方向，不展开IP-in-IP与直接回包。未把Katran画成HTTP业务处理或每包随机分配。

来源于2026-09-05在线复核；本课故意丢合法行情属于故障注入，不等于生产中常态过滤某只股票。

## 源码中的局部重复检查

运行 ③ 重点展示第 140～147 行：先检查声明长度为 36，再证明整条消息可读。C 第 152 行的 `itch + 3` 和第 159 行的 `stock + 8` 已被第 144 行整体检查覆盖，保留它们是为了就近读懂字段访问条件，不代表必须逐字段重复检查；源码未改。

<a id="retired-assets"></a>

## 历史资产：仅供查阅

以下均为 `RETIRED / HISTORICAL`，不是本章运行入口。保留原路径供旧报告追溯；学生正文的资产表只列现役程序。

| 文件（相对本目录） | 历史用途 |
| --- | --- |
| `04-xdp-counter-receipt.sh`、`05-xdp-verified-evidence.sh` | 旧计数回执与已验证输出展示 |
| `live-support/run-xdp-inline-live.sh` | 旧工具机桥接实验 |
| `05-xdp-span-live.sh`、`live-support/run-xdp-span-live.sh` | 旧 SPAN 副本实验 |
| `analyze_mold_pcap.py` | 旧副本实验的 pcap 解析 |
| `xdp-span-show.plan`、`xdp-span-apply.plan`、`xdp-span-restore.plan` | 旧 SPAN 查询、设置与恢复计划 |
| `flle_xdp_a1_exact.c` | 旧 ICMP 过滤程序 |
| `xdp-lifecycle-native-20260820.txt`、`xdp-map-native-20260820.txt`、`xdp-standard-cli-native-20260820.txt` | 旧 ICMP 生命周期、map 与 CLI 记录 |
