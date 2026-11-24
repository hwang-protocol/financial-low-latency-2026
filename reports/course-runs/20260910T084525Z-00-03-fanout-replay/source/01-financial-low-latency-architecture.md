# 第一部分：认清实验环境——接线、网卡、驱动与交换机

## 先把一条报文的路认清

第零部分解释了报文进入主机后怎样等待和处理。本章把视线移到真实设备：SSH 能登录，网口也显示 `UP`，为什么接收程序仍可能收不到数据？我们沿着接线检查，最后发出三条 ping 请求，在接收端抓到它们。

继续用厨房来想：报文是一箱箱送来的食材，数据网口是收货口。收货口旁的自动搬运设备像网卡，PCIe 是通往存货区的内部通道，主机内存就是存货区。

驱动像负责安排搬运的人：先在存货区腾出空位，再把位置写进清单，交给搬运设备。食材送到后，设备沿通道照单放好，主厨不用亲自一箱箱搬运。对应到主机，就是驱动准备内存空间、登记地址，网卡经 PCIe 把报文写到指定位置；CPU 这位“主厨”随后读取这些数据，执行处理代码。

交换机连接两端的数据口，VLAN 划定它们所在的二层网络。

本章的检查主线是两台虚拟机（VM）：`.1`（`10.1.1.1`）将运行交易所程序 Exchange，`.2`（`10.1.1.2`）将运行交易客户端 Trader。准备阶段还会为 `.1`、`.2`、`.11`、`.101` 四台 VM 补齐工具，恢复交换机登录并配置数据网络。第二部分再让交易程序使用这条通路。

| 厨房里的角色 | 实验中的对象 | 本章先看什么 |
| --- | --- | --- |
| 收货口与自动搬运设备 | 数据接口与网卡（NIC） | 线接在哪个口，接口叫什么 |
| 内部通道 | PCIe：网卡连接主机的总线 | 系统把这块设备登记在哪里 |
| 腾出空位、登记清单的人 | 驱动（Driver） | 当前由哪个驱动管理网卡 |

本章只做三件事：

1. 恢复工具、公钥登录和 VLAN20，让后续命令能顺序执行。
2. 从 Linux 接口名找到对应网卡、驱动和交换机端口。
3. 从 `.1` 发送三条 ping 请求，在 `.2` 保存抓包文件（pcap），确认请求到达数据口。

