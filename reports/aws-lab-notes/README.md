# AWS 实验记录（总览）

这里按章记录：课程中哪些实验在 AWS EC2 上做过、结果如何、和课程原版有什么不同。每章一个文件，做完一章就更新对应的文件和下面的进度表。

每章文件里都有**实际执行过的完整命令**、参数解释、真实输出和踩过的坑，照着可以重做一遍。机器本身怎么建的见 [aws-setup.md](aws-setup.md)。

## 进度表

| 章 | 课程内容 | AWS 能否做 | 状态 | 记录 |
|---|---|---|---|---|
| 00 | CPU、缓存与操作系统基础 | ✅ 可以 | ✅ 完成 2026-11-24 | [00-cpu-cache-os.md](00-cpu-cache-os.md) |
| 01 | 实验环境：接线、网卡、驱动、交换机 | 🟡 部分 | ✅ 能做的都做了 2026-11-24 | [01-architecture.md](01-architecture.md) |
| 02 | 部署完整交易平台，完成第一笔交易 | ✅ 可以（单播替代组播） | ✅ 完成 2026-11-15 | [02-trading-baseline.md](02-trading-baseline.md) |
| 03 | 抓包读懂行情和订单报文 | 🟡 运行 ② 需组播 | ✅ 完成 2026-11-15（①③） | [03-live-traffic.md](03-live-traffic.md) |
| 04 | C++ 热路径：队列、忙轮询、CPU 隔离 | ✅ 需 ≥4 vCPU | 🟡 跑完 2026-11-24，方向清楚，课程严格检查未过 | [04-software-design.md](04-software-design.md) |
| 05 | OpenOnload / TCPDirect / DPDK 内核旁路 | 🟡 只有 DPDK | ⬜ 未开始 | [05-kernel-bypass.md](05-kernel-bypass.md) |
| 06 | Arista cut-through、PTP 时间 | ❌ 需要真实硬件 | ⛔ 只能读文档 | [06-arista-ptp.md](06-arista-ptp.md) |
| 07 | eBPF / XDP 可编程网络 | ✅ 可以（ENA 支持 XDP） | ✅ 完成 2026-11-24 | [07-xdp.md](07-xdp.md) |
| 08 | FPGA：从代码到设备 | 🟡 只能仿真 | ⬜ 未开始 | [08-fpga.md](08-fpga.md) |

建议顺序：~~02~~ → ~~03~~ → ~~04~~ → ~~07~~ → ~~00~~ → ~~01~~ → 05 → 08。

## 运行报告

| 日期 | 报告 | 内容 |
|---|---|---|
| 2026-11-15 | [02-trading-baseline.md](02-trading-baseline.md)、[03-live-traffic.md](03-live-traffic.md) | 第 02、03 章 |
| 2026-11-24 | [2026-11-24-run-report.md](2026-11-24-run-report.md) | 第 00、01、04、07 章 |

## AWS 环境

| 课程实验台 | AWS | 说明 |
|---|---|---|
| `.1` 交易所 | `flle-exchange-1` i-0c8565112268f92fb，内网 172.31.10.43 | SSH 别名 `flle-ex1` |
| `.2` 交易员 AUTO/MANUAL | `flle-trader-2` i-0872ca5de433c6364，内网 172.31.12.156 | SSH 别名 `flle-tr2` |
| `.101` 网关 / 网页 | 也在 `flle-trader-2` 上 | 端口 8088 |
| Arista 交换机 | AWS VPC 网络 + 置放群组 `flle-lab-pg` | 没有组播、没有交换机命令行 |
| 数据网 20.1.1.x + 管理网 10.1.1.x | 每台一块 ENA 网卡 `enp39s0`、一个内网 IP | |

- 机型：c7i.large（2 vCPU），Ubuntu 22.04，40GB gp3，东京 ap-northeast-1c
- SSH 经过跳板 `ec2-tokyo`（ProxyJump），用内网 IP 连接
- 行情模式：**UNICAST**（VPC 默认不支持组播）
- 程序位置：两台机器都在 `~/flle/app`（源码和编译结果），运行目录 `~/flle/run`，行情数据 `~/flle/data`（在 ex1 上）
- **不要动** `vpn-tokyo`（i-0159ac80a3eef4443），那是个人代理服务器

## 常用操作

在 Git Bash 里，从 `apps/flle-trading-lab` 目录运行：

```bash
aws/flle-aws.sh start      # 启动整套交易系统（可加回放速度，默认 1）
aws/flle-aws.sh status     # 查看各组件状态
aws/flle-aws.sh tunnel     # 打开网页隧道，然后浏览 http://localhost:8088/
aws/flle-aws.sh logs       # 查看日志
aws/flle-aws.sh stop       # 停止所有程序
```

开机或停机：

```bash
aws ec2 start-instances --region ap-northeast-1 --instance-ids i-0c8565112268f92fb i-0872ca5de433c6364
aws ec2 stop-instances  --region ap-northeast-1 --instance-ids i-0c8565112268f92fb i-0872ca5de433c6364
```

## 费用记录

| 日期 | 事件 |
|---|---|
| 2026-11-15 | 创建两台 c7i.large，开始计费（合计约 0.2 美元/小时） |
| 2026-11-17 | 两台停机；之后只收硬盘费，约 7 美元/月 |
| 2026-11-24 | 开机约 25 分钟做第 00/01/04/07 章（trader 临时改 c7i.xlarge），约 0.15 美元；做完改回 c7i.large 并停机 |

## 部署时踩过的坑

- Windows 上 checkout 的文件是 CRLF 换行，上传到 Linux 后要去掉 `\r`，否则测试失败
- 行情接收程序要求 UDP 接收缓冲 ≥ 8 MiB；已在 `/etc/sysctl.d/90-flle.conf` 设成 16 MiB
- Git Bash 会改写 `/aws/...` 这类参数，运行 aws 命令前加 `MSYS_NO_PATHCONV=1`
- 网卡名是 `enp39s0`，不是课程里的 `ens64np1`
- 第 04 章：测量程序必须绑到 CPU 1（`taskset -c 1`），否则它占满一个核，干扰被测线程
- 第 04 章：要 4 vCPU，先停机把 trader 改成 c7i.xlarge，做完再改回 c7i.large
- 第 07 章：ENA 原生 XDP 要求 MTU ≤ 3498、队列减半；改这些会让网卡重置、瞬间丢包，之后要重启回放
- 远程执行 `pkill -f 某名字` 时，如果整条 ssh 命令里也含这个名字，会把自己杀掉；改用 `bash -s` 从标准输入传脚本
