# 第 06 章本地配套资产

### 2026-09-16 · 帧长口径与历史输出标识收尾

运行 ④ 结果卡就近注明“单播行情”；章末按本轮评估补回原始 `evidence=` 行，与该输出的历史归档对应。序列化参考脚本统一使用含 FCS 的 64/1518 字节，明确不含前导码和帧间隙；10G 换算为 51.2/1214.4 ns，差值 1163.2 ns。该参考脚本的旧 RUN 保持原件，主线部署及现场实验脚本不变。

### 2026-09-16 · 输出来源与顺刷提示精简

运行 ②～④ 的旧实现来源统一放到运行 ② 之前，三处结果卡保留“历史实测”标识，原始读数不改。明确 Q5 的 240 是帧数、TRex 1514 字节不含 4 字节 FCS、历史样例保留的 80 条恰好是 40 对开始/结束记录；收口 PTP 主从角色。资产表按运行 ①～⑤ 排列主线，备用与历史证据另列。第四章快照的补齐命令限定在第五章准备 B 之前；本轮仅调整文档，未重跑现场实验。

### 2026-09-16 · 第五、六章接续复核（LOCAL PASS / LIVE PENDING）

第二章原上线命令可复用第四章末的 A/B 平台并补齐打标客户端、控制脚本与官方 LANZ 工具；第五章启用，第六章使用。正文修正部署归属、配对订单持仓表述与 PTP 对称路径前提；官方 LANZ 完整 Go 示例保留。QoS/PTP 旧读数保持历史身份。

发现并修正第六章运行 ④ 的 A/B 接续遗漏：分析器现识别 A/B 精确地址/端口，保留历史单播 pcap 兼容；`.2` 的 `capture_market.py` 临时加入两组并限定 Exchange 来源，随后 exec tcpdump，由同一进程持有订阅，退出即释放。两端抓包都确认启动成功后才进入采样窗口，不切换 Exchange 行情模式。新增双路相同载荷的完整合成 pcap 测试与本机 tcpdump 加组/释放验证；历史 3705 对 pcap 重分析全字段不变。硬件时间戳、交换机转发和恢复快照后的完整顺刷尚未重跑。[核验](../../refs/evidence/chapter05-06-continuity-review-20260916.json)

正文现在先展示完整 LanzRecord 的标准 Protobuf 文本表示，再讲网页摘要。五字段示例来自官方 TestSuccessPath，本地直接打印核对；不是现场记录。现有 CLI 仍输出中文摘要或网页 JSON，未增加新参数或更新可执行文件。

### 2026-09-16 · LANZ 改为官方客户端库

按用户要求，LANZ 接收、分帧、Protobuf 解码与重连统一调用 Arista 官方 `goarista/lanz`；不再维护本课 Python 二进制解析器。固定 SDK、许可证、Go/Protobuf 版本和重建入口见 `lanz-reader/README.md`。`flle-lanz-reader` 是本课对官方库的薄调用程序，不是厂商独立 CLI；终端可直接查看事件，`-json` 交给原 Python HTTP/历史列表接口，8088 页面不变。第二章上线入口预置官方读取工具；`04b` 核对并启动已备好的工具，快照内无需安装 Go。旧第四章快照在第二章入口加 `--prepare-capabilities` 补齐。

正文按官网→下载编译→连接→官方 getter 提取事件→简述网页呈现组织，取消手写解析和包字段展开。原 10k/25k 的事件数字仍为旧采集器历史读数。已通过官方 LANZ 包 6 项、本课 Go 2 项、SDK→HTTP/退出集成 1 项、原 GUI reset 4 项及展示 3 项；源码包离线重建逐字节一致。未改交换机配置，未重跑完整 TRex/LANZ 实机实验。



2026-09-16 接续修复：准备 B 刚启动的客户端只有 `launch_verified=true`，尚无真实连接路径记录。QoS 入口先验证启动状态、按需预热连接，再执行所选客户端的 `attest` 并核对路径记录与 PID，之后才设置 QoS。不能在预热之前要求 `verified=true`，也不能省掉预热后的实际路径核验。入口失败时保存状态并打印具体条件。九项本地恢复/接续测试通过；只读 API 确认了此次入口阻断原因，修复后全程实机实验尚未重跑。

