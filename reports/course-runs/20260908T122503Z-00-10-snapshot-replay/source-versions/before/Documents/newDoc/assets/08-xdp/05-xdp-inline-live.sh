#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
exec bash Documents/newDoc/assets/08-xdp/live-support/run-xdp-receiver-live.sh
