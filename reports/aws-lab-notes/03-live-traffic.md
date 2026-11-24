# 第 03 章：抓包读懂行情和订单报文

- **状态：** ✅ 2026-11-15 完成（运行 ①、③；运行 ② 需要组播，跳过）
- **课程原文：** [03-live-trading-traffic-and-protocols.md](../../03-live-trading-traffic-and-protocols.md)
- **课程脚本：** [assets/03-live-traffic/](../../assets/03-live-traffic/)
- **抓包文件：** [../aws-runs/20261115T034730Z-03-live-traffic/](../aws-runs/20261115T034730Z-03-live-traffic/)
- **前置：** 第 02 章的交易系统在运行（`bash aws/flle-aws.sh start`）

---

## 准备：把课程的解析脚本搬到 `.2`，改地址

课程的 `01-capture-live-market.sh` 外面包了很多课程实验台专用的东西（`/qyt-fll` 路径、切换行情模式、生成哈希）。真正干活的只有两步：**tcpdump 抓包**，再用 **`inspect_*_pcap.py` 解析**。所以只搬三个 Python 解析脚本，把里面写死的地址换掉。

在本机 `assets/03-live-traffic` 目录执行：

```bash
cd assets/03-live-traffic
tar -cf - pcap_tools.py inspect_market_pcap.py inspect_order_pcap.py | ssh flle-tr2 'set -e
mkdir -p ~/flle/ch03 && cd ~/flle/ch03 && tar -xf -
sed -i "s/\r$//" *.py                                     # 去 Windows 换行符
sed -i -e "s/233\.74\.125\.32:31032/172.31.12.156:42121/g; s/\"233\.74\.125\.32\"/\"172.31.12.156\"/g; s/destination_port != 31032/destination_port != 42121/" \
       -e "s/20\.1\.1\.1/172.31.10.43/g; s/20\.1\.1\.2/172.31.12.156/g" \
       inspect_market_pcap.py inspect_order_pcap.py
grep -n "172\.31\|42121\|233\.\|20\.1\.1" inspect_market_pcap.py inspect_order_pcap.py   # 确认替换干净
ip -o route get 172.31.10.43 | grep -oP "dev \K\S+"       # 去 .1 的包走哪个网口 → enp39s0'
```

| 课程 | AWS |
|---|---|
| 行情：组播 `233.74.125.32:31032` | 单播 `172.31.12.156:42121` |
| `.1` 数据口 `20.1.1.1` | `172.31.10.43` |
| `.2` 数据口 `20.1.1.2` | `172.31.12.156` |
| 抓包网口 `ens64np1` | `enp39s0` |

`ip route get` 的用法：问内核“去这个 IP 的包从哪个网口出”，用来确定该在哪个网口上抓。

---

## 运行 ①：抓取并解读行情包 ✅ `LIVE_MARKET_FLOW_PASS`

### 执行的命令

```bash
ssh flle-tr2 'set -e; cd ~/flle/ch03
sudo timeout 8 tcpdump -i enp39s0 -nn -s 0 -c 200 -w live-market.pcap "udp dst port 42121 and src host 172.31.10.43"
sudo chown ubuntu live-market.pcap
python3 inspect_market_pcap.py live-market.pcap'
```

| 参数 | 意思 |
|---|---|
| `timeout 8` | 最多抓 8 秒，防止没流量时一直挂着 |
| `-s 0` | 抓完整的包（snaplen 不截断），解析需要完整报文 |
| `-c 200` | 抓 200 个就停 |
| `-w live-market.pcap` | 写进文件，不在屏幕上显示 |
| `udp dst port 42121 and src host 172.31.10.43` | 只要 `.1` 发来、目的端口 42121 的 UDP（行情） |
| `chown` | tcpdump 用 sudo 跑，文件属于 root，改回普通用户方便后续读 |

### 实际输出

```text
tcpdump: listening on enp39s0, link-type EN10MB (Ethernet), snapshot length 262144 bytes
200 packets captured
980 packets received by filter
0 packets dropped by kernel
pcap_magic=d4c3b2a1 linktype=1 packets=200 mold_packets=200
path=172.31.10.43:49471->172.31.12.156:42121 session=0612260001
sequence=438796..438995 message_count=1..1 itch_types=A:86,D:69,E:9,P:4,U:32
Frame 3: 100 bytes on wire, 100 bytes captured
Ethernet II, Src: 0a:ff:fb:76:11:81, Dst: 0a:ff:f4:5f:2b:61
Internet Protocol Version 4, Src: 172.31.10.43, Dst: 172.31.12.156
User Datagram Protocol, Src Port: 49471, Dst Port: 42121
MoldUDP64
    Session: 0612260001
    Sequence Number: 438798
    Message Count: 1
    Message Length: 36
Nasdaq TotalView-ITCH 5.0
    Message Type: A (Add Order)
    Stock Locate: 37
    Tracking Number: 0
    Timestamp: 34360774167292
    Order Reference Number: 97968153
    Buy/Sell Indicator: B
    Shares: 40
    Stock: AAPL
    Price: 2958400
verdict=LIVE_MARKET_FLOW_PASS
```

