# 第02章课程图片集

## 2026-09-07 · DEC-377 全课顺稿配图

本轮新增下列原生 SVG，图标表示角色，保留旧图文件作历史审计。正文入口以本表为准；旧日期条目记录当时状态。

| 当前图 | 回答什么 | 替换的正文图 |
| --- | --- | --- |
| `02-build-start-trade.svg` | 运行①构建启动，运行②首笔交易 | `02-snapshot-restore-flow.svg`（已退出正文） |

依据为本章现役正文与配套实现；不包含新增运行读数或硬件实测。使用自绘文件、包裹、时钟、芯片、内存、队列等矢量图标。箭头遵硬规则 §3.3.3：本组固定 12×12 用户坐标头部、refX=0、2.5 线宽、butt 线帽，尖端与目标框至少间隔 12；无箭头的比较图不强加方向。800px 与 1200px 已逐张检查，修复缺字和标题越界。


> 生成日期：2026-08-23  
> 生成方式：Codex内置`imagegen`，用途分类`scientific-educational`  
> 当前定位：第02章图片目录；正文使用2张交易系统SVG，原3张wire教学SVG与25张PNG全部保留作审计

## 2026-08-28交易系统基线重写

第02章不再以自定义`wire-v1`和五个本机语义实验作为主线，改为从持久管理机恢复普通Linux交易系统，并完成一笔确定性纸面IOC。新增两张可编辑SVG：

| 文件 | 当前职责 | 画布 |
| --- | --- | --- |
| `02-trading-lab-runtime.svg` | 分开`.1/.2` C++热路径、`.101` Python观察路径与管理机持久真源 | `1200×720` |
| `02-snapshot-restore-flow.svg` | 从第一章环境交接，经预检/构建/部署/验签到首笔交易 | `1200×560` |
| `02-ui-replay-book-order.png` | 干净快照网页：回放、盘口与手工下单 | `3192×1456` |
| `02-ui-trend-latency.png` | 干净快照网页：价格走势、延时基线与策略开关 | `3202×866` |
| `02-ui-blotter-path.png` | 干净快照网页：统一交易记录与系统路径 | `3186×1140` |
| `02-ui-first-trade-receipt.png` | 干净快照运行 ②：网页手动订单回执，与 `raw/first-trade.txt` 同一笔 | `782×222` |

正文统一限制`max-width:800px`。两张图都只解释架构与恢复关系，不填性能数字；现行交易协议和成交证据来自真实应用与RUN。原`02-order-book-l1-l2.svg`、`02-price-time-priority.svg`和`02-wire-v1-byte-layout.svg`暂不删除，继续保留此前冻结章的视觉审计历史。

同日返修`02-trading-lab-runtime.svg`的四组箭头：marker改用`userSpaceOnUse`固定尺寸，不再随热路径粗线成倍放大；第一次收小后按投屏反馈放大到主箭头`28×24`、旁路箭头`26×22`，两条热路径仍保持较细的4画布单位。灰色旁路线改为圆角折线，箭头前竖直末段加长到40画布单位，使转折和方向可以同时看清。路径职责与文字内容没有变化。

同日按实机进程边界再次收口两图：`.2 Trader`不再画成同时承载手动与自动的单进程，而是明确为`AUTO/MANUAL`两个C++客户进程、两份Feed状态与两条SoupBinTCP/OUCH会话；首笔交易流程改为历史行情持续回放时并行提交IOC，不再画“暂停历史行情”。

## 2026-08-27正文重审

第02章已经按第01章的最新载体规则收敛：普通流程、状态、分支和证据链改用Mermaid；订单簿、Price-Time队列和52-byte精确偏移改用仓库原生SVG。25张PNG全部保留在本目录作生成历史与语义审计，不因正文撤下而删除。

原`02-02-price-time-priority.png`的业务关系正确，但16:9位图在正文中占幅过大；当前入口改为本目录更紧凑的`02-price-time-priority.svg`，继续保持`S1 100 + S2 50 = B1 150`与剩余`S2 150`。其余PNG或与正文重复，或把内存实验画成真实网络路径，或存在超出代码证据的状态结论，因此不再作为当前教学入口。

