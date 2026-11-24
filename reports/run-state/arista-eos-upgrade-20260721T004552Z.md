# Arista EOS Upgrade Run State

- `RUN_ID`: `20260721T004552Z`
- 状态：`COMPLETED`
- 运行态补建时间：2026-07-21 00:45:52 UTC / 2026-07-21 08:45:52 CST
- 实际工作开始：早于本运行态文件；精确起点未单独持久化，首个可复核的破坏性状态转换为控制节点在 2026-07-21 08:31:25 CST 观测到管理口进入 DOWN
- 目的：把 DCS-7150S-24-F 从 EOS 4.13.4F 升级到经过签名、平台和传输完整性检查的 EOS 4.23.16M-2GB，并完成启动、硬件、管理面与数据面回归
- Profile：`arista-7150-eos-standard-cold-upgrade`
- 唯一主变量：EOS 启动镜像由 `flash:/EOS-4.13.4F.swi` 切换到 `flash:/EOS-2GB-4.23.16M.swi`
- 非目标：不执行 ISSU/fast-boot，不单独升级 Aboot，不把临时 LANZ/PTP/eAPI 测试配置写入 startup-config，不产生性能结论
- 管理保护：控制节点持续监控 `10.1.1.253`；用户提供本地串口观察；升级前配置与旧镜像保存于仓库外受控备份目录
- 外部回滚引用：`/var/backups/flle/arista-10.1.1.253-pre-eos-4.23.16M-20260721/`
- 结果目录：`reports/20260721T004552Z-arista-eos-upgrade/`
- 当前状态：目标 EOS 已启动；SSH、VLAN20、四个 10G 数据口、agent、环境、FPGA/SMBus 与 flash 健康验收通过；后续 LANZ/PTP/eAPI 单变量 smoke 也通过并已撤销，结论为 `PASS WITH WARNINGS`
- 深度 feature smoke 证据：`reports/20260720T235906Z-arista-423-feature-smoke/`
- 已知 WARN：LANZ 撤销后的 FM6000 动态字段残留、低影响 `rpcbind.socket` failed、无可信墙钟的 UCD 历史 fault record；分别见 PIT-14、PIT-15、PIT-16
- 主报告：`reports/20260721T004552Z-arista-eos-upgrade/report.md`
