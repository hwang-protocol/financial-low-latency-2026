# Kernel / OpenOnload true-order mechanism probe

`strace` 只作路径收据，不读取被跟踪订单的延迟。

第一表来自 32 笔 `strace` 跟踪真单；第二表来自独立的 1000 笔无跟踪真单及随后 200 ms 观察窗。
第二表的线程身份、CPU 绑定与计数差全部从已落盘的 `status` / `schedstat` pre/post 原文复算。
计数窗口从远端 pre 原件到远端 post 原件；原件传输与解析在 post 之后，不进入这段差值。
探针本身的执行字节保存在 `provenance/`；其 SHA 同时写入 `summary.json`。
`schedule_probe.wall_ns` 包含管理口提交、查询与短连接编排，不作订单延迟。

| Path | traced orders (32) | order TCP syscalls |
| --- | ---: | ---: |
| SOCKET | 32 | 192 |
| OPENONLOAD | 32 | 0 |

| Path | untraced orders (1000) | voluntary switches | CPU runtime | runqueue wait |
| --- | ---: | ---: | ---: | ---: |
| SOCKET | 1000 | 2026 | 26629203 ns | 1220834 ns |
| OPENONLOAD | 1000 | 1022 | 40357760 ns | 2172916 ns |
