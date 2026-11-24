# Chapter 06 balance-preserving analysis

主表先在每个 Williams 单元内计算 nearest-rank 分位数，再把四个单元等权平均。
四格才是平衡重复单位；4000 笔合并分布和四轮中位数保留在 JSON 中，只作描述。
每格 pre/post 都从原始 /proc NUL argv、管理监听、线程 affinity 与 STATE 独立重建应用合同；不接受控制器布尔值代替路径证据。
OpenOnload 四格原生 stackdump 另验 CTPIO：ctpio_pkts delta 合计 4396，DMA fallback delta 合计 0；这是硬件路径收据，不冒充订单数。
DPDK 四格另从 Exchange 侧复解当前服务端 PID 下至少一个 20.1.1.2 目标端点；端点集合允许随快照变化，也不是 DPDK 客户端 PID 绑定证明。
DPDK 四格 port 0 的 RX/TX 均增长：ipackets delta 合计 8814，opackets delta 合计 4404；imissed / ierrors / oerrors / rx_nombuf 的格内 delta 全为 0。
DPDK 四格各自封存 1800 秒 systemd 独立所有权租约；验收格数 4，token 在 gate / client / lease 间一致。
TCPDirect 四格 ZF endpoint retransmits delta 合计 8；它只作路径健康线索，不能映射到某笔延迟样本。
后处理所用 analyzer 与 measure 模块均逐字匹配 formal RUN 封存副本。

| Transport | send→final P50 / P95 / P99 | queue→final P50 / P95 / P99 |
| --- | ---: | ---: |
| Kernel Socket | 38449 / 51017 / 56638 ns | 47223 / 60716 / 66699 ns |
| OpenOnload | 24851 / 28461 / 31936 ns | 33425 / 38414 / 44622 ns |
| TCPDirect | 24353 / 28127 / 31471 ns | 32970 / 37816 / 44827 ns |
| DPDK + F-Stack TCP | 30686 / 34228 / 40379 ns | 36501 / 46926 / 59407 ns |
