set -Eeuo pipefail
cd "$1"
python3 -m zipfile -e inputs.zip .
cd flle-ch09-vivado
sha256sum -c SHA256SUMS
printf '\n===== Compile the SV circuit and GUI testbench =====\n'
iverilog -V 2>&1 | head -1 || true
iverilog -g2012 -s market_filter_sim_tb -o gui-test.vvp market_filter.sv market_filter_sim_tb.sv
vvp gui-test.vvp | tee gui-test.log
grep -Fx 'RTL_GUI_SIMULATION=PASS cases=14 hardware=NOT_RUN' gui-test.log
printf '\n===== Build and test the same core using Verilator =====\n'
bash offline-selftest.sh "$1/verilator-results"
printf '\n===== Archive verification logs =====\n'
cd "$1"
tar -czf results.tgz flle-ch09-vivado/gui-test.log verilator-results/tools.txt verilator-results/adapter-build.log verilator-results/adapter-selftest.log verilator-results/regression-build.log verilator-results/regression.log verilator-results/SHA256SUMS
sha256sum results.tgz > results.sha256
