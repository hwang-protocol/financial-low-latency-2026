# 第08～10章客户端过滤与连续重刷验收

> 2026-09-05 · DEC-333 · IMPLEMENTED / CONTINUOUS LIVE PASS / NOT FROZEN
> 基于现有第06章 RUN `20260903T061746Z-06-four-path-orders`；没有恢复快照，不是从第01章 fresh 零起点重刷。

## 1. 用户确认的主线

`.1` 始终是交易所，`.2` 始终是交易客户端；三章分别启用一层过滤，不叠加。

| 章节 | 真实执行路径 | 边界 |
| --- | --- | --- |
| 08 | `.1 → 7150 VLAN20 → .2 X2522/sfc/native XDP → 行情程序` | 不用 BMv2，不修改交换机；网卡保留 IP、UP、sfc |
| 09 | `.1 → BMv2/P4 → .2` | BMv2 的实际宿主机仍是 `.11`；不能隐去接线或虚构多一个交易角色 |
| 10 | `.1 → .2 真实网卡/Linux → adapter → Verilated RTL → 行情程序` | CPU 模拟应用前过滤，不冒充实体 FPGA 位于网线前端 |

真 FPGA 网卡对照是“网线 → FPGA 卡内过滤 → DMA 到主机内存 → 行情程序”。假设真机/真卡的操作说明仍为设计、未实测；没有因此改动 OpenFDK/OpenNIC 工程边界。

## 2. 第07章背景流量与第09章桥接的交接

用户回忆 `.11/.12` 发背景流量。本次核对现役 `07/11-qos-real-order-contention-live.sh`、`07/04b-lanz-stream-ab.sh` 及 `live-support/lanz/remote-lanz-trex-control.sh`：实际管理目标是一台 `.11` 的双 BCM57414，分别连接交换机 Et11、Et12。不要把端口编号解释成新增客户端，也不对未登记的 `.12` 管理主机执行命令。

第07章已有 stop/recover：停 TRex、归还 `bnxt_en`、清数据口地址/master、双口 DOWN、归还大页、恢复交换机。第08章不使用这两口。第09章新增共享只读门复查两口 PCI 身份、driver、UP/IP/master/XDP、旧发包/交换进程和 9090；同时核对 Et1/2/11/12 实际在 access VLAN20、无 VLAN100/200。先隔离工具口，再启桥，最后切 endpoint；退出逆向交还。

`check-filter-handoff.sh` 不自动清除未知占用或重绑设备。正常顺刷依赖上一章自己的恢复，异常时安全拒绝，不把别人的进程或配置当作残留删掉。第08章另检查 `.2` 的 BDF/MAC/IP、sfc、无旧 XDP/RTL、交易 profile。

## 3. `.2` native XDP 的证据

只读门确认 `.2` 为 `vm-2522-02`，kernel `5.15.0-164-generic`，X2522 `1924:0b03 / 1924:8028 @ 0000:03:00.0`，netdev `ens64np1`，MAC `00:0f:53:d3:af:21`，IP `20.1.1.2/24`，`sfc 6.1.0.1009`、固件 `8.0.0.1015 rx1 tx1`。`ens64np0` 在本次 `.2` 上不存在，不代表网卡丢失。

