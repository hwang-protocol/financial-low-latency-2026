#!/usr/bin/env bash
cd ~/flle/app/tests
TR=172.31.12.156; out=~/flle/ch04/03-spsc-spin; mkdir -p $out
echo "START $(date -u +%FT%TZ)"
taskset -c 1 python3 software_measurement_aws.py --profiles FIXED_CV:dedicated,SPSC_SPIN:dedicated --base-url http://$TR:8088 --trader-host $TR --repeat 8 --control-port 48121 --treatment-cpu 2 --control-cpu 3 --precondition-samples 1000 --warmup 40 --samples 400 --interval-us 20000 --control-every 5 --stability-limit-pct 20 --environment-equivalence-pct 40 --direction-consistency-pct 87.5 --single-profile-spread-limit 1.5 --bootstrap-resamples 4000 --bootstrap-seed 20260828 --shared-cpu 1 --housekeeping-cpus 0-1 --output $out/software.csv > $out/result.txt 2>&1
echo "rc=$? $(date -u +%FT%TZ)"
taskset -c 1 python3 restore_software_profile_aws.py > ~/flle/ch04/restore-after-03.txt 2>&1
echo RERUN-DONE
