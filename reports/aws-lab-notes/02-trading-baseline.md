# 第 02 章：部署完整交易平台，完成第一笔交易

- **状态：** ✅ 2026-11-15 完成，`FIRST_TRADE_PASS`
- **课程原文：** [02-host-native-trading-system-baseline.md](../../02-host-native-trading-system-baseline.md)
- **启停脚本：** [apps/flle-trading-lab/aws/flle-aws.sh](../../apps/flle-trading-lab/aws/flle-aws.sh)
- **前置：** 两台机器已经按 [aws-setup.md](aws-setup.md) 建好

## 整体结构

```text
           flle-ex1 (.1, 172.31.10.43)                    flle-tr2 (.2, 172.31.12.156)
 ┌────────────────────────────────┐   行情 UDP 单播 :42121   ┌─────────────────────────────────┐
 │ flle-exchange                  │ ───────────────────────▶ │ flle-feed-receiver              │
 │  · 读 ITCH 文件回放行情           │                          │   └▶ unix socket feed.sock     │
 │  · 撮合订单                      │   订单 TCP :43120         │ flle-trader --role AUTO  :48121 │
 │  · 管理口 :48120                 │ ◀─────────────────────── │ flle-trader --role MANUAL:48122 │
 └────────────────────────────────┘                          │ gateway (python 网页) :8088      │
                                                             └─────────────────────────────────┘
```

课程里网关在 `.101`，这里放在 `.2` 上；课程用组播，这里用单播（VPC 默认没有组播）。

---

## 第 1 步：两台机器装编译环境

在本机 Git Bash 执行，`&` 让两台并行装，`wait` 等两台都装完：

```bash
for h in flle-ex1 flle-tr2; do
  ssh $h 'sudo DEBIAN_FRONTEND=noninteractive apt-get update -qq &&
          sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq g++-11 make python3 tcpdump ethtool >/dev/null &&
          g++-11 --version | head -1 && python3 --version' 2>&1 | sed "s/^/[$h] /" &
done; wait
```

- `DEBIAN_FRONTEND=noninteractive`：装包时不弹交互问题
- `sed "s/^/[$h] /"`：在每行输出前加上主机名，两台并行输出也分得清

输出：

```text
[flle-tr2] g++-11 (Ubuntu 11.4.0-1ubuntu1~22.04.3) 11.4.0
[flle-tr2] Python 3.10.12
[flle-ex1] g++-11 (Ubuntu 11.4.0-1ubuntu1~22.04.3) 11.4.0
[flle-ex1] Python 3.10.12
```

## 第 2 步：上传源码并编译

在本机 `apps/flle-trading-lab` 目录下，把源码打成 tar 包，通过 SSH 管道直接解压到远端（不用 scp、不落中间文件）：

```bash
cd apps/flle-trading-lab
tar -cf - Makefile src flle_trading web tests scripts tools \
    -C ../../assets/06-arista-time lanz_stream_collector.py format_lanz_result.py > /tmp/flle-src.tar

for h in flle-ex1 flle-tr2; do
  ( ssh $h 'rm -rf ~/flle/app && mkdir -p ~/flle/app && cd ~/flle/app && tar -xf - &&
            mv lanz_stream_collector.py format_lanz_result.py tests/ &&
            make -j2 all tools 2>&1 | tail -3 && ls build/' < /tmp/flle-src.tar | sed "s/^/[$h] /" ) &
done; wait
```

- `tar -cf -`：`-` 表示输出到标准输出，而不是写文件
- `-C 目录 文件`：先切到那个目录再打包后面的文件（测试要用到这两个第 06 章的脚本）
- `make -j2 all tools`：用 2 个核并行编译。编出 `build/flle-exchange`、`flle-trader`、`flle-feed-receiver`、`flle-book-checkpoint` 等

## 第 3 步：跑单元测试，修两个坑

```bash
ssh flle-tr2 'cd ~/flle/app && make test 2>&1 | tail -40'
```

