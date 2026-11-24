# U250 checksum pipeline validation

RUN_ID: `20260918T131841Z-u250-checksum-pipeline`.
Started 2026-09-18 13:18:41 UTC in the Linux maintenance workspace.

Trigger: user Windows post-route Path 81 screenshot, adapter data1_reg[216]
to core/m_mold_seq register CE, axis_aclk_0, requirement 4 ns, data delay
5.784 ns, 18 logic levels (including 8 CARRY8), slack -1.943 ns.
This run checks an RTL repair candidate, not Windows timing closure.
Original adapter preserved in design/evidence/ch09-u250-checksum-pipeline-20260918/.

Final local results: adapter-sim-v3.log PASS cases=29; control-sim-v3.log
PASS cases=12 vendor_cdc=0; stress-sim.log PASS cases=102. All exit 0.
rtl-lint-final.log and integration-lint.log: exit 0, no diagnostics.
Earlier failed candidates retained in unsuffixed and v2 simulation logs.

Simulation uses iverilog -g2012 then vvp, top flle_rx_filter_tb or
flle_rx_control_tb. Stress enables -Pflle_rx_filter_tb.EXTRA_PIPELINE_TESTS=1.
RTL lint uses verilator --lint-only -Wall -Wno-DECLFILENAME -Wno-UNUSED
-Wno-PINCONNECTEMPTY; integration adds -Wno-TIMESCALEMOD, top p2p_250mhz,
fixed upstream src include directory and the existing interface_stubs.sv.
No AMD vendor simulation or Vivado implementation is available in this run.
Durable evidence and logs: Documents/design/evidence/ch09-u250-checksum-pipeline-20260918/.
