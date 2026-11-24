# 第06章课程图片集

## 2026-09-07 · DEC-377 全课顺稿配图

本轮新增下列原生 SVG，图标表示角色，保留旧图文件作历史审计。正文入口以本表为准；旧日期条目记录当时状态。

| 当前图 | 回答什么 | 替换的正文图 |
| --- | --- | --- |
| `06-four-path-roles.svg` | 四种收发方式的接口、TCP 实现与网卡归属 | `06-four-gates.svg`（已退出正文） |

依据为本章现役正文与配套实现；不包含新增运行读数或硬件实测。使用自绘文件、包裹、时钟、芯片、内存、队列等矢量图标。箭头遵硬规则 §3.3.3：本组固定 12×12 用户坐标头部、refX=0、2.5 线宽、butt 线帽，尖端与目标框至少间隔 12；无箭头的比较图不强加方向。800px 与 1200px 已逐张检查，修复缺字和标题越界。


> 生成日期：2026-08-23；当前主线重构并逐图复核：2026-09-02
> 生成方式：历史图使用Codex内置`imagegen`；当前主线新增仓库原生SVG  
> 使用位置：`Documents/newDoc/06-openonload-tcpdirect-dpdk-kernel-bypass.md`

## 当前正文主线（2026-09-02）

旧 37 张 PNG 与未被本轮正文引用的原生 SVG 全部保留作历史审计。按 DEC-208/214/215/218/222/223，当前第六章正文使用 11 张仓库原生 SVG；其中 4 张总览图负责全章关系，4 张同版式路径图分别紧邻运行 ①～④，计时图负责统一字段边界，模式切换图解释网页按钮与 curl 的同一 API，比较方法图解释四轮平衡采样与汇总：

| 文件 | 教学任务 |
| --- | --- |
| `06-four-gates.svg` | 章首：同一笔 SoupBinTCP/OUCH 订单对应四种本机 Transport；第四条同时更换 TCP 实现与设备所有权 |
| `06-guest-iommu-vfio-chain.svg` | 准备 B：用“仓库 / DMA 叉车 / 地址围栏”串起 ESXi I/O MMU、GRUB、Guest cmdline、IOMMU group 与 VFIO；强调 group 7 的数字只是本机标签，真正门闸是组内只有 X2522；unsafe no-IOMMU 明确拒绝 |
| `06-sfc-vs-vfio-data-path.svg` | 准备 B：把四路重新归纳成两类 owner；左侧 Kernel、Onload、TCPDirect 都保留 `sfc`，右侧 DPDK 独占走 F-Stack → `net_sfc_efx` PMD → `vfio-pci + IOMMU type 1`，下方单列管理面切换链并与单笔订单热路径分开 |
| `06-classroom-run-flow.svg` | 准备 D：把课堂收成四段纵向流程——A～C 各查一次、D 部署并启动一次、①～④各讲一路并下一笔、⑤统一预热和比较；只表达教学顺序，不承载性能或现场状态结论 |
| `06-order-timing-windows.svg` | 运行 ①～④之前：用提交、OUCH 发出、最终 Executed 三个时间点分开 `queue_to_send_ns` 与 `order_rtt_ns`，并用总括号说明两段之和为 `submit_to_final_ns` |
| `06-kernel-socket-path.svg` | 运行 ①：同一 OUCH 订单经 POSIX Socket、系统调用门、Linux TCP/IP、`sfc` 与 X2522 到 Exchange；底栏只保留标准易排障与热路径经过通用内核栈的取舍 |
| `06-onload-order-path.svg` | 运行 ②：同一 Trader 与 POSIX API 经 Onload 透明拦截进入用户态 TCP 和 VI/CTPIO；灰色支路明确建栈、异常和慢路径仍与 Linux 协作 |
| `06-tcpdirect-order-path.svg` | 运行 ③：显式 ZF API、主动 reactor、ZF 用户态 TCP 与 VI/CTPIO 串成主线；owner 仍为 `sfc`，线上协议不变 |
| `06-dpdk-fstack-order-path.svg` | 运行 ④：F-Stack TCP/IP、DPDK `net_sfc_efx` PMD、VFIO/IOMMU 与 X2522 独占连成主线；强调它同时更换 API、栈和 PCI owner |
| `06-dataplane-mode-switch.svg` | 运行 ④：网页按钮与课堂 curl 都走 `POST /api/data-plane`；后台是停客户端、`dpdk-devbind` 换 `sfc`/`vfio-pci`、再启动 |
| `06-balanced-comparison-method.svg` | 运行 ⑤：先固定订单与环境，再用 4×4 轮换顺序让四路各处于第 1～4 位一次；每格 100 笔预热、1000 笔正式采样，最后按路径四格等权汇总 |

