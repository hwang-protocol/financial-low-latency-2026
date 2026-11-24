# 第00章课程图片集

## 2026-09-07 · DEC-377 全课顺稿配图

本轮新增下列原生 SVG，图标表示角色，保留旧图文件作历史审计。正文入口以本表为准；旧日期条目记录当时状态。

| 当前图 | 回答什么 | 替换的正文图 |
| --- | --- | --- |
| `00-memory-workbench.svg` | CPU、缓存与主内存的取数关系 | `00-02-memory-hierarchy.png`（已退出正文） |

依据为本章现役正文与配套实现；不包含新增运行读数或硬件实测。使用自绘文件、包裹、时钟、芯片、内存、队列等矢量图标。箭头遵硬规则 §3.3.3：本组固定 12×12 用户坐标头部、refX=0、2.5 线宽、butt 线帽，尖端与目标框至少间隔 12；无箭头的比较图不强加方向。800px 与 1200px 已逐张检查，修复缺字和标题越界。


> 生成日期：2026-08-22；技术修订：2026-08-25
> 生成方式：Codex内置`imagegen`，用途分类`scientific-educational`  
> 使用位置：`Documents/newDoc/00-cpu-cache-memory-os-basics.md`  
> 边界：图片用于解释角色、路径、分支和证据归属；实际数值、命令结果与结论仍以正文原始输出为准。

## 统一Prompt合同

```text
Use case: scientific-educational
Asset type: 16:9 classroom diagram for a Chinese financial low-latency engineering course
Style: clean white classroom slide; premium flat-isometric technical illustration;
crisp vector-like edges; restrained 3D depth; recognizable hardware, terminals,
memory pages and evidence files; deep navy outlines; cyan normal/data path;
orange handoff or DMA; red interrupt/fault; purple memory/control; green PASS/recovery;
large readable English labels; generous whitespace.
Constraints: exact arrow direction and ownership boundary; no logos; no watermark;
no unverified performance numbers; no fake counters or hashes; no direct NIC-to-app leap.
```

每张图在统一合同上追加下列主题和精确约束：

| 文件 | Prompt主题 | 必须保持的逻辑 |
| --- | --- | --- |
| `00-01-kernel-boundary.png` | Application、System Call、Kernel、Hardware四层 | 应用不能直接连接硬件；请求向下、结果向上 |
| `00-02-memory-hierarchy.png` | Registers→L1→L2→L3/LLC→RAM→可选Disk慢路径 | 层级表示距离，不暗示每次访问逐层串行 |
| `00-03-tlb-translation.png` | TLB HIT/MISS、Page Table与Page Fault分支 | HIT绕过页表；只有Page Not Ready进入Fault |
| `00-04-chapter-roadmap.png` | CPU/Cache→Locality→Page/TLB→Scheduler→IRQ/NAPI→Hot Path | 恰好六站，顺序固定 |
| `00-05-cache-hierarchy.png` | L1i/L1d、L2、共享L3/LLC与RAM剖面 | L1i和L1d分离后汇入L2；不虚构容量 |
| `00-06-cache-observation-flow.png` | lscpu、Page Size、Cache sysfs和只读边界 | 只观察层级，不生成性能结论 |
| `00-07-cache-evidence-pipeline.png` | Jump Host→SSH→.101→raw result→SHA | RUN目录属于跳板机；SHA最后生成 |
| `00-08-locality-patterns.png` | Compact与Scattered字段布局对照 | 两侧字段相同；分别占1条与4条Line |
| `00-09-cache-line-model.png` | Offset÷64→Unique Line IDs→Count | `0/8/16/24`得到1条，`0/64/128/192`得到4条；模型不是计时 |
| `00-10-cache-line-evidence.png` | .101 Python模型与结果证据链 | 不在图中填充虚构结果或SHA |
| `00-11-virtual-memory-page-fault.png` | Virtual Address→Page Table→Physical Page→CPU Cache | Not Ready才进入Kernel Page Fault，随后安装映射 |
| `00-12-page-touch-experiment.png` | page_size→before→allocate→每页1 byte→after→delta | before/after显示窗留空，不冒充实测值 |
| `00-13-page-fault-evidence.png` | .101 Python进程内bytearray与page touch取证 | bytearray、触碰和delta都属于远端进程 |
| `00-14-scheduler-core-selection.png` | Runnable、Scheduler、Running CPU与Blocked状态 | 只有Running线程才转入Blocked；Ready后回Runnable，再经Scheduler选择 |
| `00-15-scheduler-observation.png` | PSR、Allowed CPU Set、Context Switches | 三类字段分开解释；不修改Affinity |
| `00-16-scheduler-evidence.png` | 三类调度字段的远端取证链 | 三分支到raw result才汇合，SHA最后生成 |
| `00-17-nic-interrupt-napi.png` | NIC→CPU→Kernel IRQ→softirq/NAPI→Socket→App | 不暗示每包一次中断，不允许NIC直连App |
| `00-18-interrupt-counter-reading.png` | `/proc/interrupts`与`/proc/softirqs`读表 | 先认CPU列再找行；不填虚构counter |
| `00-19-interrupt-evidence.png` | 两份proc输出的远端采集和验签 | 两来源独立读取，进入raw后再SHA |
| `00-20-os-hot-path-summary.png` | NIC、主机RX descriptors、DMA/RAM、CPU内IRQ/NAPI、Cache与App | NIC读descriptor后直接DMA写buffer；IRQ独立通知CPU；NAPI是CPU内的软件阶段；步骤可重叠 |

