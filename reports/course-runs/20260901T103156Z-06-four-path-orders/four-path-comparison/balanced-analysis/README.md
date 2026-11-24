# Chapter 06 balance-preserving analysis

主表先在每个 Williams 单元内计算 nearest-rank 分位数，再把四个单元等权平均。
四格才是平衡重复单位；4000 笔合并分布和四轮中位数保留在 JSON 中，只作描述。
OpenOnload 四格原生 stackdump 另验 CTPIO：ctpio_pkts delta 合计 4396，DMA fallback delta 合计 0；这是硬件路径收据，不冒充订单数。
后处理所用 analyzer 与 measure 模块均逐字匹配 formal RUN 封存副本。

| Transport | send→final P50 / P95 / P99 | queue→final P50 / P95 / P99 |
| --- | ---: | ---: |
| Kernel Socket | 39650 / 53576 / 67733 ns | 48477 / 62539 / 78245 ns |
| OpenOnload | 24586 / 31279 / 37234 ns | 33056 / 39981 / 46737 ns |
| TCPDirect | 21528 / 27952 / 35846 ns | 30032 / 37208 / 47242 ns |
| DPDK + F-Stack TCP | 28856 / 37603 / 45108 ns | 34573 / 50032 / 71463 ns |