**第一次失败：**

```text
AssertionError: 2 != 0 : /home/ubuntu/flle/app/scripts/platform-baseline.sh: line 3: syntax error near unexpected token `$'{\r''
...
Ran 270 tests in 6.318s
FAILED (failures=4, errors=1, skipped=13)
```

**坑 1：Windows 换行符。** 报错里的 `$'{\r'` 说明脚本行尾有 `\r`。原因是本机 git 设了 `core.autocrlf=true`，checkout 出来的文件都是 CRLF：

```bash
git -C ../.. config core.autocrlf          # → true
file scripts/labctl.sh                      # → ... with CRLF line terminators
```

修复：在两台机器上把所有文本文件的 `\r` 去掉：

```bash
for h in flle-ex1 flle-tr2; do
  ssh $h 'cd ~/flle/app && grep -rlI $'"'"'\r'"'"' . --exclude-dir=build | xargs -r sed -i "s/\r$//" && echo crlf_fixed'
done
```

- `grep -rlI '\r'`：递归（r）找含 `\r` 的文件，只列文件名（l），跳过二进制（I）
- `xargs -r sed -i "s/\r$//"`：对这些文件原地删掉行尾的 `\r`；`-r` 表示没找到文件就不执行
- `$'"'"'\r'"'"'` 是在单引号里再嵌一个 `$'\r'` 的写法，看着乱，其实就是 `$'\r'`

**坑 2：UDP 接收缓冲区。** 再跑还剩一个失败，单独启动行情接收程序看原因：

```bash
ssh flle-tr2 'cd ~/flle/app && timeout 3 build/flle-feed-receiver --data-ip 127.0.0.1 --multicast-source 127.0.0.1 \
  --socket /tmp/t.sock --unicast-port 50001 --multicast-port 50002 --multicast-port-b 50003 --telemetry-host off;
  echo rc=$?; sysctl net.core.rmem_max'
```

```text
rc=1
feed_receiver: feed UDP receive buffer capped: CAP_NET_ADMIN or a sufficient net.core.rmem_max is required
net.core.rmem_max = 212992
```

程序要求 UDP 接收缓冲 ≥ 8 MiB，系统默认上限只有 208 KB。修复（写进配置文件，重启也生效）：

```bash
for h in flle-ex1 flle-tr2; do
  ssh $h 'echo -e "net.core.rmem_max=16777216\nnet.core.wmem_max=16777216" | sudo tee /etc/sysctl.d/90-flle.conf >/dev/null &&
          sudo sysctl -q --system && sysctl net.core.rmem_max'
done
ssh flle-tr2 'cd ~/flle/app && make test 2>&1 | tail -4'
```

```text
net.core.rmem_max = 16777216
Ran 270 tests in 6.668s
OK (skipped=13)
```

**为什么缓冲区重要：** 行情是 UDP，没有重传。如果程序来不及读、内核缓冲又满了，新来的包会被直接丢掉，行情就出现缺口。缓冲区越大，能扛的突发流量越多。

## 第 4 步：上传行情数据，生成开盘订单簿

```bash
# 562 MB 的 ITCH 文件：直接 scp 到 ex1 的公网 IP，不走跳板（更快）
cd artifacts/blobs/nasdaq/S061226-v50
ssh flle-ex1 'mkdir -p ~/flle/data'
scp -o ProxyJump=none -o HostName=<ex1公网IP> -o Compression=no \
    AAPL_NVDA.itch AAPL_NVDA.manifest.json flle-ex1:flle/data/
ssh flle-ex1 'cd ~/flle/data && sha256sum AAPL_NVDA.itch'     # 和 manifest 里的哈希对一下

# 从 09:30:00 开盘时刻（34200000000000 纳秒 = 9.5 小时）生成订单簿快照
ssh flle-ex1 'mkdir -p ~/flle/run && cd ~/flle/run &&
  ln -sf ~/flle/data/AAPL_NVDA.itch . && cp ~/flle/data/AAPL_NVDA.manifest.json . &&
  time ~/flle/app/build/flle-book-checkpoint AAPL_NVDA.itch opening-book.checkpoint 34200000000000 &&
  sha256sum opening-book.checkpoint'

