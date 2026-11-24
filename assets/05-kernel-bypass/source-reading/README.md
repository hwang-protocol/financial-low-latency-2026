# 第五章源码索引

这些文件供阅读与图文对照。Socket／Onload 的 trader.cpp、posix_order_transport.cpp、order_transport.hpp 来自 posix-qos-v1 更新包；其余 C++ 文件逐字来自 v13 封存源码；`start_sfc_clients.sh` 仅摘录当前控制脚本中的启动函数。这里不参与编译、安装或启动。

下面使用以项目根目录为起点的绝对链接，直接打开文件与对应行；对应磁盘目录为 `/qyt-fll/assets/05-kernel-bypass/source-reading/`。

| 图中位置 | 原始源码 |
|---|---|
| K1 | [posix_order_transport.cpp:14](posix_order_transport.cpp#L14) |
| K2 | [common.hpp:118](common.hpp#L118) |
| K3 | [common.hpp:130](common.hpp#L130) |
| K4 | [common.hpp:133](common.hpp#L133) |
| O1 | [start_sfc_clients.sh:6](start_sfc_clients.sh#L6) |
| O2 | [common.hpp:118](common.hpp#L118) |
| O3 | [common.hpp:130](common.hpp#L130) |
| Z1 | [tcpdirect_order_transport.cpp:31](tcpdirect_order_transport.cpp#L31) |
| Z2 | [tcpdirect_order_transport.cpp:71](tcpdirect_order_transport.cpp#L71) |
| Z3 | [tcpdirect_order_transport.cpp:87](tcpdirect_order_transport.cpp#L87) |
| Z4 | [tcpdirect_order_transport.cpp:82](tcpdirect_order_transport.cpp#L82) |
| D1 | [dpdk_trader.cpp:116](dpdk_trader.cpp#L116) |
| D2 | [dpdk_trader.cpp:309](dpdk_trader.cpp#L309) |
| D3 | [dpdk_trader.cpp:326](dpdk_trader.cpp#L326) |
| D4 | [dpdk_trader.cpp:631](dpdk_trader.cpp#L631) |

队列等待实现：[order_queue.hpp](order_queue.hpp#L80)。

O4 的事件推进由外部 Onload 库实现；项目沿用 Socket 接口。完整浏览器阅读页与 SHA 映射位于上级目录。
