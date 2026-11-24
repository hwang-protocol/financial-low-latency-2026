# 第 08 章：FPGA——从代码到设备

- **状态：** ⬜ 未开始
- **课程原文：** [08-fpga-from-code-to-device.md](../../08-fpga-from-code-to-device.md)
- **AWS 能否做：** 🟡 只能做仿真

## 各部分在 AWS 上能否做

| 部分 | AWS | 说明 |
|---|---|---|
| Verilog 代码 + Verilator 仿真（`assets/09-verilator`） | ✅ | 普通 Linux 实例即可 |
| 烧写到 Arista 交换机里的 FPGA | ❌ | 没有设备 |
| AWS F2 实例（自带 FPGA） | 🟡 | 是真 FPGA，但开发流程（Vivado、AFI）和课程的 Arista FPGA 不同，费用也高，不建议 |

## 结果

（待填）

## 笔记 / 疑问

（自己补充）
