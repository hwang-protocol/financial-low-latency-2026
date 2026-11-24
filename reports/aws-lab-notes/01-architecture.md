# 第 01 章：实验环境——接线、网卡、驱动与交换机

- **状态：** ✅ 2026-11-24 能做的都做了（交换机部分做不了）
- **课程原文：** [01-financial-low-latency-architecture.md](../../01-financial-low-latency-architecture.md)
- **原始输出：** [../aws-runs/20261124T1012Z-01-nic-ping/](../aws-runs/20261124T1012Z-01-nic-ping/)

## 各个运行在 AWS 上能否做

| 课程步骤 | AWS | 说明 |
|---|---|---|
| 准备 A：核对系统、补齐工具 | ✅ | 见 [02 章的部署步骤](02-trading-baseline.md) |
| 准备 B：交换机公钥登录 | ❌ | 没有 Arista 交换机 |
| 准备 C：交换基础拓扑 | ❌ | 同上 |
| 运行 ①：核对两类接口 | 🟡 | 只有一个 ENA 网口，没有 X2522 / BCM57414 |
| 运行 ②：从接口名找设备地址 | ✅ | |
| 运行 ③：查当前驱动 | ✅ | |
| 运行 ④：对齐主机与交换机链路 | ❌ | 看不到交换机侧 |
| 运行 ⑤：抓到三条 ping | ✅ | |

---

## 运行 ①②③：接口 → PCI 地址 → 驱动

### 执行的命令

在本机一次性送到 `.2` 上执行，输出存到文件。`set -x` 会在每条命令前打印一行 `+ 命令`，方便看哪段输出属于哪条命令。

```bash
mkdir -p reports/aws-runs/ch01
ssh flle-tr2 'set -x
ip -br link                                   # ① 有哪些网口，UP 还是 DOWN（-br = 简洁格式）
ip -br addr                                   # ① 每个网口的 IP
ls -l /sys/class/net/enp39s0/device           # ② 网口名 → PCI 地址（是个符号链接）
ethtool -i enp39s0                            # ③ 驱动名、版本、bus-info
lspci -nn | grep -i -E "ether|ena"            # ② PCI 设备的厂商和型号 ID
ethtool enp39s0 | grep -E "Speed|Duplex|Link detected"   # 链路状态
ip link show enp39s0 | grep -o "mtu [0-9]*"   # MTU
ethtool -l enp39s0                            # 队列（channel）数
ethtool -g enp39s0                            # 收发环（ring）大小
ethtool -k enp39s0 | grep -E "^(rx-checksumming|tx-checksumming|tcp-segmentation-offload|generic-receive-offload|large-receive-offload)"   # 网卡卸载功能
ethtool -T enp39s0                            # 支不支持硬件时间戳
' > reports/aws-runs/ch01/01-03-nic-driver.txt 2>&1
```

### 实际输出（去掉了 `+` 行）

```text
lo               UNKNOWN        00:00:00:00:00:00 <LOOPBACK,UP,LOWER_UP>
enp39s0          UP             0a:ff:f4:5f:2b:61 <BROADCAST,MULTICAST,UP,LOWER_UP>
lo               UNKNOWN        127.0.0.1/8 ::1/128
enp39s0          UP             172.31.12.156/20 metric 100 fe80::8ff:f4ff:fe5f:2b61/64

/sys/class/net/enp39s0/device -> ../../../0000:27:00.0

driver: ena
version: 6.8.0-1069-aws
bus-info: 0000:27:00.0

27:00.0 Ethernet controller [0200]: Amazon.com, Inc. Elastic Network Adapter (ENA) [1d0f:ec20]

	Link detected: yes
mtu 9001

Channel parameters for enp39s0:
Pre-set maximums:   Combined: 4
Current hardware settings:  Combined: 4

Ring parameters for enp39s0:
Pre-set maximums:   RX: 8192   TX: 1024
Current hardware settings:  RX: 1024   TX: 1024

rx-checksumming: on
tx-checksumming: on
tcp-segmentation-offload: off
generic-receive-offload: on
large-receive-offload: off [fixed]

Time stamping parameters for enp39s0:
Capabilities:
	software-transmit
	software-receive
	software-system-clock
PTP Hardware Clock: none
Hardware Transmit Timestamp Modes: none
Hardware Receive Filter Modes: none
```

### 怎么读

| 输出 | 意思 | 和课程对比 |
|---|---|---|
| 只有 `enp39s0` | 一块网卡，管理和数据都走它 | 课程每台有管理口 + X2522/BCM57414 数据口 |
| `-> 0000:27:00.0` | PCI 地址：域 0000、总线 27、设备 00、功能 0 | 课程用这个地址把网口对应到具体的卡 |
| `[1d0f:ec20]` | 厂商 ID 1d0f = Amazon，设备 ID ec20 = ENA | X2522 是 `1924:...`（Solarflare） |
| `driver: ena` | 内核驱动 ena | 课程是 `sfc`（X2522）和 `bnxt_en`（Broadcom） |
| `mtu 9001` | AWS 默认开巨帧 | 课程一般 1500 |
| `Combined: 4` | 4 个收发队列（每个 vCPU 一个） | 第 07 章 XDP 要降到 2 |
| `RX: 1024`，最大 8192 | 接收环有 1024 个槽，可以调大防丢包 | |
| `ethtool -k` 那一行报 `netlink error` | 普通用户查不了部分信息，加 sudo 就行 | |
| **`PTP Hardware Clock: none`** | **没有硬件时间戳**，只能用软件时间戳 | X2522 有，第 06 章要用；所以第 06 章在 AWS 上做不了 |