### 2026-09-16 · 订单 DSCP 改由应用设置

`10-qos-real-order-live.sh` 与 `11-qos-real-order-contention-live.sh` 共用 `order-dscp-control.sh`，调用 `.111` 上的 `apps/flle-trading-lab/scripts/order-dscp.py`。控制消息由 `.2` 的订单线程在空闲时处理，调用 `setsockopt(IP_TOS)` 并回读；保持原 TCP 连接，重连沿用配置。默认 Kernel Socket；指定 `FLLE_QOS_TRANSPORT=OPENONLOAD` 可选择第五章同一个更新程序的 Onload 进程。回报方向不打标。

前置为第五章准备 B 已完成。若测试客户端刚重新启动、尚未建连，QoS 脚本先发两笔方向相反的预热单，单独留证，不计入 A/B 比较。正式抓包按所选连接的源端口过滤，避免把另一客户端的包混进来。恢复操作校验原 PID；即使设置成功的回复丢失，EXIT trap 仍尝试恢复原 DSCP，失败明确报错。`iptables-save` 仅用于证明规则未变，不再写 mangle 规则。

当前只完成本机真实 TCP 包头和恢复逻辑测试；未重跑 X2522/Arista/TRex。正文 120 笔/240 帧及 90.90% 仍是原 iptables 实验的历史结果，已在输出卡标注；不能据此宣称新实现实机通过。

本轮固定 Onload 源码 `onload-9f330e7/src/lib/transport/ip/common_sockopts.c` 的 `IP_TOS` 分支同时实现 get/set，TCP 保留 ECN 两位并更新缓存 IP 头。来源是 vault 中的厂商源码包，不以 iptables 是否看得到报文推断功能。

配套新增工具：`order-dscp-control.sh`（83 行）负责平台检查、连接与路径核验、设置和恢复；`apps/flle-trading-lab/scripts/order-dscp.py`（58 行）负责控制消息与格式化回读，均由课堂入口自动调用。

### 2026-09-13 · 全章评估取舍与生产案例补充依据

正文按已核实意见删重、顺序调整并修配置模式；现役实验脚本、五段实测输出、图字节均不改。运行①的八条 show 逐条来自 `01-arista-fabric-inventory.sh`；生产配置是命令示例，Et24 前置为上游 PTP 跟随口，`no-errdisable` 只保留端口，不代替 PTP 配置。TAP 模式需上游静态转发 PTP 组播，Keyframe 的服务器地址按部署设置。

第二轮出处核对：7280R3 源 MAC 48 位戳引用 Advanced Policy，Flow Diff 的 7280R3/7800R3 范围引用 Service Node；两者分别说明。详见[第二轮核验](../../refs/evidence/chapter06-editorial-review-second-pass-20260913.json)。

