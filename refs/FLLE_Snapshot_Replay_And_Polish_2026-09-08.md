# 2026-09-08 快照后全课复刷与精修报告

状态：**完成，PASS_WITH_RECORDED_FIXES**。总 RUN：`20260908T122503Z-00-10-snapshot-replay`。用户恢复四台 VM 和交换机后，授权从第00章执行到第10章并逐章精读。初始 Git HEAD：`134f93ad571c878fc52fc8415b92fb6c0c6f04de`；初始工作树干净。没有执行 Git 提交、推送或标签。

**结论：全课真实操作已经顺序走完，最终环境可继续使用；本次发现并修复了一个第二章启动阻断，因此不能宣称最终代码从快照零修改一遍通过。** 第五章固定队列批次被原有性能门槛判无效，保留这项结果，不用历史表格或重跑挑选掩盖它。

## 执行口径

59个真实Bash代码块逐项保存原文、SHA、时间、返回码和输出，另执行第三章原生EOS绿卡。第04章浏览器按用户既有要求留给本人查看，API与指标由本轮核验；第10章八张明确标注模拟的硬件命令不执行。原始过程见 `reports/course-runs/20260908T122503Z-00-10-snapshot-replay/`，逐卡状态保存在 `reports/run-state/full-course-replay.json`。

本轮59个Bash块共61次执行：02部署有一次失败后的完整重试，02首单有一次正文/资产同步后的补验；其余入口各执行一次，第三章EOS卡另计。59个块的最终现象均通过，但性能批次有效性单独登记。没有再次恢复四VM快照重刷最终代码，因此仍不称为“最终代码从快照零修改一遍通过”。

## 已确认的结果

- 00：首次按页写入128页，minor_fault_delta=128。
- 01：离线工具、EOS公钥、VLAN20、管理/数据面、PCI/驱动、10G链路及3/3 ICMP与接收pcap全部通过。
- 02：Onload冷安装和IOMMU准备通过；平台124028Z失败，修复后完整重新部署124624Z通过。191项Python测试中9项按隔离部署跳过，C++构建/自测通过；首笔GUI路径IOC成交，持仓+1。
- 03：原生配置并查询IGMP，VLAN20 pruning=True/flooding=False，查询器20.1.1.254，233.74.125.32动态成员仅Et2；Linux单订阅。三模式120单播/120组播/双路60+60，序号重合60，pending/gaps=0；真实订单协议链通过。
- 04：20预热+200正式订单均成交；独立CSV复算P99=57548ns，与Prometheus0.000057548s一致；服务active，Grafana API八面板。
- 05：五卡执行与恢复通过。重复性 VALID（8/8 稳定、跨度 1.41×）；固定队列比较因 AUTO 两条件环境差异判无效，保留而不重跑挑结果；SPSC 与 CPU 隔离两组 VALID，八轮方向分别一致。
- 06：十卡通过，16 格、17,600 笔全部成交；独立复算 16 份 raw 的 36 项等权分位数与主表完全一致。Socket / Onload / TCPDirect / DPDK 的 send→final p50/p99 分别为 33.265/54.849、20.653/26.921、19.748/26.376、24.083/31.489 µs。固定簿面 stable=1，总账增量 17,600，末尾 SFC/READY/sfc、三路 ONLINE、DPDK WAITING、HTTP200、ping3/3。
- 07：五卡通过。QoS 两组各 120 笔成交，Q1/Q5 原生计数对应，p99 从 2,343,116 降到 222,555 ns；LANZ 低档 0 对、高档 40 对 START/END；PTP SLAVE，镜像配对 4809/4809，时钟边界保留。章末两单、持仓 0→0、ping3/3、三路 ONLINE，临时配置已恢复且未保存 startup。
- 08：六卡通过。真实 XDP 丢包序号 586 与 Feed next_expected=586 对应，缺口 1、API 拒单；卸载后 HEALTHY、两单成交、净持仓不变。
- 09：七卡通过。P4 五字段规则正确，三次实等 120 秒后仍为同一暂停会话；只丢序号 184 的一帧，Feed 恰缺 184，缺口 1 且拒单。恢复 VLAN20、退出 BMv2、工具口 DOWN、HEALTHY、两笔成交及持仓 0→0 均通过。四份正文输出和对应数字已统一为 RUN `20260908T132840Z-09-p4-drop-live`，逐字对应展示回执。
- 10：五卡通过。六项自测通过，三次实际120秒停顿；模型丢弃209，Feed恰缺209，缺口1，交易闸门抑制并拒单。退出adapter与控制文件后恢复HEALTHY/OPEN、两单成交、持仓0→0。四段正文逐字更新为 `20260908T133803Z-10-rtl-stages` 的展示回执。

## 修复与精修

