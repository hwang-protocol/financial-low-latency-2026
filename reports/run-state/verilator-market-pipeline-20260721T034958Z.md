# Verilator Market Pipeline Run State

- `RUN_ID`: `20260721T034958Z`
- 状态：`COMPLETED — FUNCTIONAL_PASS_WITH_BOUNDARIES`
- 创建时间：2026-07-21 03:49:58 UTC / 2026-07-21 11:49:58 CST
- 目标：在 `.101` 用 Verilator 4.038 验证教学级固定二进制行情 RTL：ready/valid parser、symbol filter、cycle timestamp、4-entry FIFO/backpressure 与精确 drop counters。
- Profile：`verilator-market-pipeline-ready-valid-fifo4-v1`
- 允许对象：仅 `.101` 的 `/root/flle-verilator-market-pipeline-20260721T034958Z` 隔离工作目录及其 Verilator/G++/Make 编译、仿真进程。
- 保护边界：跳板机只作 SSH 编排与仓库证据；不停止、不重启、不修改 Prometheus、prometheus-node-exporter、Grafana 或 Loki。
- 通过门闸：lint、build、覆盖 13 个输入 case 的机器自检、两次 stdout/VCD 一致、VCD required-signal/transition audit、远端 build 清理及监控服务 PID/active/enabled/HTTP 回归全部通过。
- 结论边界：Verilator simulation cycle 只证明 RTL 逻辑顺序；不等于墙钟时间、综合后 Fmax、timing closure、FPGA 资源或硬件延迟。
- 结果目录：`reports/20260721T034958Z-verilator-market-pipeline/`
- 权威结果：从无 `obj_dir` 开始的 lint/build 与两次仿真全部通过；13 个 case、8 个有序输出、bad-magic/nonmatch=`2/3`、FIFO max=`4`、matching stall=`3 cycles`，timestamp 序列 `[2,4,5,6,7,13,14,20]` 严格递增。
- 重复性：两次 stdout 与两份 VCD 各自 byte-identical；VCD required-signal/activity audit 通过。最终 `runner_rc=0`，完成时间 2026-07-21 04:03:10 UTC。
- 过程披露：attempt 1 因 summary 期望未打印标签而 wrapper `rc=1`；attempt 2 因 `pipefail + head` 的 SIGPIPE 在 preflight `rc=141` 且未启动 lint/build；两者原始证据均保留，后续全量 clean rerun 通过。
- 清理门闸：2026-07-21 04:04:55 UTC 远端精确工作目录和编译/仿真进程均不存在；`.101` 四个既有监控服务 PID 未变、active/enabled 且四个 HTTP health 均为 200。
- 最终报告：`reports/20260721T034958Z-verilator-market-pipeline/report.md`
