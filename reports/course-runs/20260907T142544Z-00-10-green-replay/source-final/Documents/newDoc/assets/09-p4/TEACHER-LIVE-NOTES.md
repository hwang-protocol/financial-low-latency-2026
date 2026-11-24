# 第09章四步演示：教师说明

2026-09-07 · DEC-387 · 当前完整实跑 `20260907T151801Z-09-p4-drop-live`：四步全0退出、RESTORED；三次120秒课堂停顿后接续成功。丢177=Feed缺177、gap1/API400；恢复0612260008、两笔成交、AAPL1→1。正文四份输出与该RUN逐字一致，GAP网页另有实际截图（总RUN142544Z/browser/09-p4-gap.png）。上一轮132605Z与后文早期记录保留历史身份，不作为当前未完成状态。

学生正文只保留三态SVG与4张绿色卡片。每个脚本在前台执行当前阶段，完成就退出；后台保护进程只负责执行异常的恢复，不会代替教师运行下一阶段或预先生成结果。

| 入口 | 实际执行 | 结束时保留什么 |
| --- | --- | --- |
| `09a-configure-p4-path.sh` | 交接检查、编译/复制JSON、隔离工具口、启动BMv2、CLI装表、移动交易端口、验证放行 | VLAN100/200路径、运行中的BMv2、额度0、HEALTHY/PAUSED |
| `09b-inspect-p4-path.sh` | EOS show、CLI show_tables/table_dump/register_read/counter_read、Feed检查 | 相同路径与暂停状态；允许重复查看 |
| `09c-drop-one-packet.sh` | CLI额度1、恢复播放、GAP后暂停、拒单/GUI合同、撤销额度、序号/计数对账 | 额度0与GAP；不提前重放或恢复 |
| `09d-restore-p4-path.sh` | 回切VLAN20、停止BMv2、归还工具口、重放与恢复后两笔订单 | 原路径、HEALTHY、净持仓不变 |

完整执行源码：`live-support/stage-actions.sh`（237 行）。阶段/保护管理：`live-support/stage-session.py`（240 行）。终端摘要由 `live-support/stage-output.py`（89 行）从当次真实回执生成，完整输出保存在 `raw/<阶段>-full.txt`，展示文本保存为 `raw/<阶段>-display.txt`。输出格式器验证Feed状态，缺所需字段时报错，不填默认示例数值。四个短入口只选择各自阶段，不是调用完整实验后截取输出。旧 `09-trading-p4-drop-live.sh` 与 `live-support/run-trading-p4-drop-live.sh`（184 行）保留为教师自动回归入口，已撤出学生主线；不要与四步入口交叉运行。

## 状态、顺序与退出

第1步开始才生成RUN_ID；阶段身份入口为 `Documents/reports/run-state/ch09-p4-stages.json`，当次目录内的 `session.json` 保存阶段、原行情模式、保护进程PID/启动时刻/boot ID与当前动作截止时刻。后3步读取这个入口，不手填或复用示例RUN。源码、JSON摘要与原始回执保存在当次 `Documents/reports/course-runs/`。

顺序为 CONFIGURED → OBSERVED → DROPPED → RESTORED；第2步可重复，第3步禁止重复。第4步可在任一已建立的阶段提前退出，其PASS仅表示恢复与订单通过，不暗示已经做过DROP。

后台保护进程跨脚本持有 `/var/tmp/flle-ch08-10.lock`，每个前台阶段另持当次动作锁。正常 CONFIGURED/OBSERVED/DROPPED 状态不限时等待下一张卡；保护进程只对失败或中断超时的动作执行cleanup。前台阶段最长240秒，失败/超时/中断先停当前动作及其子进程，再尝试恢复；恢复失败记录RESTORE_REQUIRED并保留保护重试。保护身份失效时拒绝继续操作；第4步仅在共享锁无人占用时重新建立保护并尝试恢复。

## 接管与回切

交接门沿用第二章平台持久运行态与第08章恢复要求，核对 `.11` 两只BCM网口为 `bnxt_en / DOWN / 无IP`，没有XDP、Linux bridge、旧BMv2/发包器和9090占用；不覆盖未知使用者。PCI BDF必须结合所在主机判断。`.11` 是已有双PF直通的工具VM，BMv2是其内的Linux进程，管理口不参与。

进入：先Et11→100、Et12→200，再启动BMv2并装表，最后Et1→100、Et2→200。配置脚本内完成两端移动，随后重新验证HEALTHY。EOS计划包含建立VLAN、access模式、区域名称和临时IGMP设置；`switchport access vlan`才是把接口划到该区域的命令。

