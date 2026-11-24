#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
exec python3 Documents/newDoc/assets/10-verilator/live-support/stage-session.py restore
