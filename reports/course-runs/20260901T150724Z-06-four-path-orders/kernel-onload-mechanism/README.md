# Kernel / OpenOnload true-order mechanism probe

`strace` 只作路径收据，不读取被跟踪订单的延迟。

第一表来自 32 笔 `strace` 跟踪真单；第二表来自独立的 1000 笔无跟踪真单及随后 200 ms 观察窗。
第二表的线程身份、CPU 绑定与计数差全部从已落盘的 `status` / `schedstat` pre/post 原文复算。
计数窗口从远端 pre 原件到远端 post 原件；原件传输与解析在 post 之后，不进入这段差值。
探针本身的执行字节保存在 `provenance/`；其 SHA 同时写入 `summary.json`。
四批被比较订单各自保存 `.batch.json`：RESET generation、提交 ID 顺序与返回样本 ID 顺序/集合必须精确一致，且每笔均为 `E` 并通过共同计时恒等式。
`strace` 脱离后还要等跟踪进程真正退出并同步 trace 文件，才允许复制原文。
`schedule_probe.wall_ns` 包含管理口提交、查询与短连接编排，不作订单延迟。

| Path | traced orders (32) | order TCP syscalls |
| --- | ---: | ---: |
| SOCKET | 32 | 192 |
| OPENONLOAD | 32 | 0 |

| Path | untraced orders (1000) | voluntary switches | CPU runtime | runqueue wait |
| --- | ---: | ---: | ---: | ---: |
| SOCKET | 1000 | 2024 | 17876863 ns | 2668255 ns |
| OPENONLOAD | 1000 | 1019 | 25015071 ns | 435913 ns |
