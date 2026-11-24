# Kernel / OpenOnload true-order mechanism probe

`strace` 只作路径收据，不读取被跟踪订单的延迟。

| Path | true orders | order TCP syscalls | voluntary switches | CPU runtime |
| --- | ---: | ---: | ---: | ---: |
| SOCKET | 32 | 192 | 2076 | 48271314 ns |
| OPENONLOAD | 32 | 0 | 1022 | 51100811 ns |
