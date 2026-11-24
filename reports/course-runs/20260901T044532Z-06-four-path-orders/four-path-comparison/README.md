# Chapter 06 four real order transports

RUN_ID: `20260901T044532Z-06-four-path-orders`

四条路径都使用 1 股可立即成交 IOC、SoupBinTCP/OUCH、逐笔单飞和锁定的 DEQUE_CV 应用交接。
DPDK 必须独占 VFIO，所以固定放在单独阶段，不能冒充和三条 sfc 路径逐笔交错。

| Transport | median round P50 send→final | median round P99 | median round P50 queue→final |
| --- | ---: | ---: | ---: |
| Kernel Socket | 38426 ns | 102335 ns | 46852 ns |
| OpenOnload | 24373 ns | 65632 ns | 31862 ns |
| TCPDirect | 20281 ns | 104707 ns | 27895 ns |
| DPDK + F-Stack TCP | 28715 ns | 42608 ns | 34502 ns |
