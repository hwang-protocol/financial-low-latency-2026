# 第 07 章现役机制图

## 2026-09-19 · Offloaded XDP 产品卡

`07-netronome-agilio-cx-2x25gbe.jpg` 为 Netronome 产品资料 https://netronome.com/pb_agilio_cx_2x25gbe-3-24/ 第1页内嵌JPEG直接提取，619×425，未裁切或重绘；正文最大宽320px。来源产品编号 ISA-4000-25-2-2，版权归厂商。Agilio CX卸载能力依据 https://github.com/Netronome/bpf-samples 与厂商BPF固件说明，需匹配驱动/固件及支持的程序特性。本课未对此卡实测。

## 2026-09-19 · eBPF 技术开场原图

用户提供的 `image.png` 按原字节归档为 `07-ebpf-capabilities-overview.png`（991×497），用于章首介绍网络、安全、可观测性与追踪三类用途及用户态/内核层次。未裁剪或重绘，正文最大显示宽度800px；两级SHA256清单已登记。

## 2026-09-17 · 三个行业案例合为同一张 SVG

按用户最终要求，直接重画 `07-xdp-real-world-cases.svg`：上方蓝色EPAM/Deltix测量FIX请求到首个响应的时延，中间橙色Cloudflare L4Drop过滤攻击，下方绿色Meta Katran分配连接。正文不增加单独金融图或长篇案例，仍引用13处图片；同源PNG用于显示，点击进入SVG。

