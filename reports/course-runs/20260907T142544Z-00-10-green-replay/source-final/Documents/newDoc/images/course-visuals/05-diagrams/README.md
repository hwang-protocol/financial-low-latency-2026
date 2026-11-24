# 第05章课程图片集

> 生成日期：2026-08-23；当前主线重构：2026-08-28
> 生成方式：历史图使用Codex内置`imagegen`；当前主线使用仓库原生SVG
> 使用位置：`Documents/newDoc/05-low-latency-software-design.md`

## 当前正文主线（2026-08-28）

旧 32 张 PNG 全部保留作历史审计。当前第五章正文使用 12 张原生 SVG 加 1 张驾驶舱截图，统一限制 `max-width:800px`：

| 文件 | 教学任务 |
| --- | --- |
| `05-grafana-hot-path-idle.png` | 准备 A：刚装好的交棒计时页；样本 0 是正常空闲 |
| `05-relay-handoff.svg` | 章首接力比喻：管理线程、交接区、下单线程；术语延后出现 |
| `05-deque-cv-handoff.svg` | 运行 ①：deque / mutex / condition_variable 对应储物格、钥匙、喊一声 |
| `05-manual-vs-auto.svg` | 运行 ①：现在两边共用同一套 deque + 钥匙 + 喊一声 |
| `05-auto-watch.svg` | 运行 ①：AUTO 跟着跑是为了看现场有没有自己变；变很多则这一轮不可信 |
| `05-measure-rounds.svg` | 运行 ①：现场热身 1000，每轮预热 40、计入 400 |
| `05-run2-vs-run1.svg` | 运行 ②：跟上一步比，只换 MANUAL 的储物格 |
| `05-fixed-slots.svg` | 运行 ②：上边一截一个框；下边头尾小格加省略号代表 1024 格，写到头转回第 1 格 |
| `05-run3-vs-run2.svg` | 运行 ③：跟上一步比，只改 MANUAL 怎么等棒 |
| `05-run4-vs-run3.svg` | 运行 ④：有的轮只坐 CPU 2，有的轮整个人搬到 CPU 0 |
| `05-course-optimization-map.svg` | 第02～10章现役位置图；全卡同色同宽灰边，颜色只放顶栏/徽章；第11/12章留在历史文档，不进入现役路线 |
| `05-order-phase-contract.svg` | 固定 queue ingress、OUCH send、final E/J 三个 C++ 时间点 |
| `05-sleep-vs-stare.svg` | 运行 ③：睡着叫醒对一直盯着；右边浅橙色标题才是本步要换上的 |

所有当前箭头按 DEC-117：`marker` 为 `20×15`、`refX=1`、`overflow="visible"`；线在目标框前约 16 个单位结束，尖停在框边。普通连接只用直线和正交折线。卡片描边按 DEC-127：全卡 `#94a3b8` / `stroke-width=2`，先填后描，不用彩色外框制造「粗框」错觉。旧 `05-rss-order-cpu.svg` 仍保留审计，但因 `SO_INCOMING_CPU` 在窗口内漂移而退出正文；当前 CPU 图冻结角色，不追逐瞬时 RX CPU。`05-queue-profiles.svg` 退出正文，留盘审计：Array / Head / Tail 三栏读者对不上运行 ② 的格子。`05-cpu-isolation.svg` 退出正文，留盘审计：读者会把「挤」读成 0 和 2 一起用。

## 历史位图的统一视觉与证据合同

```text
16:9 clean white classroom slide; premium flat-isometric/vector technical
illustration; crisp navy outlines; cyan data/action, purple memory/control,
green verified ownership/evidence, orange interpretation/boundary, red only
for a genuine slow/fault/remote branch; large English labels readable from a
classroom screen. No logos, watermarks, fabricated IPs, ports, PIDs, IRQs,
CPU IDs, timestamps, hashes, packet counts, timing values or speed claims.
```

| 文件范围 | 教学任务 | 硬约束 |
| --- | --- | --- |
| `05-01`～`05-04` | 从线缆到处理函数的全章主线、章节路线、优化脊柱与G++工具链证据 | 工具可用性不等于性能结论；每次只解释一个变量 |
| `05-05`～`05-10` | Cold/Hot Path、allocator可变分支、逐消息分配与预分配A/B | 调用次数不等于延迟；预分配不自动等于prefault；两路checksum必须一致 |
| `05-11`～`05-19` | slot所有权、Producer/Consumer、Mutex/Condition、SPSC与release/acquire | `wait()`释放锁且唤醒后重新获取；SPSC严格一产一消；Producer拥有head、Consumer拥有tail；release/acquire不提供MPMC、公平性或满队列策略 |
| `05-20`～`05-26` | RSS两次选择、配置读取、RX queue/IRQ/CPU三层与只读证据链 | `ethtool -x`是配置而非逐包落点；IRQ运行时发现；中断累计次数不等于报文数；脚本不写affinity |
| `05-27`～`05-29` | NUMA局部性、同一短时shell的process affinity变化与证据 | 双NUMA图是通用模型，当前guest只见单node；allowed set变化是位置证据而非速度证据 |
| `05-30`～`05-32` | 公平A/B合同、程序保存/改变/恢复与证据判读顺序 | 相同binary/input/function/checksum；affinity是唯一意图变量；先验正确性再读timing；单轮不是普遍结论 |

## 人工返修与拒收记录

- `05-01`首稿把分支中的SPSC重复绘制，无法准确表达“Mutex或SPSC”二选一，已拒收并重画。
- `05-15`明确补上Condition的完整语义：Consumer在`wait()`时释放mutex，收到notify后必须重新获得mutex才能pop。
- `05-17`首稿错误暗示Producer推进tail，已拒收；最终版固定Producer独占head、Consumer独占tail，并只让Producer观察tail判断full。
- `05-21`首稿生成了标为conceptual的虚构RETA数字与hash key，仍不符合证据纪律，已拒收；最终版只保留无值字段卡，并把整个上层读取链标为configuration plane。
- `05-28`首稿拼错`POSITION`，且没有精确表达修改同一shell；最终版改为同一短时shell上的`taskset -p $$`、`taskset -pc <candidate> $$`、再读一次。
- 内置绘图服务在`05-15`、`05-16`、`05-21`、`05-23`与`05-30`生成期间出现网络失败；均保持同一内置生成渠道重试，没有改用外部图片或脚本占位。
- 所有证据图不伪造IRQ/PID/CPU编号、端口、RUN_ID、时间戳、SHA、报文计数或耗时；可复核值只保留章节确定的`10/10/10/45`、`1/1`、`20`、`100000`与`4999950000`等教学合同。

## 尺寸与投屏层级

32张最终PNG中26张为`1672×941`，6张为`1671×941`；均使用Markdown的`width:100%;height:auto`等比显示，没有拉伸。12张位于投屏主线，20张保留在原有折叠实验/审计层。

历史 32 张 PNG、12 张当前正文 SVG、1 张准备 A 截图、退役 `05-rss-order-cpu.svg`、`05-queue-profiles.svg` 与 `05-cpu-isolation.svg` 共 48/48 固定摘要见同目录 `SHA256SUMS`。
