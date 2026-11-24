# 第一部分教师说明

## 2026-09-14 · 二次复读后的结构小修

接线图另设总览标题，设备角色改为短表；准备节统一先导航，必要定义在卡后。准备A的四行输出明确标为关键行摘录，原脚本与输出原件保持。正文未使用的 `appendix-trader-ports` 锚点已删除，配套端口资料中的同名锚点保留。运行③只解释本步version，运行④保留自己的Port说明。

运行④的主机初始快照读数与EOS活动成员仍分别沿用下方已登记的来源。下次实际重跑运行④时，应从同一个RUN的主机与EOS原件统一更新展示；本轮不重新采集或改写原始记录。

## 2026-09-14 · 顺稿与初始快照示例对齐

本轮依据用户评估适度整理：目标与检查范围前移，删除重复任务表与过渡语，运行⑤后直接总结、理解检查；沪市扩展与流量图移到章末。逐箭头与Trader端口长表移入 [TRAFFIC-REFERENCE.md](TRAFFIC-REFERENCE.md)，保留原编号。虚拟机资源说明仍在章末供恢复时查阅。

运行③、④的主机示例统一按厂商驱动安装前的初始快照理解。同日重读并验证 `20260829T012057Z-01-driver-owner` 的2项SHA和 `20260829T012210Z-01-link-pair` 的5项SHA：两台分别为 `version: 5.15.0-164-generic`、`Port: FIBRE`。运行④正文恢复这份原始Port字段，现行脚本的分段打印只是阅读格式；EOS的VLAN/STP活动成员仍采用下节记录的用户输出。安装厂商驱动后的 `Direct Attach Copper` 只留为版本变化说明，不改历史RUN或声称当前机器已恢复快照。