1. **实际阻断：Onload启动等待器。** 旧函数在exec过渡期第一次cmdline不匹配便立即报错。失败后同一PID已成为正确Trader并监听48123，原错误未记录瞬时cmdline，不能还原其当时字节。受控延迟exec复现了旧检查误拒，并发现原等待器不核验启动时间。修复保持20秒上限，按PID/启动时间/boot ID固定身份，等待目标命令与同PID监听；延迟exec、错误命令、其他PID监听、错误启动时间四项行为测试通过，真实重新部署与首单通过。见PIT-20260908-10。
2. **正文/资产六处旧分叉。** 第二章首单验收入口和第五章提示输出需同步；已保存差异并同步：第二章按更新后的原文重新验收通过；第五章资产对齐实际执行的正文，只有提示与注释变化，原测量不重跑。五份旧清单的源码引用仍能与执行前封存副本核验。见PIT-20260908-11。
3. **职责和原理。** 修正第一章管理面用途、Guest BDF与物理卡归属、驱动安装章节；第二章48121/48122管理地址、共享行情接收源码与启动顺序；第三章唯一订阅和历史端点身份；第五章对照单由测量脚本注入、逐笔区间与分位数不可混加、SPSC交付顺序、幂等部署不清零。
4. **章节交接与证据。** 第七章明确三步连起两段通信、章末验收必做、待用工具口可无链路；第八章说明运行⑤会启用Guardian/接收器。第六章准备 C、正式主表与最终验收、以及第七章清点已更新为本轮原始读数；第九章四阶段原先混 RUN 的输出已按本轮同一次分步实验统一，解释表也同步。教师说明的现役v13路径、准备顺序及资产职责同步核对。

11章均已完整精读，保留原章节标题、学习目标、理解检查与图片。最终静态核验：11章74张导航卡、18张08～10执行卡、24图片引用、59个Bash原文、22个完整内联资产逐字同步（其中12个带SELF）；图册所有SHA清单、Markdown解析、diff空白通过。证据清单递归核验54份，1220项直接匹配，另5项历史源码引用与执行前封存副本匹配，无无法解释的失配。小型可提交收据见 [snapshot-replay-20260908.json](evidence/snapshot-replay-20260908.json)。

## 执行边界与审批记录

第十章四张真实软件实验卡初次被自动审批误归为八张排除的模拟硬件命令。只读核对正文标签、四个固定入口和 Verilator CPU 编译动作后，以同一原命令附范围证据重新审批通过。未绕过审批，也未执行真实 FPGA/Vivado/JTAG 示例。该事件不记为课堂脚本失败。

仍沿用原工程边界：SIGKILL 后遗留 feed.sock 的处理、AF_UNIX 发送缓冲标定及控制器仅按 peer IP 放行未在本轮扩改；不把本实验结论外推为生产部署验收。

## 最终交还

平台仍是第二章的 `20260908T124624Z-02-trading-platform`，没有为各章节重建不同系统。恢复常用 SOFTWARE / SFC / READY / sfc，六个业务组件 ONLINE，回放 PLAYING，Feed session `0612260010`、HEALTHY/OPEN、pending/gaps=0。Socket、Onload、TCPDirect 各一对订单共6笔全部成交，每对净持仓不变；录下当前PID/启动时间/boot ID及Kernel TCP、Onloaded(Valid)、ZF established/CTPIO3收据。网页为 `http://10.1.1.101:8088/`。

四机source/deployed清单一致；`.1/.2`仍加载sfc6.1.0.1009，无本课TC/XDP/RTL/BMv2/TRex/PTP残留；`.11` BCM两口DOWN、bnxt_en、hugepages0。控制器只在`.2`管理地址监听48606，`.111`无监听。两个行情UDP端点由同一个feed-receiver持有，主机组播订阅1，EOS动态成员仅Et2，查询器20.1.1.254。交换机临时配置已撤，startup规范化SHA仍为 `dcc38c10ca0779b67d717fd0a406793f3c72460a6775a0bd41e1c7850eba1ceb`，与开刷前一致。

附加交还工具第一次误以为SOFTWARE状态接口也返回TRANSPORT的hardware_receipts子项，在6笔订单成功后报KeyError。核对源码确认该接口在SOFTWARE下按设计返回空对象，随后只读原生连接完成验收，未重复下单、未改产品代码。这个验证工具修正与第二章真实课堂失败分开记录。

## 提交范围与建议

代码提交包含 `apps/flle-trading-lab/scripts/transport_labctl.sh` 与新增 `apps/flle-trading-lab/tests/test_listener_startup.py`，建议：`fix: wait for trader exec before validating listener identity`。

文档提交包含01/02/03/05/06/07/08/09/10章、教师说明、第五章5个提示同步资产、第七章清点资产、5份治理文件以及本报告/小型收据，建议：`docs: refresh snapshot replay evidence and refine course handoffs`。00和04已全文阅读并实跑，原文无需修改；图片字节保持不变。原始大体积RUN目录不强制加入Git，便携收据记录各次输出SHA、事实与边界。未执行commit、push或tag。

## 评估后补充：identity 多余字段守卫

复核意见成立：`test -z "${extra:-}" && test "$pid_field" = "pid=$pid"` 中首项失败属于 `set -e` 的例外，不能可靠拒绝多余字段。已拆成两个独立 `test`，其他等待与身份逻辑不变。新增 `test_extra_identity_field_is_rejected`，先在修前复现误返回0，修后全部5项函数回归通过；`bash -n` 和 `git diff --check` 通过。

本次只做本地补修，未部署到现有VM或重跑整套实验；上文191项测试和全课实机结论仍对应原封存版本，原证据及SHA不改写。独立补验见 [listener-identity-guard-20260908.json](evidence/listener-identity-guard-20260908.json)。代码/测试纳入原第一条commit，报告与治理记录纳入第二条；其他设计无需调整，未执行提交。