### 怎么读

**一个行情包的层次：** 以太网 → IP → UDP → **MoldUDP64**（传输层封装）→ **ITCH 5.0**（业务消息）

| 字段 | 值 | 意思 |
|---|---|---|
| `pcap_magic=d4c3b2a1` | | pcap 文件的魔数（小端），说明文件格式正确 |
| `Session` | 0612260001 | 当天的会话 ID。06-12 + 26 年 + 第 0001 次回放 |
| `Sequence Number` | 438798 | 消息序号。接收方靠它**发现丢包**：收到 438800 而期待 438799，就知道丢了一个 |
| `sequence=438796..438995` | | 200 个包序号连续，没有缺口、没有重复 |
| `Message Count: 1` | | 这个包里装了 1 条 ITCH 消息（MoldUDP64 允许一个包装多条） |
| `Message Type: A` | Add Order | 有人新挂了一个单 |
| `Stock Locate: 37` | | 股票的数字编号（AAPL=37），程序比较整数比比较字符串快 |
| `Timestamp` | 34360774167292 | 当天零点以来的纳秒数 = 9:32:40.77 |
| `Buy/Sell: B, Shares: 40, Price: 2958400` | | 买 40 股 @ 295.84（价格乘了 10000） |
| `itch_types=A:86,D:69,E:9,P:4,U:32` | | 200 条里：新单 86、撤单 69、成交 9、非显示成交 4、改单 32 |

`980 packets received by filter`：8 秒里过滤器看到 980 个包，抓够 200 就停了。

---

## 运行 ②：对照三种行情传输模式 ⏭️ 跳过

课程要比较 MULTICAST_A / DUAL（A+B 双路组播）/ UNICAST。AWS VPC 默认没有组播。AWS 有 Transit Gateway 组播，但配置复杂、额外收费，也不能代表交易所的真实组播，所以没做。

---

## 运行 ③：下一单，看请求与回报 ✅ `LIVE_ORDER_FLOW_PASS`

### 思路

后台开 tcpdump 抓订单端口 43120，同时用 `first_trade.py` 下一笔手动单，再记下两个交易员各自用的 TCP 连接，最后解析。

### 执行的命令

```bash
ssh flle-tr2 'cd ~/flle/ch03; rm -f live-order.pcap
# 1) 后台抓包，6 秒后发 SIGINT 让 tcpdump 正常收尾
sudo timeout -s INT 6 tcpdump -i enp39s0 -nn -s 0 -U -w live-order.pcap "tcp port 43120" 2>tcpdump.txt & CAP=$!
sleep 0.7
# 2) 下一单（MANUAL 交易员）
python3 ~/flle/app/tests/first_trade.py --base-url http://172.31.12.156:8088 > first-trade.txt 2>&1
cat first-trade.txt
# 3) 记录两个交易员的 PID 和它们连交易所的 TCP 连接
{ printf "auto_pid="; cat ~/flle/run/trader-auto.pid
  printf "manual_pid="; cat ~/flle/run/trader-manual.pid
  sudo ss -ntpH state established "( dport = :43120 )"; } > sessions.txt
cat sessions.txt
wait $CAP; cat tcpdump.txt
sudo chown ubuntu live-order.pcap
# 4) 解析：用 sessions.txt 区分哪条连接是 MANUAL
python3 inspect_order_pcap.py live-order.pcap sessions.txt --first-trade first-trade.txt'
```

| 参数 | 意思 |
|---|---|
| `timeout -s INT 6` | 6 秒后发 Ctrl+C 信号而不是强杀，tcpdump 会把缓冲写完再退 |
| `-U` | 每个包立刻写进文件（不攒缓冲），配合上面防止丢掉最后几个包 |
| `& CAP=$!` | 后台运行，记下它的 PID，后面 `wait $CAP` 等它结束 |
| `ss -ntpH state established "( dport = :43120 )"` | 列出所有已建立、目的端口 43120 的 TCP 连接：`-n` 不解析名字、`-t` TCP、`-p` 显示进程、`-H` 不要表头 |

### 实际输出

