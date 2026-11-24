# 第五章当前主线资产

本目录只操作第二章已经在线的真实 Trading Lab：安装一张 Grafana dashboard，再对 MANUAL C++ 的队列储存、同步方式与 CPU 角色做配平复测。行情回放和 AUTO 策略始终继续；独立 AUTO 进程以 10 Hz 充当环境哨兵。正文内联五段 shell 必须与本目录逐字一致，并用 `# ~~~~~……~~~~~` 分段。

| 文件 | 唯一变量 |
| --- | --- |
| `00-install-hot-path-dashboard.sh` | 只增加 dashboard，不改交易进程 |
| `01-measure-deque-cv.sh` | `DEQUE_CV/dedicated` 连续复测 8 轮 |
| `02-measure-fixed-cv.sh` | `DEQUE↔FIXED` 按 `ABBA→BAAB` 配平，只换储存 |
| `03-measure-spsc-spin.sh` | `FIXED↔SPSC` 配平，只把 CV 等待换成 release/acquire + x86 `PAUSE` |
| `04-measure-spsc-shared-cpu.sh` | SPSC 不变，只把 MANUAL order thread 从隔离 CPU 2 移到共享 CPU 0；退出时自动恢复 |

每个 profile 重复 8 轮。MANUAL 每轮 40 warmup + 400 measured、20 ms 间隔（50 Hz）；AUTO 每 5 个 MANUAL 节拍随行一笔，即 8 + 80（10 Hz）。每个 arm 合并 3200 个 MANUAL measured 做 p99 bootstrap，另合并 640 个 AUTO measured 做 p50 环境门。

CPU 角色冻结为 MANUAL order=2、AUTO order=3、普通 housekeeping=0–1；共享核卡把 housekeeping 与 MANUAL order 都固定到 CPU 0。SPSC 使用真忙轮询，必须有隔离核。测量订单在每个 phase 前按当前持仓选择安全首单，随后买卖交替，保持净仓位为 0，真实风控不关闭。

裁判要求：AUTO 每轮前后半窗 p50 漂移≤20%；检测到的环境顺风不得超过主效应一半；检测到 queue 效应时至少 7/8 相邻配对同方向；单 profile 的 round p99 最大/最小≤1.50。任一道门失败仍保留 raw 并输出 `REJECTED_*`，不得事后放宽阈值追 PASS。
