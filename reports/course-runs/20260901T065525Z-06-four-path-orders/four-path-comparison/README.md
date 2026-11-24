# Chapter 06 four real order transports

RUN_ID: `20260901T065525Z-06-four-path-orders`

四条路径都使用 1 股可立即成交 IOC、SoupBinTCP/OUCH、逐笔单飞和锁定的 DEQUE_CV 应用交接。
四轮采用 4×4 Latin 方：每条路径各占一次第 1 / 2 / 3 / 4 位。DPDK 到位时独占 VFIO，随后按下一路径所需 mode 切换。

client_order_id 身份硬门：total=unique=16000；16 份 raw 均通过文件内与全局唯一性检查。

| Transport | send→final P50 / P95 / P99 | queue→final P50 / P95 / P99 |
| --- | ---: | ---: |
| Kernel Socket | 39861 / 52007 / 82467 ns | 48262 / 62226 / 139769 ns |
| OpenOnload | 25214 / 30939 / 59319 ns | 32997 / 40440 / 90922 ns |
| TCPDirect | 24378 / 29832 / 57821 ns | 32082 / 39684 / 99852 ns |
| DPDK + F-Stack TCP | 27195 / 36770 / 46954 ns | 33461 / 66474 / 78521 ns |
