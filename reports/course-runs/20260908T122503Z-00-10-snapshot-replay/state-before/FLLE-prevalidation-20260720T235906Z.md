# FLLE Prevalidation Run State

- `RUN_ID`: `20260720T235906Z`
- 状态：`ACTIVE`
- 创建时间：2026-07-20 23:59:06 UTC / 2026-07-21 07:59:06 CST
- 设计基线：`Documents/design/FLLE_Financial_Low_Latency_Engineering_Lab_Design.md`
- 目标：在快照后的五台 VM 与 Arista 上完成驱动、授权、下载、工具链、拓扑和最小端到端 smoke tests，尽早暴露课程实施阻塞。
- 非目标：本 RUN 不产出可发表的绝对单向延迟结论，不升级 EOS，不冻结课程章节。
- 管理保护：所有 PCI 解绑只允许 BDF `03:00.0` 的实验数据设备；禁止解绑 `ens33`/VMXNET3 管理口。
- VM 恢复点：用户确认五台 VM 已建立快照，RUN 结束后由用户恢复。
- 交换机恢复点：`flash:/startup-config.pre-flle-20260721`；实验配置只留在 running-config，收尾时恢复并与 startup-config 对比。
- 当前 profile：`prevalidation-mixed-functional`，结果只证明功能与兼容性，不作为性能排行榜数据。
- 主报告：`Documents/reports/FLLE_Hands_On_Prevalidation_2026-07-21.md`
- 已完成：环境基线；P4C→BMv2→P4Runtime 表项闭环；Verilator lint/build/run；BCM57414 DPDK/UIO 枚举、XDP smoke 与 4096 帧跨端口 DPDK 实包 RX 闭环；X2522 双端 DPDK `net_sfc_efx` macswap 实包 RX/TX、回滚及 Onload/TCPDirect 回归；在独立升级 RUN 完成 EOS 4.23 后，Arista LANZ、PTP E2E Transparent Clock 与仅本地 Unix socket eAPI 功能 smoke 均通过，临时配置已撤销并完成四口 VLAN20 回归。
- Arista 证据：`Documents/reports/20260720T235906Z-arista-423-feature-smoke/`；判定 `PASS WITH WARNINGS`，不包含 LANZ 拥塞、PTP 精度或远程 HTTPS 结论。
- Linux XDP 证据：`Documents/reports/20260721T013744Z-linux-xdp-icmp-drop-smoke/`；`.12` BCM57414 native XDP 完成精确 ICMP 的 5/5 PASS → 7/7 DROP 且 counter=7 → detach 后 5/5 PASS，环境回滚通过；不包含性能或 jumbo 结论。
- X2522 DPDK 证据：`Documents/reports/20260720T235906Z-x2522-dpdk-smoke/`；`.1/.2` 各作为 `net_sfc_efx` macswap 目标，反端各发送 256 个唯一二层探针，两个方向均 256/256 返回；两端回滚和 Onload/TCPDirect 回归 PASS。当前 guest 无 IOMMU group，因此仅为 UIO 功能 smoke，不包含安全 VFIO、性能或稳定性结论。
- 进行中：AppFlex/PTP；TRex；监控栈；端到端流量。