恢复：先Et1/Et2→20，确认这段命令成功，再停BMv2/双口DOWN，最后Et11/Et12→20、恢复IGMP并删除100/200。只改running-config，不保存startup。保护清理无需课堂确认；正常第4步额外用新Session与两笔真实协议订单核验恢复。

如果要直接进入原生CLI，在第1步完成后另开终端：先 `ssh root@10.1.1.11`，再 `simple_switch_CLI --thrift-port 9090`。看到 `RuntimeCmd:` 后可做只读查询，Ctrl+D退出客户端；不要绕过四步顺序手工改额度/表项。第4步结束后实例已停止。

## 回执与边界

CLI每次打印本条命令/作用、原生输出、解释；本阶段内连续完成，不要求教师逐条贴命令。安装/查看/武装/清零读数分别保存在 `raw/table-install.txt`、`cli-inspect.txt`、`register-block.txt`、`register-clear.txt`。EOS查看使用短计划 `p4-trading-inspect.plan`，原详细计划继续用于身份与恢复检查。

历史物理结果来自 `20260905T024425Z-09-p4-drop-live`。699、588、100字节不是下一次固定值。第3步的5秒额度保护在武装并恢复播放后启动；证明丢包仍需policy_drop_packets=1且dropped_sequence等于当次Feed next_expected。主动清零后的额度0不能单独证明丢包。GUI检查为页面代码与状态合同，不是浏览器截图。新四阶段没有复用历史读数来冒充当次结果。

本地检查：`python3 Documents/newDoc/assets/common/verify-filter-course-cards.py`；`python3 Documents/newDoc/assets/09-p4/live-support/test-stages.py`。测试在隔离的临时根目录使用假设备动作，验证独立执行、跨脚本锁、顺序/重复限制、失败/中断动作回切、任意时长讲解接续与保护失效恢复，不接设备。格式器另以当次与历史回执核对正文四块输出；当前第3/4步已按开头所列RUN完成实测。


## 本轮实机故障与修复

用户执行配置产生 `20260906T040223Z-09-p4-drop-live`。随后新增的boot ID必填校验错误拒绝这份已启动的旧运行态，第2步在设备查询前返回1；已复现。现在用既有PID/启动时刻加实际guard命令行验证旧记录，并补齐boot ID。前台动作锁等待短暂guard轮询，避免正常抢锁立即exit1；已有本地回归。

放行复测另发现持续播放数分钟后非策略缺口：policy_drop_packets=0，但Feed next_expected8344、gap_size17。本次检查失败后已实机自动归还VLAN20/双口DOWN并恢复原模式（ROLLED_BACK）。不能把这次缺口算成P4策略命中；缺包根因尚未单独定位。

现役配置改为BMv2 `--log-level warn`，避免默认trace逐包输出；放行验证后暂停行情，查看阶段维持暂停，丢包阶段才恢复播放，出现缺口后再次暂停。保存进入前播放状态，清理时恢复。此组合针对分步教学，不是吞吐能力结论，也不把日志开销认定为已证实的唯一根因。

`20260906T041235Z-09-p4-drop-live`：新版配置与第2步rc0；VLAN100=Et1/Et11、200=Et2/Et12，额度0、丢包计数0，session0612260113、next_expected174、HEALTHY/PAUSED；约5分钟后只读复核仍健康。当前保留在OBSERVED阶段，后续由教师运行第3或第4步；空闲保护仍有效。阶段身份以持久JSON为准，不把本文时间点状态当成永久现状。

正文①②是该RUN真实回执的当前格式化结果，③④来自历史 `20260905T024425Z-09-p4-drop-live` 经同一格式器生成，不能称为新版③④已实测。源码与回执摘要分阶段更新；先关闭本步完整日志、写完展示文本，再计算SHA，避免把仍在写入的日志纳入摘要。


## 2026-09-06 审核修订与离线验证（DEC-359）

准备A现在与B一样，先对公开Release.key强制比对固定SHA，再登记公钥/软件源；公开文件下载复算、正确与错误公钥片段测试通过，没有执行安装。正文准备卡与资产逐字同步。

配置展示中的EOS命令去掉记录器的`$ `前缀；注释写“EOS配置命令节选”，不伪造交换机提示符，raw与历史展示稿保持原件。四段正文分别用041235Z的configure/inspect、024425Z的drop/restore原件经过现役stage-output.py生成并逐字对比通过；历史结果不等于新版③④现场复测。

本地阶段测试覆盖独立运行、锁、重复/顺序拒绝与失败/中断动作回切、任意时长讲解接续；共享卡片验证通过，09保持7绿卡/7图/7导航。本文和PINS中的OBSERVED只代表所列RUN检查时刻，本次未读设备当前状态；没有新的设备RUN。
