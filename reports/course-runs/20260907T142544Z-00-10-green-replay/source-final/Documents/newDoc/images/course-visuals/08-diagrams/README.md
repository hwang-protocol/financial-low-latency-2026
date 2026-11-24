# 第08章现役机制图

2026-09-05 DEC-347：新增`08-xdp-real-world-cases.svg/.png`替换行业主线AF_XDP图，以Cloudflare L4Drop防攻击、Meta Katran为VIP连接选择后端说明真实价值。AF_XDP图不删，转补充链接。SVG1200×1100/PNG1600×1467，静态Noto/resvg导出、800px目视无溢出。依据[Cloudflare2018 L4Drop](https://blog.cloudflare.com/l4drop-xdp-ebpf-based-ddos-mitigations/)、[2021防护流程](https://blog.cloudflare.com/deep-dive-cloudflare-autonomous-edge-ddos-protection/)与[Meta2018 Katran](https://engineering.fb.com/2018/05/22/open-source/open-sourcing-katran-a-scalable-network-load-balancer/)，本日在线复核。图只示意入站处理，不是厂商当前部署全图/性能复现；规则生成与map边界见教师说明。正文仍11图（8PNG+3SVG），目录23图片文件。

2026-09-05 DEC-346：新增`08-af-xdp-explained.svg/.png`替换行业节旧`08-26-af-xdp-resource-contract.png`，原图留参考。先画同一类以太网/IP/UDP/行情帧，再对照PASS后应用拿到UDP载荷与REDIRECT/AF_XDP应用拿到完整帧，不展开UMEM/ring资源结构。SVG1200×920、PNG1600×1227；静态Noto/resvg导出、800px目视清楚无溢出。依据[Linux AF_XDP文档](https://docs.kernel.org/networking/af_xdp.html)，2026-09-05在线核对；仅概念示意，不是数据包复制、实机截图或零拷贝测试。正文仍11图（8PNG+3SVG），目录21图片文件。

2026-09-05 DEC-349 精修：运行⑤图和正文统一采用084150Z证据（Sequence756），七步输出保留，PNG重新渲染。

2026-09-05 DEC-345 补图（证据现按DEC-349更新）：新增`08-live-steps-and-evidence.svg/.png`，以七步流程把运行⑤自动操作与输出配对，核心框强调XDP丢1包且sequence756、Feed gap_size1且next_expected756；注明历史示例。本图依据115行`run-xdp-receiver-live.sh`与`reports/course-runs/20260905T084150Z-08-xdp-receiver-live/raw/`逐字段核对，不是本次设备结果。SVG1200×1450、PNG1600×1934；静态Noto/resvg按下述方法导出，800px目视文字不出框。正文撤重复结果表，最终11图（8PNG+3SVG），目录19图片文件。

2026-09-05 DEC-345：按用户要求压缩运行⑤，`08-maps-and-one-shot.svg`与`08-17-netdev-program-map-chain.png`退出学生正文，保留原文件供教师参考；维护解释移至`newDoc/assets/08-xdp/TEACHER-LIVE-NOTES.md`。没有改图或设备状态，当前正文10图（7PNG+3SVG），目录仍17个图片文件。

2026-09-05 DEC-344：新增 `08-parser-safety-and-policy.svg/.png`，用双阶段流程替换运行③PPT07：加载时Verifier强制安全审核；挂载后parser读边界/范围/格式，再匹配证券与一次性开关。框内真实C条件摘录配中文，代码词典解释变量；不是完整可编译代码或实测截图。SVG1200×1530、PNG1600×2040，800px目视无裁切/重叠。依据[Linux Verifier](https://docs.kernel.org/bpf/verifier.html)与现役`flle_xdp_mold_itch.c`，同日在线/源码核对。渲染沿用下方静态Noto字库与resvg命令。

2026-09-05 DEC-343 释义补充：报文图明确Stock字符/空格各1B，NVDA加4空格填满8B；Locate标为行情内部编号，当日固定、跨交易日可能重新分配。图尺寸及引用数量不变。

2026-09-05 DEC-343：重画 `08-shared-filter-wire.svg`，新增同源 `08-shared-filter-wire.png`，正文前移至运行②、运行③回指。完整Type A字段按顺序排布，中文解释MoldUDP64信封/ITCH消息，橙色突出筛选字段并分开包内字段与主机开关。SVG为1200×1550，PNG为1600×2067；本课固定无VLAN/IPv4无选项/单消息布局，不是抓包截图。800px目视无裁切，字重清晰。源依据为[Nasdaq ITCH5.0](https://www.nasdaqtrader.com/content/technicalsupport/specifications/dataproducts/NQTVITCHSpecification.pdf)和[MoldUDP64](https://nasdaqtrader.com/content/technicalsupport/specifications/dataproducts/moldudp64.pdf)，于本日在线复核；规则以`assets/08-xdp/flle_xdp_mold_itch.c`为准。绘图不代表重新运行策略。

2026-09-05 DEC-340：图首新增“未挂载XDP的普通收包”基线，再对照主动挂载Native/Generic的位置；原生指驱动入口，通用指适配范围。Offloaded标明本课X2522 + sfc 6.1.0.1009组合不支持（固定源码核验）。当前PNG为1600×1467，SVG为1200×1100；800px目视通过。既有1600×1227是DEC-339前版尺寸。模式图PNG继续作为正文显示，图数不变。

2026-09-05 显示兼容修复：用户阅读器未加载模式SVG；本地路径/XML/resvg正常，阅读器侧具体原因待确认。正文现引用同源导出的1600×1227 PNG，保持800px显示宽度，SVG仅保留为可编辑源。PNG本地打开及图片引用检查通过，用户阅读器刷新后的显示待确认。

2026-09-05 DEC-338：新增 `08-xdp-modes-and-skb.svg`，三行独立对照 Native XDP（Driver）、Generic XDP（SKB）与 Offloaded XDP（Offload）；突出 `.2 X2522 / ens64np1 / sfc`，显示 DMA、XDP、建立 skb 的先后及 PASS/DROP 去向。skb 定义为主机内的包处理记录，报文字节位于关联缓冲区。图为概念示意，不是设备实测截图。

2026-09-05 DEC-333：第08章改为客户端 `.2` 的 native XDP；装载/RX 图的 PASS 终点改成行情程序，横向比较图明确 `.2` 驱动。两图已在 800 px 渲染复核，图数不变；PPT 原图与 map 解释保留。

> 更新：2026-09-05 · DEC-327 / DEC-329 / DEC-330 / DEC-332 · DOC/FIGURE-ONLY

面向网络工程师：图先讲位置、流向与职责，正文就近解释系统和硬件术语。新增 SVG 是教学机制图/硬件设计图，不是实测截图。

| 文件 | 用途与边界 |
| --- | --- |
| `08-04-xdp-action-exits.png` | 四种常用业务动作；ABORTED 错误动作由正文补充 |
| `08-11-verifier-load-gate.png` | 保留参考；正文由原课件验证流程图替换，未删除 |
| `08-17-netdev-program-map-chain.png` | 接口/程序/map身份；DEC-345退出正文，教师参考保留 |
| `08-26-af-xdp-resource-contract.png` | 原资源结构图；DEC-346退出正文，保留参考 |
| `08-af-xdp-explained.png` / `.svg` | 同包两种收法；DEC-347转补充链接，保留文件 |
| `08-xdp-real-world-cases.png` / `.svg` | Cloudflare防攻击与Meta负载均衡：问题、流向与业务价值 |
| `08-ebpf-load-and-xdp-rx.svg` | 装载与逐包执行两条时间线 |
| `08-xdp-modes-and-skb.png` / `.svg` | 先画无XDP普通收包，再比较Native/Generic/Offloaded；本课明确选Native |
| `08-shared-filter-wire.png` / `.svg` | 整包→行情信封→Type A九字段；筛选字段、包外开关和读取边界 |
| `08-what-is-a-map.svg` | 首次解释 map：内核共享表，格子写规则和账本 |
| `08-maps-and-one-shot.svg` | 共享额度/审计/逐核计数；DEC-345退出正文，教师参考保留 |
| `08-10-execution-comparison.svg` | XDP、P4 软件、Arista FPGA、FPGA 网卡横向对比 |
| `08-ppt-s04-kernel-layers.png` | 原课件第4页 image111：应用/内核/硬件分层，正文聚焦网络列 |
| `08-ppt-s06-hook-overview.png` | 原课件第6页 image114：Hook 能力概览；正文限定本课 native XDP 在主机 CPU |
| `08-ppt-s07-verifier-jit.png` | 原课件第7页保留参考；DEC-344退出正文，原文件未改 |
| `08-parser-safety-and-policy.png` / `.svg` | 装载审核与逐包判定分开；框内C摘录、中文和PASS/DROP箭头 |
| `08-live-steps-and-evidence.png` / `.svg` | 七步脚本操作与对应输出；丢包计数/序号、Feed GAP互证及恢复 |

本目录保留 23 个图片文件（含模式图、报文图、审核流程图、实机步骤图、AF_XDP补充图、真实案例图的 SVG 源与 PNG 显示版）；正文实际引用 11 张（8 PNG + 3 SVG）。`08-xdp-modes-and-skb.svg` 与 `08-what-is-a-map.svg` 已做 1200/800 px 带 Noto 审图；其余 SVG 维持此前复核。三张课件 PNG 已检查原尺寸和 800 px 显示。摘要见本目录及上级 `SHA256SUMS`。

模式图资料于 2026-09-05 在线复核：[Linux sk_buff](https://docs.kernel.org/networking/skbuff.html) 说明元数据与关联缓冲区；[Cilium XDP](https://docs.cilium.io/en/latest/reference-guides/bpf/progtypes/#xdp) 说明三种模式与 Native PASS 后分配 skb；[xdp-tools xdpdump](https://github.com/xdp-project/xdp-tools/tree/main/xdp-dump) 说明 native/skb/hw 别名和 XDP 层抓包边界。环境身份沿用 DEC-333 的既有验证，本次未重新挂载或运行设备。

## 本课驱动支持边界（2026-09-05源码核验）

固定OpenOnload revision `9f330e7058f6062596f2a7316952c67963a0aac3`，`net_driver.h:95`定义`6.1.0.1009`；`efx.c:1673`将`ndo_bpf`接到`efx_xdp`，`xdp.c:417–455`只实现普通程序设置/查询及XSK设置，无`XDP_SETUP_PROG_HW`，未知命令`-EINVAL`；`xdp.c:664`调用`bpf_prog_run_xdp`。这支持“当前卡+驱动组合不提供XDP硬件卸载”，不推断网卡未来固件能力。

[上游固定源码](https://github.com/Xilinx-CNS/onload/blob/9f330e7058f6062596f2a7316952c67963a0aac3/src/driver/linux_net/drivers/net/ethernet/sfc/xdp.c)已在线复核；本地从`artifacts/blobs/x2522/onload/v9.0.2/onload-9f330e7-vm-2522-01.tgz`核对同名源码，archive SHA=`998d218db3733d85e3732f56790eca963f24deb05c6da4306d4dd9ab0c29d9e2`，`xdp.c` SHA=`e6ff5a960bb886c7ad4925a05dda670a9d1b119e1d2ca5bc20a8043d23b98d76`。没有现场尝试`xdpoffload`。本课`live-support/xdp-session.py:71`显式`xdpdrv`；[ip-link手册](https://man7.org/linux/man-pages/man8/ip-link.8.html)确认禁止回退Generic。

## 课件来源与筛选

原件为用户提供的 `Documents/newDoc/19.eBPF.pptx`，7 页，SHA-256=`a69fd93245053c6fce3a3858c9a73e121f6cf856ea25fcf3fde640f05a20893d`。三张图分别逐字节提取自 ZIP 中 `ppt/media/image111.png`、`image114.png`、`image115.png`，未裁剪、重画或改动 PPT；课件标注的公开参考为 https://ebpf.io/what-is-ebpf/ 。

第3页生态图信息过多，第4页内核修改方案以文字为主，第5页 execve/代码图会引出另一组实验，均不进入当前主线。PPT 第2页内部项目链接未访问，附件不作为命令执行依据。理论只补读图提示并压缩原表格，不新增导航或实验。

原 DEC-275 删除的失真旧协议/接口/RUN 图不恢复；本轮不删除既有图片。

## 报文图再生成

SVG为可编辑源；使用resvg，加载Noto Sans CJK SC的静态Regular/Bold OTF（公开源：notofonts/noto-cjk的Sans/OTF/SimplifiedChinese目录），`--skip-system-fonts --width 1600`导出PNG，另以`--width 800`导出审图。用两次`--use-font-file`指定字库；本图未使用AI位图生成。Stock示例里的中点代表实际的ASCII空格，不是报文字节本身。
