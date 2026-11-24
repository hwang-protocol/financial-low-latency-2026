#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
source Documents/newDoc/assets/common/flle-remote.sh
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-10-itch-pipeline"
OUT="Documents/reports/course-runs/$RUN_ID"; REMOTE="/var/tmp/$RUN_ID"
SRC=Documents/newDoc/assets/09-verilator
mkdir -p "$OUT/raw" "$OUT/artifacts"; printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
cleanup(){ ssh -n "${FLLE_SSH_OPTS[@]}" root@10.1.1.101 "find '$REMOTE' -type f -delete 2>/dev/null; find '$REMOTE' -depth -type d -empty -delete 2>/dev/null || true"; }
trap cleanup EXIT
ssh -n "${FLLE_SSH_OPTS[@]}" root@10.1.1.101 "mkdir '$REMOTE'"
scp -q "${FLLE_SSH_OPTS[@]}" "$SRC/market_pipeline.sv" "$SRC/itch_pipeline_tb.cpp" "$SRC/itch_add_order_golden.txt" root@10.1.1.101:"$REMOTE/"
ssh -n "${FLLE_SSH_OPTS[@]}" root@10.1.1.101 "cd '$REMOTE'; verilator --cc --exe --trace --assert --build --Wall -Wno-fatal --top-module market_pipeline market_pipeline.sv itch_pipeline_tb.cpp; ./obj_dir/Vmarket_pipeline itch-pipeline.vcd itch_add_order_golden.txt" 2>&1 | tee "$OUT/raw/clean.txt"
ssh -n "${FLLE_SSH_OPTS[@]}" root@10.1.1.101 "cd '$REMOTE'; verilator -DFLLE_MUTANT_FIFO --cc --exe --trace --assert --build --Wall -Wno-fatal --Mdir obj_mutant --top-module market_pipeline market_pipeline.sv itch_pipeline_tb.cpp; set +e; result=\$(./obj_mutant/Vmarket_pipeline mutant.vcd itch_add_order_golden.txt 2>&1); rc=\$?; set -e; printf '%s\n' \"\$result\"; test \"\$rc\" -ne 0; grep -q 'TEST_FAIL fifo accepted while full' <<<\"\$result\"" 2>&1 | tee "$OUT/raw/mutant.txt"
scp -q "${FLLE_SSH_OPTS[@]}" root@10.1.1.101:"$REMOTE/itch-pipeline.vcd" "$OUT/artifacts/"
cp "$SRC/market_pipeline.sv" "$SRC/itch_pipeline_tb.cpp" "$SRC/itch_add_order_golden.txt" "$OUT/artifacts/"
(cd "$OUT" && sha256sum raw/* artifacts/* run.env >SHA256SUMS)
printf 'evidence=%s\n' "$OUT"
