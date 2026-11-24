# 第三章补充读法与较完整的输出节选

**版本说明：**下方旧三模式回执来自“一路 UDP 单播 + 一路 UDP 组播”的历史实现，保留用于追溯，里面的命令不适用于当前 A/B 入口。当前双路为两个 UDP 组播组，第三章正文已收录新的三模式实测节选，完整来源见 [README](README.md#运行②实测节选来源)。

这些内容供核对字段和排查问题使用。输出沿用正文原有历史抓取，不是本轮新抓包；正文只展示关键节选。

### 四个编号分别归谁

第二章管理接口返回的 **client_order_id（客户端编号）**，在线上对应 OUCH 的 **UserRefNum**。它由客户端按规则生成，返回给网页只表示本地已接收并排队，不等于 Exchange 已受理。

| 字段 / 宽度 | 谁生成 | 出现在哪里、用来做什么 |
| --- | --- | --- |
| UserRefNum / 4 字节整数 | 客户端 | O/A/E/J 都带回同一个值，本步靠它把请求、受理、成交对成一笔 |
| ClOrdID / 14 字节字符 | 客户端 | 请求 O 与回报 A/J 中的客户自定义标识；课程 MANUAL 使用 MANU 加客户端编号，E 不带它 |
| Order Reference Number / 8 字节整数 | Exchange | 在 A 中分配给已受理订单的服务端引用号，输出简写为 order_ref |
| Match Number / 8 字节整数 | Exchange | 在 E 中标识这一次成交，输出简写为 match；一笔订单可以有多次成交 |

Nasdaq 的 UserRefNum 在规定账户与编号流范围内须当日唯一、严格递增；ClOrdID 是另一项字符标识，不能代替它的去重与关联规则。[OUCH 5.0 编号规则](https://www.nasdaqtrader.com/content/technicalsupport/specifications/TradingProducts/OUCH5.0.pdf)

课程 OUCH 的订单引用号、成交编号由本次模拟 Exchange 生成；ITCH 中同名字段来自历史市场数据。**本课不能用两边同名的号把一笔模拟成交硬对到历史成交。**

### 把 Enter Order 读成一笔委托

请求 O 的字段从 OUCH 消息起点算偏移。四个编号已在上面讲过，下面只解释这笔单的业务条件与长度：

| 字段（请求 O 的偏移 / 宽度） | 读法 |
| --- | --- |
| Side（5 / 1） | B 买入、S 卖出；这里的 S 属于订单方向，不是外层 Soup S |
| Quantity（6 / 4） | 下单股数；成交回报 E 中同名字段则是本次成交股数 |
| Symbol（10 / 8） | 股票代码，右侧补空格；同样用途在 ITCH 中叫 Stock |
| Price（18 / 8） | 限价，隐含四位小数；**OUCH 占 8 字节，ITCH A 的 Price 占 4 字节** |
| Time In Force（26 / 1） | 订单有效方式；本课取字符 3，表示 IOC（Immediate Or Cancel，立即成交，剩余取消） |
| Display（27 / 1） | 是否展示，Y 表示展示；它不是网页显隐开关 |
| Capacity（28 / 1） | 参与者交易身份，A 表示代理；课堂固定字段，不证明生产账户授权 |
| InterMarket Sweep Eligibility（29 / 1） | 跨市场扫单资格标志，本课为 N |
| CrossType（30 / 1） | 交易时段/撮合类型，本课 N 表示连续交易 |
| Appendage Length（45 / 2） | 后附可选字段的字节数，本课为 0，故请求固定为 47 字节 |

本课没有附加字段时，O/A/E 分别为 47/64/36 字节；加上 Soup 的一字节 Packet Type，Packet Length 分别为 **48/65/37**。解析器先重组 TCP 字节，再按 Soup 长度切消息，最后按 UserRefNum 找回这笔订单；不能仅凭报文紧挨着就判断属于同一笔。


## 历史输出节选

```text
10.1.1.2 / capture
===== 抓取 200 个组播行情包 =====
[抓包] 对: 200 packets captured；kernel drops 为 0  证: 本窗口的抓包完整性
$ timeout 8 tcpdump -i ens64np1 -nn -s 0 -c 200 -w …/capture.pcap 'udp dst port 31032 and dst host 233.74.125.32'
tcpdump: listening on ens64np1, link-type EN10MB (Ethernet), snapshot length 262144 bytes
200 packets captured
1375 packets received by filter
0 packets dropped by kernel

Low-Latency-Ops / readback
===== 查行情包的原始端点 =====
[报文] 对: 源 20.1.1.1，目的 233.74.125.32.31032  证: 组播包到达 Trader 数据口
$ tcpdump -nn -t -r …/live-market.pcap -c 3
reading from file …/live-market.pcap, link-type EN10MB (Ethernet), snapshot length 262144
IP 20.1.1.1.50424 > 233.74.125.32.31032: UDP, length 57
IP 20.1.1.1.50424 > 233.74.125.32.31032: UDP, length 57
IP 20.1.1.1.50424 > 233.74.125.32.31032: UDP, length 57
[解码说明] 以下字段由配套解析器读取原始文件生成；统计与 verdict 是程序汇总，不是 tcpdump 原文。

Low-Latency-Ops / decode
===== 解码 Mold 与 ITCH 字段 =====
[解码] 对: 同一 session 内序号连续，Type A 长度 36  证: 消息顺序与字段边界
$ python3 /qyt-fll/assets/03-live-traffic/inspect_market_pcap.py …/live-market.pcap
pcap_magic=d4c3b2a1 linktype=1 packets=200 mold_packets=200
path=20.1.1.1:50424->233.74.125.32:31032 session=0612260001
sequence=246200..246399 message_count=1..1 itch_types=A:180,U:20
Frame 9: 100 bytes on wire, 100 bytes captured
Ethernet II, Src: 00:0f:53:d3:af:20, Dst: 01:00:5e:4a:7d:20
Internet Protocol Version 4, Src: 20.1.1.1, Dst: 233.74.125.32
User Datagram Protocol, Src Port: 50424, Dst Port: 31032
MoldUDP64
    Session: 0612260001
    Sequence Number: 246208
    Message Count: 1
    Message Length: 36
Nasdaq TotalView-ITCH 5.0
    Message Type: A (Add Order)
    Stock Locate: 8095
    Tracking Number: 0
    Timestamp: 34250084310501
    Order Reference Number: 29440431
    Buy/Sell Indicator: B
    Shares: 1
    Stock: NVDA
    Price: 1700000
verdict=LIVE_MARKET_FLOW_PASS
[就绪说明] LIVE_MARKET_FLOW_PASS 是解析器自拼的有限检查汇总，表示本窗口解析及内置检查走通；须核对原始端点、序号与字段，不代表长期无丢包。
```

```text
10.1.1.253 / verify
===== 查行情组的成员端口 =====
[成员] 对: VLAN20 / 233.74.125.32 / Dynamic / Et2  证: 接收者在 Trader 数据口
$ show ip igmp snooping groups
20    233.74.125.32    Dynamic  -                      Et2

Low-Latency-Ops / readback
===== 查 UNICAST 的原始目的地址 =====
[报文] 对: 仅单播 20.1.1.2:42121  证: 识别本窗口的交付路径
$ tcpdump -nn -t -r …/UNICAST.pcap -c 2
reading from file …/UNICAST.pcap, link-type EN10MB (Ethernet), snapshot length 262144
IP 20.1.1.1.50424 > 20.1.1.2.42121: UDP, length 58
IP 20.1.1.1.50424 > 20.1.1.2.42121: UDP, length 41

Low-Latency-Ops / readback
===== 查 MULTICAST 的原始目的地址 =====
[报文] 对: 仅组播 233.74.125.32:31032  证: 识别本窗口的交付路径
$ tcpdump -nn -t -r …/MULTICAST.pcap -c 2
reading from file …/MULTICAST.pcap, link-type EN10MB (Ethernet), snapshot length 262144
IP 20.1.1.1.50424 > 233.74.125.32.31032: UDP, length 41
IP 20.1.1.1.50424 > 233.74.125.32.31032: UDP, length 41

Low-Latency-Ops / readback
===== 查 DUAL 的原始目的地址 =====
[报文] 对: 单播 20.1.1.2:42121 与组播 233.74.125.32:31032 均有包  证: 识别本窗口的交付路径
$ tcpdump -nn -t -r …/DUAL.pcap -c 2
reading from file …/DUAL.pcap, link-type EN10MB (Ethernet), snapshot length 262144
IP 20.1.1.1.50424 > 233.74.125.32.31032: UDP, length 41
IP 20.1.1.1.50424 > 20.1.1.2.42121: UDP, length 41

10.1.1.2 / membership
===== 查行情组的主机订阅 =====
[成员] 对: inet 233.74.125.32；一个订阅时省略 users  证: 行情接收器已加组
$ ip maddr show dev ens64np1
	inet  233.74.125.32
[解码说明] 以下字段由配套解析器读取原始文件生成；统计与 verdict 是程序汇总，不是 tcpdump 原文。

Low-Latency-Ops / decode
===== 对照三种模式与应用计数 =====
[解码] 对: DUAL 两端点有包、重合与 duplicate_delta 大于 0、pending/gaps 为 0  证: 短窗口副本及去重关系
$ python3 /qyt-fll/assets/03-live-traffic/inspect_transport_pcaps.py …/UNICAST.pcap …/MULTICAST.pcap …/DUAL.pcap --duplicates-before 73 --duplicates-after 1629 --membership-users 1 --pending 0 --gaps 0
mode=UNICAST captured=120 multicast=0 unicast=120
mode=MULTICAST captured=120 multicast=120 unicast=0
mode=DUAL captured=120 multicast=60 unicast=60
membership=233.74.125.32 users=1 dual_sequence_overlap=60 duplicate_delta=1556 pending=0 gaps=0
verdict=THREE_TRANSPORT_MODES_PASS
[就绪说明] THREE_TRANSPORT_MODES_PASS 是解析器自拼的有限检查汇总，表示三窗解析及内置检查走通；须核对目的地址、序号重合和应用计数，不代表长期无丢包。
```

```text
10.1.1.2 / sessions
===== 查订单连接与进程归属 =====
[连接] 对: AUTO/MANUAL 各有到 .1:43120 的已建立连接  证: 用 PID 区分两条会话
$ printf 'auto_pid='; cat …/trader-auto.pid; printf 'manual_pid='; cat …/trader-manual.pid; ss -ntpH state established '( dport = :43120 )'
auto_pid=23449
manual_pid=23455
0      0      20.1.1.2:55407 20.1.1.1:43120 users:(("flle-trader",pid=23455,fd=7))
0      0      20.1.1.2:50879 20.1.1.1:43120 users:(("flle-trader",pid=23449,fd=6))

Low-Latency-Ops / first-trade
===== 提交一股 MANUAL IOC =====
[本单] 对: ORDER_EXECUTED、filled=1；记下 order_id  证: 关联本次成交与报文
$ python3 /qyt-fll/apps/flle-trading-lab/tests/first_trade.py --base-url http://10.1.1.101:8088

Low-Latency-Ops / first-trade
===== 查本次提交结果 =====
[本单] 对: ORDER_EXECUTED、filled=1；记下 order_id  证: 与 O/A/E 的 user_ref 对号
$ sed -n '/^order_id=/p; /^result=/p' …/first-trade.txt
order_id=2100000001 attempts=1 origin=MANUAL_GUI symbol=AAPL side=SELL quantity=1
result=ORDER_EXECUTED filled=1

Low-Latency-Ops / readback
===== 查订单包的原始端点 =====
[报文] 对: MANUAL 临时端口与 Exchange 43120 双向通信  证: 订单沿同一 TCP 连接往返
$ tcpdump -nn -t -r …/live-order.pcap -c 2
reading from file …/live-order.pcap, link-type EN10MB (Ethernet), snapshot length 262144
IP 20.1.1.2.55407 > 20.1.1.1.43120: Flags [P.], seq 1538463760:1538463810, ack 2092278696, win 502, options [nop,nop,TS val 417620606 ecr 2244201062], length 50
IP 20.1.1.1.43120 > 20.1.1.2.55407: Flags [P.], seq 1:68, ack 50, win 509, options [nop,nop,TS val 2244227528 ecr 417620606], length 67
[解码说明] 以下字段由配套解析器读取原始文件生成；统计与 verdict 是程序汇总，不是 tcpdump 原文。

Low-Latency-Ops / decode
===== 关联 OUCH 请求与回报 =====
[解码] 对: O/A/E 的 user_ref 等于本单 order_id，E 的 filled=1  证: 同一笔订单受理并成交
$ python3 /qyt-fll/assets/03-live-traffic/inspect_order_pcap.py …/live-order.pcap …/sessions.txt --first-trade …/first-trade.txt
pcap_magic=d4c3b2a1 linktype=1 established_sessions=2 captured_payload_flows=2 auto_pid=23449 manual_pid=23455
manual_flow=20.1.1.2:55407->20.1.1.1:43120 soup_client=U soup_server=S
OUCH_O user_ref=2100000001 clordid=MANU2100000001 symbol=AAPL side=SELL quantity=1 limit_x10000=2916300
OUCH_A user_ref=2100000001 order_ref=100022 state=L
OUCH_E user_ref=2100000001 filled=1 fill_x10000=2966300 match=900022
identity=user_ref:O=A=E clordid:O=A verdict=LIVE_ORDER_FLOW_PASS
[就绪说明] LIVE_ORDER_FLOW_PASS 是解析器自拼的有限检查汇总，表示所选订单解析及内置检查走通；须核对本单 order_id、O/A/E 和 filled，不代表长期无丢包或所有订单均成功。
Frame 1: 116 bytes on wire, 116 bytes captured
Ethernet II, Src: 00:0f:53:d3:af:21, Dst: 00:0f:53:d3:af:20
Internet Protocol Version 4, Src: 20.1.1.2, Dst: 20.1.1.1
Transmission Control Protocol, Src Port: 55407, Dst Port: 43120
SoupBinTCP
    Packet Length: 48
    Packet Type: U (Unsequenced Data)
Nasdaq OUCH 5.0
    Type: O (Enter Order)
    UserRefNum: 2100000001
    Side: S
    Quantity: 1
    Symbol: AAPL
    Price: 2916300
    Time In Force: 3
    Display: Y
    Capacity: A
    InterMarket Sweep Eligibility: N
    CrossType: N
    ClOrdID: MANU2100000001
    Appendage Length: 0
```

## Session 与回放

**Session 何时更换，由发布端的会话管理规则决定。** MoldUDP64 允许按时间划分会话，但没有规定每日更换次数，也没有规定重启或故障切换必定更换。查到的 Nasdaq 公开资料没有说明：实际运行中，Session 每天更换几次，以及什么情况下会更换。[MoldUDP64 规范](https://www.nasdaqtrader.com/content/technicalsupport/specifications/dataproducts/moldudp64.pdf)

序号只在所属 Session 内有意义，不能跨 Session 接着比较；补发旧消息保留原序号。本课每包只装一条 ITCH，重新开始回放时创建新会话并从 1 编号，暂停后继续则沿用原会话。[本课发布程序](../../apps/flle-trading-lab/src/exchange.cpp)

## TCP 中怎样划分业务消息

### 这笔订单的三个业务包与完整抓包

正文只展示 O/A/E。09-10 的订单 pcap 共 9 帧：所选 MANUAL 连接占前 4 帧，其余 5 帧属于 AUTO 的另一条连接。

| pcap 帧号 | MANUAL 连接中的内容 | TCP 载荷长度 |
| --- | --- | --- |
| 1 | 客户端 → Exchange，Soup U 承载 O 下单请求 | 50 字节 |
| 2 | Exchange → 客户端，Soup S 承载 A 受理回报 | 67 字节 |
| 3 | Exchange → 客户端，Soup S 承载 E 成交回报 | 39 字节 |
| 4 | 客户端 → Exchange，纯 TCP ACK | 0 字节 |

TCP ACK 确认字节收到，成交由 E 回报。连接在抓包前已经建立并登录；三条业务消息各占一包是本次样例的结果，协议不保证固定包数。

逐帧证据见 [包数核对记录](../../refs/evidence/chapter03-order-packet-counts-20260912.json)；请求的网络层详情见 [第 1 帧解码树](../../images/course-visuals/03-diagrams/03-order-packet-details.svg)。

### 先分帧，再认请求和回报

TCP 提供有序字节流：一条消息可能跨多个 TCP 报文，多条也可能合在一包中。**分帧（framing）** 就是从字节流里切出完整消息。

SoupBinTCP 的格式是“2 字节 Packet Length + 1 字节 Packet Type + 消息内容”；Packet Length 只计算后两项，不包括自身的 2 字节。

Soup 的 **U（Unsequenced Data，未编号业务数据）** 承载客户端请求，**S（Sequenced Data，按会话顺序编号的业务数据）** 承载服务端回报。内层才是 OUCH 类型；S 的顺序由会话计数维护，消息里没有显式序号。[SoupBinTCP 规范](https://www.nasdaqtrader.com/content/technicalsupport/specifications/dataproducts/soupbintcp.pdf)