| 官方入口 | 用来核对什么 |
| --- | --- |
| [Linux PCI 设备目录](https://docs.kernel.org/PCI/sysfs-pci.html) | 接口背后的设备地址和身份 |
| [Linux 接口状态](https://docs.kernel.org/networking/operstates.html) | 接口启用与实际链路状态的区别 |
| [Linux NAPI](https://docs.kernel.org/networking/napi.html) | 收到通知后，驱动怎样批量处理报文 |

<div style="border-left:6px solid #7e22ce;background:#f3e8ff;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#7e22ce;color:#fff;font-weight:800;">关键图</span> <span style="font-weight:700;color:#581c87;">全课程实验台接线总览：先认设备与接口归属，再沿四根 DAC 查 IP 和交换机端口；底部保留尚未接入的硬件延伸设计。</span></div>

<div style="background:#f8fafc;border:1px solid #cbd5e1;border-radius:12px;padding:10px;max-width:820px;margin:14px auto;">
<img src="images/course-visuals/01-diagrams/01-physical-topology-host-owned.svg" alt="FLLE 设备接线图：Win2019、.111 管理机、.101 监测 VM；.1 ens64np0 接 Et1、.2 ens64np1 接 Et2，来自同一张 X2522；.11 的 BCM57414 双口 ens64f0np0/ens64f1np1 接 Et11/Et12；标明接口 IP，保留未接入的 7130 FPGA 与 Alveo U250" style="display:block;width:100%;max-width:800px;height:auto;margin:0 auto;border-radius:8px;background:#fff;">
</div>

**读图时先找三件事：**

- **管理接口接入同一管理网。** `.111` 是管理机，`.101` 是监测 VM；`.1` 是 Exchange VM，`.2` 是 Trader VM，`.11` 是实验 VM。`.1`、`.2`、`.11` 三台的管理口都叫 `ens33`，通过 ESXi 虚拟交换机（vSwitch）接入 `10.1.1.0/24` 管理网。`.101` 通过虚拟管理口接入同一管理网，网页和监控服务都使用这条连接。Arista 的管理口 `Management1` 也使用这个网段。图中虚线表示管理网的逻辑连接。
- **沿接口名核对四根数据线。** `.1` 的 `ens64np0` 接 Et1，`.2` 的 `ens64np1` 接 Et2，两者各使用同一张 X2522 双口卡的一口，通过直通方式分配——宿主机把对应网口整体交给虚拟机；`.11` 的 BCM57414 接口 `ens64f0np0`、`ens64f1np1` 分别接 Et11、Et12。每条实线代表一根 10G 全双工直连铜缆（DAC）。
- **区分已接入设备与硬件延伸设计。** 底部 Arista 7130 FPGA、AMD Alveo U250 尚未接入，未分配实际接线或 IP；它们保留为硬件设计示意。

## 设备之间实际传哪些流量

接线图说明网口接在哪里，通信图说明程序之间传什么。它也是后续部分的端口索引：本章先认两台交易主机和管理机，运行交易、监控实验时再按编号查对应通信。

监测 VM（`.101`）内部运行网页后台（Gateway）、保存指标的 Prometheus 和显示看板的 Grafana。

<div style="border-left:6px solid #7e22ce;background:#f3e8ff;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#7e22ce;color:#fff;font-weight:800;">关键图 · 流量与端口</span> <span style="font-weight:700;color:#581c87;">蓝色是 TCP，橙色是 UDP；方框标明设备、进程和地址，箭头起点是源、尖端是目的。每条箭头的编号与下表逐项对应。</span></div>

<div style="background:#f8fafc;border:1px solid #cbd5e1;border-radius:12px;padding:10px;max-width:820px;margin:14px auto;">
<img src="images/course-visuals/01-diagrams/01-traffic-flows-and-ports.svg" alt="九组通信、十六条编号箭头：标明源目的地址、TCP蓝色与UDP橙色、控制48606、事件46120、LANZ50001及网页、行情、订单、进程控制、指标和SSH端口" style="display:block;width:100%;max-width:800px;height:auto;margin:0 auto;border-radius:8px;background:#fff;">
</div>

表内 `.x` 是管理网 `10.1.1.x` 的简称，数据网地址完整写出。图中 a/b 分别表示同组内的箭头；服务的监听端口固定，客户端临时端口由系统分配。

| 图中编号 | 谁向谁通信 | 用途与返回方向 |
| --- | --- | --- |
| ①a/b | `.101 → .2:48606`，HTTP/TCP | 网页后台请求切换网卡收发方式；`.2` 沿同一连接返回结果 |
| ②a | `.1/.2 → .101:46120`，UDP | 交易程序上报回放进度、订单与成交状态 |
| ③a/b | `.101 → .253:50001`，TCP | 采集器建连后，交换机沿同一连接向 `.101` 发送排队事件（LANZ） |
| ④a/b | Windows Server 2019 浏览器 → `.101:8088 / :3000 / :8089`，HTTP/TCP | 分别访问交易网页、指标看板、LANZ 查询；结果沿原连接返回 |
| ⑤a/b | `20.1.1.1 → 233.74.125.32:31032` 或 `20.1.1.2:42121`，UDP | 两种行情发送方式：组播发往组地址，单播发往 Trader 数据口 |
| ⑥a/b | `20.1.1.2 → 20.1.1.1:43120`，TCP | Trader 提交订单；Exchange 沿同一连接返回处理结果 |
| ⑦a/b | `.101 → .1:48120 / .2:48121～48125`，TCP | 网页后台向指定进程发命令，目标进程沿原连接返回结果 |
| ⑧a/b | Prometheus → `10.1.1.101:8088/metrics`；Grafana → `127.0.0.1:9090`，均为 HTTP/TCP | ⑧a 定期读取指标，⑧b 查询已有记录；均在 `.101` 内，结果沿各自连接返回 |
| ⑨a | `.111 → .1/.2/.11/.101/.253:22`，SSH/TCP | 管理机登录、执行命令和传输文件，输出沿原连接返回 |

[逐箭头说明](#appendix-flows)、[五个 Trader 管理端口](#appendix-trader-ports)和[第四部分指标索引](#appendix-metrics)放在章末，运行对应部分的实验时按图查阅。

## 本章学习目标

1. 看懂课程接线，分清每台主机的管理口、X2522 数据口和对应 Arista 端口。
2. 按“接口名 → 设备地址与型号 → 驱动 → 两端链路 → 抓包”逐步核对。
3. 区分接口已启用、链路已连接和报文已到达，按输出判断检查进行到哪一步。

<div style="border-left:6px solid #7e22ce;background:#f3e8ff;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#7e22ce;color:#fff;font-weight:800;">本章检查范围</span> <span style="font-weight:700;color:#581c87;">本章检查接口、设备、驱动和链路，并用三条 ping 确认报文到达。交易程序的收发从第二部分开始。</span></div>

课程快照已包含虚拟机资源设置，可直接沿用；迁移、克隆或开机提示资源不足时，按[资源配置附录](#appendix-resources)复核。

## 本章导航

<div style="border-left:6px solid #7e22ce;background:#f3e8ff;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#7e22ce;color:#fff;font-weight:800;">本章导航</span> <span style="font-weight:700;color:#581c87;">本章分成三个阶段，共 8 个导航项；先用总图看完整路线，再在每节导航卡里查看全章与本组位置。外层大框从上往下推进，框内卡片从左往右执行。</span></div>

```mermaid
flowchart TB
  subgraph prep["基础设施准备"]
    direction LR
    pa["准备A 补齐工具<br/>四台主机要用什么"]
    pb["准备B 恢复登录<br/>管理机怎样连交换机"]
    pc["准备C 建立数据网络<br/>哪些端口需要转发"]
    pa --> pb --> pc
  end
  subgraph identity["接口与设备身份"]
    direction LR
    r1["① 核对两类接口<br/>登录和探针各走哪边"]
    r2["② 找到设备地址<br/>接口背后是哪块网卡"]
    r3["③ 查当前驱动<br/>谁在管理这块网卡"]
    r1 --> r2 --> r3
  end
  subgraph proof["链路与报文检查"]
    direction LR
    r4["④ 对齐两端链路<br/>两边连接是否正常"]
    r5["⑤ 抓到三条 ping<br/>请求是否到达数据口"]
    r4 --> r5
  end
  prep --> identity --> proof
  classDef step fill:#eef2ff,stroke:#4f46e5,stroke-width:2px,color:#312e81;
  class pa,pb,pc,r1,r2,r3,r4,r5 step;
```

固定顺序就是：**基础设施准备 → 接口与设备身份 → 链路与报文检查**。

## 任务地图

| 导航项 | 所属阶段 | 这一项回答什么 |
| --- | --- | --- |
| 准备 A：核对系统并补齐工具 | 基础设施准备 | 四台主机需要哪些基础工具 |
| 准备 B：恢复交换机公钥登录 | 基础设施准备 | 怎样确认交换机身份并恢复登录 |
| 准备 C：建立课程交换基础拓扑 | 基础设施准备 | 哪些端口需要加入数据网络 |
| 运行 ①：核对两类接口 | 接口与设备身份 | 登录与探针分别走哪个接口 |
| 运行 ②：从接口名找到设备地址 | 接口与设备身份 | 接口背后是哪块设备 |
| 运行 ③：查当前驱动 | 接口与设备身份 | 当前由哪个驱动管理网卡 |
| 运行 ④：对齐主机与交换机链路 | 链路与报文检查 | 网线两端的链路状态是否一致 |
| 运行 ⑤：抓到三条 ping | 链路与报文检查 | 三条请求是否到达指定接口 |

## 准备 A：核对系统并补齐工具

先确认四台 VM 的系统版本，补齐常用诊断工具，再给 `.101` 装好编译工具。`.101` 同时承担构建机（Builder）的工作，第二部分会用它把课程源码编译成程序。大包和完整依赖已提前存放在 `.111`；课堂通过管理网分发，不等待公网下载。软件源只作维护备用，本步安装使用 `.111` 的离线缓存，不在线刷新索引。

<div style="border:2px solid #4f46e5;background:#eef2ff;padding:10px 12px;border-radius:8px;margin:14px 0;"><div style="font-weight:900;color:#312e81;margin-bottom:4px;">导航卡 · 基础设施准备</div><div style="font-weight:700;color:#312e81;margin-bottom:8px;">范畴：工具准备　本步知识：四台主机需要哪些基础工具　位置：全章第 1 / 8 项 · 本组第 1 / 3 项</div><span style="display:inline-block;margin:3px;padding:4px 10px;border-radius:6px;background:#15803d;color:#fff;font-weight:800;">准备 A：核对系统并补齐工具</span><span style="display:inline-block;margin:3px;padding:4px 10px;border-radius:6px;background:#f8fafc;border:1px solid #a5b4fc;color:#312e81;font-weight:800;">准备 B：恢复交换机公钥登录</span><span style="display:inline-block;margin:3px;padding:4px 10px;border-radius:6px;background:#f8fafc;border:1px solid #a5b4fc;color:#312e81;font-weight:800;">准备 C：建立课程交换基础拓扑</span></div>

<div style="border-left:6px solid #15803d;background:#dcfce7;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#15803d;color:#fff;font-weight:800;">需要运行 · 准备 A</span> <span style="font-weight:700;color:#14532d;">在【跳板机 .111】以 root 运行；顺序处理 <code>.1/.2/.11/.101</code>；核对四台 VM 的 Ubuntu 22.04/amd64 并统一维护用软件源；从 <code>.111</code> 缓存补齐四机基础工具，并给 <code>.101</code> 安装 <code>g++-11</code> 与 <code>make</code>，不访问公网；预期四台系统检查通过且 <code>.101</code> 打印三项工具路径。</span></div>

```bash
#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-01-vm-apt-china-mirror"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"

{
python3 artifacts/tools/check-course-package-cache.py
for host in 10.1.1.1 10.1.1.2 10.1.1.11 10.1.1.101; do
  printf '\n%s / prepare\n===== 补齐基础工具 =====\n从管理机离线缓存安装本机需要的工具。\n$ python3 Documents/newDoc/assets/common/install-offline-packages.py %s base\n' "$host" "$host"
  python3 Documents/newDoc/assets/common/install-offline-packages.py "$host" base
  if [ "$host" = 10.1.1.101 ]; then
    printf '===== 补齐编译工具 =====\n监测 VM 同时负责编译第二部分的交易程序。\n$ python3 Documents/newDoc/assets/common/install-offline-packages.py %s builder\n' "$host"
    python3 Documents/newDoc/assets/common/install-offline-packages.py "$host" builder
  fi
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes "root@$host" \
    bash -s -- "$host" <<'REMOTE'
set -Eeuo pipefail
REMOTE_HOST="$1"
. /etc/os-release
printf '%s / verify\n===== 查系统版本 =====\n[系统] 对: Ubuntu 22.04（jammy）  证: 与课程离线软件包匹配\n$ cat /etc/os-release\n' "$REMOTE_HOST"; cat /etc/os-release
printf '===== 查处理器架构 =====\n[架构] 对: amd64  证: 与课程软件包的架构一致\n$ dpkg --print-architecture\n'; dpkg --print-architecture
if [ "$ID" != ubuntu ] || [ "$VERSION_CODENAME" != jammy ]; then
  printf 'STOP: this card expects Ubuntu jammy\n' >&2; exit 1
fi
[ -e /etc/apt/sources.list.flle-original ] || cp -a /etc/apt/sources.list /etc/apt/sources.list.flle-original
install -m 0644 /dev/stdin /etc/apt/sources.list <<'SOURCES'
deb https://mirrors.aliyun.com/ubuntu/ jammy main restricted universe multiverse
deb https://mirrors.aliyun.com/ubuntu/ jammy-updates main restricted universe multiverse
deb https://mirrors.aliyun.com/ubuntu/ jammy-backports main restricted universe multiverse
deb https://mirrors.aliyun.com/ubuntu/ jammy-security main restricted universe multiverse
SOURCES
printf '===== 查维护用软件源 =====\n[软件源] 对: 四行 jammy 系列地址  证: 日后维护的来源已登记；本次安装仍使用离线缓存\n$ cat /etc/apt/sources.list\n'; cat /etc/apt/sources.list
printf '系统检查通过；课堂安装使用 .111 离线缓存，不刷新公网索引。\n'
if [ "$REMOTE_HOST" = 10.1.1.101 ]; then
  printf '\n%s / verify\n===== 查编译工具 =====\n[编译工具] 对: 三项都有 /usr/bin/ 下的路径  证: 监测 VM 已能调用第二部分需要的编译与脚本工具\n$ command -v g++-11 make python3\n' "$REMOTE_HOST"; command -v g++-11 make python3
  printf '===== 查编译器版本 =====\n[编译器] 对: g++-11，版本 11.4.0  证: 明确本次构建使用的 C++ 编译器版本\n$ g++-11 --version | head -1\n'; g++-11 --version | head -1
fi
REMOTE
done
} 2>&1 | tee "$OUT/raw/result.txt"
(cd "$OUT" && sha256sum raw/result.txt run.env >SHA256SUMS); printf 'evidence=%s\n' "$OUT"
```

<div style="border-left:6px solid #7e22ce;background:#f3e8ff;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#7e22ce;color:#fff;font-weight:800;">仅供展示 · 输出解读</span> <span style="font-weight:700;color:#581c87;"><code>.101</code> 的编译工具检查示例。</span></div>

```text
10.1.1.101 / verify
===== 查编译工具 =====
[编译工具] 对: 三项都有 /usr/bin/ 下的路径  证: 监测 VM 已能调用第二部分需要的编译与脚本工具
$ command -v g++-11 make python3
/usr/bin/g++-11
/usr/bin/make
/usr/bin/python3
===== 查编译器版本 =====
[编译器] 对: g++-11，版本 11.4.0  证: 明确本次构建使用的 C++ 编译器版本
$ g++-11 --version | head -1
g++-11 (Ubuntu 11.4.0-1ubuntu1~22.04.3) 11.4.0
```

<div style="border-left:6px solid #0891b2;background:#cffafe;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#0891b2;color:#fff;font-weight:800;">完成后继续</span> <span style="font-weight:700;color:#164e63;">四台系统检查与 <code>.101</code> 工具校验通过后，进入准备 B；出现报错先处理。</span></div>

## 准备 B：恢复交换机公钥登录

Arista 交换机运行的操作系统叫 EOS。本步恢复 SSH 公钥登录，让 `.111` 管理机能继续向交换机执行课程命令。

**本课的交换机实验配置只修改当前生效的 `running-config`，不保存到 `startup-config`。**因此，每次重启后，交换机都会重新加载预先保存的配置，回到课程起点。

首次搭建环境或交换机重启后，请执行本步骤，把管理机的 SSH 公钥加入交换机，恢复公钥登录。先用 `show version` 核对型号与系统版本。

<div style="border:2px solid #4f46e5;background:#eef2ff;padding:10px 12px;border-radius:8px;margin:14px 0;"><div style="font-weight:900;color:#312e81;margin-bottom:4px;">导航卡 · 基础设施准备</div><div style="font-weight:700;color:#312e81;margin-bottom:8px;">范畴：工具准备　本步知识：怎样确认交换机身份并恢复登录　位置：全章第 2 / 8 项 · 本组第 2 / 3 项</div><span style="display:inline-block;margin:3px;padding:4px 10px;border-radius:6px;background:#f8fafc;border:1px solid #a5b4fc;color:#312e81;font-weight:800;">准备 A：核对系统并补齐工具</span><span style="display:inline-block;margin:3px;padding:4px 10px;border-radius:6px;background:#15803d;color:#fff;font-weight:800;">准备 B：恢复交换机公钥登录</span><span style="display:inline-block;margin:3px;padding:4px 10px;border-radius:6px;background:#f8fafc;border:1px solid #a5b4fc;color:#312e81;font-weight:800;">准备 C：建立课程交换基础拓扑</span></div>

<div style="border-left:6px solid #7e22ce;background:#f3e8ff;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#7e22ce;color:#fff;font-weight:800;">仅供展示 · 配机前先认身份</span> <span style="font-weight:700;color:#581c87;">在交换机控制台执行 <code>show version</code>，核对型号、系统版本和主机名。示例中的序列号已隐藏。</span></div>

```text
fll-arista#show version
Arista DCS-7150S-24-F
Hardware version:      02.00
Serial number:         （设备序列号略）
Hardware MAC address:  001c.7368.e239
System MAC address:    001c.7368.e239

Software image version: 4.23.16M-2GB
Architecture:           i686
Internal build version: 4.23.16M-2GB-40226546.42316M
Internal build ID:      bb71297b-4523-465f-a576-6c7d1cb24663

Uptime:                 0 weeks, 2 days, 11 hours and 55 minutes
Total memory:           4009040 kB
Free memory:            3065276 kB
```

| 看哪一行 | 记录值 | 它表示什么 |
|---|---|---|
| 提示符 `fll-arista#` | 主机名已是课程名 | 课程主机名；与型号、管理地址一并核对所连设备 |
| `DCS-7150S-24-F` / `Hardware version: 02.00` | 24 口 7150S | 本章的 VLAN20 和 10G DAC 接在这台交换机上 |
| `Software image version: 4.23.16M-2GB` | i686，build `4.23.16M-2GB-40226546.42316M` | 本章公钥和 VLAN 命令的实测版本 |
| `Hardware MAC` / `System MAC` | `001c.7368.e239` | 交换机自己的系统 MAC，不是 `.1` / `.2` 网卡 MAC |

<div style="border-left:6px solid #15803d;background:#dcfce7;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#15803d;color:#fff;font-weight:800;">需要运行 · 准备 B</span> <span style="font-weight:700;color:#14532d;">在【跳板机 .111】以 root 运行；需要时按终端提示输入交换机登录密码；完成后应能通过公钥登录，并看到用户账户信息。</span></div>

```bash
#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-01-eos-key-bootstrap"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"

python3 Documents/newDoc/assets/common/eos-key-bootstrap.py \
  >"$OUT/raw/bootstrap-tool.txt" 2>&1
printf '%s\n' 'show users accounts' >"$OUT/raw/eos.plan"
printf '===== admin@10.1.1.253 · EOS public key =====\n'; python3 Documents/newDoc/assets/common/eos_cli.py --mode show \
  --plan "$OUT/raw/eos.plan" --output "$OUT/raw/eos.txt" \
  2>&1 | tee "$OUT/raw/eos-terminal.txt"
(cd "$OUT" && sha256sum raw/* run.env >SHA256SUMS); printf 'evidence=%s\n' "$OUT"
```

<div style="border-left:6px solid #7e22ce;background:#f3e8ff;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#7e22ce;color:#fff;font-weight:800;">仅供展示 · 关键命令</span> <span style="font-weight:700;color:#581c87;">下面代码块用于讲解脚本发给交换机的命令，不需要执行。</span></div>

```text
switch> enable
switch# configure terminal
switch(config)# username admin ssh-key ssh-ed25519 <公钥正文> flle-course-jump-host-20260722
switch(config)# end
switch# show users accounts
```

| EOS 命令 | 作用 |
| --- | --- |
| `enable` | 必要时从 `>` 进入特权模式 |
| `configure terminal` | 进入 running-config 配置模式 |
| `username admin ssh-key …` | 给 `admin` 安装课程公钥 |
| `end` | 退出配置模式 |
| `show users accounts` | 查看账户、角色与公钥 |

公钥正文是一长串字符，示例用 `<公钥正文>` 代替显示。脚本会从 `/root/.ssh/flle_course_ed25519.pub` 读取完整公钥，自动组成这条配置命令并发送给交换机。

末尾的 `flle-course-jump-host-20260722` 是公钥的备注名，用于标识来源。

<div style="border-left:6px solid #7e22ce;background:#f3e8ff;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#7e22ce;color:#fff;font-weight:800;">仅供展示 · 账户信息</span> <span style="font-weight:700;color:#581c87;">执行 <code>show users accounts</code>，查看用户账户信息。</span></div>

```text
$ show users accounts
user: admin
       role: network-admin
       privilege level: 15
       ssh public key: ssh-ed25519 AAAA…（公钥内容略） flle-course-jump-host-20260722
```

| 关键行 | 判断 |
| --- | --- |
| `user: admin` / `role: network-admin` | 课程使用的账户和角色存在 |
| `privilege level: 15` | 后续 show 与受控配置命令可执行 |
| `ssh public key: ssh-ed25519 …` | 课程公钥已在 running-config 中，免密登录可用 |

<div style="border-left:6px solid #0891b2;background:#cffafe;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#0891b2;color:#fff;font-weight:800;">完成后继续</span> <span style="font-weight:700;color:#164e63;">公钥登录成功、账户信息核对无误后，进入准备 C；出现报错先处理。</span></div>

## 准备 C：建立课程交换基础拓扑

公钥登录恢复后，再让数据端口处于同一个 VLAN。本步在当前配置中建立 VLAN20，把 Et1、Et2、Et11、Et12 加入其中，并配置交换机自身的 `Vlan20` 接口地址。

脚本随后检查生成树状态（STP），等待已连接端口进入 `forwarding`，也就是可以转发报文。本步先建立二层连通；总图里的 IGMP 查询器和组播成员检查在第三部分配置、验证。

<div style="border:2px solid #4f46e5;background:#eef2ff;padding:10px 12px;border-radius:8px;margin:14px 0;"><div style="font-weight:900;color:#312e81;margin-bottom:4px;">导航卡 · 基础设施准备</div><div style="font-weight:700;color:#312e81;margin-bottom:8px;">范畴：工具准备　本步知识：哪些端口需要加入数据网络　位置：全章第 3 / 8 项 · 本组第 3 / 3 项</div><span style="display:inline-block;margin:3px;padding:4px 10px;border-radius:6px;background:#f8fafc;border:1px solid #a5b4fc;color:#312e81;font-weight:800;">准备 A：核对系统并补齐工具</span><span style="display:inline-block;margin:3px;padding:4px 10px;border-radius:6px;background:#f8fafc;border:1px solid #a5b4fc;color:#312e81;font-weight:800;">准备 B：恢复交换机公钥登录</span><span style="display:inline-block;margin:3px;padding:4px 10px;border-radius:6px;background:#15803d;color:#fff;font-weight:800;">准备 C：建立课程交换基础拓扑</span></div>

<div style="border-left:6px solid #15803d;background:#dcfce7;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#15803d;color:#fff;font-weight:800;">需要运行 · 准备 C</span> <span style="font-weight:700;color:#14532d;">在【跳板机 .111】以 root 运行；前置是准备 B 已完成；配置 VLAN20、Et1/Et2/Et11/Et12 和 Vlan20，重复执行会核对并应用同一组设置，只改 running-config；确认交易口和已连接的工具口进入 <code>forwarding</code>；预期打印最终 STP 状态。</span></div>

```bash
#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency

RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-01-switch-course-baseline"
OUT="Documents/reports/course-runs/${RUN_ID}"
mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"

cat >"$OUT/raw/eos-plan.txt" <<'EOS'
configure terminal
vlan 20
name fll
interface Ethernet1
switchport access vlan 20
spanning-tree portfast
interface Ethernet2
switchport access vlan 20
spanning-tree portfast
interface Ethernet11
switchport access vlan 20
spanning-tree portfast
interface Ethernet12
switchport access vlan 20
spanning-tree portfast
interface Vlan20
ip address 20.1.1.254/24
no ip routing
end
show vlan id 20
show interfaces Ethernet1 status
show interfaces Ethernet2 status
show interfaces Ethernet11 status
show interfaces Ethernet12 status
show ip interface brief
EOS

printf '===== admin@10.1.1.253 · EOS course baseline =====\n'; python3 Documents/newDoc/assets/common/eos_cli.py \
  --mode controlled-config --plan "$OUT/raw/eos-plan.txt" \
  --output "$OUT/raw/eos.txt" 2>&1 | tee "$OUT/raw/eos-terminal.txt"
printf '%s\n' 'show interfaces status' 'show spanning-tree vlan 20' >"$OUT/raw/eos-stp-plan.txt"; ready=0
for attempt in $(seq 1 15); do
  python3 Documents/newDoc/assets/common/eos_cli.py --mode show \
    --plan "$OUT/raw/eos-stp-plan.txt" --output "$OUT/raw/eos-stp.txt" \
    >"$OUT/raw/eos-stp-terminal.txt" 2>&1
  python3 Documents/newDoc/assets/01-architecture/check-switch-forwarding.py "$OUT/raw/eos-stp.txt" && { ready=1; break; }; sleep 2
done
cat "$OUT/raw/eos-stp-terminal.txt"; (( ready == 1 ))
(cd "$OUT" && sha256sum raw/*.txt run.env >SHA256SUMS); printf 'evidence=%s\n' "$OUT"
```

<div style="border-left:6px solid #7e22ce;background:#f3e8ff;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#7e22ce;color:#fff;font-weight:800;">仅供展示 · 输出解读</span> <span style="font-weight:700;color:#581c87;">依次查看 VLAN 成员、接口地址和生成树转发状态。</span></div>

```text
$ show vlan id 20
20    fll                              active    Cpu, Et1, Et2

$ show ip interface brief
Management1       10.1.1.253/24       up           up                1500
Vlan20            20.1.1.254/24       up           up                1500

$ show spanning-tree vlan 20
Et1              designated forwarding 2000      128.1    P2p Edge
Et2              designated forwarding 2000      128.2    P2p Edge
```

| 命令 | 重点输出 | 判断 |
| --- | --- | --- |
| `$ show vlan id 20` | `20 fll active Cpu, Et1, Et2` | 课程数据 VLAN 已建立，Et1、Et2 为活动成员；待用的 Et11、Et12 可以不出现在列表中 |
| `$ show ip interface brief` | `Management1 10.1.1.253/24`、`Vlan20 20.1.1.254/24` | 管理面还是 `.253`；`Vlan20` 是交换机在数据 VLAN 内的接口，与主机同网段，本实验不做路由 |
| `$ show spanning-tree vlan 20` | 已连接的课程口均为 `designated forwarding` | Et1/Et2 必须在线；待用工具口可无链路 |

Et11、Et12 已划入 VLAN20；链路未接通时，`show vlan id 20` 不会显示它们。要查看全部已配置端口，执行 `show vlan id 20 configured-ports`。[命令说明](https://www.arista.com/en/um-eos/eos-virtual-lans-vlans)

<div style="border-left:6px solid #0891b2;background:#cffafe;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#0891b2;color:#fff;font-weight:800;">完成后继续</span> <span style="font-weight:700;color:#164e63;">Et1、Et2 都能转发后，接下来查看两台主机的网口和 IP 地址。</span></div>

## 运行 ①：核对两类接口

数据端口已加入 VLAN20，现在回到两台主机，确认登录与探针分别使用哪个接口。

<div style="border:2px solid #4f46e5;background:#eef2ff;padding:10px 12px;border-radius:8px;margin:14px 0;"><div style="font-weight:900;color:#312e81;margin-bottom:4px;">导航卡 · 接口与设备身份</div><div style="font-weight:700;color:#312e81;margin-bottom:8px;">范畴：现场只读　本步知识：登录与探针分别走哪个接口　位置：全章第 4 / 8 项 · 本组第 1 / 3 项</div><span style="display:inline-block;margin:3px;padding:4px 10px;border-radius:6px;background:#15803d;color:#fff;font-weight:800;">运行 ①：核对两类接口</span><span style="display:inline-block;margin:3px;padding:4px 10px;border-radius:6px;background:#f8fafc;border:1px solid #a5b4fc;color:#312e81;font-weight:800;">运行 ②：从接口名找到设备地址</span><span style="display:inline-block;margin:3px;padding:4px 10px;border-radius:6px;background:#f8fafc;border:1px solid #a5b4fc;color:#312e81;font-weight:800;">运行 ③：查当前驱动</span></div>

### 本步理论：管理面和数据面是两条路

同一间厨房可以有人员通道和收货口。同一台 VM 也有两类接口：管理口 `ens33 / 10.1.1.x` 用来登录、发命令；X2522 数据口（`.1` 的 `ens64np0`、`.2` 的 `ens64np1`）使用 `20.1.1.x` 地址，承载探针和后续交易报文。

Linux 中的网络接口对象称为 netdev，`ens33`、`ens64np0` 就是接口名。管理口登录成功，只确认了管理网这条路；数据口要单独检查。

**理论落到实验：** 脚本对 `.1/.2` 各执行两次 `ip -4 -o addr show`，一次读管理口、一次读数据口，据此区分管理网与数据网地址。

<div style="border-left:6px solid #15803d;background:#dcfce7;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#15803d;color:#fff;font-weight:800;">需要运行 · 运行 ①</span> <span style="font-weight:700;color:#14532d;">在【跳板机 .111】以 root 运行，查看 <code>.1/.2</code> 的管理口与 X2522 数据口地址。</span></div>

```bash
#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency

RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-01-plane-map"
OUT="Documents/reports/course-runs/${RUN_ID}"
mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"

{
for item in '10.1.1.1 ens64np0' '10.1.1.2 ens64np1'; do
  read -r host data_if <<<"$item"
  printf '\n===== root@%s =====\n' "$host"
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes "root@$host" \
    bash -s -- "$data_if" <<'REMOTE'
set -Eeuo pipefail
data_if="$1"
printf '$ ip -4 -o addr show dev ens33\n'
ip -4 -o addr show dev ens33
printf '$ ip -4 -o addr show dev %s\n' "$data_if"
ip -4 -o addr show dev "$data_if"
REMOTE
done
} 2>&1 | tee "$OUT/raw/planes.txt"
(cd "$OUT" && sha256sum raw/planes.txt run.env >SHA256SUMS); printf 'evidence=%s\n' "$OUT"
```

<div style="border-left:6px solid #7e22ce;background:#f3e8ff;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#7e22ce;color:#fff;font-weight:800;">仅供展示 · 输出解读</span> <span style="font-weight:700;color:#581c87;">查看两台主机的管理口和数据口地址。</span></div>

```text
===== root@10.1.1.1 =====
$ ip -4 -o addr show dev ens33
2: ens33    inet 10.1.1.1/24 brd 10.1.1.255 scope global ens33
$ ip -4 -o addr show dev ens64np0
3: ens64np0    inet 20.1.1.1/24 brd 20.1.1.255 scope global ens64np0
```

```text
===== root@10.1.1.2 =====
$ ip -4 -o addr show dev ens33
2: ens33    inet 10.1.1.2/24 brd 10.1.1.255 scope global ens33
$ ip -4 -o addr show dev ens64np1
3: ens64np1    inet 20.1.1.2/24 brd 20.1.1.255 scope global ens64np1
```

<div style="border-left:6px solid #7e22ce;background:#f3e8ff;padding:14px 18px;border-radius:8px;margin:14px 0;">
<div style="font-weight:900;color:#581c87;margin-bottom:8px;">仅供展示 · 看懂一个接口名</div>
<div style="font-weight:700;color:#581c87;">接口名 <code>ens33</code> / <code>ens64np0</code> 来自 systemd/udev 的 <a href="https://www.freedesktop.org/software/systemd/man/latest/systemd.net-naming-scheme.html">可预测网卡命名</a>：以太网前缀 + 固件给出的 PCI 热插拔槽位号；多端口卡再拼上固件端口名。</div>
<pre style="background:#faf5ff;border:1px solid #c4b5fd;padding:12px 14px;border-radius:6px;margin:12px 0 0;overflow-x:auto;color:#3b0764;"><code>ens64np0
│  │ └─ n + p0   n 表示后面跟 phys_port_name；固件端口名就是 p0
│  └──── s64     PCI 热插拔槽位 64（固件编号）
└─────── en      Ethernet</code></pre>
</div>

| 课程里的名字 | 拆开以后 | 现场对应 |
| --- | --- | --- |
| `ens33` | `en` + `s33` | 管理虚拟口；单口，没有 `n…` 后缀 |
| `ens64np0` | `en` + `s64` + `n` + `p0` | `.1` 的 X2522 口，`phys_port_name=p0` |
| `ens64np1` | `en` + `s64` + `n` + `p1` | `.2` 的 X2522 口，`phys_port_name=p1` |

`s33`、`s64` 使用固件给出的槽位编号；`n` 后面接端口名 `p0` 或 `p1`。本课按完整接口名执行命令，设备身份还要通过运行 ② 的 PCIe 地址核对。

| 命令 | 重点输出 | 判断 |
| --- | --- | --- |
| `.1` `$ ip -4 -o addr show dev ens33` | `2: ens33 inet 10.1.1.1/24` | 管理口，承载登录、控制与观测 |
| `.1` `$ ip -4 -o addr show dev ens64np0` | `3: ens64np0 inet 20.1.1.1/24` | 数据口；后续 ping 与 pcap 用这个端点 |
| `.2` `$ ip -4 -o addr show dev ens33` | `2: ens33 inet 10.1.1.2/24` | 管理口，承载登录、控制与观测 |
| `.2` `$ ip -4 -o addr show dev ens64np1` | `3: ens64np1 inet 20.1.1.2/24` | 数据口名称与 `.1` 不同，命令不能互抄 |

<div style="border-left:6px solid #0891b2;background:#cffafe;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#0891b2;color:#fff;font-weight:800;">关键现象</span> <span style="font-weight:700;color:#164e63;">两台主机都返回 <code>ens33 / 10.1.1.x</code> 和各自 X2522 数据口 <code>/ 20.1.1.x</code>。若数据口没有 <code>20.1.1.x</code>，先停在这一步，不要继续做设备身份和抓包。</span></div>

接口名和地址已经对应起来。还要确认这个接口背后确实是 X2522，运行 ② 就去查系统登记的设备身份。

## 运行 ②：从接口名找到设备地址

`ens64np0` 是 Linux 接口名。本步沿接口目录找到对应设备，再核对它在系统中的地址、厂商和型号。

<div style="border:2px solid #4f46e5;background:#eef2ff;padding:10px 12px;border-radius:8px;margin:14px 0;"><div style="font-weight:900;color:#312e81;margin-bottom:4px;">导航卡 · 接口与设备身份</div><div style="font-weight:700;color:#312e81;margin-bottom:8px;">范畴：现场只读　本步知识：接口背后是哪块设备　位置：全章第 5 / 8 项 · 本组第 2 / 3 项</div><span style="display:inline-block;margin:3px;padding:4px 10px;border-radius:6px;background:#f8fafc;border:1px solid #a5b4fc;color:#312e81;font-weight:800;">运行 ①：核对两类接口</span><span style="display:inline-block;margin:3px;padding:4px 10px;border-radius:6px;background:#15803d;color:#fff;font-weight:800;">运行 ②：从接口名找到设备地址</span><span style="display:inline-block;margin:3px;padding:4px 10px;border-radius:6px;background:#f8fafc;border:1px solid #a5b4fc;color:#312e81;font-weight:800;">运行 ③：查当前驱动</span></div>

### 本步理论：一个网口有多种身份

查一台厨房设备时，可以同时看它安装在哪里、铭牌上是什么型号、贴了什么标签。这里也看三项：BDF 定位设备功能，PCI ID 给出厂商与设备编号，MAC 是网口当前使用的二层地址。把它们放在一起，即使接口名改变，也有线索找到原来的数据口。

<div style="border-left:6px solid #7e22ce;background:#f3e8ff;padding:14px 18px;border-radius:8px;margin:14px 0;">
<div style="font-weight:900;color:#581c87;margin-bottom:8px;">仅供展示 · 看懂一个 BDF 地址</div>
<div style="font-weight:700;color:#581c87;">Linux 按 <code>Domain:Bus:Device.Function</code> 编排 PCIe 地址，现场常把完整地址简称 BDF。它表示设备在当前主机内的位置。</div>
<pre style="background:#faf5ff;border:1px solid #c4b5fd;padding:12px 14px;border-radius:6px;margin:12px 0 0;overflow-x:auto;color:#3b0764;"><code>0000:03:00.0
│    │  │  └─ Function 0
│    │  └──── Device/Slot 00
│    └─────── Bus 03
└──────────── Domain 0000</code></pre>
</div>

把完整地址按四段读：`Domain` 是 PCI 域编号，本课为 `0000`；`Bus` 是总线编号；`Device` 是总线上的设备编号；`Function` 是设备提供的功能编号。一个设备可以提供多个功能，系统通过这些编号分别识别它们。这里的设备编号属于系统登记的拓扑，不直接对应机箱槽位。

<div style="border-left:6px solid #7e22ce;background:#f3e8ff;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#7e22ce;color:#fff;font-weight:800;">关键图</span> <span style="font-weight:700;color:#581c87;">从硬件、软件和网络三个方面，认识同一个数据口的身份。</span></div>

<div style="background:#f8fafc;border:1px solid #cbd5e1;border-radius:12px;padding:10px;max-width:820px;margin:14px auto;">
<img src="images/course-visuals/01-diagrams/01-interface-identities.svg" alt="同一个X2522数据口对应六种身份信息：BDF、厂商与设备编号、sfc驱动、接口名、MAC与IPv4地址" style="display:block;width:100%;max-width:800px;height:auto;margin:0 auto;">
</div>

**读图：** 从硬件地址和型号，找到管理它的驱动，再对应到 Linux 接口、MAC 和 IP。它们描述的是同一个数据口的不同方面。

**理论落到实验：** 依次查出数据口对应的设备位置、MAC 地址和设备编号，再对照结果理解这些查询命令。

<div style="border-left:6px solid #15803d;background:#dcfce7;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#15803d;color:#fff;font-weight:800;">需要运行 · 运行 ②</span> <span style="font-weight:700;color:#14532d;">在【跳板机 .111】以 root 运行。读取每台数据口的 sysfs 设备路径、MAC，以及对应 PCI 设备的一行 <code>lspci</code>。</span></div>

```bash
#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency

RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-01-pci-identity"
OUT="Documents/reports/course-runs/${RUN_ID}"
mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"

{
for item in '10.1.1.1 ens64np0' '10.1.1.2 ens64np1'; do
  read -r host data_if <<<"$item"
  printf '\n%s / verify · %s\n' "$host" "$data_if"
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes "root@$host" \
    bash -s -- "$data_if" <<'REMOTE'
set -Eeuo pipefail
data_if="$1"
printf '===== 查设备位置 =====\n[设备位置] 对: 路径末段为 0000:03:00.0  证: 找到这个网口对应的 PCI 设备\n$ readlink -f /sys/class/net/%s/device\n' "$data_if"
readlink -f "/sys/class/net/$data_if/device"
printf '===== 查 MAC 地址 =====\n[MAC] 对: 六组十六进制数  证: 读到这个网口当前使用的 MAC 地址\n$ cat /sys/class/net/%s/address\n' "$data_if"
cat "/sys/class/net/$data_if/address"
bdf="$(basename "$(readlink -f "/sys/class/net/$data_if/device")")"
printf '===== 查设备类型与编号 =====\n[设备类别] 对: 0200  证: 以太网控制器\n[厂商 ID] 对: 1924  证: Solarflare Communications\n[设备 ID] 对: 0b03  证: SFC9250 以太网控制器\n$ lspci -nn -s %s\n' "$bdf"
lspci -nn -s "$bdf"
REMOTE
done
} 2>&1 | tee "$OUT/raw/pci-identity.txt"
(cd "$OUT" && sha256sum raw/pci-identity.txt run.env >SHA256SUMS); printf 'evidence=%s\n' "$OUT"
```

<div style="border-left:6px solid #7e22ce;background:#f3e8ff;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#7e22ce;color:#fff;font-weight:800;">仅供展示 · 输出解读</span> <span style="font-weight:700;color:#581c87;">依次查看设备路径、MAC 地址和 <code>lspci</code> 列出的网卡信息。</span></div>

```text
10.1.1.1 / verify · ens64np0
===== 查设备位置 =====
[设备位置] 对: 路径末段为 0000:03:00.0  证: 找到这个网口对应的 PCI 设备
$ readlink -f /sys/class/net/ens64np0/device
/sys/devices/pci0000:03/0000:03:00.0
===== 查 MAC 地址 =====
[MAC] 对: 六组十六进制数  证: 读到这个网口当前使用的 MAC 地址
$ cat /sys/class/net/ens64np0/address
00:0f:53:d3:af:20
===== 查设备类型与编号 =====
[设备类别] 对: 0200  证: 以太网控制器
[厂商 ID] 对: 1924  证: Solarflare Communications
[设备 ID] 对: 0b03  证: SFC9250 以太网控制器
$ lspci -nn -s 0000:03:00.0
03:00.0 Ethernet controller [0200]: Solarflare Communications XtremeScale SFC9250 10/25/40/50/100G Ethernet Controller [1924:0b03] (rev 01)
```

<div style="border-left:6px solid #7e22ce;background:#f3e8ff;padding:14px 18px;border-radius:8px;margin:14px 0;">
<div style="font-weight:900;color:#581c87;margin-bottom:8px;">仅供展示 · sysfs 与查询命令</div>
<div style="margin-top:10px;color:#3b0764;"><strong>sysfs：</strong>Linux 通过 <code>/sys</code> 这套目录展示设备和驱动信息。<code>/sys/class/net</code> 按接口名组织网口；网口目录里的 <code>device</code> 是一个符号链接，像捷径一样指向对应的设备目录。</div>
<div style="margin-top:8px;color:#3b0764;"><strong><code>readlink -f</code>：</strong>沿符号链接找到最终目录，打印完整路径；这里用它从接口名找到 PCI 设备，路径末段就是设备地址（BDF）。下一步查询驱动时，<code>bus-info</code> 应与这个地址一致。</div>
<div style="margin-top:8px;color:#3b0764;"><strong><code>cat</code>：</strong>打印文件内容；这里读取网口目录中的 <code>address</code>，得到当前 MAC 地址。</div>
<div style="margin-top:8px;color:#3b0764;"><strong><code>lspci</code>：</strong>查询 PCI/PCIe 设备信息。<code>-s</code> 指定要查的设备地址，<code>-nn</code> 同时显示名称和数字 ID；末尾的 <code>rev</code> 表示硬件修订号。</div>
</div>

这里查到的 SFC9250 是控制器名称，X2522 是本课网卡的产品型号。[PCI ID 数据库](https://raw.githubusercontent.com/pciutils/pciids/master/pci.ids)

BDF 是每台虚拟机内部的设备地址，所以两台都可以显示 `0000:03:00.0`。本课把同一张 X2522 的两个端口分别交给这两台虚拟机使用。

<div style="border-left:6px solid #0891b2;background:#cffafe;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#0891b2;color:#fff;font-weight:800;">关键现象</span> <span style="font-weight:700;color:#164e63;">两台主机分别按输出中的提示核对即可。若提示路径不存在，检查接口名；若厂商或设备 ID 不同，检查是否选中了其他网卡。</span></div>

设备身份已经确认。要让 Linux 使用这个网口，还需要驱动管理它；运行 ③ 检查当前绑定的驱动。

## 运行 ③：查当前驱动

操作系统已经看见这块 PCI 设备。本步确认：当前由哪个 Linux 驱动在管理它。

<div style="border:2px solid #4f46e5;background:#eef2ff;padding:10px 12px;border-radius:8px;margin:14px 0;"><div style="font-weight:900;color:#312e81;margin-bottom:4px;">导航卡 · 接口与设备身份</div><div style="font-weight:700;color:#312e81;margin-bottom:8px;">范畴：现场只读　本步知识：当前由哪个驱动管理网卡　位置：全章第 6 / 8 项 · 本组第 3 / 3 项</div><span style="display:inline-block;margin:3px;padding:4px 10px;border-radius:6px;background:#f8fafc;border:1px solid #a5b4fc;color:#312e81;font-weight:800;">运行 ①：核对两类接口</span><span style="display:inline-block;margin:3px;padding:4px 10px;border-radius:6px;background:#f8fafc;border:1px solid #a5b4fc;color:#312e81;font-weight:800;">运行 ②：从接口名找到设备地址</span><span style="display:inline-block;margin:3px;padding:4px 10px;border-radius:6px;background:#15803d;color:#fff;font-weight:800;">运行 ③：查当前驱动</span></div>

### 本步理论：先认出当前驱动名字

设备位置查清以后，还要找到负责操作它的软件。驱动像熟悉设备的人：负责初始化网卡、准备收发缓冲区，并把收包结果交给内核网络栈。`lspci` 确认设备存在，驱动查询则确认由谁管理它。

<div style="border-left:6px solid #7e22ce;background:#f3e8ff;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#7e22ce;color:#fff;font-weight:800;">关键图</span> <span style="font-weight:700;color:#581c87;">本章检查实线连接的 <code>sfc</code> 驱动路径；虚线保留第六部分用户态收发的学习入口。</span></div>

<div style="background:#f8fafc;border:1px solid #cbd5e1;border-radius:12px;padding:10px;max-width:820px;margin:14px auto;">
<img src="images/course-visuals/01-diagrams/01-driver-ownership.svg" alt="实线连接X2522、sfc驱动、网络接口与套接字接口，虚线连接第六部分用户态直接收发入口" style="display:block;width:100%;max-width:800px;height:auto;margin:0 auto;">
</div>

本章沿实线检查：`sfc` 驱动提供网络接口，内核网络栈通过套接字（Socket）与程序交换数据。虚线只标出第六部分的学习入口，届时再比较其他收发方式。

**理论落到实验：** 一条线索读 `/sys/bus/pci/devices/<BDF>/driver` 指向哪个驱动目录；另一条用 `ethtool -i` 从接口读出 `driver` 和 `bus-info`。两条都指向同一个名字，并且 `bus-info` 与运行 ② 的 BDF 相同。

<div style="border-left:6px solid #15803d;background:#dcfce7;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#15803d;color:#fff;font-weight:800;">需要运行 · 运行 ③</span> <span style="font-weight:700;color:#14532d;">在【跳板机 .111】以 root 运行。读取每台数据口对应 PCI 设备的 driver 路径，以及 <code>ethtool -i</code> 里的 driver 和 bus-info。</span></div>

```bash
#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency

RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-01-driver-owner"
OUT="Documents/reports/course-runs/${RUN_ID}"
mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"

{
for item in '10.1.1.1 ens64np0' '10.1.1.2 ens64np1'; do
  read -r host data_if <<<"$item"
  printf '\n%s / verify · %s\n' "$host" "$data_if"
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes "root@$host" \
    bash -s -- "$data_if" <<'REMOTE'
set -Eeuo pipefail
data_if="$1"
bdf="$(basename "$(readlink -f "/sys/class/net/$data_if/device")")"
printf '===== 查当前绑定的驱动 =====\n[驱动归属] 对: 路径末段为 sfc  证: 这个 PCI 设备当前由 sfc 驱动管理\n$ readlink -f /sys/bus/pci/devices/%s/driver\n' "$bdf"
readlink -f "/sys/bus/pci/devices/$bdf/driver"
printf '===== 从网口核对驱动信息 =====\n[驱动] 对: driver 为 sfc  证: 与设备目录查到的驱动一致\n[设备地址] 对: bus-info 为 %s  证: 与运行 ② 查到的 BDF 一致\n[版本] 看: version 是驱动版本，firmware-version 是网卡固件版本\n$ ethtool -i %s\n' "$bdf" "$data_if"
ethtool -i "$data_if"
REMOTE
done
} 2>&1 | tee "$OUT/raw/driver-owner.txt"
(cd "$OUT" && sha256sum raw/driver-owner.txt run.env >SHA256SUMS); printf 'evidence=%s\n' "$OUT"
```

<div style="border-left:6px solid #7e22ce;background:#f3e8ff;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#7e22ce;color:#fff;font-weight:800;">仅供展示 · 输出解读</span> <span style="font-weight:700;color:#581c87;">以 <code>.1</code> 为例，保留输出中的关键字段。</span></div>

```text
10.1.1.1 / verify · ens64np0
===== 查当前绑定的驱动 =====
[驱动归属] 对: 路径末段为 sfc  证: 这个 PCI 设备当前由 sfc 驱动管理
$ readlink -f /sys/bus/pci/devices/0000:03:00.0/driver
/sys/bus/pci/drivers/sfc
===== 从网口核对驱动信息 =====
[驱动] 对: driver 为 sfc  证: 与设备目录查到的驱动一致
[设备地址] 对: bus-info 为 0000:03:00.0  证: 与运行 ② 查到的 BDF 一致
[版本] 看: version 是驱动版本，firmware-version 是网卡固件版本
$ ethtool -i ens64np0
driver: sfc
version: 5.15.0-164-generic
firmware-version: 8.0.0.1015 rx1 tx1
bus-info: 0000:03:00.0
```

<div style="border-left:6px solid #7e22ce;background:#f3e8ff;padding:14px 18px;border-radius:8px;margin:14px 0;">
<div style="font-weight:900;color:#581c87;margin-bottom:8px;">仅供展示 · sfc 与 ethtool -i</div>
<div style="margin-top:0;color:#3b0764;"><strong><code>sfc</code>：</strong>Solarflare Communications 网卡驱动在 Linux 中使用的简称；系统也用这个名字建立驱动目录 <code>/sys/bus/pci/drivers/sfc</code>。</div>
<div style="margin-top:8px;color:#3b0764;"><strong><code>ethtool -i</code></strong>：从网口视角查询当前驱动、驱动版本、固件版本和 PCI 总线地址。</div>
</div>

示例中的驱动随内核提供，因此 `version` 使用内核版本编号；第二部分安装厂商驱动后，这个编号会改变。

<div style="border-left:6px solid #0891b2;background:#cffafe;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#0891b2;color:#fff;font-weight:800;">关键现象</span> <span style="font-weight:700;color:#164e63;">逐台核两组对应：sysfs 末段 <code>sfc</code> 与 <code>driver: sfc</code> 相同，<code>bus-info: 0000:03:00.0</code> 与运行 ② 的 BDF 相同。</span></div>

驱动已经对应到正确设备。还要确认网线两端建立了 10G 链路，并接入同一个 VLAN，运行 ④ 同时查看主机与交换机。

## 运行 ④：对齐主机与交换机链路

本步对照同一根线的两端：主机看速率、双工和链路检测结果，交换机看端口连接状态与 VLAN。

<div style="border:2px solid #4f46e5;background:#eef2ff;padding:10px 12px;border-radius:8px;margin:14px 0;"><div style="font-weight:900;color:#312e81;margin-bottom:4px;">导航卡 · 链路与报文检查</div><div style="font-weight:700;color:#312e81;margin-bottom:8px;">范畴：现场只读　本步知识：网线两端的链路状态是否一致　位置：全章第 7 / 8 项 · 本组第 1 / 2 项</div><span style="display:inline-block;margin:3px;padding:4px 10px;border-radius:6px;background:#15803d;color:#fff;font-weight:800;">运行 ④：对齐主机与交换机链路</span><span style="display:inline-block;margin:3px;padding:4px 10px;border-radius:6px;background:#f8fafc;border:1px solid #a5b4fc;color:#312e81;font-weight:800;">运行 ⑤：抓到三条 ping</span></div>

### 本步理论：接口启用以后，还要查什么

要判断网口能否正常通信，可以像检查厨房能否收货一样，沿着过程一步步看：收货门有没有打开，对应接口是否启用；门外通道有没有接通，对应链路是否建立；试送的货物能否到达，对应探针能否得到回应。网络通信还要核对地址、路由和邻居信息，具体用哪些工具检查，见下表。[Linux 接口状态说明](https://docs.kernel.org/networking/operstates.html)

| 检查什么 | 常用命令或文件 | 怎样理解 |
| --- | --- | --- |
| 接口是否启用（admin up） | `ip link` | 管理员允许接口工作 |
| 链路是否建立（carrier） | `ethtool` | 驱动报告是否检测到链路，并给出速率和双工状态 |
| 地址与路由 | `ip addr`、`ip route` | 本机使用哪个 IP，准备从哪个接口发送 |
| 邻居地址与探针回应 | `ip neigh`、`ping` | 前者查看邻居地址解析状态，后者检查请求是否得到回应 |
| 报文是否被观察到 | pcap、网卡与交换机计数器 | 指定观察位置是否记录到了报文 |

本章的操作顺序是：运行 ① 核对接口和 IP 地址；当前运行 ④ 对照主机与交换机，检查链路、速率和 VLAN；运行 ⑤ 再发送 ping 并抓包，查看实际收发的报文。

<div style="border:2px solid #7e22ce;background:#faf5ff;padding:14px 16px;border-radius:10px;margin:16px 0;">
<div style="font-weight:900;color:#581c87;margin-bottom:10px;">实体链路 · Cisco SFP-H10GB-CU5M</div>
<img src="images/cisco-sfp-h10gb-cu5m-dac.png" alt="连接 .1 Exchange NIC 与 Arista Et1 的 Cisco 5 米 SFP+ 双轴直连线" style="display:block;width:100%;max-width:800px;height:auto;margin:0 auto;border-radius:8px;background:#fff;">
<div style="color:#581c87;font-weight:700;margin-top:10px;">两条数据链路都是 10GBASE-CR SFP+ DAC。照片是 <code>.1 Exchange ↔ Et1</code> 这一根 Cisco SFP-H10GB-CU5M（5 米）；<code>.2 Trader ↔ Et2</code> 是同类的另一根。主机侧把它读成 <code>10000Mb/s</code>、<code>Full</code> 与 <code>Link detected: yes</code>。</div>
</div>

**理论落到实验：** 主机的 `ethtool` 输出应包含 `10000Mb/s`、`Full` 和 `Link detected: yes`；交换机的 `show interfaces ... status` 应显示对应端口连接在 VLAN20，并使用 10G 全双工。把同一根线的两端逐项对照。

<div style="border-left:6px solid #15803d;background:#dcfce7;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#15803d;color:#fff;font-weight:800;">需要运行 · 运行 ④</span> <span style="font-weight:700;color:#14532d;">在【跳板机 .111】以 root 运行。读取 <code>.1/.2</code> 数据口的 <code>ethtool</code>，以及交换机 Et1、Et2 和 VLAN20 的状态。</span></div>

```bash
#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-01-link-pair"
OUT="Documents/reports/course-runs/${RUN_ID}"
mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
{
# 主机侧：保留完整输出，课堂只显示链路字段
for item in '10.1.1.1 ens64np0' '10.1.1.2 ens64np1'; do
  read -r host data_if <<<"$item"
  printf '\n%s / verify · %s\n===== 查主机侧链路 =====\n' "$host" "$data_if"
  printf '[链路] 对: 10000Mb/s、Full、yes  证: 本端检测到 10G 全双工链路\n[端口类别] 看: Port 是当前驱动报告的类别，需结合交换机 Type 判断介质\n$ ethtool %s\n' "$data_if"
  if ssh -n -o BatchMode=yes -o StrictHostKeyChecking=yes "root@$host" \
    "ethtool '$data_if'" >"$OUT/raw/host-$host.txt" 2>&1; then
    sed -n -E '/^[[:space:]]*(Speed|Duplex|Port|Link detected):/p' "$OUT/raw/host-$host.txt"
  else
    rc=$?; tail -n 20 "$OUT/raw/host-$host.txt"; printf '完整输出：%s\n' "$OUT/raw/host-$host.txt"; exit "$rc"
  fi
done
# 交换机侧：一次连接查询三项，在每条命令前加入对应说明
printf '%s\n' 'show interfaces Ethernet1 status' \
  'show interfaces Ethernet2 status' 'show vlan id 20' >"$OUT/eos.plan"
printf '\n10.1.1.253 / verify\n'
if python3 Documents/newDoc/assets/common/eos_cli.py --mode show \
  --plan "$OUT/eos.plan" --output "$OUT/raw/arista-links.txt" >"$OUT/raw/arista-terminal.txt" 2>&1; then
  awk '
    /^\$ show interfaces Ethernet[12] status$/ {
      port=($4=="Ethernet1" ? "Et1" : "Et2")
      print "===== 查交换机 " port " 链路 ====="
      print "[端口] 对: connected、20、full、10G  证: 已连接并接入 VLAN20，使用 10G 全双工"
    }
    /^\$ show vlan id 20$/ {
      print "===== 查 VLAN20 活动端口 ====="
      print "[VLAN] 对: active，包含 Et1、Et2  证: VLAN20 已启用，两条数据链路处于活动状态"
    }
    { print }
  ' "$OUT/raw/arista-links.txt"
else
  rc=$?; tail -n 20 "$OUT/raw/arista-terminal.txt"; printf '完整输出：%s\n' "$OUT/raw/arista-terminal.txt"; exit "$rc"
fi
} 2>&1 | tee "$OUT/classroom.txt"
(cd "$OUT" && sha256sum raw/* run.env eos.plan classroom.txt >SHA256SUMS); printf 'evidence=%s\n' "$OUT"
```

<div style="border-left:6px solid #7e22ce;background:#f3e8ff;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#7e22ce;color:#fff;font-weight:800;">仅供展示 · 输出解读</span> <span style="font-weight:700;color:#581c87;">对照主机与交换机两端的链路状态、速率和 VLAN；交换机示例只保留关键行。</span></div>

```text
10.1.1.1 / verify · ens64np0
===== 查主机侧链路 =====
[链路] 对: 10000Mb/s、Full、yes  证: 本端检测到 10G 全双工链路
[端口类别] 看: Port 是当前驱动报告的类别，需结合交换机 Type 判断介质
$ ethtool ens64np0
	Speed: 10000Mb/s
	Duplex: Full
	Port: Direct Attach Copper
	Link detected: yes
```

`Port` 是驱动报告的物理端口类别。内核自带的 `sfc` 可把 X2522 的插槽报告为 `FIBRE`；安装第二部分运行依赖后，课程驱动报告 `Direct Attach Copper`（直连铜缆），上面展示的是后一种读数。交换机 Type 的 `10GBASE-CR` 也指铜缆介质；驱动读数不同不表示换了线。`.2` 的 `$ ethtool ens64np1` 四行相同。

```text
10.1.1.253 / verify
===== 查交换机 Et1 链路 =====
[端口] 对: connected、20、full、10G  证: 已连接并接入 VLAN20，使用 10G 全双工
$ show interfaces Ethernet1 status
Et1               connected    20       full   10G    10GBASE-CR
```

```text
===== 查交换机 Et2 链路 =====
[端口] 对: connected、20、full、10G  证: 已连接并接入 VLAN20，使用 10G 全双工
$ show interfaces Ethernet2 status
Et2               connected    20       full   10G    10GBASE-CR
```

```text
===== 查 VLAN20 活动端口 =====
[VLAN] 对: active，包含 Et1、Et2  证: VLAN20 已启用，两条数据链路处于活动状态
$ show vlan id 20
20    fll                              active    Cpu, Et1, Et2
```


<div style="border-left:6px solid #0891b2;background:#cffafe;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#0891b2;color:#fff;font-weight:800;">关键现象</span> <span style="font-weight:700;color:#164e63;">主机侧两台都是 <code>10000Mb/s / Full / yes</code>；交换机侧 Et1、Et2 都是 <code>connected / 20 / full / 10G</code>，VLAN20 为 <code>active</code>。出现 <code>Unknown!</code>、低于 10G、<code>Half</code>、<code>no</code> 或 <code>notconnect</code> 时，直接指出异常字段属于哪一端。</span></div>

两端链路状态符合预期。运行 ⑤ 在 `.2` 抓包，用三条实际请求确认报文到达这个接口。

## 运行 ⑤：抓到三条 ping

本步从 `.1` 发出三条 ping 请求，在 `.2` 保存对应的抓包文件，让接口和链路检查有实际报文可以核对。

<div style="border:2px solid #4f46e5;background:#eef2ff;padding:10px 12px;border-radius:8px;margin:14px 0;"><div style="font-weight:900;color:#312e81;margin-bottom:4px;">导航卡 · 链路与报文检查</div><div style="font-weight:700;color:#312e81;margin-bottom:8px;">范畴：现场只读　本步知识：三条请求是否到达指定接口　位置：全章第 8 / 8 项 · 本组第 2 / 2 项</div><span style="display:inline-block;margin:3px;padding:4px 10px;border-radius:6px;background:#f8fafc;border:1px solid #a5b4fc;color:#312e81;font-weight:800;">运行 ④：对齐主机与交换机链路</span><span style="display:inline-block;margin:3px;padding:4px 10px;border-radius:6px;background:#15803d;color:#fff;font-weight:800;">运行 ⑤：抓到三条 ping</span></div>

### 本步理论：在指定数据口抓三条 ICMP 探针

ping 收到回应，说明请求到达了能回应它的主机；在指定数据口抓到请求，则把到达位置也记录下来。像在收货口留下到货记录，这一步确认报文到了哪里，第二部分再确认交易程序读取和解析了什么。

`.1` 从数据口发出三条 ICMP Echo Request。`.2` 的 `tcpdump` 在 `ens64np1` 上把匹配帧写入 pcap。本步要看的就是这三条出现在指定数据口上的报文。

<div style="border-left:6px solid #7e22ce;background:#f3e8ff;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#7e22ce;color:#fff;font-weight:800;">关键图</span> <span style="font-weight:700;color:#581c87;">沿箭头 ① → ② → ③ 读主线，再看 ④a 抓包、④b 回应两条分支。</span></div>

<div style="background:#f8fafc;border:1px solid #cbd5e1;border-radius:12px;padding:10px;max-width:820px;margin:14px auto;">
<img src="images/course-visuals/01-diagrams/01-packet-and-evidence.svg" alt="① DMA写入内存，②中断通知，③驱动批量读取；随后分为④a抓包留副本和④b内核ICMP回应" style="display:block;width:100%;max-width:800px;height:auto;margin:0 auto;">
</div>

第零部分的“存货区、清单、照单放货”，在这台 X2522 上对应同一组动作。本张收包图的步骤编号分别表示：

| 箭头 | 从哪里到哪里 | 发生什么 |
| --- | --- | --- |
| ① | 网卡 → 主内存缓冲区 | 驱动预先准备缓冲区并登记地址；网卡收到请求后，通过 PCIe 用 DMA 把报文字节写进去。[Linux DMA 指南](https://docs.kernel.org/core-api/dma-api-howto.html) |
| ② | 网卡 → CPU | 图示的中断驱动方式中，网卡通知有报文待处理，内核安排 NAPI 收包工作。 |
| ③ | 主内存缓冲区 → CPU / 驱动 | NAPI 调用驱动的 `poll` 函数，批量处理已收到的报文；CPU 读取内存中的数据。[Linux NAPI 说明](https://docs.kernel.org/networking/napi.html) |
| ④a | 接收路径 → tcpdump | 报文副本交给抓包工具，保存到 pcap，供我们查看请求是否到达指定数据口。 |
| ④b | 接收路径 → 内核 ICMP 处理 | 内核生成 Echo Reply，经 `.2` 数据口发回 `.1`；发送端收到回应后，`ping` 才把它计入 `received`。 |

④a、④b 表示两条分支，内核生成回应无需等待抓包工具保存完成。

| 图中对象 | 名字与职责 |
| --- | --- |
| RAM 缓冲区 | 接收缓冲区（RX Buffer）：主内存中预先准备的收包空间 |
| 驱动登记的地址 | 接收描述符（RX Descriptor）：描述可用缓冲区的记录，供网卡找到写入位置 |
| DMA | 直接内存访问：网卡把报文写入主机内存，CPU 无需逐字节搬运；准备和处理工作仍由 CPU 执行 |
| CPU / 驱动 | `sfc` 是本课网卡驱动；NAPI 安排批量收包，驱动的 `poll` 函数处理已收到的报文 |
| tcpdump 留副本 | 抓包使用报文套接字（packet socket）观察二层报文，结果写入 pcap 文件 |
| 内核处理 ICMP | 判断请求是否发给本机，并生成 Echo Reply 回应 |

`tcpdump` 通过报文套接字观察数据，而不是替交易程序接收和解析行情。[Linux 报文套接字说明](https://man7.org/linux/man-pages/man7/packet.7.html)

**理论落到实验：** 脚本先在 `.2` 的 `ens64np1` 启动抓包，再让 `.1` 的 `ens64np0` 发送三条 ping。过滤表达式（BPF）只保留 `.1 → .2` 的 ICMP Echo Request；执行后对照发送统计和 pcap 中的方向、序号。

<div style="border-left:6px solid #15803d;background:#dcfce7;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#15803d;color:#fff;font-weight:800;">需要运行 · 运行 ⑤</span> <span style="font-weight:700;color:#14532d;">在【跳板机 .111】以 root 运行。先在 <code>.2</code> 的 <code>ens64np1</code> 上抓包，再从 <code>.1</code> 发出三条 ICMP 探针，最后回读 pcap。</span></div>

```bash
#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-01-packet-proof"
OUT="Documents/reports/course-runs/${RUN_ID}"
REMOTE="/var/tmp/$RUN_ID"
mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
SSH=(-o BatchMode=yes -o StrictHostKeyChecking=yes)
BPF='icmp[icmptype] = icmp-echo and src 20.1.1.1 and dst 20.1.1.2'
cleanup() {
  ssh -n "${SSH[@]}" root@10.1.1.2 "rm -rf -- '$REMOTE'" >/dev/null 2>&1 || true
}
trap cleanup EXIT
{
# 先在 .2 启动抓包，过滤 .1 → .2 的 ICMP echo request
printf '\n10.1.1.2 / capture · ens64np1\n===== 启动接收端抓包 =====\n[抓包范围] 看: 只记录 20.1.1.1 → 20.1.1.2 的 ICMP 请求，抓到三条后结束\n'
printf '$ timeout 8 tcpdump -ni ens64np1 -c 3 -w %s/probe.pcap %s\n' "$REMOTE" "'$BPF'"
ssh -n "${SSH[@]}" root@10.1.1.2 "mkdir -m 700 '$REMOTE'"
ssh -n "${SSH[@]}" root@10.1.1.2 \
  "timeout 8 tcpdump -ni ens64np1 -c 3 -w '$REMOTE/probe.pcap' '$BPF'" \
  >"$OUT/raw/capture.txt" 2>&1 &
CAPTURE_PID=$!
sleep 1
# 再从 .1 数据口发出三条 ping
printf '\n10.1.1.1 / probe · ens64np0\n===== 发送三条 ping =====\n[探针] 对: 3 transmitted、3 received、0%% packet loss  证: 三条请求都有回应\n$ ping -I ens64np0 -c 3 -W 1 20.1.1.2\n' \
  | tee "$OUT/raw/sender.txt"
ssh -n "${SSH[@]}" root@10.1.1.1 \
  'ping -I ens64np0 -c 3 -W 1 20.1.1.2' 2>&1 | tee -a "$OUT/raw/sender.txt"
if wait "$CAPTURE_PID"; then
  printf '\n10.1.1.2 / verify · ens64np1\n===== 查抓包统计 =====\n[抓包结果] 对: 3 packets captured、0 packets dropped by kernel  证: 捕获三条请求，抓包未报告内核丢包\n'
  cat "$OUT/raw/capture.txt"
else
  rc=$?; cat "$OUT/raw/capture.txt"; exit "$rc"
fi
scp "${SSH[@]}" "root@10.1.1.2:$REMOTE/probe.pcap" "$OUT/raw/probe.pcap"
printf '\n===== 读取三条请求 =====\n[报文] 对: 20.1.1.1 > 20.1.1.2、echo request、seq 1/2/3  证: 到达数据口的方向、类型与序号符合预期\n$ tcpdump -nn -r %s/probe.pcap\n' "$REMOTE"
if ssh -n "${SSH[@]}" root@10.1.1.2 \
  "tcpdump -nn -r '$REMOTE/probe.pcap'" >"$OUT/raw/receiver.txt" 2>&1; then :; else
  rc=$?; cat "$OUT/raw/receiver.txt"; exit "$rc"
fi
cat "$OUT/raw/receiver.txt"
} 2>&1 | tee "$OUT/classroom.txt"
(cd "$OUT" && sha256sum raw/* run.env classroom.txt >SHA256SUMS); printf 'evidence=%s\n' "$OUT"
```

<div style="border-left:6px solid #7e22ce;background:#f3e8ff;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#7e22ce;color:#fff;font-weight:800;">仅供展示 · 输出解读</span> <span style="font-weight:700;color:#581c87;">对照发送与抓包结果，确认三条 ping 请求到达接收端；示例保留关键读数。</span></div>

```text
10.1.1.2 / capture · ens64np1
===== 启动接收端抓包 =====
[抓包范围] 看: 只记录 20.1.1.1 → 20.1.1.2 的 ICMP 请求，抓到三条后结束
$ timeout 8 tcpdump -ni ens64np1 -c 3 -w …/probe.pcap 'icmp[icmptype] = icmp-echo and src 20.1.1.1 and dst 20.1.1.2'
```

```text
10.1.1.1 / probe · ens64np0
===== 发送三条 ping =====
[探针] 对: 3 transmitted、3 received、0% packet loss  证: 三条请求都有回应
$ ping -I ens64np0 -c 3 -W 1 20.1.1.2
PING 20.1.1.2 (20.1.1.2) from 20.1.1.1 ens64np0: 56(84) bytes of data.
3 packets transmitted, 3 received, 0% packet loss, time 2033ms
```

```text
10.1.1.2 / verify · ens64np1
===== 查抓包统计 =====
[抓包结果] 对: 3 packets captured、0 packets dropped by kernel  证: 捕获三条请求，抓包未报告内核丢包
tcpdump: listening on ens64np1, link-type EN10MB (Ethernet)
3 packets captured
0 packets dropped by kernel
```

```text
===== 读取三条请求 =====
[报文] 对: 20.1.1.1 > 20.1.1.2、echo request、seq 1/2/3  证: 到达数据口的方向、类型与序号符合预期
$ tcpdump -nn -r …/probe.pcap
09:30:37.228135 IP 20.1.1.1 > 20.1.1.2: ICMP echo request, id 2, seq 1, length 64
09:30:38.236981 IP 20.1.1.1 > 20.1.1.2: ICMP echo request, id 2, seq 2, length 64
09:30:39.261006 IP 20.1.1.1 > 20.1.1.2: ICMP echo request, id 2, seq 3, length 64
```


ping 结尾还会打印一行往返时间统计，示例省略了这一行。本章只用 ping 检查连通性，延迟怎样测量和比较，第四部分再展开。

<div style="border-left:6px solid #0891b2;background:#cffafe;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#0891b2;color:#fff;font-weight:800;">关键现象</span> <span style="font-weight:700;color:#164e63;">发送端统计为 <code>3 transmitted / 3 received / 0% packet loss</code>；接收端 pcap 出现三条 <code>.1 → .2</code> 的 <code>ICMP echo request</code>，序号依次 1、2、3。缺序号、方向相反或接口不对时，先检查抓包接口与过滤表达式（BPF，脚本中的 <code>BPF</code> 变量）。</span></div>

## 本章总结：把检查结果连起来

| 检查结果 | 确认什么 | 适用范围 |
| --- | --- | --- |
| 管理口与数据口地址 | `ens33` 与 X2522 数据口分别使用课程预设地址 | 当前接口基线 |
| 接口 → MAC → BDF → PCI ID | 当前接口对应预期 X2522 设备功能 | 当前设备身份 |
| sysfs + `ethtool -i` | 示例中的 X2522 由内核自带的 `sfc` 驱动管理 | 运行检查时的驱动绑定关系 |
| 主机与交换机链路 | 两端已建立 10G 全双工链路 | 当前链路状态 |
| ping 统计与接收端抓包 | 三条真实探针到达 `.2` X2522 | 本次捕获的三条请求 |

<div style="border-left:6px solid #7e22ce;background:#f3e8ff;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#7e22ce;color:#fff;font-weight:800;">关键图</span> <span style="font-weight:700;color:#581c87;">本章五项检查对应到这条路径：<code>.1</code> 的 ping 从数据口发出，经 Arista VLAN20 到达 <code>.2</code>，由 <code>tcpdump</code> 写入 pcap。</span></div>

```mermaid
flowchart TB
  subgraph sender["发送主机 .1"]
    direction LR
    a1["① ping<br/>发出三条请求"] --> a2["② ens64np0<br/>X2522 · sfc 驱动"]
    a2 --> a3["③ X2522 网卡发出<br/>经直连铜缆发送"]
  end

  a4["④ Arista<br/>Et1 → VLAN20 → Et2"]

  subgraph receiver["接收主机 .2"]
    direction LR
    a5["⑤ X2522 网卡收到<br/>由 sfc 驱动管理"] --> a6["⑥ ens64np1<br/>网络接口"]
    a6 --> a7["⑦ 抓包工具 tcpdump<br/>保存报文文件"]
  end

  sender --> a4
  a4 --> receiver

  classDef host fill:#ecfeff,stroke:#0891b2,stroke-width:2px,color:#164e63;
  classDef switch fill:#e0e7ff,stroke:#4f46e5,stroke-width:2px,color:#312e81;
  class a1,a2,a3,a5,a6,a7 host;
  class a4 switch;
  linkStyle default stroke:#0891b2,stroke-width:2px;
```

**读图：** ①～③ 是 `.1` 发送请求，④ 是交换机在 VLAN20 内转发，⑤～⑦ 是 `.2` 收到请求并留下抓包记录。接口、设备、驱动、链路和实际报文至此对应起来。

第二部分会使用本章准备好的构建工具和管理连接，部署 Exchange、Trader 与网页。数据网从承载 ping 转为承载行情和订单，检查重点也随之变成“交易程序是否读到行情、交易所是否返回订单结果”。

## 理解检查

1. `.1` 和 `.2` 各有哪两类接口？真正通过 DAC 接入 Arista 的是哪一个？
2. `readlink`、`lspci`、`ethtool` 和 `tcpdump` 分别能查到哪些信息？
3. `ens64np0`、`0000:03:00.0`、`1924:0b03` 和 `sfc` 分别是什么身份？
4. 主机显示 `Link detected: yes`，这一层证明了什么？本章通过抓包确认了什么？
5. ping 和接收端 pcap 共同证明到哪里？第二部分从哪一层继续？

## 参考答案

1. 每台主机有管理口 `ens33` 和 X2522 数据口（`.1` 是 `ens64np0`，`.2` 是 `ens64np1`）。通过 DAC 接入 Arista 的是各自的 X2522 数据口。
2. `readlink` 沿 sysfs 目录找到 PCIe 设备功能；`lspci` 按 BDF 读设备类别和 PCI ID；`ethtool -i` 看驱动与 `bus-info`，不带 `-i` 看链路；`tcpdump` 在指定接口上观察二层报文并写入 pcap。
3. `ens64np0` 是 Linux 网络接口名；`0000:03:00.0` 是这台主机上的 PCIe 地址（BDF）；`1924:0b03` 是 PCI 厂商与设备编号；`sfc` 是当前接管这块卡的 Linux 驱动。
4. `Link detected: yes` 证明本端物理链路已经协商起来。抓包进一步确认请求到达 `.2` 的 `ens64np1` 数据口。
5. ping 的 `3 received` 加上 pcap 里三条 `.1 → .2` echo request，证明探针到达指定数据口。第二部分从应用层继续：部署 C++ Exchange 与两个独立 Trader，让客户端读取行情，由策略或人工操作发起订单，再核对交易所回执。

## 查阅附录

需要查端口、核对指标或恢复资源配置时，再按下面的附录查阅。

<a id="appendix-flows"></a>

## 附录 A：按箭头查通信细节

图中的 SFC 指网卡由内核 `sfc` 驱动管理的运行配置；DPDK 是用户态收发方案，第六部分会实际切换。按箭头查询时，同时核对服务属于哪台主机。

表内 `.1/.2/.11/.101/.111/.253` 是管理网 `10.1.1.x` 的简称；数据网地址写成完整的 `20.1.1.x`。Windows Server 2019 是浏览器所在的终端，使用现场配置的 IP。

①、④、⑥、⑦ 的 a/b 对应请求与返回；⑤a/⑤b 是两种可选行情发送方式。表里的 JSON 是按字段组织的数据文本；ITCH、OUCH 等交易协议在第二部分展开，这里先看发送者、接收者和目的端口。

| 图中箭头 | 通信双方与协议（源 → 目的） | 什么时候产生、目的是什么 | 接收后发生什么 |
| --- | --- | --- | --- |
| **①a · 切换请求** | `监测 VM（.101）内的网页后台 → .2:48606`；HTTP/TCP | 网页请求切到 DPDK、切回 SFC 或基线时，网页后台调用控制器的 `/mode` | 控制器调用 `.2` 本机脚本，完成该机进程与 X2522 归属切换；该服务也接受状态查询和模拟交易账户重置请求 |
| **①b · 控制结果** | `.2:48606 → 监测 VM（.101）内的网页后台`；同一 HTTP/TCP 连接 | 控制器处理完 ①a 后返回状态或错误 | 网页后台据此向网页反馈切换结果；48606 是后台控制端口，SSH 登录另见 ⑨a |
| **②a · 业务事件** | `.1/.2 交易进程 → .101:46120`；UDP | `.1` 上报重放进度等交易所状态；`.2` 上报客户端状态、订单与成交 JSON | 网页后台接收事件并更新网页事件与状态数据；UDP 是尽力上报，不能把它当作订单交易会话 |
| **③a · LANZ 建连** | `监测 VM（.101）内的 LANZ 采集器 → .253:50001`；TCP | 第七部分启动 LANZ 采集器时，由监测 VM 主动连接交换机 | 建立读取队列事件的连接；`.101` 此端使用系统分配的临时端口 |
| **③b · LANZ 事件** | `.253:50001 → 监测 VM（.101）内的 LANZ 采集器`；③a 建立的 TCP 连接 | 交换机产生 LANZ 队列监测记录时，将记录发送到监测 VM | 采集器解码事件并保存可查询状态；此流量来自交换机，区别于 ②a 的交易事件 |
| **④a · 页面与查询** | `Windows Server 2019 浏览器 → .101:8088 / :3000 / :8089`；HTTP/TCP | 打开交易终端、Grafana 看板，或请求 LANZ 查询接口时产生 | 8088 提供交易网页/API，3000 提供 Grafana，8089 提供 LANZ JSON；8088 页面中的 JavaScript 每 500 ms 请求 8089，再把 JSON 呈现在底栏 |
| **④b · 网页返回** | `.101 对应 HTTP 服务端口 → Windows Server 2019 浏览器`；原 TCP 连接 | 服务响应 ④a 的请求 | 浏览器得到页面、数据或 JSON；屏幕上看到的内容来自后台接口，LANZ 原始队列流仍是 ③b |
| **⑤a · 组播行情** | `20.1.1.1 → 233.74.125.32:31032`；UDP | Exchange 处于组播模式时发送 ITCH/MoldUDP64 行情 | `.2 Trader` 主机上的统一接收器加入该组；第三部分启用 IGMP 侦听后，Arista 根据成员表向 Et2 转发，接收器再在本机分发 |
| **⑤b · 单播行情** | `20.1.1.1 → 20.1.1.2:42121`；UDP | Exchange 处于单播模式时，按接收配置向指定端口发送行情 | `.2 Trader` 主机上的统一接收器用普通套接字（Socket）收包，再经用于本机进程通信的 Unix Socket 向自动（AUTO）和手动（MANUAL）客户端分发 |
| **⑥a · 订单请求** | `20.1.1.2 Trader → 20.1.1.1:43120`；TCP | 策略或人工操作形成订单，客户端通过持久订单会话发送 | Exchange 接收 SoupBinTCP 中的 OUCH 请求并处理订单；网页操作本身是 ④a，不直接成为这条数据面连接 |
| **⑥b · 订单回执** | `20.1.1.1:43120 → 20.1.1.2 Trader`；原 TCP 会话 | Exchange 处理订单后返回相应结果 | Trader 更新订单状态与成交记录；随后可以另走 ②a 上报事件，两条通信的职责不同 |
| **⑦a · 进程命令** | `监测 VM（.101）内的网页后台 → .1:48120 / .2:48121～48125`；TCP | 网页后台需要读取进程状态、控制回放或向相应客户端发出操作命令时 | 目标进程的管理接口读取命令；这里是课程程序的命令协议，不是 HTTP，也不承担 PCI 驱动归属切换 |
| **⑦b · 命令返回** | `.1/.2 对应管理端口 → 监测 VM（.101）内的网页后台`；原 TCP 连接 | 目标进程处理 ⑦a 后返回状态或命令结果 | 网页后台读取返回的 JSON，将结果交给网页或后续控制逻辑 |
| **⑧a · 抓取指标** | `监测 VM（.101）内的 Prometheus → 10.1.1.101:8088/metrics`；HTTP/TCP | Prometheus 按本课配置每 1 秒读取网页后台的 `/metrics` | 网页后台将已汇总的交易状态导出为指标文本，Prometheus 保存为时序数据；两端都在监测 VM 上 |
| **⑧b · 查询指标** | `监测 VM（.101）内的 Grafana → 127.0.0.1:9090`；HTTP/TCP | Grafana 刷新看板，向同机 Prometheus 查询所需时间范围的指标 | Prometheus 返回查询结果，Grafana 再生成看板数据；`127.0.0.1` 是该机回环地址 |
| **⑨a · 登录与分发** | `.111 → .1/.2/.11/.101/.253:22`；SSH/TCP | 运行课程脚本，登录 VM/交换机或向 VM 分发、取回文件时 | SSH 服务执行远端命令；SCP 复用 SSH 传输文件。设备命令输出沿 SSH 连接返回管理机 |

<a id="appendix-trader-ports"></a>

## 附录 B：五个 Trader 管理端口

`.2:48121～48125` 对应独立客户端进程的管理入口。网页后台按“客户端 → 管理端口”的对应关系，把命令交给指定进程。因此，五个端口来自五个进程入口；下单技术本身没有要求必须使用这些端口号。

| 管理地址 / TCP 端口 | 进程或角色 | 接收什么操作 |
| --- | --- | --- |
| `.1:48120` | Exchange | 查询状态，控制回放和行情发送模式 |
| `.2:48121` | AUTO；过滤实验中同一槽位用于 Guardian | 查询客户端状态，普通平台中控制自动策略 |
| `.2:48122` | 普通套接字手动下单客户端 | 接收手动订单、读取状态与测量结果；第六部分使用固定配置客户端 |
| `.2:48123` | OpenOnload 客户端 | 接收选择 OpenOnload 的订单，读取该进程状态与测量结果 |
| `.2:48124` | TCPDirect 客户端 | 接收选择 TCPDirect 的订单，读取该进程状态与测量结果 |
| `.2:48125` | DPDK/F-Stack 客户端 | 在 DPDK 配置下接收订单、读取状态与测量结果 |

这些名字代表后续比较的收发方案，先把它们当作不同客户端的名称。各进程按实验配置启停：SFC 配置中运行普通套接字、OpenOnload、TCPDirect 客户端；切到 DPDK 独占 X2522 时，先停止这三类客户端。AUTO 用于自动交易，Guardian 是过滤实验中检查行情是否完整的客户端角色。

以网页选择 TCPDirect 下单为例，命令会经过三步：

1. 浏览器向 `.101:8088/api/order` 发送 JSON，其中 `transport=TCPDIRECT` 表示所选客户端。
2. 网页后台找到 `.2:48124`，向该进程发送课程内部的 `ORDER|...` 文本命令。
3. TCPDirect 客户端沿 ⑥a，向交易所 `20.1.1.1:43120` 发送 OUCH 订单。

所有下单路径都连接这个交易所目的端口。⑦b 返回客户端的命令处理结果，⑥b 返回交易所的订单处理结果；成交以交易所回执为准。查询状态使用同一管理入口的 `STATE` 命令，结果以 JSON 返回。

<a id="appendix-metrics"></a>

## 附录 C：第四部分指标索引

`/metrics` 是网页后台在 8088 端口提供的指标查询地址。网页后台通过 ② 的事件上报和 ⑦ 的状态查询汇总交易状态；Prometheus 请求 `/metrics` 时，得到的是这份状态对应的指标文本。

[第四部分“给交易系统装仪表”](04-low-latency-software-design.md)会实际使用这些指标。先认读法：RTT 是订单发出到收到结果的往返时间；p50、p99 分别表示按耗时排序后，50%、99% 的样本所处的位置。字段名留作查表，具体怎样测量放在第四部分。

八块看板分别回答以下问题：

| 第四部分面板 | 网页后台导出的指标 | 数值是什么意思 |
| --- | --- | --- |
| 在线组件 | `flle_component_up{component=...}` | Exchange、Trader、网页后台最近是否报告在线（ONLINE）；在线记为 1，面板显示总数 |
| 行情回放进度 | `flle_replay_progress_ratio` | 当前交易时段已回放的比例，范围 0～1，面板显示百分比 |
| 实时行情速率 | `flle_market_messages_total` | 当前模拟交易周期的累计行情消息数；`rate(...[30s])` 按最近 30 秒求每秒速率 |
| AUTO 订单 RTT p99 | `flle_order_rtt_seconds{client="auto",stat="p99"}` | 自动客户端当前轮次的订单往返时间 p99，单位为秒 |
| C++ 订单 RTT 曲线 | `flle_order_rtt_seconds`、`flle_baseline_order_rtt_seconds` | 前者显示 AUTO 的 p50/p99，后者显示 MANUAL 最近一次固定测量批次的 p99 |
| 行情整理（Feed Handler）状态 | `flle_feed_pending_messages`、`flle_feed_gap_messages`、`flle_feed_duplicates` | 等待补齐前序消息的数量、当前缺失数量、重复副本数；同一行情走双路接收时会出现重复副本 |
| 订单与成交速率 | `flle_paper_orders_total`、`flle_paper_fills_total` | 各客户端当前周期的订单、成交累计数；`rate(...[1m])` 按最近 1 分钟求速率 |
| RTT 样本累计 | `flle_order_rtt_samples`、`flle_baseline_order_rtt_samples` | AUTO 当前轮次和 MANUAL 固定测量批次的样本数；用来判断统计值由多少笔订单得出 |

表中的八块面板对应第四部分的[看板配置](../../apps/flle-trading-lab/observability/flle-trading-baseline.json)。`client` 区分客户端，`stat` 区分 p50、p99 和最大值（max）；具体采样和单位换算在第四部分运行 ①～③ 完成。

订单往返时间由 C++ 客户端测量；网页后台把纳秒换算成秒，Prometheus 再定期保存这些统计值。指标查询只是读取已有结果，其 HTTP 耗时不计入订单 RTT。第四部分同时保留逐笔原始样本，用来核对看板上的统计结果。

网页后台还提供拒单数量、排队数量等指标，第五部分会用它们观察程序处理订单的情况。

第四部分还会查询 `up{job="flle-trading"}`：这个指标由 Prometheus 根据抓取结果生成，`up=1` 只说明最近一次抓取成功。它与网页后台导出的 `flle_component_up` 分别回答“能否抓到指标”和“业务组件最近是否在线”。

图中 ⑧ 从左到右是 Grafana、Prometheus、网页后台。⑧b 查询 Prometheus 已保存的数据，⑧a 定期读取网页后台的 `/metrics`；箭头表示请求，结果沿原连接返回。

两段请求独立运行。三者都在 `.101`：Grafana 访问本机 `127.0.0.1:9090`，Prometheus 每 1 秒读取 `10.1.1.101:8088/metrics`。刷新看板时，Grafana 查询的是已有记录。

需要核对指标名称和采集周期时，可查看：[网页后台导出函数](../../apps/flle-trading-lab/flle_trading/gateway.py)、[Prometheus 抓取配置](../../apps/flle-trading-lab/observability/prometheus.yml)、[Grafana 数据源](../../apps/flle-trading-lab/observability/grafana-datasource.yml)。

这里的通信位置和端口来自课程现役程序与配置，作为后续查图索引；各服务是否启用、客户端选择哪种模式，以相应部分的运行配置为准。

<a id="appendix-resources"></a>

## 附录 D：虚拟机资源配置

第零部分讲过，线程准备好以后仍可能等待 CPU。虚拟机还要等待宿主机分配执行资源，所以后续测量前，要先确认这层配置。

ESXi 是运行这些虚拟机的宿主系统，vSphere 是管理界面；文中的 Guest 指虚拟机内部的操作系统。课程快照已包含以下资源设置，正常执行课程时可直接沿用。迁移、克隆、修改虚拟机硬件或开机提示资源不足后，再通过 vSphere 复核。

<div style="border-left:6px solid #7e22ce;background:#f3e8ff;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#7e22ce;color:#fff;font-weight:800;">留作恢复提醒 · ESXi 低延迟基线</span> <span style="font-weight:700;color:#581c87;"><code>.1 Exchange</code> 与 <code>.2 Trader</code> 使用相同资源设置。先看编辑页，再确认虚拟机能正常开机；虚拟机内部的命令不能单独证明宿主机已安排独占资源。</span></div>

<div style="background:#f8fafc;border:1px solid #cbd5e1;border-radius:12px;padding:10px;max-width:820px;margin:14px auto;">
<img src="images/course-visuals/01-diagrams/01-vsphere-cpu-reservation-9200mhz.jpg" alt="vSphere 编辑 .1 Exchange：4 vCPU，CPU Reservation 9200 MHz，Limit Unlimited" style="display:block;width:100%;max-width:800px;height:auto;margin:0 auto;border-radius:8px;background:#fff;">
</div>

vSphere 编辑页显示 CPU 预留量（Reservation）为 `9200 MHz`，限制（Limit）为 `Unlimited`。这里按 4 个虚拟 CPU（vCPU）乘以 2300 MHz 标称基频计算。

<div style="background:#f8fafc;border:1px solid #cbd5e1;border-radius:12px;padding:10px;max-width:820px;margin:14px auto;">
<img src="images/course-visuals/01-diagrams/01-vsphere-latency-sensitivity-high.jpg" alt="vSphere 编辑 .1 Exchange：Latency Sensitivity 为 High，并提示必须 100% CPU 与内存预留" style="display:block;width:100%;max-width:800px;height:auto;margin:0 auto;border-radius:8px;background:#fff;">
</div>

延迟敏感度（Latency Sensitivity）设为 `High`。界面的黄色提示要求完整预留 CPU 和内存资源。

<div style="background:#f8fafc;border:1px solid #cbd5e1;border-radius:12px;padding:10px;max-width:820px;margin:14px auto;">
<img src="images/course-visuals/01-diagrams/01-vsphere-iommu-enabled.png" alt="vSphere 编辑 .1 Exchange：CPU 区 I/O MMU 已勾选 Enabled；Hardware virtualization 与 Performance Counters 保持关闭" style="display:block;width:100%;max-width:800px;height:auto;margin:0 auto;border-radius:8px;background:#fff;">
</div>

CPU 设置中的 `I/O MMU` 设为 `Enabled`，向虚拟机提供设备访问内存的地址转换与隔离功能。它像设备的领料范围：网卡只能访问系统允许的内存区域。`.1 Exchange` 与 `.2 Trader` 使用相同设置。

`Hardware virtualization` 和 `Performance Counters` 是另外两个开关，本课保持关闭。

| vSphere 项 | 本实验值 | 核对要点 |
| --- | --- | --- |
| CPU | `4 vCPU` | 测量期间保持 vCPU 数量稳定 |
| Reservation | `9200 MHz = 4 × 2300 MHz` | 按标称基频乘以 vCPU 数量填写 |
| Limit / Shares | `Unlimited / Normal` | CPU 使用量不设上限 |
| Memory | `16 GB` 且 100% 预留 | 完整预留内存，避免宿主机回收虚拟机内存或把它换出到磁盘 |
| Latency Sensitivity | `High` | 开机提示资源不足时，先解决资源问题再测量 |
| Scheduling Affinity | 留空 | 保持为空，不手工指定宿主机 CPU 列表 |
| I/O MMU | `Enabled` | 这是虚拟机可见的设置，宿主机直通设备的配置另行管理 |
| Hardware virtualization | 关闭 | 与 I/O MMU 分别设置 |

这些设置分别管两层：ESXi 根据 `High` 和资源预留为虚拟 CPU 安排物理执行资源；后续用 `taskset` 命令把线程固定到指定的虚拟 CPU。`I/O MMU` 还需要虚拟机内核配合，第六部分使用时再核验。

测量期间保持资源设置稳定，避免虚拟机迁移和快照任务。若条件发生变化，应在测量记录里写明；后续比较要在一致条件下进行。

## 外部参考资料

| 资料 | 本章用途 |
| --- | --- |
| [systemd.net-naming-scheme(7)](https://www.freedesktop.org/software/systemd/man/latest/systemd.net-naming-scheme.html) | `ens33` / `ens64np0` 这类可预测网卡名怎么拼出来 |
| [sysfs(5)](https://man7.org/linux/man-pages/man5/sysfs.5.html) | `/sys`、`/sys/class/net` 怎样展示设备信息 |
| [readlink(1)](https://man7.org/linux/man-pages/man1/readlink.1.html) | `-f` 沿着符号链接走到真实路径 |
| [lspci(8)](https://man7.org/linux/man-pages/man8/lspci.8.html) | 按 PCI 地址列出设备类别与数字 ID |
| [Linux PCI sysfs](https://docs.kernel.org/PCI/sysfs-pci.html) | PCI 设备功能与 sysfs 目录的对应关系 |
| [Linux ethtool netlink](https://docs.kernel.org/networking/ethtool-netlink.html) | 驱动信息与链路状态查询 |
| [Linux networking scaling](https://docs.kernel.org/networking/scaling.html) | 后续接收队列、RSS 与 CPU 分工的参考 |
| [tcpdump man page](https://www.tcpdump.org/manpages/tcpdump.1.html) | 接收端 pcap 与 BPF 过滤 |
| [Linux NAPI](https://docs.kernel.org/networking/napi.html) | 设备用中断通知主机，再调度 NAPI poll 处理已在内存里的收包事件 |
| [Linux packet socket `packet(7)`](https://man7.org/linux/man-pages/man7/packet.7.html) | 报文套接字如何在二层观察原始报文 |
| [Arista 7150S family paper](https://www.arista.com/assets/data/pdf/Whitepapers/Arista_7150S_Family_WP.pdf) | 交换平台、cut-through 与 PTP 定位 |
| [Configure the Virtual Machine Latency Sensitivity](https://techdocs.broadcom.com/us/en/vmware-cis/vsphere/vsphere/9-0/configure-the-virtual-machine-latency-sensitivity.html) | High 要求 CPU 预留与 100% 内存预留 |
| [Performance Tuning for Latency-Sensitive Workloads](https://www.vmware.com/docs/perf-latency-tuning-vsphere8) | Reservation 通常按基频 × vCPU 填写 |
