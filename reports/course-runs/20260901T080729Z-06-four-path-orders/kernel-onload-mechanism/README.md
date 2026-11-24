# Kernel / OpenOnload true-order mechanism probe

`strace` 只作路径收据，不读取被跟踪订单的延迟。

前两列来自 32 笔 `strace` 跟踪真单；后三列来自独立的 1000 笔无跟踪真单及随后 200 ms 观察窗。
`schedule_probe.wall_ns` 包含管理口提交、查询与短连接编排，不作订单延迟。

| Path | traced orders (32-order batch) | traced order TCP syscalls | untraced 1000-order probe voluntary switches | untraced 1000-order probe CPU runtime | untraced 1000-order probe runqueue wait |
| --- | ---: | ---: | ---: | ---: | ---: |
| SOCKET | 32 | 192 | 2192 | 26795998 ns | 382809 ns |
| OPENONLOAD | 32 | 0 | 1023 | 51282191 ns | 250101 ns |