## 生成后人工校正

- `00-05`首稿把`AAPL DATA`拼错，最终版定点修复。
- `00-07`首稿把大小写敏感的`lscpu`画成`Lscpu`；最终图改用不冒充命令的`CPU INFO`，精确命令留在正文。
- `00-11`首稿加入人物和多余图例，最终版重画为纯设备与映射路径。
- `00-12`首稿在before/after表盘填了`000000`，最终版清空显示窗，避免被误认作实测值。
- `00-20`首稿把RX queue画进NIC并写出不严谨的RAM边界；最终版重画为主机内存中的RX descriptors与packet buffer，明确DMA数据路径和IRQ/NAPI控制路径。
- `00-14`在2026-08-25复核时发现红色箭头把Runnable直接连到Blocked；终稿改成`Runnable → Scheduler → Running → Blocked/Sleeping → Runnable`状态环。
- `00-20`在2026-08-25复核时仍把DMA写入画成经过descriptor，并把NAPI画成独立硬件；终稿拆成NIC读descriptor、NIC直接DMA写buffer、IRQ独立通知、CPU内NAPI与应用解析五个阶段。
- 生成过程中内置服务有两次网络失败；未切换到需要API key的CLI，失败请求未作为最终资产。

20张最终PNG均为`1672×941`，完整摘要见同目录`SHA256SUMS`。

## 当前正文选图（2026-08-25深审）

第00章当前引用七张：`00-01`内核边界、`00-02`存储层级、`00-08`局部性、`00-03`地址翻译、`00-14`调度、`00-17`收包通知顺序、`00-20`结案全景。每节一张，职责不重复。

`00-20`与`00-17`的分工必须在近邻caption中写清：`00-17`讲**常见中断驱动路径的通知顺序**（IRQ → softirq/NAPI → Socket → App Thread），`00-20`讲**对象与数据落点**（NIC读RX Descriptor、DMA直接写RAM中的Packet Buffer、CPU经Cache读取），并同时展示独立的通知路径。`00-20`不覆盖TLB与Scheduler，因此只放在第6节“一页结案”，由同节四类等待点表补齐这两项；不得把它当成全章路线图，章首认知路线仍由可审计的Mermaid承担。

本轮只替换`00-14`与`00-20`两张存在语义错误的图片；其余18张图片字节不变，终稿摘要同步到`SHA256SUMS`。
