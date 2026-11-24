# U250 控制与接线候选验证

RUN_ID: `20260918T101540Z-u250-integration`。2026-09-18 10:15:40 UTC 开始本机验证。环境为 Linux 维护工作区，Icarus + Verilator 4.038；不是用户 Windows，也不是真实 FPGA。

## 结果与边界

| 检查 | 结果 |
| --- | --- |
| 更新后 flle_rx_filter_tb | 编译/仿真退出 0，29 项 PASS |
| flle_rx_control_tb | 最终编译/仿真退出 0，12 项 PASS，vendor_cdc=0 |
| flle_rx_filter RTL lint | 退出 0 |
| p2p_250mhz 默认 NUM_QDMA=1、NUM_INTF=1 | 端口声明替身下结构 lint 退出 0 |
| p2p_250mhz NUM_INTF=2 | 同上，退出 0 |
| flle_rx_port_tb | 声明替身下语法/展开退出 0，未运行功能仿真 |
| Windows 实际 AMD Clock Converter 联合仿真 | 后续用户截图确认 PASS，11 项，vendor_cdc=1；独立于上述 Linux RUN |
| 修改后整套 OpenNIC 综合/实现/CDC 报告/bitstream/实卡 | NOT_RUN |

`interface_stubs.sv` 只有端口声明，不含 AMD IP 行为，只用于检查模块名、端口宽度及连接；绝不能加入用户工程，不能用于声称 CDC 功能通过。Windows 测试使用工程已有 AMD IP，预期 11 项，因为 OpenNIC 用户总线没有 WSTRB，不能从它注入局部字节写测试。

2026-09-18 后续 Windows 截图：Vivado 2026.1，仿真顶层 flle_rx_port_tb，控制台 `U250_RX_CONTROL_SIMULATION=PASS cases=11 vendor_cdc=1 hardware=NOT_RUN`，正常 `$finish` 于 24856 ns。测试台路径为 C:/FPGA/build/au250/open_nic_shell/open_nic_shell.srcs/sim_1/imports/flle-integration/flle_rx_control_tb.sv。原始日志及图片文件尚未收回，本条是截图转录，不属于上方 Linux RUN_ID，也不是 FPGA 实测或完整 OpenNIC 验证。

控制测试覆盖：复位默认放行与身份寄存器；AW 先于 W；W 先于 AW；同拍 AW/W；B/R 背压稳定；授权仅丢一个目标；非目标保留额度；撤销；非法地址/非对齐/命令值/只读写入拒绝；部分字节写拒绝；一致的序号高低位快照；未使用额度超时；报文只到第一拍时超时；输出停顿期间写命令不提前确认；复位中止只有地址到达的半笔写入。

第一次控制测试为 11 项 PASS，随后补加同拍 AW/W，最终为 12 项。原记录保留。`register-lint.log` 为早期失败：旧 Verilator 不允许把同文件中已实例化的子模块直接选为顶层；随后对完整 p2p 顶层做结构检查，覆盖寄存器逻辑。`structural-lint.log` 的 TIMESCALEMOD 来自未选用的上游多 QDMA 分支引用缺失 IP；最终加 `-Wno-TIMESCALEMOD`。未屏蔽 WIDTH、MULTIDRIVEN、LATCH 等连接/逻辑诊断。Icarus 编译的 4 条 constant-select 通知表示 always_comb 敏感列表扩大。

## 执行方式

以下为开发验证命令留存，不作为用户操作脚本；在仓库根执行。输出分别存同名 run-state 和本目录。源文件摘要见 SOURCE-SHA256SUMS。

```bash
iverilog -g2012 -s flle_rx_control_tb -o /tmp/flle-u250-control.vvp Documents/newDoc/assets/09-verilator/market_filter.sv Documents/newDoc/assets/09-verilator/u250-gui/flle_rx_filter.sv Documents/newDoc/assets/09-verilator/u250-gui/flle_rx_port.sv Documents/newDoc/assets/09-verilator/u250-gui/flle_rx_control_tb.sv
vvp /tmp/flle-u250-control.vvp
iverilog -g2012 -s flle_rx_filter_tb -o /tmp/flle-u250-regression.vvp Documents/newDoc/assets/09-verilator/market_filter.sv Documents/newDoc/assets/09-verilator/u250-gui/flle_rx_filter.sv Documents/newDoc/assets/09-verilator/u250-gui/flle_rx_filter_tb.sv
vvp /tmp/flle-u250-regression.vvp
verilator --lint-only -Wall -Wno-DECLFILENAME -Wno-UNUSED -Wno-PINCONNECTEMPTY --top-module flle_rx_filter Documents/newDoc/assets/09-verilator/market_filter.sv Documents/newDoc/assets/09-verilator/u250-gui/flle_rx_filter.sv
verilator --lint-only -Wall -Wno-DECLFILENAME -Wno-UNUSED -Wno-PINCONNECTEMPTY -Wno-TIMESCALEMOD --top-module p2p_250mhz -Iartifacts/blobs/ch09-u250-reference/open-nic-shell-940907fc99fc8d73dbea0028b3a23095a660a42a/src Documents/newDoc/assets/09-verilator/u250-gui/p2p_250mhz.sv Documents/newDoc/assets/09-verilator/u250-gui/flle_rx_port.sv Documents/newDoc/assets/09-verilator/u250-gui/flle_rx_filter.sv Documents/newDoc/assets/09-verilator/market_filter.sv refs/evidence/ch09-u250-integration-20260918/interface_stubs.sv
```

双接口检查在最后一条命令增加 `-GNUM_INTF=2`。联合测试台语法检查命令：

```bash
iverilog -g2012 -s flle_rx_port_tb -o /tmp/flle-u250-vendor-elaboration.vvp Documents/newDoc/assets/09-verilator/market_filter.sv Documents/newDoc/assets/09-verilator/u250-gui/flle_rx_filter.sv Documents/newDoc/assets/09-verilator/u250-gui/flle_rx_port.sv Documents/newDoc/assets/09-verilator/u250-gui/flle_rx_control_tb.sv refs/evidence/ch09-u250-integration-20260918/interface_stubs.sv
```

未运行这个含声明替身的输出文件。真正 CDC 行为待 Windows XSim，不把纯语法结果称为联合验证。
