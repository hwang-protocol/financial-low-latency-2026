# ESXi Automatic vTopology Post-Boot Run State

- `RUN_ID`: `20260721T065034Z`
- `STATUS`: `COMPLETED — READ-ONLY DISCOVERY`
- `STARTED_UTC`: `2026-07-21T06:50:34Z`
- `CONTROL_NODE`: `jiaozhu-dgx-spark`（仅 SSH 编排与项目证据写入）
- `PROFILE`: `esxi8-auto-vtopology-postboot-readonly-v1`
- `TARGETS`: `.1`、`.2`、`.11`
- `MUTATION_BOUNDARY`: 只读；不修改 VM、guest、网卡、服务或交换机
- `RESULT_DIR`: `Documents/reports/20260721T065034Z-esxi-autovtopology-postboot/`
- `CONCLUSION_BOUNDARY`: 只验证 guest 开机后呈现的 vCPU/socket/core/vNUMA 与 PCI/netdev 状态；不证明 ESXi pCPU/pNUMA placement、PCI locality、CPU reservation、Latency Sensitivity 或性能收益
- `FINISHED_UTC`: `2026-07-21T06:52:46Z`
- `RESULT`: `.1/.2` 各呈现 1 socket×8 cores、单 guest NUMA；`.11` 呈现 1×18、单 guest NUMA；三台 DirectPath NIC/driver 与接口基线正常，open-vm-tools active；guest IOMMU group 仍为0
