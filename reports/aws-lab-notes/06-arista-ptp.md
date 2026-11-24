# 第 06 章：Arista cut-through 与 PTP 时间

- **状态：** ⛔ AWS 上做不了，只能读文档
- **课程原文：** [06-arista-cut-through-ptp-time.md](../../06-arista-cut-through-ptp-time.md)

## 为什么做不了

| 需要的 | AWS 上 |
|---|---|
| Arista 7150S 交换机（cut-through、LANZ、QoS 配置） | 没有，VPC 网络不能登录、不能配置 |
| 网卡硬件时间戳（X2522 的 SO_TIMESTAMPING） | ENA 不支持网卡收发包的硬件时间戳 |
| PTP 时钟同步 | AWS 有 Time Sync Service，部分实例支持 PTP 硬件时钟（PHC），但精度和课程的交换机 PTP 不同，且看不到交换机侧 |

## 可以做的

- 读课程原文，理解 cut-through 和 store-and-forward、QoS 严格优先级、LANZ、PTP 的原理
- 看 `reports/course-runs/` 里课程在物理实验台上留下的结果
- 要实际动手，需要回乾颐堂实验台（VPN → vCenter → Win2019 → SSH .111）

## 笔记 / 疑问

（自己补充）
