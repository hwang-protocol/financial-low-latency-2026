# 第三部分：行情与订单报文资产

## 运行②实测节选来源

用户执行 `20260915T102731Z-03-market-paths`，基于平台 `20260915T094055Z-02-trading-platform`。完整打印与 pcap 保存在 `reports/course-runs/20260915T102731Z-03-market-paths/`；`CLASSROOM_SHA256SUMS` 2 项、`SHA256SUMS` 32 项全部通过。正文只摘 DUAL 两条原始目的端点、四行解析统计和恢复 A 路的回读，不重复交换机查询、HTTP 切换与长路径。

A 窗口 120/0、B 窗口 0/120、DUAL 窗口 60/60；重合序号 60，duplicates 从 4997 到 6174、增量 1177，pending/gaps 为 0。三个抓包窗口各有 120 包且 kernel drops 为 0；应用采样区间与 pcap 的 120 包窗口不同，不能把 1177 当作抓包中的重复对数。交换机两组均为 VLAN20/Dynamic/Et2，querier 仍为 v2。本条证明当次三模式窗口，不能证明新版源过滤接收器已部署或干净快照顺刷完成；其余历史输出保持来源身份。核验见 `refs/evidence/chapter03-ab-live-excerpt-20260915.json`。

## A/B 评估后的接收与采样检查

新版两组接收器只接受配置来源 `20.1.1.1`；Linux 源过滤在接收 socket 上生效，成员表仍查看两组。UDP 42121 保留内部用途，课堂三种模式仍只有 A/B。

运行②由 `check-comparison-state.py` 核对整次比较使用同一 Exchange/Feed Session 与回放轮次，再求 duplicates 增量。换轮、重启或状态尚未同步都给出具体错误，已有 EXIT 恢复继续执行。每个检查快照保存到 raw 并纳入 SHA。56 行脚本使用正文文件入口，不再整段复制。三模式 pcap 已有上方用户实测，本地反例仍只用于回归测试。


## A/B 版本与证据状态

当前三种模式是 `MULTICAST_A`、`MULTICAST_B`、`DUAL`，分别发送 A 组、B 组、两组相同的 Mold 数据报。模式比较还检查两组订阅、同 Session/序号的内容一致及去重。代码、本地合成报文测试和上述三模式实测通过。旧 UNICAST/MULTICAST/DUAL 回执是历史资料，不能作为新 A/B 实测。

国内外依据、课程地址与部署边界见 [迁移记录](../../refs/FLLE_AB_Multicast_Migration_2026-09-15.md)。

2026-09-12 首单修复：MANUAL首次收到订单才建立TCP连接，03入口现于first_trade成功后采集ss；解析器按MANUAL PID核验端口，允许AUTO尚未连接。用户退出1的原单已成交，修复只读补解码，结果在20260912T032538Z-03-live-order/repair/，不得为补抓重下。原始失败日志保留；证据见refs/evidence/chapter03-first-order-connection-fix-20260912.json。

2026-09-15 展示范围：运行②正文保留目的端点、三种模式包数、去重与缺口读数及模式恢复；以关键节选替代此前预期表。完整终端保留在上方 RUN，脚本打印不变。本条接管 09-12 的展示范围。

2026-09-12 最新：按用户要求恢复订单 Packet Details 图，与行情解码树、六类型图、三模式图和 O/A/E 时序图一起保留。仅压缩重复讲解，可见讲解文字减少约3.65%；脚本与全部文本输出保持。正文恢复图收据：`refs/evidence/chapter03-light-edit-restore-tree-20260912.json`。

运行③的终端仍分 O 下单、A 受理、E 成交三块，说明方向、关键值与含义；价格显示四位小数。图与输出对应同一笔历史订单，TCP ACK 和完整包数见补充读法，原始解码保存在 raw/decoded.txt。显示与重解码收据：`refs/evidence/chapter03-order-message-display-20260912.json`。无新抓包或下单。

## 正文范围与补充阅读

第三章正文按“包结构与字段 → 抓包解码 → A 路/B 路/双路 → 一笔订单往返”组织。更多 OUCH 条件、编号规则和原有较完整输出移至[补充读法](READING-NOTES.md)；图中取值来自对应历史pcap，重新解码和两尺寸目视收据见 design/evidence/chapter03-concise-packet-trees-20260912.json。正文现用9图，行情和订单各有一张 Packet Details 树，另含用户提供的网页下单入口截图。

## 课堂入口与输出

