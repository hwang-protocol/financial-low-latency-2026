# P4 BMv2 Dual-Physical-Arm Link-Local Guard Smoke Run State

- `RUN_ID`: `20260721T042025Z`
- `STATUS`: `COMPLETED`
- `STARTED_UTC`: `2026-07-21T04:20:25Z`
- `FINISHED_UTC`: `2026-07-21T04:39:00Z`
- `CONTROL_NODE`: `jiaozhu-dgx-spark`（仅 SSH 编排、只读控制与仓库证据）
- `PROFILE`: `.1/Et1 + .11 port0/Et11 = access VLAN100`；`.2/Et2 + .11 port1/Et12 = access VLAN200`；`.11 simple_switch` 对 IEEE link-local `01:80:c2:00:00:00/ff:ff:ff:ff:ff:f0` 做 ingress counter+drop，其余帧 physical port 1↔2/2↔1
- `SAFETY_GATES`: 所有 page-size hugepage pool 为0；先拆 VLAN 再拉起 arm；BMv2 后四端 STP 持续 forwarding 且 BPDU 不跨 arm 后才发业务包；先停 BMv2 再恢复 VLAN20；绝不关闭 STP
- `TRAFFIC_CONTRACT`: 正向 `.1→.2` 5/5 + 反向 `.2→.1` 5/5；停 BMv2 后双向 0/3；同 profile 重启后双向 5/5
- `SWITCH_BOUNDARY`: 只修改 running-config；绝不 save/write/copy running-config startup-config
- `HOST_RECOVERY_TARGET`: `.11` 双 BCM57414 回到 bnxt_en、admin down、零地址、无 master/VLAN/XDP/BMv2/9090，2 MiB/1 GiB 等所有 hugetlb pool 为0；`.1/.2` 恢复 sfc/IP/10G
- `RESULT_DIR`: `Documents/reports/20260721T042025Z-p4-bmv2-dual-arm-linklocal-guard-smoke/`
- `CONCLUSION_BOUNDARY`: 真实双物理臂 L2 功能和控制帧安全 smoke；不产生吞吐、延迟、PPS、线速或长期稳定性结论
- `RESULT`: P4 guard 正向与恢复两次启动后 STP 四端持续 forwarding，两 arm BPDU inbound >0 / outbound=0；正向双向 5/5，停 BMv2 后双向 0/3，同 profile 重启后双向 5/5
- `CONTROL_FRAME_EVIDENCE`: positive counter port1/port2 各 60 packets / 7408 bytes，recovery 各 48 / 5913；positive BPDU capture in=52/52、out=0/0，recovery in=41/42、out=0/0
- `BUSINESS_EVIDENCE`: positive 两 arm 各 20 ICMP + 8 ARP；recovery 各 20 ICMP + 4 ARP；negative port0/port1 只有本侧 ARP 3/5，ICMP=0、opposite-arm source=0
- `RECOVERY`: `.11` 双 BCM57414 为 bnxt_en/down/空配，无 BMv2/9090/tcpdump，2 MiB/1 GiB pool 均为0；四端恢复 access VLAN20，VLAN200 删除、VLAN100 保留，未 save；`.1/.2` sfc/IP/10G 与双向/SVI 3/3 通过；`.101` 监控服务 active；`.11/.101` 本 RUN 临时目录已删除
