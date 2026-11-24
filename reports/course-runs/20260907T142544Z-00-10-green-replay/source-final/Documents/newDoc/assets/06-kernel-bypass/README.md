# 当前入口调整：沿用第二章完整平台

第二章一次安装 Onload/IOMMU 前置和全部交易程序，当前平台状态统一读取 `Documents/reports/run-state/02-trading-baseline.env`。本章准备 A/B 使用 `01c-verify-runtime.sh` 与 `02c-verify-iommu.sh` 只读核对，各自生成RUN、退出码、原始日志及SHA清单（失败也留证）；准备 D `03-four-path-lab-ready.sh` 只启用已部署的路径测试客户端，并核对 Exchange/网页进程与文件清单不变。旧 A/B 文件仅兼容委托到第二章安装入口，不再作为本章课堂卡。重复贴运行⑤时，已有报告与原生证据分别归档到comparison-history和远端native-receipts-history；新一轮单独取证，保留前次结果。

下方历史验证段保留迁移前 RUN；当前完整顺刷状态见 `../../../00.NEXT-AI-HANDOFF.md`。

# 第 06 章资产入口

正文当前按下面顺序执行：

| 正文入口 | 唯一资产 |
|---|---|
| 准备 A | `01c-verify-runtime.sh` |
| 准备 B | `02c-verify-iommu.sh` |
| 准备 C | `02-four-path-preflight.sh` + `four-path-build-contract-audit.sh` |
| 准备 D | `03-four-path-lab-ready.sh` |
| 运行 ① | `04-socket-real-order.sh` |
| 运行 ② | `05-onload-real-order.sh` |
| 运行 ③ | `06-tcpdirect-real-order.sh` |
| 运行 ④ | `07-dpdk-real-order.sh` |
| 运行 ⑤ | `08-four-path-compare.sh` |
| 实验收尾 | `09-four-path-handoff.sh` |

其余同号脚本与源码是上一版组件尺子、历史诊断或教师恢复工具，不是本章当前绿卡。它们留盘用于复核旧 RUN；不得因文件名前缀相同替换上表入口。真实课堂结果只认正文列出的资产、当前固定制品和对应 RUN 的 SHA。

迁移前历史验证：固定运行包为 v12（SHA-256=`163618ccbb99d272d1f4703822781984d754c690d23fba5503e503486e33c9f3`）；准备 A `092818Z`、去重后的准备 B `100808Z`、准备 C `100819Z` 均 exit 0且 SHA 通过，DEC-191 正式发布复现基线仍是 `020809Z/021948Z`。准备 A 只管 Onload/设备入口/地址；准备 B 只管 Guest IOMMU/VFIO；准备 C 只管 runtime、source→ELF、行情资产、Builder、RSS 和总闸。当时 live RUN 为 `20260903T004905Z-06-four-path-orders`：运行 ①～⑤、17,600 笔账本和新版交接均 exit 0，网页 HTTP 200，`SFC/READY/sfc`，Socket / Onload / TCPDirect ONLINE，DPDK WAITING；`ch06-four-path.env` 正确指向该 RUN。默认收尾不再关闭四路控制台；完全停机只供教师维护或快照前使用。

维护者静态验证使用 Python 标准库 `unittest`，不依赖 `pytest`：

```bash
python3 -m unittest discover -s apps/flle-trading-lab/tests
python3 Documents/newDoc/assets/06-kernel-bypass/test-02b-guest-iommu-prep-static.py
```