三个 Bash 入口分别为 42/56/36 行；正文①③展示脚本，②展示文件执行命令。①②各自完整展示模式请求、回读、退出码125和清理路径，不再 source 公共 Bash；③不切换模式，只保留本步的抓包清理。抓包、模式切换、下单和检查均由绿卡 Bash 编排；`classroom-output.py` 只负责 DEC-195 分段说明、回读已有 pcap/文本、将订单消息分块说明、给解析器的 verdict 附加边界说明，不调用 SSH、HTTP 或订单程序。①沿用第二章的 `transport_labctl.sh verify` 核验平台。

正文资产表登记八项现役入口/辅助的实际行数与重复执行边界。`archive/market-mode.sh` 是移入归档的37行旧实现，字节与历史清单中的 `b91407555ecebd03186bbe4687a11b30e8a48ce67224765bee85b341bf346e76` 相同，仅保留追溯，现役入口及新运行清单不引用。

新输出统一写到 `reports/course-runs/$CHAPTER_RUN_ID/`：`raw/` 保留原始抓包、命令结果及不加注释的解码；`classroom.txt` 另存完整终端打印；`SHA256SUMS` 校验源码与原件，`CLASSROOM_SHA256SUMS` 在终端记录关闭后登记课堂日志和原清单。既有报告根目录下的历史 03 目录不搬移、不改写。

显示工具是课堂预置辅助工具：输入为动作名、脚本已经确定的参数与原件路径，输出为注释、命令和原文字段；不生成 RUN、不恢复业务、不增加业务断言。`tcpdump -r` 只读已有文件。显示失败会明确提示，原抓包、HTTP、解析器的退出行为仍由 Bash 的原门槛决定。

## IGMP 操作前移与退役文件

配置、客户端订阅、交换机成员和实际收包已作为第二部分正式绿卡，先于首单执行。运行②只读取第二部分 `igmp-show.plan`，调用 `inspect-igmp.py --members --ab --display` 展示 VLAN20/Et2 原文，由学员判断；底层 CLI 错误和后续协议解析检查保持。

**`market-igmp-enable.plan` 已退役，仅为历史追溯保留，现役入口不引用。** 重启交换机后按第二部分准备 C 恢复配置，不执行此旧计划。

## 本地验证与已知限制

最新图形合同：一种 ITCH 消息占一条，条内字段左右连续分格；六种类型共用 `03-itch-type-strips.svg`。Mold 用 `03-mold-envelope-strip.svg`：上两行是 IPv4/UDP 头（目的组播地址与组播端口），最下一行才是 58 字节 UDP 载荷。图负责协议布局，正文保留字段含义与输出读数表；缓存限值移至本文配套说明；禁止重复布局表不等于禁止整个理论区出现表格。前版“每字段一条”已退役，沿革见 `refs/FLLE_Chapter03_Type_Strips_2026-09-10.md`。

`test-document-format.py` 现有 12 项本地回归：实际 Markdown 加粗解析、类型数量、验证边界、脚本逐字/行数、三模式输出、两张字段图布局、跨章共图，以及统一图框、逐步读数表和下一线索。

在课程 Ubuntu 22.04 管理机的仓库根目录执行以下维护命令。依赖由 Ubuntu 的 `python3-markdown-it` 提供，无需 pip3 或 `/tmp` 中的 Python 库；本轮验证的软件包版本为 `1.1.0-2`，Python 模块版本为 `1.1.0`。

```bash
apt-get install --no-install-recommends python3-markdown-it
python3 assets/03-live-traffic/test-document-format.py
python3 assets/03-live-traffic/test-classroom-output.py
python3 assets/03-live-traffic/test-order-selection.py
python3 assets/03-live-traffic/test-transport-pcaps.py
```

这些是维护者本地检查，不是学生绿卡。过去“九项通过”使用了临时 Python 依赖目录，不能视作裸 `python3` 可复现；本轮已补安装入口和缺依赖提示。`classroom-output.py` 当前为 170 行；下单后连接提示与首单行为一致，解析器当前166行。依赖安装及原检查结果见 `refs/evidence/chapter03-report-review-20260910.json`。