准备C的 `no ip routing` 移到 `configure terminal` 后，显式在全局模式执行。依据 [Arista IPv4命令说明](https://www.arista.com/en/um-eos/eos-ipv4) 的 Command Mode；旧归档未记录拒绝，不能据此判断旧命令未生效。本轮仅做语法、允许命令列表和顺序检查，未运行配置或设备实验。准备A安装与版本查询保持，正文仅摘工具路径，不再讲解编译器版本。

## 当前 VLAN 与生成树示例

2026-09-10 用户在恢复快照后提供输出：VLAN20 活动成员为 `Cpu, Et1, Et2`；STP只列Et1、Et2，均为designated forwarding。正文准备C与运行④的VLAN示例，以及准备C的STP示例采用这些关键行，替换历史四口在线展示。用户未提供完整接口状态，不能据此断言Et11/12具体关闭原因；show ip interface brief等其他示例未重新采集。下方历史采集索引保留原样，由本条接管对应两类读数。记录 `refs/evidence/chapter01-active-ports-20260910.json`，本轮未连接设备。

本文件保存不影响学生顺序执行的背景与历史核验细节。学生入口：[第一部分](../../01-financial-low-latency-architecture.md)。

## 准备 A 输出来源

正文编译工具输出采用当前脚本自动生成的分段格式；路径和版本读数来自 2026-08-29 的 RUN `20260829T010427Z-01-vm-apt-china-mirror`，原文为 `reports/course-runs/20260829T010427Z-01-vm-apt-china-mirror/raw/result.txt`。2026-09-10 仅调整打印与说明，没有重跑安装。

该历史记录来自恢复快照后的首次安装：`.101` 新装 `g++-11` 与 `make`，`needrestart` 列出延后重启的服务。准备 A 不主动重启服务；按系统检查、离线工具校验及工具路径/版本读数判断是否继续。维护用镜像格式来源：[阿里云 Ubuntu 镜像使用说明](https://developer.aliyun.com/mirror/ubuntu)。

## 准备 B 设备身份输出来源

正文 `show version` 示例来自 2026-08-31 的交换机控制台查询，序列号已脱敏。2026-09-10 仅精简正文提示语，未重新执行设备命令。

## TAP Aggregation 历史核验

以下记录来自 2026-08-31；2026-09-09 仅从正文移入并修顺措辞，没有执行交换机命令。记录中的 Et3 单端口检查曾修改配置并恢复，不属于只读查询；整机独占模式未启用，不能据此声称完整时间戳实验通过。

本课 7150 的另一种官方用途是：**TAP Aggregation**（tap / tool）。[Arista TAP Aggregation](https://www.arista.com/assets/data/pdf/Whitepapers/TAP_Aggregation_Product_Brief-2.pdf)把它写成线速复制、过滤，并带纳秒级报文时间戳。官方 MIB 说明：整机先进入独占复制模式后，普通 bridging / routing 关掉。

> normal switching functions like bridging, routing etc. are disabled.
>
> —— [ARISTA-TAPAGG-MIB](https://www.arista.com/assets/data/docs/MIBS/ARISTA-TAPAGG-MIB.txt)

原文翻译：桥接、路由等常规交换功能会被禁用。这里说的是整机进入 TAP Aggregation 独占模式后的行为。

<div style="border-left:6px solid #7e22ce;background:#f3e8ff;padding:12px 16px;border-radius:8px;margin:14px 0;"><span style="display:inline-block;padding:3px 12px;border-radius:6px;background:#7e22ce;color:#fff;font-weight:800;">仅供展示</span> <span style="font-weight:700;color:#581c87;">先记住这条旁路：主路径继续走；副本进 tap，7150 打时间戳，再从 tool 送给分析机。本章不配。2026-08-31 曾分别做只读状态查询和 Et3 单端口命令检查；完整时间戳链路尚未验证。</span></div>

```mermaid
flowchart LR
  prod["主路径继续走"] --> tap["tap 口<br/>只收副本"]
  tap --> stamp["7150 硬件打点"]
  stamp --> tool["tool 口<br/>只送给分析机"]
  tool --> nic["分析机网卡再打一记"]
```

| 现场核验 | 读数 |
|---|---|
| 单端口命令检查 | 空闲 Et3 上，`switchport mode tap`、`switchport mode tool`、`mac timestamp before-fcs` 都被接受；`show active` 能看到。随后已 `default interface Ethernet3` 交还。RUN `20260831T132443Z` |
| 未验证的部分 | 只有 Et1 / Et2 / Et11 / Et12 有线；`.11` 没有 PHC。整机 `tap aggregation mode exclusive` 本轮没开，开了会关二层 |
| 只读对照 | `20260831T131936Z`：`Tap-aggregation is not enabled`，没有 monitor session |

准备 C 仍然只建 VLAN20。不要在 Et1 / Et2 上写 `switchport mode tap` 或 `switchport mode tool`，也不要开整机 tapagg。


## 输出示例采集索引

2026-09-10 将正文输出提示中的采集信息集中保留于此。正文只引导命令和字段阅读；脚本、示例读数与原始证据文件不变，没有重新执行实验。以下为迁出前的来源说明：

- <code>.101</code> 的编译工具检查示例，读数采集于 2026-08-29。

- 安装工具日志落在 `raw/bootstrap-tool.txt`，EOS 只读复验结果落在 `raw/eos.txt`。下面是 2026-08-25 实测关键行（RUN `20260825T100809Z-01-eos-key-bootstrap`），展示时截断公钥内容。

- 三条原生命令来自 RUN `20260829T010922Z-01-switch-course-baseline`：VLAN 与地址在 `raw/eos.txt`，STP 在 `raw/eos-stp.txt`。每条命令只看后面那几行重点输出。

- 四条原生命令来自 RUN `20260829T011305Z-01-plane-map`，完整原文在 `raw/planes.txt`。每条命令只看后面那一行地址。

- 每台主机三段：sysfs 设备路径、MAC、`lspci` 行。下面是 2026-08-26 实测输出（RUN `20260826T005203Z-01-pci-identity`），`.2` 段结构相同，只有 MAC 末字节不同。

- 摘录 RUN `20260826T011956Z-01-driver-owner` 中 `.1` 的 8 行关键输出；完整输出与 `.2` 的记录保存在该次 RUN 目录。

- 主机 `ethtool` 与三条 EOS 命令来自 RUN `20260829T012210Z-01-link-pair`。`ethtool` 完整能力表在 `raw/host-links.txt`，交换机原文在 `raw/arista-terminal.txt`。每条命令只看后面那几行重点。

- 三条原生命令来自 RUN `20260829T013035Z-01-packet-proof`：发送端在 `raw/sender.txt`，抓包在 `raw/capture.txt`，回读在 `raw/receiver.txt`。时间戳与 ICMP id 每次会变。每条命令只看后面那几行重点。

## 学生正文移出的运行记录说明

2026-09-10，用户要求通读第一部分，移除采集日期、RUN、日志去向和其他无关维护说明。下列信息从正文移出保存；学生正文不增加跳转。八个Bash入口保持原文，日志生成、原件保存与SHA校验仍由脚本完成。本轮未执行设备操作。

运行⑤展示命令中的原目录 `/var/tmp/20260829T013035Z-01-packet-proof/` 简写为 `…/`；这是展示层的路径省略，不能作为新的实机原文。pcap三条报文、ping统计及所有其他text读数保持。

迁出内容：

- 本章确认接口、设备、驱动、链路和三条探针。输出样例保留采集日期与运行编号（RUN_ID）；本次执行会生成自己的编号，并保存对应文件。ping 与抓包确认网络探针到达，交易程序的收发从第二部分继续。

- 四台系统检查与 <code>.101</code> 工具校验通过后，进入准备 B；失败先查本次日志 <code>raw/result.txt</code>。

- 在【跳板机 .111】以 root 运行；读取仓库外 root-only EOS 凭据（`/root/.config/flle/eos_admin_password`，`0600`），凭据缺失时在交互终端提示输入一次密码；只改 running-config；预期完成后公钥登录可用并打印账户状态。

- Python 只负责 SSH 交互和证据保存。公钥尚未可用时，EOS 实际执行下面的命令；若公钥登录已经成功，工具直接返回 `PASS_EOS_PUBLIC_KEY_ALREADY_READY`，不重复配置。

- 在【跳板机 .111】以 root 运行；远端全部只读，不改网络配置；预期依次打印 `.1/.2` 的管理口与 X2522 数据口地址，并保存原始输出。

- 轮询超时会保留最后一次原始状态并以非零退出停止。本卡只进入 running-config，startup-config 保持原样。

- | [Arista TAP Aggregation](https://www.arista.com/assets/data/pdf/Whitepapers/TAP_Aggregation_Product_Brief-2.pdf) | tap / tool 复制与纳秒级时间戳 |

- | [ARISTA-TAPAGG-MIB](https://www.arista.com/assets/data/docs/MIBS/ARISTA-TAPAGG-MIB.txt) | 整机 tapagg 为独占模式，关闭普通 bridging / routing |

- | [Timestamping on the 7150 Series](https://arista.my.site.com/AristaCommunity/s/article/timestamping-on-the-7150-series) | 入向记时、出向写入；也可打在生产交换机的镜像副本上 |

## VLAN 配置成员与活动端口

2026-09-10 补充：准备C明确对Ethernet11/12执行switchport access vlan 20；VLAN归属不以链路up为前提。Arista官方VLAN命令说明的show vlan条目规定默认只显示active ports，configured-ports显示所有配置成员；旧EOS 4.15.4F手册也有该参数。正文补充查询方式，没有新增自动执行任务或生成预测现场输出。具体Et11/12链路状态仍需接口status读数，不能从用户提供的VLAN/STP两段推断未配置、disabled或未初始化。原脚本的转发检查保持。

来源：https://www.arista.com/en/um-eos/eos-virtual-lans-vlans （show vlan）；https://www.arista.com/assets/data/docs/Manuals/EOS-4.15.4F-Manual.pdf 。本轮仅核对仓库脚本与官方文档，未执行交换机命令。

## 运行②输出说明与解释顺序

2026-09-10，DEC-425：按用户要求，把sysfs/readlink/lspci详细解释移到实际执行卡与输出之后；执行前只保留查询目标。正文内嵌Bash的printf自动打印主机/阶段及设备位置、MAC、设备类型与编号三段对/证说明，原查询命令不变。示例沿用原设备路径/MAC/lspci读数，仅更新自动打印格式。提取真实打印代码做五场景本地模拟，确认两台主机格式与三种命令失败；未实机运行。收据 `refs/evidence/pci-output-flow-20260910.json`。

同轮追加：按用户反馈拆分0200设备类别、1924厂商ID、0b03设备ID，实际printf与示例保持一致。上游 [pciutils PCI ID 数据库](https://raw.githubusercontent.com/pciutils/pciids/master/pci.ids) 将1924:0b03列为SFC9250控制器，其下包含多种板卡，故正文区分控制器名称与X2522产品型号。紫卡补cat并只讲命令用途；撤重复字段表和重复核对读数。最新收据为21表HTML、74卡、五场景本地模拟通过，无实机执行。

## 运行③自动输出说明

2026-09-10：仅调整运行③内嵌Bash的printf，输出按主机、任务说明、命令、结果分段。正文示例沿用已有driver/version/firmware-version/bus-info读数，明确只展示关键字段；未新采现场数据。两主机本地打印模拟核对格式，查询命令及错误处理保持；收据 `refs/evidence/driver-output-flow-20260910.json`。

运行③紫卡按用户要求压成一句，说明Solarflare Communications、sfc驱动名及sysfs目录名的对应。厂商与驱动关系核对 [Linux sfc 源码](https://github.com/torvalds/linux/blob/master/drivers/net/ethernet/sfc/rx_common.h)；此处说明驱动简称，不将sysfs目录描述为驱动代码存储位置。代码与输出保持。

## 运行④⑤输出格式统一

2026-09-10，DEC-426：正文和内嵌脚本同步分段说明。运行④原始ethtool分主机保存为raw/host-<IP>.txt，课堂仅展示Speed/Duplex/Port/Link detected；EOS查询计划不变，三条show仍单次连接，原文保存后逐段插入说明。运行⑤打印启动抓包、发送ping、查看捕获统计、回读pcap四阶段，两卡另存classroom.txt。原示例读数沿用既有记录，不增加采样。

本地八场景采用已有示例读数作fixture：验证正常输出、空过滤、SSH/EOS/ping/capture/read失败的诊断和退出码；原文保存、课堂摘录顺序与SHA清单通过。其结果只验证编排和展示，不证明当前设备状态或实机抓包成功。收据 `refs/evidence/later-output-flow-20260910.json`。
