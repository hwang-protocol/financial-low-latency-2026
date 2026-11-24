#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
exec python3 Documents/newDoc/assets/09-verilator/live-support/stage-session.py verify
