# Guest Measurement Capability Discovery Run State

- `RUN_ID`: `20260721T041045Z`
- `STATUS`: `COMPLETED — DISCOVERY`
- `STARTED_UTC`: `2026-07-21T04:10:45Z`
- `CONTROL_NODE`: `jiaozhu-dgx-spark`（仅 SSH 编排与项目证据写入）
- `PROFILE`: `guest-cpu-numa-clock-iommu-readonly-v1`
- `TARGETS`: `.1`、`.2`、`.11`、`.101`
- `MUTATION_BOUNDARY`: 只读；不安装包、不写 sysctl/cgroup/IRQ affinity、不改网卡、服务或交换机
- `RESULT_DIR`: `Documents/reports/20260721T041045Z-guest-measurement-capability-discovery/`
- `CONCLUSION_BOUNDARY`: 只决定 guest 内可观察的教学/测量前提；不能代替 ESXi pCPU/pNUMA、资源预留、Latency Sensitivity、vMotion 或 PCI locality 证据
- `FINISHED_UTC`: `2026-07-21T04:14:46Z`
- `RESULT`: 四台同构采集完成；guest 功能教学可用，但 CPU/NUMA/VFIO 性能 profile 未就绪；`.11` 多页尺寸 hugepage 假干净边界已捕获并恢复
