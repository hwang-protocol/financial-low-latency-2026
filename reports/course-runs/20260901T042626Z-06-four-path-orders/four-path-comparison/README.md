# Chapter 06 four real order transports

RUN_ID: `20260901T042626Z-06-four-path-orders`

四条路径都使用 1 股可立即成交 IOC、SoupBinTCP/OUCH、逐笔单飞和锁定的 DEQUE_CV 应用交接。
DPDK 必须独占 VFIO，所以固定放在单独阶段，不能冒充和三条 sfc 路径逐笔交错。

| Transport | median round P50 send→final | median round P99 | median round P50 queue→final |
| --- | ---: | ---: | ---: |
| Kernel Socket | 38918 ns | 95412 ns | 47270 ns |
| OpenOnload | 22320 ns | 55936 ns | 30991 ns |
| TCPDirect | 25122 ns | 44805 ns | 33606 ns |
| DPDK + F-Stack TCP | 30441 ns | 66857 ns | 39135 ns |
