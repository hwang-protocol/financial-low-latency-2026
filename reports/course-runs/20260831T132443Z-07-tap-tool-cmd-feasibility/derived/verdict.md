# tap/tool 命令可行性

- RUN: `20260831T132443Z-07-tap-tool-cmd-feasibility`
- 范围: 只动空闲 Et3；不开 tap aggregation / mode exclusive
- 交还: `default interface Ethernet3`；diffs 回到课程基线

## 命令

| 命令 | 结果 |
|---|---|
| `switchport mode tap` | 接受，`show active` 可见 |
| `switchport mode tool` | 接受，`show active` 可见 |
| `mac timestamp before-fcs` | 接受，与 tool 同时可见 |
| `monitor session 1` / `FLLEPROBE` | `% Incomplete command`，本轮不算可用 |

## 环境

命令可行。完整 tap-tool 实战还缺已接线 tool 口和带 PHC 的分析网卡。VLAN20 交还后 ping 3/3。