37 张 PNG 全部退出正文并留盘审计。`06-four-real-order-paths.svg`、`06-tcpdirect-transport-adapter.svg`、`06-onload-runtime-three-piece.svg`、`06-tcpdirect-zf-hardware-path.svg` 与 `06-dpdk-fstack-owner-cpu.svg` 也保留为历史教学资产，但不再承担当前正文步骤。`06-31-pci-owner-state-machine.png` 是曾用于运行 ④ 的 VFIO/UIO 通用图，现由课程专用 SVG 替换；`06-kernel-loopback-syscall-sequence.svg` 也退出主线，因为真实 Kernel Socket 下单已经承担基线入口。`06-13-onload-path-selection.png` 继续退役，因为它容易把“PCI function 仍绑定 `sfc`”误读成“加速包仍逐包穿过普通 netdev 热路径”。

## 后续路径图怎样继承这张母版

`06-kernel-loopback-syscall-sequence.svg` 同时是后续路径图的视觉母版，但不要求后续实验仍是本机 loopback。复制成新文件后保持以下结构，使学员能一眼看出“哪里没有变、哪里换了”：

| SVG 分组 | 固定职责 | 后续怎样改 |
| --- | --- | --- |
| `lane-frame` | 左边调用者、中间执行路径、右边接收者的三栏位置 | 保持栏位、颜色层级和标题位置；按真实实验重命名参与者 |
| `server-listen` / `connection-setup` | 监听与建连 API、必要先后和各调用职责 | Onload 保留 socket API；TCPDirect 换成 ZF API；DPDK 换成端口/队列动作 |
| `request-path` / `ack-path` | 请求与回复真正经过的运行时和数据路径 | 只画本轮真实经过的对象；远端实验必须把物理 NIC / 线缆 / 对端放在同一抽象层级 |
| `evidence-layer` | 本轮观察到的调用账与证据边界 | 只有新 RUN 已取证后才能改数字和结论 |

派生图继续使用相同编号圆点、蓝色请求箭头、绿色回复箭头和底部证据边界。所有用 `<path>` 画出的连线都必须显式写 `fill="none"`；否则浏览器会把折线路径首尾闭合并填成黑色多边形。不能直接在 Kernel 母版上覆盖事实；应复制成新文件，让各条路径留下可审计版本。当前真实交易主线已经由 `06-four-real-order-paths.svg` 接管；后续派生图必须继续保持 SoupBinTCP/OUCH 任务和对应 Transport 的真实层级。

`06-tcpdirect-transport-adapter.svg` 保留 `normal-posix-client`、`tcpdirect-adapted-client`、`broker-view`、`replacement-seam`、`adaptation-contract` 与 `course-evidence-boundary` 分组。当前图已经对应真实 `OrderTransport` / ZF 实现和真单 RUN；后续若替换交易协议或 Transport 接口，应复制新版本，不覆盖这份已经取证的结构。

## 统一视觉与证据合同

```text
16:9 clean white classroom slide; premium flat-isometric/vector technical
illustration; crisp navy outlines; cyan data/action, purple runtime/memory,
green verified evidence/recovery, orange ownership/interpretation, red only
for a genuine unavailable/unsafe branch; large English labels readable from
a classroom screen. No logos, watermarks, fabricated IPs, ports, PIDs, BDFs,
timestamps, hashes, packet counts, timing values or speed claims.
```

| 文件范围 | 教学任务 | 硬约束 |
| --- | --- | --- |
| `06-01`～`06-05` | 四条软件路径、统一测量合同、PCI所有权、章节路线与责任迁移 | 四条路径都有CPU；OS不消失；不做未实测性能排序 |
| `06-06`～`06-18` | Kernel syscall路径、Onload准备/清单/活连接/加载器与对照证据 | `strace`时间不是网络延迟；清单和`libonload.so`不是活流量证明；`Onloaded(Valid)`只归属于观察窗口内的具体socket |
| `06-19`～`06-26` | TCPDirect固定制品、ZF对象生命周期与四道就绪门 | SHA相同只证明字节一致；ELF只证明可装载形态；设备入口不等于业务流量；RUN 4只得出就绪性结论 |
| `06-27`～`06-29` | HugePage、TLB、DMA与`0→4→0`可逆生命周期 | 大页不保证延迟收益；必须先读零基线、注册恢复动作并证明回到零 |
| `06-30`～`06-37` | DPDK轮询/mbuf/队列所有权、BDF身份、IOMMU门禁、功能证据与总复盘 | 同一PCI功能所有权互斥；Guest 现有 group 7；课堂走 VFIO 真包走并交还；UIO 历史收据不写成当前延迟 |

## 人工返修与拒收记录

