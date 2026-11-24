# 第9章 2026-08-20 现场证据来源

这些文件来自同一轮 `20260820T024758Z-09-p4-live`。本轮在 `.101` 重新编译
P4 source，在 `.11` 双 BCM 物理 arm 运行 BMv2，并由 `.1/.2` 发送与接收真实
Ethernet 帧；另在 `.101` 独立完成 P4Runtime `INSERT → READ → DELETE → empty`
闭环。设备与 EOS 均在采集后恢复基线。

| 课程资产 | 当前来源 | SHA-256 |
| --- | --- | --- |
| `linklocal-tcpdump.txt` | 两口 `tcpdump -Q in/out` 的四份逐字解码：ingress 各 3 帧，egress 各 0 帧 | `ee2691e23993a9776f886e261321fc85cef4159d4a26a490f512182ba0779393` |
| `linklocal-eos-stp.txt` | 临时 VLAN3101/3102 物理双臂窗口的 EOS 只读快照；四口均 forwarding | `59912ca9745915f002fb91e464ce029c82840ec1d3e437b2d1142d8048479d49` |
| `counter-hit-lr-before.txt` | `simple_switch_CLI --thrift-port 9090`，hit-lr 发包前 | `60f36b2e1c4e5aede65a56a60ee239d1788d56d111abb387efe2c45d498ad348` |
| `counter-hit-lr-after.txt` | 同一窗口发包后，`mac_hit_forward[1] +5` | `a08f5f50ee6f01fedff2bccd177d87983f4dd54f890a81a5673152dc9dcaca80` |
| `counter-miss-lr-before.txt` | unknown-unicast 发包前 | `b3a60a26827d2f54a91737b007c98d5cd4f89b65678a62dde43147f218d4b313` |
| `counter-miss-lr-after.txt` | 同一窗口发包后，`mac_miss_default_drop[1] +5` | `c9b53b409c4bf4dce66ebde35b814f925a63ce442191ba0fe7bd102a85bb9716` |
| `p4runtime-rw.log` | 当前 P4Info/JSON 上的 P4Runtime shell 客户端逐字输出 | `6583daae428a40bde1564d234e87e919c3fe9ea4b7ce5f3e892594e3c46be0d2` |

完整现场树位于
`Documents/reports/newdoc-full-live-20260820/live/p4/20260820T024758Z-09-p4-live/`，
其中还保存双向 hit、双向 miss、broadcast、停止负例、重启恢复、P4Runtime server
日志、EOS 回滚和最终设备审计。上表只投影绿色卡需要逐字展示的最小窗口。