```text
order_id=2100000001 attempts=1 origin=MANUAL_GUI symbol=AAPL side=SELL quantity=1
limit_price_x10000=2912900 fill_price_x10000=2962900
result=ORDER_EXECUTED filled=1
position_delta=-1 manual_position=0 order_rtt_ns=302572
verdict=FIRST_TRADE_PASS

auto_pid=7610
manual_pid=7771
0      0      172.31.12.156:57033 172.31.10.43:43120 users:(("flle-trader",pid=7771,fd=7))
0      0      172.31.12.156:49829 172.31.10.43:43120 users:(("flle-trader",pid=7610,fd=6))

12 packets captured
======
established_sessions=2 captured_payload_flows=2 auto_pid=7610 manual_pid=7771
manual_flow=172.31.12.156:57033->172.31.10.43:43120 soup_client=U soup_server=S
OUCH_O user_ref=2100000001 clordid=MANU2100000001 symbol=AAPL side=SELL quantity=1 limit_x10000=2912900
OUCH_A user_ref=2100000001 order_ref=100060 state=L
OUCH_E user_ref=2100000001 filled=1 fill_x10000=2962900 match=900060
identity=user_ref:O=A=E clordid:O=A verdict=LIVE_ORDER_FLOW_PASS

Frame 1: 116 bytes on wire
Internet Protocol Version 4, Src: 172.31.12.156, Dst: 172.31.10.43
Transmission Control Protocol, Src Port: 57033, Dst Port: 43120
SoupBinTCP
    Packet Length: 48
    Packet Type: U (Unsequenced Data)
Nasdaq OUCH 5.0
    Type: O (Enter Order)
    UserRefNum: 2100000001
    Side: S
    Quantity: 1
    Symbol: AAPL
    Price: 2912900
    Time In Force: 3
    ClOrdID: MANU2100000001
```

### 怎么读

**一个订单包的层次：** 以太网 → IP → TCP → **SoupBinTCP**（会话层）→ **OUCH 5.0**（下单协议）

| 消息 | 方向 | 内容 |
|---|---|---|
| **O** Enter Order | 交易员 → 交易所 | 卖 1 股 AAPL，限价 291.29 |
| **A** Accepted | 交易所 → 交易员 | 交易所接受了，给它分配交易所内部编号 order_ref=100060 |
| **E** Executed | 交易所 → 交易员 | 成交 1 股 @ 296.29，成交编号 900060 |

- 三条消息靠 `user_ref=2100000001` 串起来（`O=A=E`）。这个号是交易员自己编的，所以 MANUAL 从 21 亿开始、AUTO 从 1 开始，永远不会撞
- `soup_client=U`：客户端发的是 SoupBinTCP 的 U 类型包（Unsequenced，无序号）；`soup_server=S`：交易所回的是 S 类型（Sequenced，带序号，断线可以按序号补发）
- 限价 291.29 低于市价，作为卖单会立刻按更好的价格 296.29 成交
- 有两条 TCP 连接（AUTO 和 MANUAL 各一条），`ss -p` 的 pid 告诉我们哪条是 MANUAL：端口 57033
- 往返 302 µs，比第 02 章那次 114 µs 慢，是云网络的抖动

**行情 vs 订单：**

| | 行情 | 订单 |
|---|---|---|
| 方向 | 交易所 → 所有人 | 交易员 ↔ 交易所 |
| 传输 | UDP（真实交易所用组播） | TCP |
| 丢了怎么办 | 靠 MoldUDP64 序号发现，再去补 | TCP 自动重传 |
| 协议 | MoldUDP64 + ITCH | SoupBinTCP + OUCH |

---

## 在自己电脑上用 Wireshark 看

先把文件拷回本机：

```bash
OUT="reports/aws-runs/$(date -u +%Y%m%dT%H%M%SZ)-03-live-traffic"; mkdir -p "$OUT"
for f in live-market.pcap live-order.pcap first-trade.txt sessions.txt; do
  ssh flle-tr2 "cat ~/flle/ch03/$f" > "$OUT/$f"
done
```

用命令行版 tshark（Wireshark 自带，在 PowerShell 里）：

```powershell
$t = "C:\Program Files\Wireshark\tshark.exe"
$d = "reports\aws-runs\20261115T034730Z-03-live-traffic"
# -d udp.port==42121,moldudp64 = 图形界面里的 “Decode As”：把 42121 端口当 MoldUDP64 解析
& $t -r "$d\live-market.pcap" -d udp.port==42121,moldudp64 -c 2 -V -O moldudp64,nasdaq_itch
& $t -r "$d\live-order.pcap"  -d tcp.port==43120,soupbintcp
```

图形界面：打开 pcap → 右键一个包 → **Decode As…** → 端口 42121 选 MoldUDP64（订单的 43120 选 SoupBinTCP）。

**结果：**
- 行情：能解出 MoldUDP64 的 Session、序号、条数；里面的 ITCH 只显示十六进制
- 订单：Wireshark 会自动认成 **BIST-OUCH**（土耳其交易所的版本），标 `Malformed Packet`，字段是错的。字段以课程脚本的解析为准，Wireshark 只用来看时间和方向

## 和课程原版的区别

- 课程脚本本身没改，只复制了三个解析脚本，替换了 IP 和端口
- 省掉了原脚本里切换行情模式、自动恢复、生成证据哈希这几步

## 笔记 / 疑问

（自己补充）
