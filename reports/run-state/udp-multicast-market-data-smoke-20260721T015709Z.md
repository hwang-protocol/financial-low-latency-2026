# UDP Multicast Market-Data Smoke Run State

- `RUN_ID`: `20260721T015709Z`
- 状态：`COMPLETED — FUNCTIONAL_PASS`
- 创建时间：2026-07-21 01:57:09 UTC / 2026-07-21 09:57:09 CST
- 完成时间：2026-07-21 02:11:51 UTC / 2026-07-21 10:11:51 CST
- 目标：验证 `.11 → Arista VLAN20 → .12` 的 UDP multicast 应用 socket 基础收发、显式 join 边界与 sequence 完整性。
- 实验流：`239.20.1.1:20001`；`.11/ens64np0/20.1.1.11` 发送，`.12/ens64np1/20.1.1.12` 接收。
- 负向门闸：`.12` socket 已 bind、但尚未 `IP_ADD_MEMBERSHIP` 时发送独立 `prejoin` 探针；只以应用 socket 接收数判定，不用 tcpdump 代替 socket 语义。
- 主流量：join 后发送固定 2048 个、256-byte payload、带 `0..2047` sequence 的 UDP datagram；核对 unique、missing、duplicate、backward arrival 与精确顺序。
- 允许对象：只在 `.11/.12` 放置临时应用脚本并使用数据口发收；不改 `ens33`、默认路由、持久网络、PCI 驱动、XDP 或 Arista 配置。
- 非目标：不形成吞吐、时延、无丢包上限、长期稳定性或交换机 IGMP snooping 性能结论。
- 证据目录：`reports/20260721T015709Z-udp-multicast-market-data-smoke/`
- 结果：pre-join 探针发送 8、socket 收到 0；join 后发送 2048、接收有效/唯一 2048，missing/duplicate/backward/malformed/foreign 均为 0，顺序精确。
- 清理：receiver 明确退组并关闭 socket；独立最终健康检查确认两端无目标 membership/IGMP entry/listener/process/temp，原驱动/IP/10G/hugepages/XDP absence 与全网连通均通过。
- 偏差：首次编排在所有流量和远端 cleanup 完成后，内联 final-audit heredoc 语法错误 rc=2；修正后的独立 final-health rc=0。见 PIT-60，不重发数据掩盖首次失败。
