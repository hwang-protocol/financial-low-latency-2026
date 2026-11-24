# Chapter 06 balance-preserving analysis

主表先在每个 Williams 单元内计算 nearest-rank 分位数，再把四个单元等权平均。
四格才是平衡重复单位；4000 笔合并分布和四轮中位数保留在 JSON 中，只作描述。

| Transport | send→final P50 / P95 / P99 | queue→final P50 / P95 / P99 |
| --- | ---: | ---: |
| Kernel Socket | 38000 / 50098 / 61608 ns | 47058 / 59433 / 70999 ns |
| OpenOnload | 24847 / 31958 / 39771 ns | 33157 / 41271 / 51268 ns |
| TCPDirect | 24833 / 31697 / 41395 ns | 33753 / 40739 / 51191 ns |
| DPDK + F-Stack TCP | 28842 / 36802 / 51783 ns | 34613 / 51843 / 74936 ns |