`python3 assets/03-live-traffic/test-classroom-output.py` 行情单路和订单使用历史原件，A/B 模式使用明确标记的本地合成报文，在 `/tmp/ch03-output-check/` 的隔离副本中替代所有 SSH/curl/下单命令；运行27个正常、失败和异常成员显示场景，不连接设备、不创建正式 RUN；订单fixture在首次提交前仅展示AUTO连接，提交后才展示MANUAL连接。覆盖去除归档库后整卡执行、恢复 POST/GET 失败、回读不符、业务失败叠加恢复失败、首次状态失败和单次切换失败后恢复，并核对日志、清理及原退出码。fixture 的解释器固定为 `/usr/bin/python3`，防止 PATH 中的同名测试工具递归调用。

运行①课堂节选改用 `20260915T082055Z-03-live-market` 的抓包计数、组播去向和第一条 A；完整终端仍在该 RUN 的 classroom.txt。学生正文不再放 Profile 卡或模式恢复红卡。①②恢复请求失败或实际模式不符返回125，恢复成功保留原业务退出码。③传入 `--first-trade`，按实际成交的 `order_id` 选择 O/A/E，不把前一次被拒的尝试当成本次成交。`test-order-selection.py` 的七项回归覆盖先拒后成、目标缺失、缺成交回报、仅MANUAL连接且含登录、PID归属缺失，以及格式化编号/价格与展示失败回退。PIT-20260910-13/14 的正常路径此前已在平台三卡顺刷验证；本次恢复内联和 verify 入口同步仅做本地验证，未重跑设备。历史课堂输出与 SHA 不改写；不能用历史源码清单证明本次改动已实机执行。最新来源见教师说明。

## 消息处理与课程恢复细节

以下保留第三章压缩前的补充读法。ITCH 消息语义来自公开规范；缓存限值、停单与恢复操作属于本课实现，不是 Nasdaq 协议要求。

沿相同的格子向下比较，区别就集中在这些位置：

- F 在 A 的主体后追加 Attribution（4 字节参与者标识），仍然是新增挂单。
- E 按原引用号扣减 Executed Shares（本次成交股数）；Match Number 是这次历史市场成交的编号，不是订单号。图例原有 200 股、成交 50 股后剩 150 股；余量为 0 才移除挂单。
- D 在共同头后只保留引用号，删除原单全部余量，因此不需要再携带股数。
- U 撤下 Original Order Reference Number（旧引用号），按 New Order Reference Number（新引用号）、Shares 和 Price 建新单；股票、方向及原参与者标识从原单继承，Shares 不是扣减量。
- P 记录非展示成交，更新成交统计而不增减展示簿。它的引用号固定为 0、方向固定为 B，不能照 A 的含义找展示挂单或判断真实买卖方向；末尾 Match Number 标识这次成交。

E/D/U 没有明文 Stock，即使知道证券索引，也要保存原单才能找到该扣减或移除的价格档。**网页五档是这些订单按价格聚合的结果，不是五种消息类型；P 不改变展示簿。** 历史 ITCH 事件也不会变成 AUTO/MANUAL 模拟账本中的一笔新成交。

Mold 序号用于同一 Session 内的连续交付。同序号副本记为 **duplicate（重复）**；先来的后续消息暂存为 **pending（等待前序的消息）**；缺失前序形成 **gap（缺口）**，此时暂停下单。

| 完整性读数 | 含义 |
| --- | --- |
| gap_size | 最前面空洞的宽度，不是全部缺失消息数 |
| gaps | 本轮出现过的缺口次数 |
| gap_messages | 缺口期间到达的非重复消息数 |

本机分发会保留短暂停顿期间的报文并按序重试；已经缺失的消息则需要补回，当前课程没有自动补包服务。每个客户端的行情处理逻辑（Feed Handler）使用的等待缓存受以下限制：

| 限制 | 何时要求重新同步 |
| --- | --- |
| 32768 条消息 | 新消息会使等待条数超过上限 |
| 8 MiB 消息内容 | 新消息会使等待字节数超过上限 |
| 缺口持续 5 秒 | 收到后续非重复消息时，检查到缺口已达到此时长 |

触及限制后标记 `resync_required`（需要重新同步），保持停单。使用第二章的“重新开始并清空交易”，从开盘订单簿与新 Session 的序号 1 一起重建；中途重启 Trader 或只重连接收器都不能恢复完整性。

Mold 还用 Message Count=0 表示心跳、0xffff（65535）表示会话结束，两者均无 ITCH 消息。心跳序号指向下一条预期消息；补包请求由接收端反向发送。当前 Exchange 只发布数据消息。[MoldUDP64 规范](https://www.nasdaqtrader.com/content/technicalsupport/specifications/dataproducts/moldudp64.pdf)