---

## 运行 ⑤：抓到三条 ping

### 思路

在 `.2` 上先开 tcpdump 等着，然后让 `.1` 去 ping `.2`，看 `.2` 能不能抓到。

### 执行的命令

```bash
# 终端 A（后台）：在 .2 上抓 3 个来自 .1 的 ICMP echo request，最多等 20 秒
ssh flle-tr2 'sudo timeout 20 tcpdump -i enp39s0 -nn -e -c 3 "icmp[icmptype] == icmp-echo and src 172.31.10.43"' \
  > reports/aws-runs/ch01/05-ping-capture.txt 2>&1 &
sleep 3    # 等 tcpdump 先就绪

# 终端 B：从 .1 发 3 个 ping，再发 1000 个看统计
ssh flle-ex1 'ping -c 3 -i 0.5 172.31.12.156
echo "--- 1000 pings, 10ms interval:"
ping -q -c 1000 -i 0.01 172.31.12.156 | tail -2' | tee reports/aws-runs/ch01/05-ping-from-ex1.txt
wait
```

| tcpdump 参数 | 意思 |
|---|---|
| `-i enp39s0` | 在这个网口上抓 |
| `-nn` | 不把 IP 解析成主机名、不把端口解析成服务名（快，也不会额外产生 DNS 包） |
| `-e` | 显示 MAC 地址（二层头） |
| `-c 3` | 抓到 3 个就退出 |
| `icmp[icmptype] == icmp-echo` | BPF 过滤：只要 ping 请求，不要回复 |

| ping 参数 | 意思 |
|---|---|
| `-c 1000` | 发 1000 个 |
| `-i 0.01` | 间隔 10 毫秒（小于 0.2 秒的间隔在新版 ping 里普通用户也能用） |
| `-q` | 只输出最后的统计 |

### 实际输出

`.1` 这边：

```text
64 bytes from 172.31.12.156: icmp_seq=1 ttl=64 time=0.278 ms
64 bytes from 172.31.12.156: icmp_seq=2 ttl=64 time=0.421 ms
64 bytes from 172.31.12.156: icmp_seq=3 ttl=64 time=0.375 ms
rtt min/avg/max/mdev = 0.278/0.358/0.421/0.059 ms

--- 1000 pings, 10ms interval:
1000 packets transmitted, 1000 received, 0% packet loss, time 10994ms
rtt min/avg/max/mdev = 0.095/0.316/0.724/0.112 ms
```

`.2` 抓到的：

```text
10:12:29.645486 0a:ff:fb:76:11:81 > 0a:ff:f4:5f:2b:61, ethertype IPv4 (0x0800), length 98: 172.31.10.43 > 172.31.12.156: ICMP echo request, id 1, seq 1, length 64
10:12:30.146537 0a:ff:fb:76:11:81 > 0a:ff:f4:5f:2b:61, ethertype IPv4 (0x0800), length 98: 172.31.10.43 > 172.31.12.156: ICMP echo request, id 1, seq 2, length 64
10:12:30.650588 0a:ff:fb:76:11:81 > 0a:ff:f4:5f:2b:61, ethertype IPv4 (0x0800), length 98: 172.31.10.43 > 172.31.12.156: ICMP echo request, id 1, seq 3, length 64
3 packets captured
26 packets received by filter
0 packets dropped by kernel
```

### 怎么读

- 三个包间隔约 0.5 秒，对应 `-i 0.5`；`seq 1/2/3` 和 ping 那边一一对应
- `length 98` = 14 字节以太网头 + 20 字节 IP 头 + 8 字节 ICMP 头 + 56 字节数据
- 源 MAC `0a:ff:fb:76:11:81` 是 `.1` 的 ENA 网卡。AWS VPC 里两台机器看起来像二层直连，其实中间是 Nitro 虚拟网络
- `26 packets received by filter`：过滤器一共看到 26 个包（包括 SSH 等），只有 3 个符合条件
- **延迟：** 平均 0.316 ms = 316 µs，抖动（mdev）112 µs。课程实验台用 X2522 直连 Arista，ping 只要十几微秒。**云网络比实验台慢 10 倍以上**，后面所有章节的绝对数字都要带着这个背景看

---

## 自己再练的命令

```bash
ssh flle-tr2
ethtool -S enp39s0 | head -40         # 网卡统计：每个队列收发多少包，有没有丢包
cat /proc/interrupts | grep -i ena    # 每个队列的中断落在哪个 CPU
sudo tcpdump -i enp39s0 -nn -c 5 not port 22    # 抓 5 个非 SSH 的包看看
ip -s link show enp39s0               # 收发计数和错误计数
```

## 笔记 / 疑问

（自己补充）
