# Kernel / OpenOnload true-order mechanism probe

`strace` 只作路径收据，不读取被跟踪订单的延迟。

第一表来自 32 笔 `strace` 跟踪真单；第二表来自独立的 1000 笔无跟踪真单及随后 200 ms 观察窗。
`schedule_probe.wall_ns` 包含管理口提交、查询与短连接编排，不作订单延迟。

| Path | traced orders (32) | order TCP syscalls |
| --- | ---: | ---: |
| SOCKET | 32 | 192 |
| OPENONLOAD | 32 | 0 |

| Path | untraced orders (1000) | voluntary switches | CPU runtime | runqueue wait |
| --- | ---: | ---: | ---: | ---: |
| SOCKET | 1000 | 2040 | 49057972 ns | 1692536 ns |
| OPENONLOAD | 1000 | 1019 | 51170995 ns | 1279743 ns |