SVG为1200×1400，Noto字体，统一12×12箭头、尾部参考点、尖端距目标框12px；800/1200px已完整渲染目视，无文字溢出，1600px导出PNG。图仅说明机制，A123为示意订单标识，无实测性能数字。依据[EPAM工具](https://github.com/epam/ebpf-fix-latency-tool)、[Deltix入口](https://ember.deltixlab.com/docs/tools/latency-tool/)、下方已登记的Cloudflare/Meta公开资料；金融案例使用TC，其他两例使用XDP。原图其余历史记录保留。

## 2026-09-17 · 阅读顺序调整，图件字节保持

后续按用户反馈，将 `07-parser-safety-and-policy.png` 及图卡移到运行②绿色入口紧前，按“先看结构 → 运行 → 对照源码”阅读；仍为13处图片，图件字节不变。

装载/收包图前移至准备A术语表之前，map图移到BLOCK与额度首次讲解之前；运行②③④三张当前步骤高亮图继续保留。内核分层PPT图与07～09执行位置对照图转为教师说明中的补充链接，正文图片引用15→13。全部SVG/PNG及生成脚本保持原字节；本轮不重新渲染图，也不提高实机验证状态。

## 2026-09-17 · 源码、编译、装载三步命令卡

新增 `07-xdp-workflow-2/3/4.svg` 与同源 PNG，由 `generate-xdp-workflow.py` 统一生成三种当前步骤高亮。运行②、③、④分别显示绿色当前卡；每张卡先列任务，再列 `nl`、`clang` / `llvm-objdump`、`ip` 核心命令。图中命令按源码所在目录书写；实际绿色入口负责执行。运行④先重新编译当前源码，再装载本次对象，图中不展开复制与留档。

图件 1200×966，正文按 800px 显示；原生 SVG 为编辑源，PNG 用本地 Chromium 与 Noto 字体导出。800/1200px 三种状态均已渲染目视，文字边界与两根箭头检查通过：统一 12×12 箭头，尾部参考点，尖端距下张卡 12px。本轮正文由 12 个图片引用变为 15 个，旧图字节保持。两级摘要同步；仅文档与图示，未编译、挂载或运行课程实验。

命令依据为 `assets/07-xdp/03-xdp-parser-bounds.sh`、`04-xdp-build.sh`、`live-support/run-xdp-receiver-live.sh` 和 `live-support/xdp-session.py`。编译卡省略脚本的调试路径归一化选项，保留影响教学的编译参数；装载对象以文件名表示脚本工作目录内的同一文件。原理依据：[Clang 参数](https://clang.llvm.org/docs/CommandGuide/clang.html)、[BTF](https://docs.kernel.org/bpf/btf.html)、[libbpf 装载与挂接](https://docs.kernel.org/bpf/libbpf/libbpf_overview.html)。

## 2026-09-14 · 实跑丢包与网页手动恢复截图

用户提供的两张截图按原字节改名归档，分别嵌入运行④输出之后、运行⑤网页操作之后。正文共12个图片引用，保留终端关键5行并压缩重复解释；⑤改为用户点击“重新开始并清空交易”，服务重启脚本只留教师备用。

| 文件 | 来源及可见结果 |
| --- | --- |
| `07-xdp-feed-gap-held-20260914.png` | 原 `image.png`，1886×950；FEED GAP、next_expected626、pending237、gap_size1、已持续42012ms，第7轮暂停、订单簿灰显。对应用户RUN `20260914T033315.701914816Z-07-xdp-drop`。 |
| `07-xdp-feed-restored-20260914.png` | 原 `screenshot_20260914_114745_20260914_114800_421542.png`，1886×954；用户手动恢复后，红条消失、行情ONLINE、第8轮播放、订单簿恢复。按钮标注来自用户原图。 |

两图只证明可见界面状态；恢复后的API读数、试单成交和再次丢包接续尚未实测核验。源PNG与归档PNG摘要一致，未裁切、重绘或修改标注；[证据记录](../../../refs/evidence/chapter07-drop-held-live-20260914.json)包含完整SHA与来源。

## 2026-09-14 · 删除打印样例步骤，配图随源码前移

PASS/DROP 动作图、共用 ITCH 字段图、map 图及程序判断图统一归入运行②“查看 C 源码与过滤规则”；后续为③编译、④丢包、⑤手动重启。正文仍有10个图片引用，图文件与摘要保持；下方历史条目沿用当时运行编号。

## 2026-09-14 · 丢包与手动重启分开

学生正文撤下 `07-live-steps-and-evidence.png`，改用内嵌 Mermaid 表达“丢包→停下来观察网页→手动重启”；原 SVG/PNG 和摘要保持，仅供教师说明中的历史链接追溯。现役正文共 10 个图片引用；本轮没有修改图文件字节，新分步脚本尚未在设备上完整实跑。

## 2026-09-12 · 现役第07章

本目录由原第08章前移，现役图文件与链接采用新编号；下方历史条目保留原日期和验证身份。本轮未新增设备实验。

## 2026-09-10 · 当前共图：六类型各一条

本章过滤位置直接嵌入 `../03-diagrams/03-itch-type-strips.svg`（1200×1350），与第3/8/9/10章完全同源。六种类型各一条，字段在条内横向分格；本章只匹配A行，图卡已明确。旧 `03-market-packet-fields.svg` 不再被本章引用，下方登记为上一版历史。800/1200px及桌面/手机实际嵌入核验通过；本目录图片字节不变，共图由03-diagrams及总目录SHA登记，不升级实机结论。

## 2026-09-10 · 过滤位置直接嵌入共用字段图

本章在讲解过滤字段处直接显示 `../03-diagrams/03-market-packet-fields.svg`（现为1200×1624），与第三、八、九、十章引用同一文件，不维护副本，也不只留跳转链接。Type/Locate/Stock 黄色标记与本章源码一致；是否丢包和额度仍由本章规则说明。共图800/1200px及桌面/手机嵌入验收见03-diagrams最新条目。本目录原图字节不变；共图SHA由03-diagrams与总清单登记，不提高本章实机验证等级。下方不同尺寸或“仅链接”的描述为历史状态。

## 2026-09-10 · 与第三章共用行情字段图

第八章运行②改引 `../03-diagrams/03-market-packet-fields.svg`（1200×1400），与第三章使用相同文件；第九、十章同源链接。只画协议层与 Type A 字段位置，BLOCK、额度与有效期继续在第八章规则段和程序判断图说明，不属于线上字段。800/1200px Chrome 渲染、真实归档字节与 XDP/P4/RTL 取字段核对见第三章图册本日记录。第八章图数仍 11。

原 `07-shared-filter-wire.svg/.png` 均保留原字节与摘要，但退出学生正文；下方使用范围为历史记录。本目录没有图片字节变化，新共用图摘要由 03-diagrams 与总清单登记。

## 2026-09-08 · DEC-393 统一流量与端口

本轮更新：`07-shared-filter-wire.svg`。控制器归属 `.2`，行情由一个普通 Socket 接收后本机分发；组播 `233.74.125.32:31032`、单播 `.2:42121`。生产案例仅用官方公开端点，中间路由器为机制示意。本地无 PIM/RP 配置。800/1200px 渲染检查；历史抓包与旧性能图保留原始字节及其出处。


2026-09-05 DEC-347：新增`07-xdp-real-world-cases.svg/.png`替换行业主线AF_XDP图，以Cloudflare L4Drop防攻击、Meta Katran为VIP连接选择后端说明真实价值。AF_XDP图不删，转补充链接。SVG1200×1100/PNG1600×1467，静态Noto/resvg导出、800px目视无溢出。依据[Cloudflare2018 L4Drop](https://blog.cloudflare.com/l4drop-xdp-ebpf-based-ddos-mitigations/)、[2021防护流程](https://blog.cloudflare.com/deep-dive-cloudflare-autonomous-edge-ddos-protection/)与[Meta2018 Katran](https://engineering.fb.com/2018/05/22/open-source/open-sourcing-katran-a-scalable-network-load-balancer/)，本日在线复核。图只示意入站处理，不是厂商当前部署全图/性能复现；规则生成与map边界见教师说明。正文仍11图（8PNG+3SVG），目录23图片文件。

2026-09-05 DEC-346：新增`07-af-xdp-explained.svg/.png`替换行业节旧`07-26-af-xdp-resource-contract.png`，原图留参考。先画同一类以太网/IP/UDP/行情帧，再对照PASS后应用拿到UDP载荷与REDIRECT/AF_XDP应用拿到完整帧，不展开UMEM/ring资源结构。SVG1200×920、PNG1600×1227；静态Noto/resvg导出、800px目视清楚无溢出。依据[Linux AF_XDP文档](https://docs.kernel.org/networking/af_xdp.html)，2026-09-05在线核对；仅概念示意，不是数据包复制、实机截图或零拷贝测试。正文仍11图（8PNG+3SVG），目录21图片文件。

2026-09-05 DEC-349 精修：运行⑤图和正文统一采用084150Z证据（Sequence756），七步输出保留，PNG重新渲染。

2026-09-05 DEC-345 补图（证据现按DEC-349更新）：新增`07-live-steps-and-evidence.svg/.png`，以七步流程把运行⑤自动操作与输出配对，核心框强调XDP丢1包且sequence756、Feed gap_size1且next_expected756；注明历史示例。本图依据115行`run-xdp-receiver-live.sh`与`reports/course-runs/20260905T084150Z-08-xdp-receiver-live/raw/`逐字段核对，不是本次设备结果。SVG1200×1450、PNG1600×1934；静态Noto/resvg按下述方法导出，800px目视文字不出框。正文撤重复结果表，最终11图（8PNG+3SVG），目录19图片文件。

2026-09-05 DEC-345：按用户要求压缩运行⑤，`07-maps-and-one-shot.svg`与`07-17-netdev-program-map-chain.png`退出学生正文，保留原文件供教师参考；维护解释移至`assets/07-xdp/TEACHER-LIVE-NOTES.md`。没有改图或设备状态，当前正文10图（7PNG+3SVG），目录仍17个图片文件。

2026-09-05 DEC-344：新增 `07-parser-safety-and-policy.svg/.png`，用双阶段流程替换运行③PPT07：加载时Verifier强制安全审核；挂载后parser读边界/范围/格式，再匹配证券与一次性开关。框内真实C条件摘录配中文，代码词典解释变量；不是完整可编译代码或实测截图。SVG1200×1530、PNG1600×2040，800px目视无裁切/重叠。依据[Linux Verifier](https://docs.kernel.org/bpf/verifier.html)与现役`flle_xdp_mold_itch.c`，同日在线/源码核对。渲染沿用下方静态Noto字库与resvg命令。

2026-09-05 DEC-343 释义补充：报文图明确Stock字符/空格各1B，NVDA加4空格填满8B；Locate标为行情内部编号，当日固定、跨交易日可能重新分配。图尺寸及引用数量不变。

2026-09-05 DEC-343：重画 `07-shared-filter-wire.svg`，新增同源 `07-shared-filter-wire.png`，正文前移至运行②、运行③回指。完整Type A字段按顺序排布，中文解释MoldUDP64信封/ITCH消息，橙色突出筛选字段并分开包内字段与主机开关。SVG为1200×1550，PNG为1600×2067；本课固定无VLAN/IPv4无选项/单消息布局，不是抓包截图。800px目视无裁切，字重清晰。源依据为[Nasdaq ITCH5.0](https://www.nasdaqtrader.com/content/technicalsupport/specifications/dataproducts/NQTVITCHSpecification.pdf)和[MoldUDP64](https://nasdaqtrader.com/content/technicalsupport/specifications/dataproducts/moldudp64.pdf)，于本日在线复核；规则以`assets/07-xdp/flle_xdp_mold_itch.c`为准。绘图不代表重新运行策略。

2026-09-05 DEC-340：图首新增“未挂载XDP的普通收包”基线，再对照主动挂载Native/Generic的位置；原生指驱动入口，通用指适配范围。Offloaded标明本课X2522 + sfc 6.1.0.1009组合不支持（固定源码核验）。当前PNG为1600×1467，SVG为1200×1100；800px目视通过。既有1600×1227是DEC-339前版尺寸。模式图PNG继续作为正文显示，图数不变。

2026-09-05 显示兼容修复：用户阅读器未加载模式SVG；本地路径/XML/resvg正常，阅读器侧具体原因待确认。正文现引用同源导出的1600×1227 PNG，保持800px显示宽度，SVG仅保留为可编辑源。PNG本地打开及图片引用检查通过，用户阅读器刷新后的显示待确认。

2026-09-05 DEC-338：新增 `07-xdp-modes-and-skb.svg`，三行独立对照 Native XDP（Driver）、Generic XDP（SKB）与 Offloaded XDP（Offload）；突出 `.2 X2522 / ens64np1 / sfc`，显示 DMA、XDP、建立 skb 的先后及 PASS/DROP 去向。skb 定义为主机内的包处理记录，报文字节位于关联缓冲区。图为概念示意，不是设备实测截图。

2026-09-05 DEC-333：第08章改为客户端 `.2` 的 native XDP；装载/RX 图的 PASS 终点改成行情程序，横向比较图明确 `.2` 驱动。两图已在 800 px 渲染复核，图数不变；PPT 原图与 map 解释保留。

> 更新：2026-09-05 · DEC-327 / DEC-329 / DEC-330 / DEC-332 · DOC/FIGURE-ONLY

面向网络工程师：图先讲位置、流向与职责，正文就近解释系统和硬件术语。新增 SVG 是教学机制图/硬件设计图，不是实测截图。

| 文件 | 用途与边界 |
| --- | --- |
| `07-04-xdp-action-exits.png` | 四种常用业务动作；ABORTED 错误动作由正文补充 |
| `07-11-verifier-load-gate.png` | 保留参考；正文由原课件验证流程图替换，未删除 |
| `07-17-netdev-program-map-chain.png` | 接口/程序/map身份；DEC-345退出正文，教师参考保留 |
| `07-26-af-xdp-resource-contract.png` | 原资源结构图；DEC-346退出正文，保留参考 |
| `07-af-xdp-explained.png` / `.svg` | 同包两种收法；DEC-347转补充链接，保留文件 |
| `07-xdp-real-world-cases.png` / `.svg` | Cloudflare防攻击与Meta负载均衡：问题、流向与业务价值 |
| `07-ebpf-load-and-xdp-rx.svg` | 装载与逐包执行两条时间线 |
| `07-xdp-modes-and-skb.png` / `.svg` | 先画无XDP普通收包，再比较Native/Generic/Offloaded；本课明确选Native |
| `07-shared-filter-wire.png` / `.svg` | 整包→行情信封→Type A九字段；筛选字段、包外开关和读取边界 |
| `07-what-is-a-map.svg` | 首次解释 map：内核共享表，格子写规则和账本 |
| `07-maps-and-one-shot.svg` | 共享额度/审计/逐核计数；DEC-345退出正文，教师参考保留 |
| `07-09-execution-comparison.svg` | XDP、P4 软件、Arista FPGA、FPGA 网卡横向对比 |
| `07-ppt-s04-kernel-layers.png` | 原课件第4页 image111：应用/内核/硬件分层，正文聚焦网络列 |
| `07-ppt-s06-hook-overview.png` | 原课件第6页 image114：Hook 能力概览；正文限定本课 native XDP 在主机 CPU |
| `07-ppt-s07-verifier-jit.png` | 原课件第7页保留参考；DEC-344退出正文，原文件未改 |
| `07-parser-safety-and-policy.png` / `.svg` | 装载审核与逐包判定分开；框内C摘录、中文和PASS/DROP箭头 |
| `07-live-steps-and-evidence.png` / `.svg` | 七步脚本操作与对应输出；丢包计数/序号、Feed GAP互证及恢复 |

本目录保留 23 个图片文件（含模式图、报文图、审核流程图、实机步骤图、AF_XDP补充图、真实案例图的 SVG 源与 PNG 显示版）；正文实际引用 11 张（8 PNG + 3 SVG）。`07-xdp-modes-and-skb.svg` 与 `07-what-is-a-map.svg` 已做 1200/800 px 带 Noto 审图；其余 SVG 维持此前复核。三张课件 PNG 已检查原尺寸和 800 px 显示。摘要见本目录及上级 `SHA256SUMS`。

模式图资料于 2026-09-05 在线复核：[Linux sk_buff](https://docs.kernel.org/networking/skbuff.html) 说明元数据与关联缓冲区；[Cilium XDP](https://docs.cilium.io/en/latest/reference-guides/bpf/progtypes/#xdp) 说明三种模式与 Native PASS 后分配 skb；[xdp-tools xdpdump](https://github.com/xdp-project/xdp-tools/tree/main/xdp-dump) 说明 native/skb/hw 别名和 XDP 层抓包边界。环境身份沿用 DEC-333 的既有验证，本次未重新挂载或运行设备。

## 本课驱动支持边界（2026-09-05源码核验）

固定OpenOnload revision `9f330e7058f6062596f2a7316952c67963a0aac3`，`net_driver.h:95`定义`6.1.0.1009`；`efx.c:1673`将`ndo_bpf`接到`efx_xdp`，`xdp.c:417–455`只实现普通程序设置/查询及XSK设置，无`XDP_SETUP_PROG_HW`，未知命令`-EINVAL`；`xdp.c:664`调用`bpf_prog_run_xdp`。这支持“当前卡+驱动组合不提供XDP硬件卸载”，不推断网卡未来固件能力。

[上游固定源码](https://github.com/Xilinx-CNS/onload/blob/9f330e7058f6062596f2a7316952c67963a0aac3/src/driver/linux_net/drivers/net/ethernet/sfc/xdp.c)已在线复核；本地从`artifacts/blobs/x2522/onload/v9.0.2/onload-9f330e7-vm-2522-01.tgz`核对同名源码，archive SHA=`998d218db3733d85e3732f56790eca963f24deb05c6da4306d4dd9ab0c29d9e2`，`xdp.c` SHA=`e6ff5a960bb886c7ad4925a05dda670a9d1b119e1d2ca5bc20a8043d23b98d76`。没有现场尝试`xdpoffload`。本课`live-support/xdp-session.py:71`显式`xdpdrv`；[ip-link手册](https://man7.org/linux/man-pages/man8/ip-link.8.html)确认禁止回退Generic。

## 课件来源与筛选

原件为用户提供的 `19.eBPF.pptx`，7 页，SHA-256=`a69fd93245053c6fce3a3858c9a73e121f6cf856ea25fcf3fde640f05a20893d`。三张图分别逐字节提取自 ZIP 中 `ppt/media/image111.png`、`image114.png`、`image115.png`，未裁剪、重画或改动 PPT；课件标注的公开参考为 https://ebpf.io/what-is-ebpf/ 。

第3页生态图信息过多，第4页内核修改方案以文字为主，第5页 execve/代码图会引出另一组实验，均不进入当前主线。PPT 第2页内部项目链接未访问，附件不作为命令执行依据。理论只补读图提示并压缩原表格，不新增导航或实验。

原 DEC-275 删除的失真旧协议/接口/RUN 图不恢复；本轮不删除既有图片。

## 报文图再生成

SVG为可编辑源；使用resvg，加载Noto Sans CJK SC的静态Regular/Bold OTF（公开源：notofonts/noto-cjk的Sans/OTF/SimplifiedChinese目录），`--skip-system-fonts --width 1600`导出PNG，另以`--width 800`导出审图。用两次`--use-font-file`指定字库；本图未使用AI位图生成。Stock示例里的中点代表实际的ASCII空格，不是报文字节本身。
