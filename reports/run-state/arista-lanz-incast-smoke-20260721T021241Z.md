# RUN STATE — Arista LANZ Incast Smoke

- `RUN_ID`: `20260721T021241Z`
- `STATUS`: `ABORTED BEFORE TRAFFIC — SWITCH CLI DISCOVERY ONLY; RECOVERY PASS`
- `STARTED_UTC`: `2026-07-21T02:12:41Z`
- `CONTROL_NODE`: `jiaozhu-dgx-spark`（仅 SSH 编排与仓库证据操作）
- `PROFILE`: `.11/ens64np0 + .12/ens64np1` 两个 10G UDP ingress → `.2/ens64np1` 单个 10G egress；Arista Et2 临时 LANZ queue-length monitoring
- `SWITCH_CHANGE_BOUNDARY`: 只改 running-config；禁止 save/write/copy running-config startup-config；完成后显式撤销
- `RESULT_DIR`: `reports/20260721T021241Z-arista-lanz-incast-smoke/`
- `CONCLUSION_BOUNDARY`: 短时实包功能 smoke；不作为正式吞吐、时延、长期稳定性或无损证明
- `FINISHED_UTC`: `2026-07-21T02:19:34Z`
- `EXECUTED_TRAFFIC`: `NONE`；只做了 LANZ CLI/config discovery，没有 VM 侧发流证据，不得写成 incast、queue event 或 drop 测试
- `OBSERVED`: LANZ 可启用；Et2 threshold `64/32` 可配置；尝试100000 usec update interval时设备明确警告小于5秒可能丢 congestion message，随后恢复默认5000000 usec
- `FINAL_RECOVERY`: Et2 threshold 与 global queue-monitor 均已 default；running-config 无 queue-monitor 行、LANZ disabled/agent not running；四口原 access VLAN20、errors/discards0、startup-config parse PASS；未保存配置
