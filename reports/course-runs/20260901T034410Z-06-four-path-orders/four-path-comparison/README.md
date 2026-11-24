# Chapter 06 four real order transports

RUN_ID: `20260901T034410Z-06-four-path-orders`

四条路径都使用 1 股可立即成交 IOC、SoupBinTCP/OUCH、逐笔单飞和锁定的 DEQUE_CV 应用交接。
DPDK 必须独占 VFIO，所以固定放在单独阶段，不能冒充和三条 sfc 路径逐笔交错。

| Transport | median round P50 send→final | median round P99 | median round P50 queue→final |
| --- | ---: | ---: | ---: |
| Kernel Socket | 47615 ns | 67092 ns | 55191 ns |
| OpenOnload | 30432 ns | 78924 ns | 38797 ns |
| TCPDirect | 28993 ns | 45318 ns | 36649 ns |
| DPDK + F-Stack TCP | 46000 ns | 112458 ns | 51655 ns |
