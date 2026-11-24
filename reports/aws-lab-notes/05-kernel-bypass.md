# 第 05 章：OpenOnload / TCPDirect / DPDK 内核旁路

- **状态：** ⬜ 未开始
- **课程原文：** [05-openonload-tcpdirect-dpdk-kernel-bypass.md](../../05-openonload-tcpdirect-dpdk-kernel-bypass.md)
- **AWS 能否做：** 🟡 只有 DPDK 部分

## 各部分在 AWS 上能否做

| 技术 | AWS | 原因 |
|---|---|---|
| OpenOnload | ❌ | 只支持 AMD Solarflare（X2522 等）网卡 |
| TCPDirect | ❌ | 同上 |
| DPDK | 🟡 | DPDK 有 ENA 驱动（ENA PMD），可以做；但要给 DPDK 单独加一块网卡（ENI），否则 SSH 会断 |
| F-Stack | 🟡 | 基于 DPDK，同上 |

## 只能读文档的部分

OpenOnload 和 TCPDirect 的原理、测量方法可以读课程原文和课程留下的运行结果（`reports/course-runs/`）来理解。

## 结果

（待填）

## 笔记 / 疑问

（自己补充）
