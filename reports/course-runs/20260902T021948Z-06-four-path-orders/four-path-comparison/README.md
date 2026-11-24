# Chapter 06 four real order transports

RUN_ID: `20260902T021948Z-06-four-path-orders`

四条路径都使用 1 股可立即成交 IOC、SoupBinTCP/OUCH、逐笔单飞和锁定的 DEQUE_CV 应用交接。
四轮顺序同时平衡位置与行内一阶前序：每条路径各占一次第 1 / 2 / 3 / 4 位，12 种不同的有序前序各在轮内出现一次；每格先用 100 笔 warmup 减弱前一路径的残留影响，但不宣称将其消除。
连续轮次之间还有 3 条边界，它们会不可避免地重复已有前序；因此完整执行序列只承诺12 种可能前序都至少出现，不把 15 次连续切换泛称为全部各一次。DPDK 到位时独占 VFIO，随后按下一路径所需 mode 切换。

全部提交身份硬门（warmup + measurement）：submitted total=unique=17600；16 份结果均通过文件内与全局唯一性检查。
热身响应身份硬门：warmup total=unique=1600；每轮 warmup 提交 ID、返回 ID、顺序和 Executed 结果精确闭合。
正式样本身份硬门：measured total=unique=16000；每轮 measurement 提交 ID、返回 ID、顺序和 Executed 结果精确闭合。
交易所账本硬门：before=2070，after=19670，delta=expected=17600；少增会抓住缓存复用，多增会抓住 GUI 或外来订单。
每格在首笔 warmup 后保存 pre 原件，再用剩余 warmup 隔开重型探针；1000 笔结束后保存 post 原件，两次都在计时窗外。
DPDK 端点原件来自 Exchange 侧当前服务端 PID 所见 peer；它不冒充客户端 PID 绑定。

下表是四轮统计量中位数，只作描述；平衡主表由后处理器对四个 Williams 单元等权。

| Transport | send→final P50 / P95 / P99 | queue→final P50 / P95 / P99 |
| --- | ---: | ---: |
| Kernel Socket | 34902 / 50488 / 55526 ns | 43637 / 60343 / 67792 ns |
| OpenOnload | 21521 / 26442 / 28873 ns | 30071 / 35307 / 40459 ns |
| TCPDirect | 20991 / 25665 / 28060 ns | 30030 / 35169 / 40192 ns |
| DPDK + F-Stack TCP | 25147 / 32214 / 35617 ns | 30612 / 42365 / 55132 ns |