# 交易员那边也需要同一份快照：直接从 ex1 管道转给 tr2
ssh flle-tr2 'mkdir -p ~/flle/run'
ssh flle-ex1 'cat ~/flle/run/opening-book.checkpoint' | ssh flle-tr2 'cat > ~/flle/run/opening-book.checkpoint && sha256sum ~/flle/run/opening-book.checkpoint'
```

```text
checkpoint=PASS start_ns=34200000000000 source_messages=97498 active_orders=18108
1543c06f281665e3...  opening-book.checkpoint            ← ex1
1543c06f281665e3...  /home/ubuntu/flle/run/opening-book.checkpoint   ← tr2，一致
```

**这是什么：** ITCH 文件从凌晨开始记录。开盘前已经有 18108 笔挂单，如果不先建好订单簿，交易员看到的盘口就不对。快照让交易所和交易员从同一个起点开始。

## 第 5 步：按顺序启动五个程序

把课程的 `labctl.sh` 改写成了 [flle-aws.sh](../../apps/flle-trading-lab/aws/flle-aws.sh)。在本机 `apps/flle-trading-lab` 目录运行：

```bash
bash aws/flle-aws.sh start
```

它实际依次执行的远程命令（简化后）：

```bash
# .2 上：1) 行情接收，单播，收到的行情通过 unix socket 分给两个交易员
flle-feed-receiver --socket ~/flle/run/feed.sock --data-ip 172.31.12.156 --multicast-receiver 0 --telemetry-host 172.31.12.156

# .2 上：2) AUTO 交易员（自动策略），管理端口 48121；等端口监听、行情接收 READY 再往下
flle-trader --role AUTO --data-ip 172.31.12.156 --management-ip 172.31.12.156 --exchange-data-ip 172.31.10.43 \
  --management-port 48121 --feed-socket ~/flle/run/feed.sock --user-ref-base 1 --user-ref-span 2000000000 \
  --clordid-prefix AUTO --telemetry-host 172.31.12.156 --book-checkpoint ~/flle/run/opening-book.checkpoint

# .2 上：3) MANUAL 交易员（网页手动下单），管理端口 48122，订单号从 2100000000 开始，避免和 AUTO 冲突
flle-trader --role MANUAL ... --management-port 48122 --user-ref-base 2100000000 --clordid-prefix MANU ...

# .1 上：4) 交易所：单播把行情发到 .2，回放 2026-06-12 的数据，1 倍速
flle-exchange --data-ip 172.31.10.43 --trader-data-ip 172.31.12.156 --management-ip 172.31.10.43 \
  --telemetry-host 172.31.12.156 --market-mode UNICAST --replay-file ~/flle/run/AAPL_NVDA.itch \
  --book-checkpoint ~/flle/run/opening-book.checkpoint --market-date 2026-06-12 --replay-speed 1

