# 7150 tap/tool 只读核验

- RUN: `20260831T131936Z-07-tap-tool-readonly-probe`
- 模式: 只读 `show` + 主机 `ethtool -T`
- 变更: 无 configuration mode，无 write/save/reload

## 结论

1. CLI 入口在。默认树有 `tap aggregation`、`switchport tap` / `tool`、`no mac timestamp`。
2. 当前未启用。`show tap aggregation groups` = `Tap-aggregation is not enabled`；`show monitor session` = `No sessions created`；24 口均为 access。
3. 没有空闲 DAC。只有 Et1/Et2/Et11/Et12 有线。
4. 第二条硬件尺子只在 `.1`/`.2` X2522。`.11` BCM 当前无 PHC。
5. 整机 tapagg 现在不能开：会关 bridging，VLAN20 会断。

不得把本 RUN 写成已经打过交换机时间戳。