教师补充：DMF Flow Diff 目前提供 min/max/mean，要求 push-per-filter；packet-timeout 默认 200ms，可配置，不能把它讲成固定丢包窗口。官方当前推荐 replace-src-mac，不应写成仅支持该格式。[官方说明](https://www.arista.com/en/ug-dmf/dmf-dmf-service-node-appliance)

本课 7150 本地 Master 的实验不证明 UTC 同步精度；同台 ASIC 两入口的相对间隔无需跨设备对时，但仍受计数频率、回绕和采集线路时延差影响。旧 56.832/101.376µs 与用户新 7.168/11.776µs 各属原 RUN，差异未归因。RUN_ID 的 `-07-` 后缀本轮不改，避免混入运行代码及归档迁移。[核验](../../refs/evidence/chapter06-editorial-review-20260913.json)

### 2026-09-13 · 教师扩展参考（退出学生正文）

以下资料保留供扩展备课，当前主线未展开这些主题。

| 官方入口 | 扩展用途 |
| --- | --- |
| [linuxptp phc2sys](https://www.linuxptp.org/documentation/phc2sys/) | PHC 与系统时钟的同步方向 |
| [EU RTS 25](https://eur-lex.europa.eu/legal-content/en/ALL/?uri=CELEX%3A32017R0574) | HFT / 交易场所业务钟的 UTC 最大偏差与粒度 |
| [CAT Clock Synchronization FAQ](https://www.catnmsplan.com/faq/r1) | CAT Industry Member business clock 的 NIST 同步要求 |
| [ITU-T G.8275](https://www.itu.int/rec/T-REC-G.8275/en) | full / partial timing support profile 的官方入口 |

### 2026-09-13 · 生产节只保留两方案与TAP/TOOL关键配置

学生正文现用06-dmf-multipoint-analysis.svg与06-tap-tool-multipoint.svg分开讲；讲解文字压缩55.9%。专职7150示例为TAP Et1～3→ANALYZE→TOOL Et10，来源101/102/103，出口附加入口短戳；PTP Et24已有配置并通过no-errdisable保留，Keyframe仍需按实际服务器设置。只作官方命令说明，不是当前7150执行入口，也未提供新的生产分析程序。两图/源码文字/Markdown静态验证通过，无新设备实验；下方Cboe案例原文保留作教师资料。[核验](../../refs/evidence/chapter06-production-two-diagrams-tap-tool-20260913.json)

### 2026-09-13 · 生产案例补充资料

学生正文按用户要求只保留DMF和朋友的多点TAP/TOOL方案。以下Cboe公开案例保留供教师查阅。

<a id="cboe-timestamp-case"></a>

#### 真实案例：Cboe 怎样记录订单经过的时刻

前面讲了专职设备接收副本、记录时间。Cboe 的公开时间戳服务就采用这类分工：从交易网络取出报文副本，再由负责计时的交换机加上时间戳。[Cboe 时间戳服务规范，PDF第6—7页](https://cdn.cboe.com/resources/membership/Equities_Timestamping_Service_Specification.pdf)

| 工作 | 谁来完成 | 得到什么 |
| --- | --- | --- |
| 对时 | 汇聚交换机通过 PTP 跟随 Cboe 的 GPS 时间源 | 负责计时的设备有共同时间参考 |
| 取副本 | 业务链路上的光学 TAP 分出一份报文 | 交给旁路观察的报文副本 |
| 计时 | 汇聚交换机给每份副本添加时间戳头 | 记录这份报文在网络观察点出现的时刻 |

这里的 GPS 提供卫星时间参考，PTP 把时间关系传给计时设备。光学 TAP 负责复制；时间戳由收到副本的汇聚交换机添加。规范将这个字段称为 Network Discovery Time（网络观察时刻），并与订单服务器网卡的接收时间戳分别列出。

要测一段时延，仍须找到同一报文在两个位置留下的时间戳，并确认两个时钟可以比较。副本线路走过的时间和对时误差都会影响差值；字段写到纳秒，只说明记录单位，不能据此认定测量误差也是一纳秒。

### 2026-09-13 · 用户两次12号脚本实跑与正文结果更新（USER LIVE VERIFIED）

用户执行103102Z、103311Z两次stamped-span入口，均完成并恢复：配对6313/6313、3705/3705，Keyframe均8，p50均7.168µs，p99分别11.264/11.776µs。正文取第二次完整关键输出，第一次数值仅作简短复跑说明。各38项清单、根SHA和封存入口/formatter/analyzer/PTP配置验证，原pcap重分析与完整JSON一致，result-display逐字符合formatter；当前中文输出完整现场状态由这两次用户实跑验证，取代下方“尚未执行”。运行代码与归档原件本轮未改；原101.376µs保留历史记录，差异未归因。正文管理机调用和三段Python细节改为配对图与原理。[核验](../../refs/evidence/chapter06-frame-matching-and-user-ptp-results-20260913.json)

### 2026-09-13 · PTP 主线精简及12号脚本中文结果（LOCAL FORMAT PASS）

正文按NTP/PTP区别→同步配置→SPAN/Keyframe→抓包配对相减展开，Linux配置/脚本随步骤出现，讲解文字减少56.8%。`12-stamped-span-live.sh` 新增 `format_stamped_span_result.py`：终端输出PTP跟随状态、有效窗配对、Keyframe数、统一µs的最小/p50/p99/最大值、负值样本与恢复结果。raw/analyze.txt、raw/result.txt及RUN/SHA封存保留，正常终端不打印这些维护标识；新增formatter随新RUN封存。

现役分析器重读原20260903T085652Z两份pcap，全部旧字段一致，仍为15505/15505、56.832/101.376µs；7项原SHA通过。格式化正常/零样本/缺失读数/失败状态、中文列宽、bash -n通过。此次仅本地显示验证，完整设备复跑尚未执行；正文标明既有抓包按当前格式展示。[核验](../../refs/evidence/chapter06-ptp-mainline-and-output-20260913.json)

### 2026-09-13 · LANZ 主脚本直接打印交换机 show，正文只留关键结果

`04b-lanz-stream-ab.sh` 新增 `format_lanz_result.py` 作为结果格式化依赖，并随入口封存至新 RUN。终端同时显示接收器、`show queue-monitor length statistics`、`show queue-monitor length Ethernet 2` 最近两条 S/U/E 记录、`show queue-monitor streaming clients` 和恢复状态；无需另行登录交换机。明细计数注明最近80条，S/E按同一事件配对，END注明最大队列长度；timer输出仍归档但不在终端摘要展示。

实跑 `20260913T094748Z-07-lanz-stream-ab` 退出0，EOS Count164，接收累计S/E各164、保留明细各40，配置/网卡/网页恢复通过；65项根清单与入口/formatter源码一致。配对及show节选两项测试通过。正文QoS仍用用户093356Z结果，LANZ采用本次新输出；用户最新要求覆盖下方“正文完整终端34行”，完整原件继续留存。[核验](../../refs/evidence/chapter06-lanz-show-and-key-output-20260913.json)

### 2026-09-13 · 正文QoS展示用户本次完整终端

正文结果示例现采用用户提供的20260913T093356Z-07-qos-contention-live完整终端，34行保留启动、规则、统计、恢复与结论。p99 2269.697→206.489µs，90.90%，Q5+240，LANZ各1；与本轮raw/result-display.txt、统计及pcap核对。以前095143Z等权威历史原件保持，不能与当前正文示例混算。完整用户终端归档在design/evidence/chapter06-qos-user-terminal-20260913.txt，校验记录为chapter06-qos-full-output-20260913.json。

### 2026-09-13 · QoS 退出22已修复并完整在线验证

11号脚本现于交换机配置/TRex发流前检查下单门控；POST失败保留HTTP响应体、组名和订单序号，避免只看到退出22。网关COMMON_GATEWAY_BOOK纯下单模式按实际客户端状态更新门控，不覆盖已观察到的行情接收/Guardian/GAP。复跑20260913T091923Z-07-qos-contention-live退出0，A/B各120单，p99 2267.668→226.181µs，Q5+240；恢复后2单、净持仓0→0。该实跑也验证此前新增终端对照表，取代下方“未完整现场执行”的状态。入口SHA `2f70242fbde8342455f56bca1cc2645a53658a95d4f9c4498dd9319f88460486`。

### 2026-09-13 · QoS最终打印突出Q1/Q5延迟差异（LOCAL FORMAT PASS）

用户要求实际打印直观比较队列延迟。11-qos-real-order-contention-live.sh只改最后的结果呈现：保留raw/result.txt键值摘要，新建raw/result-display.txt供终端显示；Q1/Q5同表、千分位、统一µs，队列核对后以延迟差值、降幅和p99比值收尾。高/低/相同按本次数据判断，原result.json、实验判定、发流/打标/队列配置和恢复代码保持。使用20260903T095143Z-07-qos-contention-live既有result.json离线重放，机器摘要与原raw/result.txt逐字一致；另测相同、反向、零分母显示，bash -n与对齐检查通过。没有重跑设备实验，新脚本完整现场执行尚未验证。当前入口SHA256：`19c1bd8cc5efb24a4f74d86e09c312e9a80c4282acb324f42284e3c88ec0c999`。历史RUN根SHA仍为`c86a2cad555d699ef12a03257cec9d3dac0932c28954781698c06b556c04e58d`，历史文件未改。[核验](../../refs/evidence/chapter06-qos-ab-format-and-paths-20260913.json)

### 2026-09-13 · L1小节展示一对多配置

正文7130示例由Et1→Et2改为Et1→Et2/Et3/Et4，说明物理信号扇出、目的口l1 source与Source Interface核对；面向运行EOS的7130且假设四口同为10G。该紫色示例不属于本课7150可执行实验，目录脚本、原始输出和运行态未改。

### 2026-09-13 · 编解码与序列化的计时对象

正文第②项改为“信号编解码与纠错”，图文与导航同步；FEC纠错、FCS检错分开说明。序列化时延指整帧发送时间，编解码指收发电路处理时间；可流水重叠，五项不能直接串行相加。帧内容不变仍需从独立出口发送。脚本、实测读数与14项结构保持。

### 2026-09-13 · 核心术语与验收口径收简

正文五项名称统一为序列化、物理层处理、介质传播、固定转发、出口排队；导航仍4组14项。350 ns撤下FIFO工程推断，按未公布计时起止点、负载和统计口径的选型参考处理。运行④开头聚焦戳点、配对、验收目标，结果明确方法验证；三次p50漂移不作单一原因归因。现役analyzer顺序为剪短戳、配对、逐对还原时间并相减，六步讲解已对应；脚本与既有实测读数保持，本轮没有设备操作。

### 2026-09-13 · 标题层级与14项导航

正文H2三大部分、H3知识项、H4节内说明；导航更新为4组14项（6/3/4/1）。新增物理层知识项，生产部署独立于运行④；序列化、传播、转发按五项编号展开，盘纤和Layer 1作为正题保留。运行①只保留相关原理与核对，平台介绍前移章首；运行①～⑤入口和代码保持，未执行设备操作。理解检查现9题，增加序列化换算与等光程。

### 2026-09-13 · 正文先建耗时框架，再调队列，最后测量

正文现为三部分加章末验收，共4组12项：五项耗时总览→Cut-through与序列化→盘纤/L1案例；多入口排队→QoS→LANZ；计时起止点→NTP/PTP→入口戳与网卡戳。运行①～⑤仍对应原入口，代码与输出不变；本轮仅重排正文和导航，没有新增设备实验。350 ns的简要规格含义保留在转发段，FIFO等定义与规格条件表移至测量部分。

本目录把“当前只读取证”“在线交易主实验”“可选精确维护窗”“历史备用证据”“课后模型”分开。课堂按正文绿色卡依次执行运行 ①～⑤；其中 QoS、LANZ 和 PTP 三项会临时改变实验配置，使用已经确认的脚本执行并自动恢复。停交易的 PTP TC 对照保留为教师维护窗口中的可选实验。口令不进入本目录。

第六章默认复用第二章部署、经第五章验证的同一交易系统，不调用 stop。三项主入口依次为 `11-qos-real-order-contention-live.sh`、`04b-lanz-stream-ab.sh`、`12-stamped-span-live.sh`。只有为隔离 PTP Transparent Clock 自变量而选择 `09-ptp-tc-live-ab.sh` 时，才进入停机维护窗；章末 `13-trading-online-final.sh` 在复用或恢复平台后，始终调用 SFC 恢复补齐接收器与建簿 Guardian。`apps/flle-trading-lab/scripts/verify-book-handoff.py` 在两笔净零真实订单前后分别验行情：PLAYING、同 session、HEALTHY/OPEN、心跳有效、两只股票五档完整，接收计数和建簿序号连续前进。失败不打印 PASS，原始采样写入本次 raw；需要重建簿时重播，不清三条测试客户端持仓。

| 文件 | 性质 | 用途 |
| --- | --- | --- |
| `01-arista-fabric-inventory.sh` | 当前只读 | 读取 7150 / Et1 / Et2 / cut-through 工作方式 |
| `02-serialization-time.sh` | 课后换算参考 | 与正文统一按含 FCS 的 64/1518 字节换算；不计前导码和帧间隙 |
| `03-queue-fanin-model.sh` | 历史补充模型 | 正文和课堂实验不使用；保留旧的短窗 fan-in 换算脚本供历史参考 |
| `04-lanz-live-ab.sh` | 历史停机现场 | 旧的 1514B×4096 LANZ No-event / Event `show` A/B；新课堂不再以它为主入口 |
| `04b-lanz-stream-ab.sh` / `lanz-reader/` / `lanz_stream_collector.py` / `format_lanz_result.py` | 在线主实验二 | 保持当前交易 RUN 与三路客户端在线，以发往隔离测试 MAC 的 MoldUDP64/ITCH 受控负载打开 streaming，把 S/E 推到 `.101:8089` 并在 8088 最下方显示；结束后恢复实验前网页发布资产 |
| `04-lanz-verified-evidence.sh` / `lanz-native-20260820.txt` | 历史备用证据 | 无维护窗时审计旧 LANZ No-event / Event 原文，不代替 fresh live |
| `05-hardware-timestamp-capability.sh` | 当前只读 | 读取两端 X2522 hardware timestamp / PHC capability |
| `05b-linuxptp-tooling-prep.sh` | 基础准备 | 从 `.111` 离线缓存向两端安装 `linuxptp`，不启动同步、不回退公网 |
| `06-phc-readonly.sh` | 当前只读 | 先拒绝仍有 PTP 同步进程的现场，再确认 PHC 节点与纳秒读数；年份不是门闸，先前 PTP 校时也不会在退出时回滚 |
| `07-ptp-message-state.sh` / `ptp_message_model.py` | 历史模型 | 旧四报文字符串模型，正文已由机制图接管 |
| `08-ptp-tc-verified-evidence.sh` / `ptp-tc-native-20260820.txt` / `ptp-tc-client-20260820.pcap` | 历史备用证据 | 无维护窗时审计旧 EOS / ptp4l / pcap 三层收据 |
| `09-ptp-tc-live-ab.sh` | 可选精确维护窗 | 正常停止 Exchange 与 Trader 后，在原 `.1 ↔ 7150 ↔ .2` 物理路径运行 TC OFF / ON；以 Onload 实际内容、HugePages 与两侧 `flle-(trader|exchange)` 进程拦截在线或半停机交易；通过门后所有远端 / EOS 写入均先 arm cleanup，成功恢复后才 disarm；章末卡负责恢复交易 |
| `09-ptp-tc-pcap-ab.sh` | 历史备用实验 | 无维护窗时对 2026-07-21 TC OFF / ON 固定真包做全量 A/B 解码 |
| `10-qos-real-order-live.sh` | 在线快速映射 | 保持第 05 章当前交易系统运行，只给当前 Kernel Socket 订单连接临时打 DSCP 46；无争用地验证 pcap、DSCP→TC5→显式 strict Q5 与真实成交后恢复 |
| `11-qos-real-order-contention-live.sh` | 在线主实验一 | 保持当前交易系统在线，以 `.11` 发往隔离测试 MAC 的 MoldUDP64/ITCH 受控负载和真实 SoupBinTCP/OUCH 订单争用同一个 Et1；比较未标记 Q1 与 DSCP46 / strict Q5 的队列计数、LANZ 和订单 p99，最后完整恢复 |
| `11-oneway-latency-live.sh` / `live-support/oneway/` | 历史旁支 | 同卡两端硬件戳对照；`.1/.2` 共享 X2522 时基，不能用它证明两只独立钟经 PTP 对表，也不进入三项主实验 |
| `12-stamped-span-live.sh` / `format_stamped_span_result.py` | 在线主实验三 | 保持当前交易系统在线，7150 做本地 PTP 时间源，`.2` PHC 跟随；Et1 rx 镜像到 Et11 并只在副本打入口戳，与 `.2` 硬件 RX 按真实行情配对 |
| `13-trading-online-final.sh` | 章末必做 | 恢复 SFC 行情与建簿，验证五档持续更新；按当前持仓方向执行两笔净零真实订单，验收页面、客户端、数据链和业务闭环 |
| `PTP-AB-SHA256SUMS` / `ptp-*-client-20260721.pcap` | 固定备用输入 | 锁定旧 A/B pcap 身份；原始来源为 `20260721T024157Z-x2522-ptp-hwts-smoke` |
| `live-support/` / `LIVE-SUPPORT-SHA256SUMS` | tracked 运行依赖 | 保存教师卡所需的脚本、解析器与配置；入口在外部动作前逐项验 SHA，并把清单副本与清单 SHA 写入新 RUN |

2026-09-03 三项在线主证据为：QoS RUN `20260903T095143Z-07-qos-contention-live`（根清单 `c86a2cad…04e58d`）、LANZ streaming RUN `20260903T100334Z-07-lanz-stream-ab`（根清单 `8c654aed…c1c2d9`）和带戳真行情 RUN `20260903T085652Z-07-stamped-span-live`（根清单 `4cd1e17d…0c0f94d`）。QoS 两档各 120 笔真实 SoupBinTCP/OUCH 订单，未标记 Q1 p99 `2,333,197 ns`，DSCP46→TC5→strict Q5 p99 `190,867 ns`，B 档 240 个方向受限订单帧与 Q5 `+240` 对账。LANZ 以隔离 MoldUDP64/ITCH 负载得到 `10k=0`、25k 接收窗口 START/END=`40/40`，同轮 EOS 本地统计 `Et2 / TC1 / 160`；两个观察窗口相互印证，但不冒充精确计数相等。退出后 `.101` 的第五章 `source.sha256` 重新通过。PTP 内部窗为 `15505/15505`，p50 `56832 ns`。章末 RUN `20260903T100854Z-07-trading-online-final` 以两笔真实订单把 AAPL 持仓保持在 `200`，根清单 `3b770219…f2d60f`，并封存执行脚本。同配方复现审计 `102049Z / 102234Z / 102356Z` 再次得到 QoS `13.50×`、LANZ `0/0 → 40/40` 和真行情 `6870/6870`；它们证明方向可复现，不替换前三份权威原件。旧不透明二层背景流 RUN `083310Z` / `072638Z`、旧 LANZ `show` RUN `060803Z` 与可选 PTP/TC RUN `061536Z` 只保留为历史 / 精确对照，不再定义默认课堂顺序。

运行时唯一允许写入 `reports/course-runs/` 的是新证据；任何源码、配置或解析器都必须来自 tracked assets / app 源码。换言之，即使快照恢复后本地没有任何历史 `reports/` 内容，LANZ、PTP、QoS 与带戳副本教师卡的代码依赖仍然完整；QoS / 带戳副本卡按设计依赖教师先拉起第 05 章当前交易 RUN，但不读取任何历史 raw 作为输入。`reports/` 按项目决策受 `.gitignore` 管理：PINS / DECISIONS / FREEZE 只保存耐久摘要、口径和根 SHA，不能替代原始文件；根 SHA 只有在本机 RUN 仍存在时才能复算，clean snapshot 或新机器上的发布验收必须重新运行相应卡，不能声称从 Git 恢复了历史 raw。

`09-ptp-tc-pcap-ab.sh` 保留为无维护窗时的快速后备：它不启动 `ptp4l`、不登录 7150、也不改变网卡，只验签并扫描两份固定 pcap。旧原件 baseline `42+38=80` 条全零、TC `66+66=132` 条全非零；这只是历史复算，不得写成当堂重新抓包。

### 2026-09-13 文字与格式初审

本轮保留正文全部 10 项导航、5 张运行卡、图表、案例及命令和原始输出，仅润色文字、补首次名词解释、统一展示卡标签并修正 HTML 行内代码。未修改运行脚本、图片或采样数据，未执行实验。

运行 ① 展示来源仍为 `20260908T131945Z-07-arista-inventory`：`raw/eos-transcript.txt` 保存八条 show 的原文，`raw/terminal.txt` 保存课堂打印。章末仍使用 `20260903T100854Z-07-trading-online-final`；根清单 SHA-256 为 `3b770219ed4670e48cfee7667c0b03735a7872505af1ab3ba887810bccf2d60f`，实际脚本保存在该 RUN 的 `raw/source/`。上述为来源登记，本轮未重新核验现场或重采样。

逐节审图时仍需处理的旧图文字（本轮只登记、保留原图）：

- `06-ntp-vs-ptp.png` 仍写“实验三”、引用主线已不展示的“生产时间链”图，并有“墙上钟”等旧说法。应对应当前运行 ④ 和实际的生产方案小节。
- `06-official-realtime-vs-dedicated-tapagg.png` 标题和 B 区仍写“朋友的专职 7150”，正文已经使用“专职设备”。
- PTP 路径图与生产对照图的浅色细字在 800 px 下偏小，逐节细看时应优先检查文字可读性；保留已确认的关系和版式。

### 2026-09-13 · 序列化段聚焦出口发送时间

正文统一解释出口从帧首bit发到帧尾bit的耗时，线速为当前以太网端口工作速率。用含帧尾校验的64/1518字节统一比较：10G下51.2/1214.4 ns；不再混入接收方向、对象序列化、抓包长度或线路附加开销的展开。计算器和旧SVG保留原字节，仅作历史补充。定义参考[思科序列化时延说明](https://www.cisco.com/c/en/us/support/docs/voice/voice-quality/20371-troubleshoot-qos-voice.html)，帧长依据[IEEE 802.3公开材料](https://www.ieee802.org/3/by/public/May15/sun_3by_01_0515.pdf)。未执行实验。

### 2026-09-13 · 五项耗时与E系列说明收敛

五项耗时先图后文，以相同帧长/路径/配置下排队为主要变动项。350 ns继续按7150S规格书第6页端口间延迟处理，不归为查表单项。E系列仅保留25G/100G低延迟光学方案：两端使用配套E系列、在型号规定距离内，无FEC仍满足误码率要求，省去FEC延迟，最高250 ns/链路。已核对[Arista官方Q&A](https://www.arista.com/assets/data/pdf/Datasheets/E-Series-Optical-Transceivers-Q%26A.pdf)第1/2/4页（Oct 2023 / 04-0052-01）；“50m/2km”等条件按具体型号，不作为所有模块通用距离。编解码节按用户要求展示交换机关闭 FEC 的接口命令 `no error-correction encoding`，紫卡标明不能在本课 7150 上执行。2026-09-16 只读：本机 Et1/Et2 为 `10GBASE-CR`，`show interfaces error-correction` 命令存在但无输出。详细 FEC 类型表仍不恢复，不改运行脚本与采样数据。

### 2026-09-16 · LANZ 启动路径

04b 与采集器直接使用第二章准备的 `/opt/flle/lanz-reader-v1/flle-lanz-reader`。`.101` 的 `/run` 为 noexec，只保存 Python 适配器、PID、日志和状态；不把 ELF 复制到此执行。启动失败打印 `collector-start.log`。本轮实机验证仅含启动与 HTTP 就绪，10k/25k实验待用户重跑。


### 2026-09-17 · LANZ 时间与统计对齐实测

RUN `20260917T002319Z-07-lanz-stream-ab` 退出0，官方适配器v1.1：10k无事件，25k EOS Et2/TC1 Count=163，完整S/E各163条；采集器累计相同、保留80条，逐条类型/队列长度/顺序吻合且无重复。最近S/E为UTC `00:07:12.929610` / `00:07:12.929640`，EOS duration=29µs；流式10µs粒度不能替代duration。EOS时钟源仍local，未在本轮对时；UTC表示设备配置时区，不表示绝对UTC精度。网页最终按用户要求取消摘要卡与折叠，逐条显示采集器保留的全部80条记录，最新在上，每行使用自己的队列长度与时刻；无配对、合并、去重或接口/TC筛选。字段为缓冲段大小、队列长度与TC，脚注说明E的最大值含义。

现场临时交换机配置、TRex网卡与网页资产恢复通过；当前网页基线已含修复。UI部署 `20260917T004236Z-lanz-raw-list` 后，实际Chromium打开8088，80行与API逐条匹配，包含80/84/86等值；摘要与折叠已移除，刷新保持滚动位置，无横向溢出。UI核验使用同一实跑保留记录，未重发流。终端仅调整一句展示范围说明，保留原两行节选；当前格式器对同一RUN重放输出存于 `raw-list/result-display.txt`。新RUN原始证据仍在reports；Git耐久的小型原件、截图与核验位于 `refs/evidence/lanz-display-fix-20260917/`。不覆盖旧RUN或其它章节的性能结论。
