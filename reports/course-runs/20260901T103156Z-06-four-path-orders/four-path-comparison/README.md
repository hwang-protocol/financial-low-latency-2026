# Chapter 06 four real order transports

RUN_ID: `20260901T103156Z-06-four-path-orders`

四条路径都使用 1 股可立即成交 IOC、SoupBinTCP/OUCH、逐笔单飞和锁定的 DEQUE_CV 应用交接。
四轮顺序同时平衡位置与行内一阶前序：每条路径各占一次第 1 / 2 / 3 / 4 位，12 种不同的有序前序各在轮内出现一次；每格先用 100 笔 warmup 减弱前一路径的残留影响，但不宣称将其消除。
连续轮次之间还有 3 条边界，它们会不可避免地重复已有前序；因此完整执行序列只承诺12 种可能前序都至少出现，不把 15 次连续切换泛称为全部各一次。DPDK 到位时独占 VFIO，随后按下一路径所需 mode 切换。

全部提交身份硬门（warmup + measurement）：submitted total=unique=17600；16 份结果均通过文件内与全局唯一性检查。
正式样本身份硬门：measured total=unique=16000；每轮 measurement 提交 ID 与 MEASUREMENT_SAMPLES 返回 ID 的顺序和集合精确一致。
交易所账本硬门：before=2070，after=19670，delta=expected=17600；少增会抓住缓存复用，多增会抓住 GUI 或外来订单。
每格在首笔 warmup 后保存 pre 原件，再用剩余 warmup 隔开重型探针；1000 笔结束后保存 post 原件，两次都在计时窗外。

下表是四轮统计量中位数，只作描述；平衡主表由后处理器对四个 Williams 单元等权。

| Transport | send→final P50 / P95 / P99 | queue→final P50 / P95 / P99 |
| --- | ---: | ---: |
| Kernel Socket | 39801 / 53427 / 66692 ns | 48983 / 62503 / 76670 ns |
| OpenOnload | 25584 / 31467 / 36755 ns | 33733 / 40403 / 45934 ns |
| TCPDirect | 20582 / 27512 / 34986 ns | 29238 / 36744 / 47544 ns |
| DPDK + F-Stack TCP | 29386 / 37489 / 42952 ns | 35223 / 48912 / 71262 ns |
