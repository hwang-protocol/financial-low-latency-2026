# 第01章课程图片集

## 2026-09-07 · DEC-377 全课顺稿配图

本轮新增下列原生 SVG，图标表示角色，保留旧图文件作历史审计。正文入口以本表为准；旧日期条目记录当时状态。

| 当前图 | 回答什么 | 替换的正文图 |
| --- | --- | --- |
| `01-packet-and-evidence.svg` | DMA 字节路径、中断通知、抓包副本与 ICMP 回应 | `运行⑤原 Mermaid`（已退出正文） |

依据为本章现役正文与配套实现；不包含新增运行读数或硬件实测。使用自绘文件、包裹、时钟、芯片、内存、队列等矢量图标。箭头遵硬规则 §3.3.3：本组固定 12×12 用户坐标头部、refX=0、2.5 线宽、butt 线帽，尖端与目标框至少间隔 12；无箭头的比较图不强加方向。800px 与 1200px 已逐张检查，修复缺字和标题越界。


> 生成日期：2026-08-22；正文选图复核：2026-08-25
> 生成方式：Codex内置`imagegen`；用途分类`scientific-educational`
> 使用位置：`Documents/newDoc/01-financial-low-latency-architecture.md`

## 统一视觉与证据合同

```text
16:9 clean white classroom slide; premium flat-isometric technical illustration;
crisp vector-like edges; restrained depth; deep navy outlines; recognizable servers,
NICs, switch ports, terminals and evidence files; cyan data/collection; orange order
or sender action; purple ownership/control; green evidence; large English labels.
No logos, watermark, unverified measurements, fake command output, counters or hashes.
Exact arrow direction, host ownership, management/data separation and evidence boundary.
```

本目录保留原20张PNG作审计，并存放当前章首拓扑`01-physical-topology-host-owned.svg`。第01章当前正文的流程、关系、分支和证据链使用Mermaid，另保留DAC实体照片。

当前6张Mermaid统一为“块内LR、块间TB”：每个阶段横向阅读，阶段之间纵向推进；跨块连线连接subgraph，防止块内方向被外部节点连线破坏。拓扑不套用流程分块，接口必须保留在所属VM内。

| 文件范围 | 教学任务 | 硬约束 |
| --- | --- | --- |
| `01-01` | 行情到订单的业务链 | Feed与Gateway分离；风控不可绕过；三色方向固定 |
| `01-02`～`01-03` | 端到端路径与章节路线 | 两个BDF各属于本机；八步不重排 |
| `01-04`～`01-08` | 三项准备与接口映射 | 管理/数据面分离；远端只读；SHA最后生成 |
| `01-09`～`01-14` | PCI身份与Driver owner | MAC不能单独证明硬件；sysfs与ethtool独立交叉 |
| `01-15`～`01-17` | 链路分层与两端对齐 | admin/carrier/address/neighbor/packet各自取证 |
| `01-18`～`01-20` | pcap边界与三包取证 | NIC在主机内存外；DMA到RAM；先抓后发；不伪造输出 |

## 人工返修记录

- `01-01`移除生成器添加的错误回环，并修正Order Book→Publisher方向。
- `01-02`把Trader侧无依据的`0000:04:00.0`改回实测本机BDF `0000:03:00.0`。
- `01-03`、`01-10`移除虚构BDF与示例MAC。
- `01-14`重画为每个host/netdev都执行sysfs与`ethtool -i`两路。
- `01-15`移除示例IP、MAC与提前出现的PASS标记。
- `01-18`把DMA起点从wire纠正为NIC，终点为主机RAM packet buffer。
- `01-20`清空生成器虚构的终端报文与时间戳。
- 内置服务出现5次网络失败；均使用内置服务重试，没有切换到需要API key的CLI。
- 同轮正文撤下`01-07`、NIC背板照片与`01-15`：分别与章首拓扑重复、无法展示课程要辨认的端口、与近邻五层状态表重复。资产本身未删除。
- 2026-08-25曾短暂尝试5张原生SVG替代图，但投屏复核仍发现线宽、箭头比例、文字压线和越框；临时SVG已删除，正文最终使用Mermaid。

原20张PNG均保留；当前正文引用本目录1张拓扑SVG，以及三张 vSphere 截图：`01-vsphere-cpu-reservation-9200mhz.jpg`、`01-vsphere-latency-sensitivity-high.jpg`（均为 `1024×824` JPEG），以及 2026-08-31 用户提供的 `01-vsphere-iommu-enabled.png`（`1274×868` PNG）。24项摘要见同目录`SHA256SUMS`，DAC照片位于上级课程图片目录。

2026-08-29：把 `.1` 编辑页截图纳入正文，Reservation 从误写的 `4×2350=9400` 更正为现场可保存的 `4×2300=9200`；High Latency Sensitivity 截图同步证明 100% CPU/内存预留门闸。
2026-08-31：按 DEC-20260831-143 把同一页 CPU 区的 `I/O MMU → Enabled` 截图纳入正文，与预留、High 并列。表里旧行「Guest vIOMMU / Nested virtualization 均关闭」作废。`Hardware virtualization` 保持关闭，不与 I/O MMU 混为一谈。
