# Verilator Assertion / Random Scoreboard Boundary Run State

- `RUN_ID`: `20260721T045846Z`
- 状态：`COMPLETED`
- 创建时间：2026-07-21 04:58:46 UTC / 2026-07-21 12:58:46 CST
- 目标：在 `.101` 的 Verilator 4.038 上，以既有 160-bit market pipeline 为基线，验证 `--lint-only -Wall`、SystemVerilog assertion 可用边界、固定 seed 随机 input/backpressure reference scoreboard、受控 mutant 负向以及可复核 coverage。
- Profile：`verilator-assert-random-scoreboard-boundary-v1`
- 唯一允许设备：`10.1.1.101 / vm-monitor` 的管理口、临时目录 `/root/flle-verilator-assert-random-20260721T045846Z`、现有 Verilator/G++/Make/Python 工具链。
- 明确禁止：不访问 `.1/.2/.11` 或交换机；不读取或改变任何数据接口、PCI/driver、P4/BMv2、TRex、hugepage；不安装包；不停止、重启或配置 Prometheus、prometheus-node-exporter、Grafana、Loki；不做 synthesis/P&R/STA/Fmax 或 FPGA 硬件结论。
- 负向合同：mutant 或受控协议违例必须返回非零，并由 RTL assertion 或 reference scoreboard 的精确错误标签捕获；失败证据保留。随后删除 build 产物，从 clean RTL fresh build 并完成全部 seed PASS。
- coverage 合同：若 `--coverage`、runtime coverage write 和 `verilator_coverage` 可用，则归档每 seed coverage、merge/annotate 与摘要；任一能力不可用则保留明确负向，不以替代数字冒充。
- 最终门闸：远端临时目录和 Verilator/G++/Make/模型进程为零；四监控服务 PID 与运行前一致，均 active/running/enabled，本地 HTTP 9090/9100/3000/3100 均为 200；仓库凭据扫描通过。
- 结果目录：`reports/20260721T045846Z-verilator-assert-random-boundary/`
- 完成时间：2026-07-21 05:24:00 UTC / 2026-07-21 13:24:00 CST
- 最终结果：`RUN_VALIDATION_PASS`。clean `--lint-only -Wall --assert --coverage` 为 rc=0；故意 WIDTH warning 为 warning-fatal rc=1。4.038 支持 immediate assertion 与单周期 inline assert/cover property，不支持 named property、`$stable`、`|=>` 或 `[*2]`。
- 负向结果：overflow mutant 被 RTL `fifo_bound` assertion 以 rc=134 捕获；assertion-disabled reorder mutant 被 reference scoreboard 的 `output_seq` 以 rc=2 捕获。mutant 产物删除后从 clean RTL fresh build。
- 随机结果：4 个固定 seed、每 seed 4096 请求随机周期；总计 16515 active cycles、12841 accepted、7719 matched/output、2588 bad magic、2534 nonmatch、285417 scoreboard checks，FIFO max=4，每 seed 最长 input stall=20 cycles，全部 PASS。
- Coverage：每 seed runtime data、merged data、LCOV info、annotated source 和 rank 均已归档；6 个命名 cover point 非零且与 scoreboard 聚合精确一致。该结果不构成 formal、综合或硬件 coverage sign-off。
- 最终恢复：远端临时目录与相关编译/模型进程为零；四监控服务 PID 保持 `16194/15843/16740/16644`，四 HTTP 均 200；远端 68 个归档文件逐文件 SHA-256 匹配，仓库凭据扫描 PASS。
- 登记边界：按任务要求未修改 PINS、FREEZE、PIT 或 Teaching Boundary Map；建议更新项写在本 RUN `report.md` 第 8 节，交由主 agent 审核。
