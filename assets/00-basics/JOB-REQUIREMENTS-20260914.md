# 第 00 章岗位表：官方招聘要求与课程对应

2026-09-19课程对应更新：现役FPGA内容合并到第08章，以SystemVerilog关键逻辑、Vivado仿真、U250工程构建和交换机适配为主。第00章岗位表已同步；下方2026-09-14记录中的第09章/Verilator为当时版本，不代表现役目录。本轮未重新核验招聘网页。

核对日期：2026-09-14。正文：[哪些公司和岗位需要这类工程能力](../../00-cpu-cache-memory-os-basics.md#哪些公司和岗位需要这类工程能力)。

本记录用于维护岗位表：逐页打开公司官方岗位详情，核对标题、地点、职责、要求与申请入口。这里只保存短摘录和归纳，不复制完整招聘文案。页面可访问不保证此后仍开放申请；未注明发布日期的页面不补造日期，也不把搜索引擎抓取日期当作发布日期。正文对应章节由本课作者判断，不代表招聘方认可或指定本课程。

## 2026-09-14 · 课程知识直接写入岗位知识栏

用户要求即使招聘未点名，也将本课相关技术写进知识要求栏，并明确章节。正文第三列现为“岗位知识要求与本课补充（标注章节）”，分别标“招聘列出”与“本课补充”；网络岗位另保留“招聘必需 / 招聘加分”。最后一列只讲如何练习，避免重复列技术名。课程补充属于按职责所作的教学对应，不改变原岗位的硬性条件。

| 岗位 | 本课补充的知识 |
| --- | --- |
| 交易网络 | 第 05 章 Onload / TCPDirect / DPDK 收发与驱动；第 06 章 Cut-Through / LANZ / PTP / 时间戳；第 07 章 XDP 入口过滤 |
| 交易系统 | 第 00 章主机基础；第 03 章 ITCH/OUCH；第 04 章 SPSC、忙轮询、CPU 隔离；第 05 章 Onload / TCPDirect / DPDK + F-Stack；第 09 章 RTL 与软件配合 |
| C++ 交易执行 | 第 00 章缓存与内存；第 04 章交接队列与执行安排；第 05 章三种旁路接口与收发方式 |
| 交易性能 | 第 00 章等待来源；第 04 章计时、预热和 P50/P99；第 05 章三种旁路与受控比较；第 06 章对时与硬件时间戳 |
| FPGA | 第 03 章 ITCH 字段；第 09 章 RTL、Ready/Valid 与 Verilator；第 05 章的软件收发路径作为理解主机/网卡分工的补充 |

本轮再次读取宽德、IMC C++、IMC Performance 与 Optiver FPGA 四份官方岗位页，职责与上述对应方向相符；具体知识点逐项回到本课第 00、03～07、09 章核对。没有证据表明这些岗位全部必需 DPDK 或 TCPDirect，因此正文只把它们写在“本课补充”。FPGA 行不宣称第 09 章 RTL 实验使用了 DPDK / TCPDirect，也不宣称公司真卡采用本课软件方案。

## 正文采用的五个岗位

### 1. Trading Technologies：交易网络工程师

- [官方原文：Senior Network Engineer – EMEA Coverage](https://tradingtechnologies.com/job/senior-network-engineer-emea-coverage-563100/)，布拉格，全职资深岗位；页面含申请入口。
- 定位依据：负责行情与订单路径，覆盖组播交付、缺口与恢复、延迟和容量。必需技能与加分技能在原文中分列。
- 短摘录：`Kernel-bypass networking (Solarflare/Onload or similar)`。
- PTP、硬件时间戳、Onload 出现在 **Desirable** 项，正文必须保留“加分”身份；不能写成所有网络岗位的硬性要求。
- 本课对应第 01 章设备链路、第 02 章组播、第 05 章内核旁路、第 06 章队列与时间戳。课程实验不代表已具备跨地域生产网络设计经验。

### 2. 宽德量化：交易系统工程师

- [官方原文：交易系统工程师](https://www.wizardquant.com/career/%E4%BA%A4%E6%98%93%E7%B3%BB%E7%BB%9F%E5%B7%A5%E7%A8%8B%E5%B8%88)，全职，上海／其他；同页分别列校招与社招，提供申请方式。
- 短摘录：`Linux平台下低延迟系统`。
- 校招与社招均涉及软硬件基础，社招明确要求 5 年以上软件经验；不能将社招的“精通”和年限套给校招，也不能省略该岗位同时列出的 FPGA 要求。
- 第 00 章补主机基础，第 02～04 章分别对应交易系统运行、报文与并发；第 05 章补 Onload / TCPDirect / DPDK + F-Stack 收发，第 09 章提供 RTL 和软件模拟入门。PCIe/DMA 在第 00～01 章建立概念与设备对应，不宣称覆盖完整 PCIe 端点或 DMA 引擎开发。

### 3. IMC：C++ 交易执行开发

- [官方原文：C++ Software Engineer](https://www.imc.com/us/careers/jobs/4282973101)，孟买，岗位编号 `4282973101`，要求 4～8 年 C++ 工作经验；页面含申请入口。URL 中的 `us` 是网站地区路径，不是岗位地点。
- 短摘录：`latency, throughput, simplicity, scalability and maintainability`。
- 第 04 章的队列、忙轮询和 CPU 分配，第 05 章的网络出站对照，是上述性能权衡的课程练习。岗位页没有指定 SPSC、TCPDirect 或 DPDK，不能将本课实现写成招聘原文的必需技术栈。
- C++20、Linux 等在原文中属于团队技术环境；要求栏另列工作经验、计算机基础与沟通能力。

### 4. IMC：性能工程师

- [官方原文：Performance Engineer](https://www.imc.com/us/careers/jobs/4531501101)，悉尼，岗位编号 `4531501101`；页面含申请入口。
- 短摘录：`Most of the following will apply`。
- 原文将职责落在可观察的交易所连接与行情系统：统计实验、数据分析、原型验证；不是静态二进制或恶意代码分析。技能清单说明不要求每项都具备，FPGA 等硬件经历为加分项。
- 对应第 04 章计时边界与分位数、第 05 章受控比较、第 06 章网络测量。本课的小规模实验不等同于原文所需的大规模统计分析与生产代码交付经验。

### 5. Optiver：FPGA 开发实习生

- [官方原文：2027 Shanghai FPGA Developer Summer Internship](https://www.optiver.com/join-us/jobs/technology/shanghai/2027-shanghai-fpga-developer-summer-internship/)，上海，2027 暑期实习；页面含申请入口。
- 短摘录：`Masters or PhD Students`。
- 原文有明确毕业时间条件：2028 年或 2027 年 9 月之后毕业；正文提示读者按官网核对资格。不能将其改写为面向所有本科应届生的岗位。
- 工作涉及 RTL 与测试程序，要求数字逻辑、器件与开发工具、硬件描述语言，以及软件和网络基础。第 09 章对应 SystemVerilog 逻辑、握手、Verilator 自测与真实报文验证；真卡部分仍是模拟流程讲解，不是板卡实测。

## 本轮收紧筛选

按用户要求，正文只保留直接承担低延迟交易系统开发、交易网络建设、交易链路性能优化或硬件加速的岗位；删除表后的学习建议、求职补课和课程能力边界两段。四家公司、五个岗位，岗位原名与来源继续保留。

保留依据：Trading Technologies 明确建设低延迟交易网络；宽德明确在 Linux 下开发低延迟系统；IMC 的 C++ 职位处于交易执行的延迟关键环节，性能职位针对行情及交易所连接进行系统优化；Optiver 的 FPGA 实习直接面向交易硬件加速。性能岗位按其交易链路职责入选，不因通用职位名或硬件加分项入选。

以下两个岗位与交易基础设施有关，但这两份招聘的重心偏平台维护、部署和生产稳定性。为让本节集中说明直接的低延迟工程工作，移出正文；不据此声称 Linux 或生产运维与低延迟无关。二者在本轮再次打开官网复核，保留原核对记录供维护。

### Jane Street：Linux 系统工程师

- [官方原文：Linux Engineer](https://www.janestreet.com/join-jane-street/position/4276248002/)，纽约，岗位编号 `4276248002`；页面含申请入口，没有明确工作年数。
- 短摘录：`gdb, perf, DTrace, eBPF, or SystemTap`。
- 本课第 00 章讲操作系统基础，第 04 章观察线程交接与 CPU 分配。招聘中的 eBPF 用于排障与性能诊断；第 07 章的 XDP 报文过滤只提供相关机制入门，不能等同于该项工具能力。
- 原文还要求 Shell、系统编程与沟通能力，并愿意学习 OCaml；正文是技术要求节选，不是完整申请清单。

### Optiver：交易系统生产运维工程师

- [官方原文：Production Operations Engineer (Trading Systems / SRE / Application Support)](https://www.optiver.com/join-us/jobs/technology/shanghai/production-operations-engineer-trading-systems-sre-application-support/)，上海，Experienced；页面含申请入口。
- 短摘录：`high-frequency trading environments is a plus`。
- 第 02 章部署与业务核验、第 03 章请求回报抓包、第 07 章故障观察与恢复，提供理解交易应用的练习。原文另有持续集成、数据库、复杂分布式系统及值班支持要求。
- 高频交易经历在原文中不是必需条件；不能将该岗位归为只有量化交易员才能申请，也不能把课程手动恢复等同于完整生产运维训练。

## 维护边界

本次正文不再展开课程之外的求职能力要求。维护时仍须保持事实身份：招聘方没有指定本课程；第 07 章 XDP 过滤不是完整 eBPF 性能跟踪课程；第 09 章是软件模拟；本次保留的岗位没有明确要求 P4。不要为覆盖全部章节而添加职责关联弱的岗位。

原先另外核对的公司岗位与来源选择记录见前轮核验。此次只改文字、选取范围及登记，没有运行实验或操作设备。