# .2 上：5) 网页网关
python3 -m flle_trading.gateway --bind-ip 172.31.12.156 --exchange-host 172.31.10.43 --trader-host 172.31.12.156 --web-root ~/flle/app/web
```

每个程序都用 `nohup ... &` 放到后台，PID 写进 `~/flle/run/名字.pid`，日志写进 `名字.log`。脚本用 `ss -ltnp` 确认端口真的在监听才启动下一个。

**为什么是这个顺序：** 交易员要先连上行情接收，交易所一开就开始发行情和接受订单，所以接收方先就绪；网关最后，因为它要连所有组件。

输出：

```text
feed-receiver started pid=7560
trader-auto started pid=7610
trader-auto listening :48121
trader-auto market_receiver=READY
trader-manual started pid=7771
trader-manual listening :48122
trader-manual market_receiver=READY
exchange started pid=3255
exchange listening :43120
exchange listening :48120
gateway started pid=7929
gateway listening :8088
READY. Open the web UI with:  aws/flle-aws.sh tunnel   then browse http://localhost:8088/
```

检查状态：

```bash
bash aws/flle-aws.sh status
```

```text
exchange=ONLINE pid=950
feed-receiver=ONLINE pid=986
trader-auto=ONLINE pid=1038
trader-manual=ONLINE pid=1205
gateway=ONLINE pid=1369
{"schema":"flle.terminal-health.v1","session":"0612260001","market_mode":"UNICAST","replay":{"status":"PLAYING","speed":1,"source_clock":"09:30:14.308635302",...
```

## 第 6 步：完成第一笔交易

**方法一：脚本**（课程的验收脚本，在 `.2` 上跑）

```bash
ssh flle-tr2 'cd ~/flle/app && timeout 120 python3 tests/first_trade.py --base-url http://172.31.12.156:8088'
```

```text
system=READY source=NASDAQ_PUBLIC_ITCH_SAMPLE date=2026-06-12 replay=PLAYING
market_clock=09:30:43.086172155->09:30:43.820665844 source_advance_ns=734493689
order_id=2100000000 attempts=1 origin=MANUAL_GUI symbol=AAPL side=BUY quantity=1
limit_price_x10000=3014200 fill_price_x10000=2964200
result=ORDER_EXECUTED filled=1
position_delta=+1 manual_position=1 order_rtt_ns=113872
history=CLIENT_AND_EXCHANGE strategy_unchanged=true
verdict=FIRST_TRADE_PASS
```

逐行读：
- 行情钟在走（09:30:43.08 → 09:30:43.82），说明回放在推进
- 买 1 股 AAPL，限价 301.42（`x10000` 表示价格乘了 10000，用整数存，避免浮点误差），成交价 296.42
- 限价比市价高，所以立即成交；持仓 +1
- `order_rtt_ns=113872`：从发单到收到成交回报约 114 µs
- AUTO 策略没被影响（`strategy_unchanged=true`）

**方法二：网页**

```bash
bash aws/flle-aws.sh tunnel        # 本质是 ssh -N -L 8088:172.31.12.156:8088 flle-tr2
# 浏览器打开 http://localhost:8088/
```

`-L 本地端口:目标IP:目标端口` 是 SSH 本地端口转发：访问本机 8088，SSH 帮你转到 `.2` 的 8088。`-N` 表示不执行远程命令，只做转发。

## 第 7 步：收工

```bash
bash aws/flle-aws.sh stop          # 按反序停：网关 → 交易所 → 两个交易员 → 行情接收
# 然后按 aws-setup.md 停机
```

---

## 结果

| 检查项 | 结果 |
|---|---|
| 单元测试 | 270 个通过，13 个跳过（跳过的是要课程实验台专有文件的） |
| 5 个组件 | 全部 ONLINE |
| 行情 | PLAYING，从 09:30 开盘开始，HEALTHY，0 缺口 |
| AUTO 策略 | 14 笔下单，13 笔成交；下单延迟 p50 ≈ 174 µs，p99 ≈ 262 µs |
| 第一笔手动单 | 买 1 股 AAPL @ 296.42，往返 113,872 ns |

## 和课程原版的区别

| 课程 | AWS | 影响 |
|---|---|---|
| 准备 B1/B2：IOMMU、DPDK/F-Stack | 跳过 | 第 05 章才需要 |
| 准备 C：交换机组播配置 | 跳过，改用 UNICAST | 运行 ①A/①B（加入组播组、看交换机成员表）做不了 |
| `.1`/`.2` 各两个网口 | 每台一个 ENA 网口 | 数据和管理流量走同一个 IP |
| 网关在 `.101` | 网关在 `.2` | 只是位置不同 |
| 课程脚本在 `/qyt-fll` 下 | `~/flle/app` | 所以课程的 `assets/*.sh` 都不能直接跑，要改路径 |

## 笔记 / 疑问

（自己补充）
