# U250 RX adapter local validation

- RUN_ID: `20260918T093350Z-u250-rx-adapter`
- Start UTC: 2026-09-18 09:33:50
- Execution: local Linux workspace `/financial-low-latency`, no Windows/FPGA access.
- Scope: new `u250-gui/flle_rx_filter.sv` and `flle_rx_filter_tb.sv`, unchanged existing `market_filter.sv`.
- Icarus compile: exit 0 (`compile.log`); simulation: exit 0 (`simulation.log`), 29 named cases.
- Verilator 4.038 final RTL lint: exit 0 (`lint-final.log`). First attempts rejected unsupported `--timing` and `-Wno-UNUSEDSIGNAL` switches (`lint.log`, `lint-rtl.log`); removed unnecessary timing switch for RTL-only lint and used this version's `-Wno-UNUSED` spelling.
- Icarus constant-select notices enlarge the combinational sensitivity set. No suppressed protocol/test failures.
- Core source unchanged per `git diff -- Documents/newDoc/assets/09-verilator/market_filter.sv`.
- Windows XSim, synthesis, implementation, line rate, PCIe control, and board integration: NOT_RUN.

Commands executed manually by the assistant for development validation, not a classroom automation script:

```text
iverilog -g2012 -s flle_rx_filter_tb -o /tmp/flle-u250-rx-adapter.vvp Documents/newDoc/assets/09-verilator/market_filter.sv Documents/newDoc/assets/09-verilator/u250-gui/flle_rx_filter.sv Documents/newDoc/assets/09-verilator/u250-gui/flle_rx_filter_tb.sv
vvp /tmp/flle-u250-rx-adapter.vvp
verilator --lint-only -Wall -Wno-DECLFILENAME -Wno-UNUSED -Wno-PINCONNECTEMPTY --top-module flle_rx_filter Documents/newDoc/assets/09-verilator/market_filter.sv Documents/newDoc/assets/09-verilator/u250-gui/flle_rx_filter.sv
```
