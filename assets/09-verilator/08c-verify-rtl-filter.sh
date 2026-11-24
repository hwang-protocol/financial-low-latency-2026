#!/usr/bin/env bash
set -Eeuo pipefail
cd /qyt-fll
python3 assets/09-verilator/live-support/stage-session.py verify
exec python3 assets/09-verilator/live-support/stage-session.py hold