## 统一视觉与证据合同

```text
16:9 clean white classroom slide; premium flat-isometric technical illustration;
crisp vector-like edges; restrained depth; deep navy outlines; cyan normal data,
orange mutation or warning, purple identity or state, green pass/evidence;
large English labels readable from a classroom screen.
No logos, watermark, fabricated commands, filenames, hashes, IDs, output values,
field widths or business data. Exact state ownership, arrow direction, byte offsets,
parser order, sequence update rule and idempotency boundary.
```

| 文件范围 | 教学任务 | 硬约束 |
| --- | --- | --- |
| `02-01`～`02-04` | 订单簿、撮合、订单状态与交易前风控 | Best Bid/Ask与Spread使用正文样例；ACK不等于Fill；Cancel竞态保留三种结果 |
| `02-05`～`02-08` | bytes到业务动作与本章五步路线 | 先门禁再Body；sequence与correlation职责分开；不填虚构实验值 |
| `02-09`～`02-11` | session、sequence、correlation身份分类与取证 | 先排除旧session；当前session内再查重；远端证据图不伪造命令 |
| `02-12`～`02-16` | 大端法、52-byte布局与round-trip | Header 32 bytes、Body 20 bytes；offset 0～51逐格服从字段合同 |
| `02-17`～`02-19` | fail-closed门禁、单变量坏包与证据链 | size→magic→version→length顺序固定；Body只在全部通过后解析 |
| `02-20`～`02-22` | duplicate、gap、late状态机与证据 | 固定输入`0,1,2,2,4,3`；未见序号写入`seen`；`max_seen`只取最大值 |
| `02-23`～`02-25` | 订单请求幂等、缓存决策与证据 | `correlation`只做trace；作用域内的`client_order_id`承担幂等职责 |

## 人工返修记录

- `02-03`重画为“正常生命周期 + Cancel竞态三种结果”双面板，删除重复终态和含混交叉箭头。
- `02-05`把生成器误写的标的修正为`AAPL`，并移除与协议无关的企业Logo。
- `02-08`清除生成器添加的随机ID、字段尺寸、订单值与结果值，只保留五站教学路线。
- `02-11`清除虚构的SSH、目录与Python命令，保留取证阶段和三类分类名称。
- `02-13`按字段表重画精确offset，不接受生成器自行分配字段宽度。
- `02-18`删除虚构hex和长度值，重画为四道门禁与三个单变量mutation。
- `02-19`清除虚构文件树和证据文件名，只保留拒绝原因分类与证据阶段。
- `02-21`按真实Python实现纠正状态更新：LATE和GAP也写入`seen`，GAP推进`max_seen`，LATE不降低`max_seen`。
- `02-trading-lab-runtime.svg`把随线宽失控的大箭头改为固定中等尺寸，并给旁路折线留下可见的圆角转折与末段。
- 2026-08-29按四机恢复合同把两张现役SVG中的持久管理机纠正为`.111 / 10.1.1.111`，并明确`.101`工具链由第一章在fresh快照后重新物化。
- 2026-08-29重画`02-trading-lab-runtime.svg`：补上`.111 → .101 构建 → 分发到 .1/.2`；网页看盘与手工单都接到`.2` client；`.1` 的 History/Market/Paper/Execution 改成框内四枚短标签；底部说明条改为浅底深字，避免全局 `text{fill}` 把白字盖成看不见。
- 2026-08-29两张现役SVG的箭头改为`refX`落在三角根部，尖端沿线方向往前伸，避免尖端与线尾平齐、看起来像平头。
- 内置服务出现1次网络失败；使用同一内置服务重试，没有切换到需要API key的CLI。

25张PNG均为`1672×941`并继续保留；本目录5张SVG与25张PNG的30项固定摘要见同目录`SHA256SUMS`。旧“13张主线、12张折叠层”只描述2026-08-23生成时的版式；当前正文没有折叠层，也不再引用本目录PNG。
