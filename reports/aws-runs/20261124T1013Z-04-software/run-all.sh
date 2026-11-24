#!/usr/bin/env bash
# Chapter 04 on AWS: same parameters as assets/04-live-software/0[1-4]-*.sh, adapted host/mode.
set -uo pipefail
cd ~/flle/app/tests
TR=172.31.12.156
COMMON=(--base-url http://$TR:8088 --trader-host $TR --repeat 8 --control-port 48121 --treatment-cpu 2 --control-cpu 3
  --precondition-samples 1000 --warmup 40 --samples 400 --interval-us 20000 --control-every 5 --stability-limit-pct 20
  --environment-equivalence-pct 40 --direction-consistency-pct 87.5 --single-profile-spread-limit 1.5
  --bootstrap-resamples 4000 --bootstrap-seed 20260828)
run() { # name profiles extra...
  local name=$1 prof=$2; shift 2
  local out=~/flle/ch04/$name; mkdir -p $out
  echo "===== START $name $(date -u +%FT%TZ)"
  taskset -c 1 python3 software_measurement_aws.py --profiles "$prof" "${COMMON[@]}" "$@" --output $out/software.csv > $out/result.txt 2>&1
  echo "rc=$? $name $(date -u +%FT%TZ)"
}
run 01-deque-cv        DEQUE_CV:dedicated                      --shared-cpu 1 --housekeeping-cpus 0-1
run 02-fixed-cv        DEQUE_CV:dedicated,FIXED_CV:dedicated   --shared-cpu 1 --housekeeping-cpus 0-1
run 03-spsc-spin       FIXED_CV:dedicated,SPSC_SPIN:dedicated  --shared-cpu 1 --housekeeping-cpus 0-1
run 04-spsc-shared-cpu SPSC_SPIN:dedicated,SPSC_SPIN:shared    --shared-cpu 0 --housekeeping-cpus 0
taskset -c 1 python3 restore_software_profile_aws.py > ~/flle/ch04/restore.txt 2>&1; echo "restore rc=$?"
echo ALL-DONE