- `06-01`首稿擅自补入价格、数量、时间戳和交易所等行情字段，已拒收；最终版只保留已验证的`AAPL TICK · 52 BYTES`。
- `06-04`首稿用“all checks completed”收束，错误扩大了DPDK安全结论，已拒收；最终版明确拆成`FUNCTION: OBSERVED`与`IOMMU GROUP: ABSENT · NO VFIO SAFETY PROOF`。
- `06-06`首稿把`NEIGHBOR`拼错，已拒收；最终版删去不必要的内部小字并保留正确的Kernel POSIX主路径。
- `06-26`首稿擅自生成示例IP、时间戳和RUN ID，已拒收；最终版只保留四道门禁、空白收据图标和受限结论。
- `06-13`与`06-14`明确保留unsupported socket回落内核的分支，并限制`Onloaded(Valid)`只证明当时观察到的socket。
- `06-33`～`06-36`记录的是 2026-08-23 当时“Guest 无 IOMMU group”的历史图层，已退出正文。2026-08-31 本机后来写入 Guest cmdline 并得到 group 7；快照恢复又会回到无组状态。禁止把这些旧图重新当成本轮现场。
- 内置绘图服务在`06-13`和`06-29`生成时超过首轮等待窗口；均继续等待同一内置任务完成，没有改用外部图片或脚本占位。
- 按 DEC-20260831-140 返修 `06-four-gates.svg` 与 `06-exit-channel.svg`：删去「VIP 闸口 / 护照不用换」，快速通道改为自助机自己刷、认不了的退回窗口；四张卡末行统一为「闸：海关在管 / 闸：归你」，让「办手续」和「那道闸归谁」两层在同一张图里并排可见。禁止再用插队、特权、免检一类说法。
- 按 DEC-20260831-145 保留旅客 / 单子 / 出站闸骨架，但撤回“相邻始终只换一件”的过强图题：DPDK 同时换设备所有权和实验层级，底栏明确另用一把尺子；第四卡长句拆成两行短句，避免出框。
- 按 DEC-20260831-141 再修这两张 SVG：章首图改成「填哪张单子、谁来办」对「出站闸」；当时四扇门副标写过“相邻只换一件”，该句后来已由 DEC-145/146 撤回。继续禁止把专用柜台写成专用护照。
- 按 DEC-20260831-146 逐张核对正文实际引用的 6 张图：运行 ① 从会误读成物理 NIC 已经参与的 `06-06` 换成证据边界准确的 `06-07`；Onload 正文把不存在的“虚线”改成图中真实的灰色回退支路；DPDK 状态图明确是通用图，本轮只走 VFIO；两张 SVG 分别修正 06–08 阶段标签和 DPDK 的 L2 / 所有权双重变化。
- 2026-09-02 按用户反馈新增 `06-guest-iommu-vfio-chain.svg`。它只解释已经锁定的安全门闸，不改变脚本或设备现场；开机配置链和运行时 DMA 链分层，避免把 GRUB、IOMMU、group 与 VFIO 误读成同一个东西。
- 2026-09-02 继续按用户反馈新增 `06-sfc-vs-vfio-data-path.svg`。图不再把四路表现成同级平行 API，而是先按 PCI owner 分成 `sfc` 三路与 `vfio-pci` 一路；模式切换管理链和单笔订单热路径分开，避免把界面等待时间误读成 DPDK 订单延迟。
- 2026-09-02 按用户反馈新增 `06-classroom-run-flow.svg`，替换准备 D 前的等宽字符箭头。四个框只回答“准备一次、单路四次、统一比较一次”，不重复展开准备门闸，也不写任何示例延时。
- 2026-09-02 按用户反馈新增 `06-order-timing-windows.svg`，替换三个计时字段的等宽公式。图把同一笔订单固定为三个时间点和两个相邻窗口，总括号只表达精确加法关系；不把 `queue_to_send_ns` 误画成纯队列等待。
- 2026-09-02 按用户反馈新增四张同版式单路 SVG：`06-kernel-socket-path.svg`、`06-onload-order-path.svg`、`06-tcpdirect-order-path.svg`、`06-dpdk-fstack-order-path.svg`。正文四个字符路径全部退役；每张图固定订单线程、API/栈、X2522 owner、物理链路与 Exchange 的阅读方向，使学员能逐图比较“哪里没变、哪里换了”。
- 2026-09-02 按用户反馈新增 `06-dataplane-mode-switch.svg`。它只解释已经存在的模式切换 API：网页按钮和课堂 curl 是同一入口，后台才是 `labctl` 停进程与 `dpdk-devbind` 换驱动。
- 2026-09-02 按用户反馈新增 `06-balanced-comparison-method.svg`。图把 Williams 直接翻译成四行四列的轮换顺序，并把固定条件、每格 100+1000、16 格总账、四格等权汇总与“固定簿面但不冻结进程”放在同一张图里；正文删除原六行方法表和重复长解释。

## 尺寸与投屏层级

37张历史PNG中26张为`1672×941`，9张为`1671×941`，2张为`1672×940`。当前正文不再按投屏/折叠分层，只引用上表 11 张。

全部固定摘要见同目录`SHA256SUMS`。
