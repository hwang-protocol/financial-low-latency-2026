# 原第 04 章监控图片归档

2026-09-12：本目录顶层保存退役监控章图片，同目录 `SHA256SUMS` 只核对这一批图片。下文保留原说明，其中“当前”均指归档前的监控章。

软件章的 39 张旧图另存于 [software-history/](software-history/README.md)，使用独立的 [SHA256SUMS](software-history/SHA256SUMS)。两批图片存在同名但不同内容的文件，因此分目录保留。

## 2026-09-07 · DEC-377 全课顺稿配图

本轮新增下列原生 SVG，图标表示角色，保留旧图文件作历史审计。正文入口以本表为准；旧日期条目记录当时状态。

| 当前图 | 回答什么 | 替换的正文图 |
| --- | --- | --- |
| `04-stopwatch-and-samples.svg` | 同笔订单计时起止点与预热/统计分界 | `04-order-rtt-contract.svg`（已退出正文） |

依据为本章现役正文与配套实现；不包含新增运行读数或硬件实测。使用自绘文件、包裹、时钟、芯片、内存、队列等矢量图标。箭头遵硬规则 §3.3.3：本组固定 12×12 用户坐标头部、refX=0、2.5 线宽、butt 线帽，尖端与目标框至少间隔 12；无箭头的比较图不强加方向。800px 与 1200px 已逐张检查，修复缺字和标题越界。


> 生成日期：2026-08-23  
> 生成方式：Codex内置`imagegen`，用途分类`scientific-educational`  
> 使用位置：`Documents/newDoc/04-tail-latency-and-observability.md`

## 统一视觉与证据合同

```text
16:9 clean white classroom slide; premium flat-isometric technical illustration;
crisp navy outlines; cyan data/action, purple statistics/control, green retained
evidence, orange interpretation, red only for fault or evidence boundary;
large English labels readable from a classroom screen.
No logos, watermarks, fabricated commands, ports, timestamps, RUN_ID values,
hashes, metric values or dashboard plots. Measurement interval, clock domain,
sample eligibility, nearest-rank, cumulative bucket, scrape direction, timeline
correlation and dashboard-source boundaries must match the chapter exactly.
```

| 文件范围 | 教学任务 | 硬约束 |
| --- | --- | --- |
| `04-01`～`04-03` | 全章证据链、学习路线与观测主脊柱 | Raw sample、metrics、logs与dashboard分层；Grafana不充当事实源 |
| `04-04`～`04-07` | 延迟区间、时钟域、单调时钟测量与实验1证据 | 精确区分`t1−t0`、`t2−t0`、`t3−t2`；跨机monotonic不可直接相减 |
| `04-08`～`04-14` | 100条raw、10/90资格、nearest-rank与实验2/3证据 | Raw全部保留；仅90条eligible进入摘要；sequence 9/10边界不发生off-by-one |
| `04-15`～`04-17` | 相同mean、不同Tail与实验4证据 | steady与spiky总和均为10000；mean均为100；spiky的p99/max为1080 |
| `04-18`～`04-22` | 观测服务准备、累计Histogram、Metrics/Logs职责与实验5 | started不等于ready；`100−98=2`只由累计桶得到；合同校验不等于抓取成功 |
| `04-23`～`04-25` | Prometheus主动scrape、`up`边界与实验6三态 | 请求方向为Prometheus→Target；`up`只描述最近scrape；实测序列为`1→0→1` |
| `04-26`～`04-27` | 同RUN_ID事件时间线与实验7证据 | normal→fault→recovered可检索、可关联；相关性不自动证明因果 |
| `04-28`～`04-29` | Grafana panel来源映射与实验8证据 | health只证明服务响应；type/uid/expr说明查询来源；视图不证明底层数据真实 |

## 人工返修与拒收记录

- `04-01`～`04-03`首轮草图出现产品标志，且路线图状态顺序不够准确；最终版改用无品牌的文本服务节点，并按本章真实实验顺序重画。
- `04-04`逐项核对三段区间，只保留`t1−t0`、`t2−t0`与`t3−t2`，没有把内部耗时与订单往返耗时混成一条线。
- `04-08`～`04-14`逐图核对100条全保留、10条warmup、90条eligible、nearest-rank位置与sequence 9/10边界，避免“排除即删除”和off-by-one误解。
- `04-15`保留章节给出的精确构造值；其他统计图不生成随机延迟数、伪终端输出或伪性能结论。
- `04-19`用嵌套容器表现累计桶，明确`≤1 ms`的98次包含在`+Inf`的100次中；图上同时保留“没有raw和事件顺序”的边界。
- `04-23`拒收了把抓取箭头画成Target→Prometheus的初稿；最终版明确Prometheus主动向Target发起scrape。
- `04-two-read-paths.svg` 复核时发现首版只画回执方向，右侧说明框又带无归属箭头，容易把请求者看反。最终版明确画成 helper / Gateway 请求向 `.2`、JSON 回执反向返回，并把 Prometheus `scrape` 画成向 Gateway 发起。
- `04-26`拒收了自动生成具体RUN_ID值的初稿；最终版仅用无具体值的符号标签`RUN_ID`，没有伪造运行证据或时间戳。
- `04-20`～`04-29`全部移除产品Logo、伪图表、伪端口、伪查询与伪输出；Prometheus、Loki、Grafana均只以普通文本节点出现。
- 所有证据图都把raw目录与SHA清单画成审计阶段，不在图片里虚构摘要值；真实输出仍由正文中的RUN证据承担。

## 尺寸与投屏层级

当前正文使用四张可维护 SVG，外加一张驾驶舱截图：

| 文件 | 当前教学任务 |
| --- | --- |
| `04-live-observability-path.svg` | 分开 C++ 交易热路径与 `.101` 观测旁路 |
| `04-two-read-paths.svg` | 分开 `MEASUREMENT_SAMPLES` 写 CSV 与 `STATE` 喂 `/metrics` |
| `04-order-rtt-contract.svg` | 冻结 OUCH send→final response 与 warmup/measured 边界 |
| `04-evidence-layers.svg` | 说明 raw CSV、Prometheus 与 Grafana 的证据层级 |
| `04-grafana-baseline-dashboard.png` | 运行 ③ 打开 URL 后的真实驾驶舱页面 |

机制图限制为正文 `max-width:800px`。2026-08-29 箭头按第三章几何收口：`marker` 为 `20×15`、`refX=1`、`overflow="visible"`；线在目标框前约 16 个单位结束，尖停在框边，不再杵进框内。热路径线宽 5、旁路/证据层 4，与箭头比例对齐。两张路径图里的 scrape 均由 Prometheus 主动发起；双读路径图另把管理命令与 JSON 回执画成相反方向。C++ 数据面到 Gateway 只保留一根灰虚线，旁注「只读状态」。折线路径只用正交线段。原有 29 张 PNG 暂不删除，继续作为上一版课程的审计资产，不再被当前正文引用。

34/34 固定摘要见同目录 `SHA256SUMS`。
