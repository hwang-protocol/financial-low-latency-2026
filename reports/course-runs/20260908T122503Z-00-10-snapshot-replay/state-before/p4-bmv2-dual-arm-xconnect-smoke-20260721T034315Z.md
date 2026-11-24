# P4 BMv2 Dual-Physical-Arm Xconnect Smoke Run State

- `RUN_ID`: `20260721T034315Z`
- `STATUS`: `BLOCKED BY L2 CONTROL-FRAME POLICY; RECOVERY PASS`
- `STARTED_UTC`: `2026-07-21T03:43:15Z`
- `FINISHED_UTC`: `2026-07-21T04:08:00Z`
- `CONTROL_NODE`: `jiaozhu-dgx-spark`（仅 SSH 编排、只读控制与仓库证据）
- `PROFILE`: `.1/Et1 + .11 port0/Et11 = access VLAN100`；`.2/Et2 + .11 port1/Et12 = access VLAN200`；`.11 simple_switch` physical port 1↔2
- `ORDERING_SAFETY`: 先拆分 VLAN 再启动 BMv2；先停止 BMv2 再恢复 VLAN20，禁止在 Et11/Et12 同属 VLAN20 时运行 xconnect
- `SWITCH_BOUNDARY`: 只修改 running-config；绝不 save/write/copy running-config startup-config
- `HOST_RECOVERY_TARGET`: `.11` 双 BCM57414 回到 bnxt_en、admin down、零地址、无 master/VLAN/XDP/BMv2/9090，所有 hugetlb page-size pool 为0；`.1/.2` 恢复 sfc/IP/10G
- `RESULT_DIR`: `Documents/reports/20260721T034315Z-p4-bmv2-dual-arm-xconnect-smoke/`
- `CONCLUSION_BOUNDARY`: 真实双物理臂 L2 功能 smoke；不产生吞吐、延迟、PPS、长期稳定性或 P4 解析 802.1Q 的结论
- `RESULT`: 现有 all-frame xconnect 启动后透传 MSTP BPDU，使 Et12 进入 `backup/discarding`；按合同在业务发包前精确停止，正向/负向/恢复均为 `NOT TESTED`
- `RECOVERY`: BMv2 PID/9090 清理，`.11` 双口恢复 `bnxt_en`/down/空配；补充审计发现并精确清理前一 TRex RUN 遗留的 1 GiB hugetlbfs 文件，清理后 2 MiB/1 GiB pool 均为0；Et1/2/11/12 恢复 access VLAN20，本 RUN VLAN200 已删除，VLAN100 保留，未执行 save
- `FOLLOW_UP`: 独立修正版 RUN 将在 P4 中对 `01:80:c2:00:00:00/ff:ff:ff:ff:ff:f0` 做 drop+counter，重新编译、验 SHA 和执行完整正/负/恢复闭环
