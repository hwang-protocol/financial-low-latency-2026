# Chapter 06 four real order transports

RUN_ID: `20260901T080729Z-06-four-path-orders`

四条路径都使用 1 股可立即成交 IOC、SoupBinTCP/OUCH、逐笔单飞和锁定的 DEQUE_CV 应用交接。
四轮顺序同时平衡位置与行内一阶前序：每条路径各占一次第 1 / 2 / 3 / 4 位，12 种不同的有序前序各在轮内出现一次；每格先用 100 笔 warmup 减弱前一路径的残留影响，但不宣称将其消除。
连续轮次之间还有 3 条边界，它们会不可避免地重复已有前序；因此完整执行序列只承诺12 种可能前序都至少出现，不把 15 次连续切换泛称为全部各一次。DPDK 到位时独占 VFIO，随后按下一路径所需 mode 切换。

全部提交身份硬门（warmup + measurement）：submitted total=unique=17600；16 份结果均通过文件内与全局唯一性检查。
正式样本身份硬门：measured total=unique=16000；每轮 measurement 提交 ID 与 MEASUREMENT_SAMPLES 返回 ID 的顺序和集合精确一致。
交易所账本硬门：before=2070，after=19670，delta=expected=17600；少增会抓住缓存复用，多增会抓住 GUI 或外来订单。

| Transport | send→final P50 / P95 / P99 | queue→final P50 / P95 / P99 |
| --- | ---: | ---: |
| Kernel Socket | 39684 / 48499 / 77094 ns | 48282 / 58796 / 91335 ns |
| OpenOnload | 23761 / 30413 / 43130 ns | 31742 / 40741 / 73447 ns |
| TCPDirect | 24463 / 31431 / 72560 ns | 32392 / 40422 / 94422 ns |
| DPDK + F-Stack TCP | 29280 / 32102 / 37751 ns | 34986 / 65056 / 77541 ns |