厂商模块 `nm` 含 `efx_xdp_setup_prog / efx_xdp_rx / efx_xdp`；仓库 Onload `9f330e7` 源码的 `src/driver/linux_net/drivers/net/ethernet/sfc/xdp.c` 含 XDP 挂载实现。[上游 Linux v5.15 sfc](https://github.com/torvalds/linux/blob/v5.15/drivers/net/ethernet/sfc/efx.c) 也有实现，但本环境使用厂商 extra/sfc.ko，不能只凭上游结论代替挂载测试。

首轮 `20260905T023422Z-08-xdp-receiver-live` 实得 program 785、native/JIT、DROP Sequence 641。最终连续轮 program 789、tag `2825c80b3631830d`、DROP Sequence 648；`xdpdrv` 明确要求 native，不降级 generic。两个 RUN 的丢包均与 Feed `next_expected` 相等，分别完成 GAP/API拒单和恢复。

程序仍是原 `flle_xdp_mold_itch.c`：source SHA `65ba51119ffa6ec2010f841475106c3227ef9457361c70eb41a59530acc5e7b7`；build/live object SHA `f374913b23e93c3ad505b2aaaf233194318d73514fa5735678385068e5f5e09d`。用户态按本次 program 的 map_ids 选表；一次额度及 5 秒期限不变。远端看门狗 180 秒只卸载同 ifindex/program ID，正常结束后自行退出。

结论只覆盖普通 Linux socket 行情消费者；不宣称 Onload/TCPDirect/DPDK 绕过内核的接收路径也被同一 XDP 覆盖，不作性能排名。

## 4. 修复的顺刷缺口

- `.2` 最初缺少 Clang/LLVM/bpftool；准备 A 改为在 `.2` 安装用户态工具，不换 sfc。apt 显式 `NEEDRESTART_MODE=l`，避免准备步骤自动重启交易相关服务。
- 第10章正文遗漏现有 Verilator 准备脚本，绿色卡补为先安装固定版本工具、再执行 live；不依赖教师预装。
- 新增互斥锁后首轮 10 `20260905T023720Z` 在锁门返回，raw 为空、未开始模型部署。审查发现 09 后台 deadman/sleep 可能继承锁 FD；两处后台任务加 `9>&-`。后续连续 09→10 不需等待或补命令。未保留当时持锁进程快照，不把源码推断描述成进程级排他证明。
- 共享门初版要求 running-config 显式出现 `switchport mode access`，但 EOS 省略默认值；改用实际接口 VLAN20 状态 + access VLAN 配置，并排除 trunk/shutdown。失败发生在只读门，未写设备。

## 5. 最终顺序与回执

同一 shell、同一第06章交易 RUN，执行第07章章末验收后，按正文顺序完成08六个、09四个、10两个脚本入口。未在章间手工修驱动、地址、VLAN 或重建交易进程基线；它们的必要接管/恢复由卡片完成。施工时同步修订文档及交接门，不宣称整轮工作区零编辑。

| 入口 | 2026-09-05 RUN |
| --- | --- |
| 07 章末验收 | `024328Z-07-trading-online-final` |
| 08 准备 / Hook / Action / 边界 / build | `024332Z` / `024335Z` / `024336Z-08-xdp-actions` / `024336Z-08-xdp-bounds` / `024336Z-08-xdp-build` |
| 08 native DROP | `024337Z-08-xdp-receiver-live`：Sequence 648，DROP=1 |
| 09 编译工具 / BMv2工具 / 编译 | `024410Z` / `024416Z` / `024420Z` |
| 09 P4 DROP | `024425Z-09-p4-drop-live`：Sequence 699，counter=1 |
| 10 工具 / RTL DROP | `024534Z` / `024538Z-10-rtl-filter-live`：Sequence 505，drop_count=1 |

13/13 入口通过，13/13 `SHA256SUMS` 复算通过。主要根清单 SHA：

- 07：`d86879a2eef5c92ef8319c681dee180c5e123156ef2a604371dcf7152c930633`
- 08：`d8cda3fbe756980d815d66d62586abd6f3f2e658eaf1d53d792c32f16d529541`
- 09：`8c41f23367bb2df4906626d057d066a695de606a4e026b606717bb80999a740d`
- 10：`a56c8e4cca0eb6507adaf359e7a0d3cb4bb32c13279cf0ff1f8d984f6bf93877`

每章均有 DROP Sequence=Feed next_expected、GAP、API HTTP400、线上前端源码合同、新 Session 恢复及两笔净零 OUCH 测试订单。不是浏览器截图。最终 Session `0612260099`、`UNICAST / HEALTHY / OPEN / pending=0`、AAPL=220；`.2` 无 XDP/RTL/watchdog 残留，`.11` 双口 `bnxt_en/DOWN/无IP/无master/无XDP/无BMv2`，四交换口 VLAN20、无100/200。

## 6. 静态与交付边界

XDP 所有权/看门狗本地测试 6/6；现役三章 shell 语法、Python AST、SVG XML、本地图片链接及 HTML/围栏检查通过。08 前五张绿卡全文与源脚本逐字一致、均不超过50行；唯一长安全编排105行单独披露。图数11/8/5、导航7/7/6、绿卡6/3/1。两张修改 SVG 的800px渲染通过；中央171、局部13/9/8，共201条图摘要通过。

待提交包括三章正文、相关脚本、新所有权/交接检查与测试、两图及图册摘要、治理记录和本报告；保留此前用户 PPT/map 修改。不执行 commit/push/tag。建议提交说明：`fix(course): move XDP to trader and verify chapter 08-10 handoffs`。

实卡烧录、真实 FPGA 交换机/网卡性能、全新快照从01章顺刷，以及未知第三方占用的自动恢复不在本轮已验证范围。

## 7. 评估后教学修订（DEC-334，仅静态）

用户再次强调没有真卡：继续让 `.2` 软件模型挡在行情程序前，真卡只解释完整操作过程，不增加硬件绿卡。本节不产生新 RUN，也不重新确认上一节的在线终态。

| 评估项 | 本次处理与证据 |
| --- | --- |
| 模拟器改变订阅 | 10开篇/运行前/真卡第八步说明：Guardian暂关组播、adapter收42120并单播交付42121；真卡恢复原组播订阅 |
| 软件与硬件位置 | 新SVG三行比较08 native XDP、10 socket后模型、真卡DMA前设计；章节顺序不代表处理先后 |
| 第10章交接门范围 | 保留bridge范围，为顺刷复核前章恢复；绿卡前明确`.11`与EOS管理依赖，不声称三主机独立入口 |
| 卡片与源码漂移 | 09的2个准备脚本和1个编译脚本全文展示，10工具脚本单独完整展示；长live流程保留入口并披露。9短+3长共12卡，执行顺序与现役脚本未变 |
| XDP失联后的业务恢复 | 08恢复断言补教师路径：确认自有挂载已撤销→本次state-before原模式→direct Guardian→Replay RESTART→新Session/HEALTHY/OPEN |
| 互斥边界 | flock只覆盖同主机、同文件、可访问的会话；不同主机不互斥。远端没有环境级原子租约；已记PINS，不夸大为全环境排他 |
| 初始额度 | C++ `run_adapter` 在allow时装0，block才装1；既有024538Z/raw/adapter.log首两行就是ready0、arm1/5000ms，正文加入原日志 |
| 命名与主机身份 | 08首次点名policy/drop_audit/counters；09强调BDF须带主机身份，并去掉两处残留“第08章allow-all桥”描述 |
| 真硬件如何落地 | 保留09六步/10八步；补7130透明接流与U250的新卡/netdev/IP/组播/profile迁移。现役控制器要求sfc，onic适配和板级wrapper尚未实现 |

验证：`python3 Documents/newDoc/assets/common/verify-filter-course-cards.py` 通过，覆盖完整短卡逐字一致、入口顺序、bash语法、长流程行数、图片存在/SVG XML、HTML和围栏平衡。XDP所有权单测6/6；新图1200/800px渲染目视通过。当前图11/8/6、导航7/8/7、绿卡6/4/2；比DEC-333增加两张绿卡及其导航只是把原有两组入口分开，不增加执行步骤。

待提交变化在既有dirty工作区之上：三章图文、1个新SVG及图册/摘要、1个只读卡片检查器、治理与资料复核记录；既有实验脚本改动仍属于DEC-333，不能算成本轮新实现。建议本次提交说明：`docs(course): clarify simulated filtering and real FPGA deployment`。不执行Git提交或推送。

收尾复核：中央图清单172项与08/09/10局部13/9/9项，共203条SHA验证通过；`git diff --check`通过。用户最终确认交换机部分同样只作假设有硬件的教学推演，P4/BMv2交付与Arista FPGA开发/装载是不同流程；不能直接烧BMv2文件，也不要求现有课堂执行硬件命令。

## 8. 再次评估后的措辞收尾（DEC-334 补记，仅静态）

2026-09-05，从已提交的 `2d23eee` 干净工作区开始；本次未改实验脚本、检查器、图片、导航或绿卡数量。没有新决策、运行态事实漂移或新踩坑，不新增 DEC/PIT 条目。

- 检查器原本已逐字比较9张完整短卡，并检查3个长安全入口；第09章实际为3张完整短卡加1个live入口。FREEZE-LEDGER现在点名命令、数量与`source drift`失败行为，保留写作规则允许的两类卡片。
- 10章Flash措辞改为“已按资料复核记录核对”，链接既有记录；不删除历史在线复核事实，也不升级为真卡适用或烧录实测。
- PINS将原有本地flock边界显式写成“互斥仅在同一跳板机有效，不是环境级排他”。
- 08异常恢复表拆开发送模式、直接订阅、Replay与状态检查，加入3条行内curl形态；`<原模式>`必须从本次`state-before.json`读取后替换，不新增正常绿卡。

验证：12张卡片、25处图片引用、导航/HTML/围栏/bash语法检查通过。另以内存替换方式故意改动09第一张短卡，检查器按预期报`card 1 source drift`，磁盘文件未改；3条curl只做bash语法检查，其中2份JSON解析通过，未发送HTTP请求。`git diff --check`通过。

待提交6文件：08/10正文、PINS、FREEZE-LEDGER、NEXT-AI-HANDOFF和本记录。无设备操作、无新RUN、未commit/push/tag。建议提交说明：`docs(course): clarify validation records and recovery commands`。
