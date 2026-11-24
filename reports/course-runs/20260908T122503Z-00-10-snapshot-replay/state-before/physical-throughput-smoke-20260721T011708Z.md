# FLLE Physical Throughput Smoke Run State

- `RUN_ID`: `20260721T011708Z`
- 状态：`COMPLETED`
- 创建时间：2026-07-21 01:17:08 UTC / 2026-07-21 09:17:08 CST
- 目标：对经 Arista VLAN20 的 X2522 pair（`.1 ↔ .2`）与 BCM57414 pair（`.11 ↔ .12`）执行短时 iperf3 TCP 功能/稳定性 smoke。
- 非目标：不形成正式性能基准，不测绝对时延，不修改交换机、PCI 绑定、XDP、默认路由或控制节点。
- 允许对象：仅 `10.1.1.1`、`.2`、`.11`、`.12` 四台 VM；允许安装/运行 iperf3。
- 管理保护：所有 SSH 控制连接与软件安装经 `ens33/10.1.1.0/24`；测试 socket 只绑定各自 `20.1.1.x` 数据地址。
- Profile：每个 pair 执行 TCP 1 stream 15s、TCP 8 streams 15s、TCP reverse 1 stream 15s；顺序串行，避免两个 pair 互相形成背景负载。
- 证据目录：`Documents/reports/20260721T011708Z-physical-throughput-smoke/`
- 退出条件：任一数据接口不是原内核驱动/10Gb/full、管理默认路由不经 `ens33`、错误计数异常增长或无法安全清理测试进程时立即停止。
- 完成时间：2026-07-21 01:28:30 UTC / 2026-07-21 09:28:30 CST
- 结果：六个 TCP case 均 rc=0、约 15 秒、TCP retransmits=0；receiver 约 9.388–9.415 Gb/s；测试后四口 10Gb/full、全网连通、无新增已筛选 NIC 错误计数，测试进程与 listener 全部清理。
- 警告：结果仅为一次短时 smoke；X2522 在测试前已有不增长的 drop/PTP 历史计数，见 PIT-20；安装期 needrestart 影响面见 PIT-12。
