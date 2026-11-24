# Chapter 06 four real order transports

RUN_ID: `20260915T115124Z-02-trading-platform`

四条路径都使用 1 股可立即成交 IOC、SoupBinTCP/OUCH、逐笔单飞和锁定的 DEQUE_CV 应用交接。
四轮顺序同时平衡位置与行内一阶前序：每条路径各占一次第 1 / 2 / 3 / 4 位，12 种不同的有序前序各在轮内出现一次；每格先用 100 笔 warmup 减弱前一路径的残留影响，但不宣称将其消除。
连续轮次之间还有 3 条边界，它们会不可避免地重复已有前序；因此完整执行序列只承诺12 种可能前序都至少出现，不把 15 次连续切换泛称为全部各一次。DPDK 到位时独占 VFIO，随后按下一路径所需 mode 切换。

全部提交身份硬门（warmup + measurement）：submitted total=unique=17600；16 份结果均通过文件内与全局唯一性检查。
热身响应身份硬门：warmup total=unique=1600；每轮 warmup 提交 ID、返回 ID、顺序和 Executed 结果精确闭合。
正式样本身份硬门：measured total=unique=16000；每轮 measurement 提交 ID、返回 ID、顺序和 Executed 结果精确闭合。
交易所账本硬门：before=35206，after=52806，delta=expected=17600；少增会抓住缓存复用，多增会抓住 GUI 或外来订单。
每格在首笔 warmup 后保存 pre 原件，再用剩余 warmup 隔开重型探针；1000 笔结束后保存 post 原件，两次都在计时窗外。
DPDK 端点原件来自 Exchange 侧当前服务端 PID 所见 peer；它不冒充客户端 PID 绑定。

下表是四轮统计量中位数，只作描述；平衡主表由后处理器对四个 Williams 单元等权。

| Transport | send→final P50 / P95 / P99 | queue→final P50 / P95 / P99 |
| --- | ---: | ---: |
| Kernel Socket | 31023 / 47603 / 53044 ns | 39582 / 57104 / 63639 ns |
| OpenOnload | 20527 / 24271 / 26715 ns | 29179 / 33171 / 37324 ns |
| TCPDirect | 20050 / 23789 / 25923 ns | 28403 / 33077 / 38674 ns |
| DPDK + F-Stack TCP | 24204 / 30152 / 31842 ns | 29582 / 37351 / 53026 ns |
