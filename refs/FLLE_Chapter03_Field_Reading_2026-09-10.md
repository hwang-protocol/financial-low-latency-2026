# 第三章字段图与渲染核验

日期：2026-09-10。状态：LOCAL PASS / NOT LIVE。承接用户对字段表、加粗、模式读法和证据范围的评估；不沿用已经执行完的部署、清空或下单授权。

## 本轮改动

- 撤掉第三章 Mold 字段、Type A 字段和六种 ITCH 类型三张 Markdown 表，改为 Mold 独立图以及 A/F/E/D/U/P 各一张字段图。每个字段用一条全宽横条，自上而下按报文顺序排列，A为九条；条高96、间隔6，偏移/字段名/解释固定对齐，不再使用三列小框。顶部保留按字节比例的布局；ITCH 图另演示订单簿变化，演示值与抓包输出明确分开。
- 第三、八、九、十章在正文直接嵌入同一个 `03-market-packet-fields.svg`。第九、十章不再只有链接，第八章不再要求翻回前文。黄色 Type/Stock Locate/Stock 对应过滤字段，程序开关、额度和是否 DROP 不是协议字段。
- 修正七处加粗边界：payload、offset、big-endian、Unix Socket、framing、Soup U、Soup S。CommonMark 在闭合标记前为标点、后紧接汉字时可能不把它视为结束；Unix Socket 一处还会把后面的正文误吞进加粗。全章实际解析后 45 个预期加粗片段均匹配。
- `itch_types=A:180,U:20` 明确为 180 条 A、20 条 U，共 200 条。运行②终端和文中三段“对”按 UNICAST/MULTICAST/DUAL 分别说明目的地址；显示工具为 124 行，采集、切换及恢复编排不变。
- 学生正文承认节选来自此前同基线抓取，现役入口只完成本地核验。开场封装图完成本轮实际目视，并改清每个 Trader 各用一条订单连接。

## 协议与图形

依据本日在线读取的 [Nasdaq TotalView-ITCH 5.0](https://www.nasdaqtrader.com/content/technicalsupport/specifications/dataproducts/NQTVITCHSpecification_5.0.pdf) 与 [MoldUDP64](https://www.nasdaqtrader.com/content/technicalsupport/specifications/dataproducts/moldudp64.pdf)，并对照 `nasdaq_protocol.hpp`、`itch_book.hpp`、pcap 解析器和后续过滤代码。

| 图片 | 尺寸 | 内容边界 |
| --- | --- | --- |
| 03-mold-field-layout.svg | 1200×1330 | 20 字节头与两组长度/消息，示意总载荷 95 字节；课程实际每包一条 |
| 03-market-packet-fields.svg | 1200×1624 | A / 36；共享 Type 0、Locate 1/2、Stock 24/8 |
| 03-itch-f-fields.svg | 1200×1566 | F / 40；末尾 Attribution 36/4 |
| 03-itch-e-fields.svg | 1200×1260 | E / 31；引用号、成交股数、Match Number |
| 03-itch-d-fields.svg | 1200×1056 | D / 19；按引用号删除全部余量 |
| 03-itch-u-fields.svg | 1200×1362 | U / 35；旧引用号、新引用号、新股数、新价格 |
| 03-itch-p-fields.svg | 1200×1566 | P / 44；引用号填 0、方向固定 B、展示簿不变 |
| 03-protocol-and-envelope.svg | 1200×720 | 两套套叠关系，不把 AUTO/MANUAL 的订单连接画成一条 |

七张字段图合计 56 个字段解释，ITCH 六图 49 个字段；各类型字段连续覆盖到对应消息末尾，Mold 长度字段不包含自身。图中 U 的继承语义来自规范；课程订单簿不按参与者分组。Price 隐含四位小数，Stock 固定 8 字节右补空格。

七张字段图 442 个文本对象，开场图 23 个。八张图全部在 Chrome 按 800px 和 1200px 实际渲染、检查文字边界与相互重叠，并逐张目视。返修时增大行距与底部留白，Mold 相邻偏移上下错开，最终无裁切或文字重叠。六支状态变化箭头使用固定 12×12 marker、refX=0、refY=6、userSpaceOnUse、2.5 线宽与 butt；路径从 x482 到 x706，尖端 x718，距目标左边 x730 为 12。Mold 与封装图没有流向箭头。

## 本地验证

1. `test-document-format.py` 九项通过：全部加粗实际解析、七处明确回归、样例数量、现役验证口径、42/50/36 行绿卡逐字相同、八项资产行数、分模式终端说明、六种字段布局及箭头、Mold 图替表与后续三章原位共图。部分项目合并在同一测试方法。
2. `test-classroom-output.py` 27 个隔离场景通过；补充检查三种模式“对”不同。所有设备、HTTP、下单动作均为本地替身；不是重新执行实机实验。
3. 第0～3章结构、脚本语法、链接、样例及全课 79 张导航卡通过；第三章剩 10 张表、11 张图片。新图所在字段讲解区没有 Markdown 表。
4. 第三章在 940/390px 检查实际 HTML，无水平溢出，11 张图片均加载；七个曾失败术语为正确 strong、字重 700。第3/8/9/10章共八个桌面/手机位置均加载同一图文件。
5. 三份历史样例原始读数有序逐字对应原课堂日志；仅三模式“对”按当前显示工具更新，不改写原日志。六份原清单内共 38 项历史原件摘要仍通过。
6. 从历史行情 pcap 第9帧复算 100 字节、序号246208、Count 1、A36、Locate8095、Stock NVDA加四空格；Type/Locate/Stock 与 RTL 位切片一致。
7. 图片两级 SHA256SUMS 为 53/227 项，全通过；`git diff --check` 通过。

收据：[chapter03-field-reading-20260910.json](evidence/chapter03-field-reading-20260910.json)。持久回归入口为 `Documents/newDoc/assets/03-live-traffic/test-document-format.py`，需安装 markdown-it-py；本轮使用既有本地隔离依赖，不改仓库运行环境。

## 仍然待确认

本轮没有连接设备、部署、重启、清空、发单或创建正式 RUN。此前 085246Z 的21卡实刷是历史事实，其中第三章①②源码已在上一轮变更；当前显示辅助也与旧实刷源码不同。当前三个入口仍待按顺序实机重跑，不据历史样例提高验证等级，也不外推为1倍速完整6.5小时或第4～10章新基线已通过。

本轮待提交范围是第三章正文/显示辅助/两项测试、七张字段图与开场图、后续第8～10章嵌图位置、图片登记与两级摘要、教师说明、报告/收据及五份治理文件。其余此前未提交的应用和文档改动保留，不能混称本轮新改。AI 没有执行提交、推送或标签操作。

建议提交信息：`docs(ch03): 将行情字段改为逐类型图解并修正加粗与验收口径`
