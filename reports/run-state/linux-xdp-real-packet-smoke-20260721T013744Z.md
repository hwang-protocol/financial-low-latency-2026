# Linux XDP Real-Packet Smoke Run State

- `RUN_ID`: `20260721T013744Z`
- 状态：`COMPLETED`
- 创建时间：2026-07-21 01:37:44 UTC / 2026-07-21 09:37:44 CST
- 首个实测门闸：2026-07-21 01:37:30 UTC / 2026-07-21 09:37:30 CST
- 目标：在 `.12/ens64np1` 临时挂载精确匹配 `.2 → .12` IPv4 ICMP 的最小 XDP drop 程序，完成 attach 前 PASS、attach 时 DROP+counter、detach 后 PASS 的真包闭环
- Profile：`bcm57414-xdp-exact-icmp-drop-v1`
- 唯一主变量：`.12/ens64np1` 上临时 XDP attach 状态
- 接收端：`10.1.1.12 / vm-broadcom-02 / ens64np1 / 20.1.1.12/24 / bnxt_en / 0000:03:00.0`
- 发送端：`10.1.1.2 / vm-2522-02 / ens64np1 / 20.1.1.2/24`；只发送 ICMP，不改变驱动或配置
- 严禁对象：两端 `ens33`、跳板机网络、Arista 配置、`.11` 数据口
- Attach 策略：先 native；仅在驱动明确拒绝时才 fallback generic，并在报告中保留原始错误
- 恢复策略：远端 guard 注册 EXIT/HUP/INT/TERM trap 且有 120 秒自动超时；控制端完成计数后发送 stop，随后显式复核并删除精确 `/run` 临时文件
- 结果目录：`reports/20260721T013744Z-linux-xdp-icmp-drop-smoke/`
- 完成结果：native attach rc=0；attach 前 `.2→.12` 5/5 PASS，attach 中 7/7 DROP 且 map 从 0 精确增至 7，管理面 7/7 PASS，detach 后数据 5/5 PASS
- 最终状态：`.12` 无 XDP/map/远端临时文件，恢复 `bnxt_en`、原 IP、10G/full、服务 active/enabled；到 `.1/.2/.11/.254` 各 3/3，管理面正常；`.2` 驱动与配置未变
- 判定：`PASS WITH WARNINGS`；`/run noexec` 已按 PIT-40 解决，native XDP 的 maxmtu/统计重置副作用按 PIT-41 保留边界
