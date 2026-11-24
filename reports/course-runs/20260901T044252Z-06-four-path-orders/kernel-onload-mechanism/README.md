# Kernel / OpenOnload true-order mechanism probe

`strace` 只作路径收据，不读取被跟踪订单的延迟。

| Path | true orders | order TCP syscalls | voluntary switches | CPU runtime |
| --- | ---: | ---: | ---: | ---: |
| SOCKET | 32 | 192 | 2027 | 31259384 ns |
| OPENONLOAD | 32 | 0 | 1020 | 40730327 ns |
