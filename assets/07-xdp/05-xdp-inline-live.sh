#!/usr/bin/env bash
set -Eeuo pipefail
cd /qyt-fll
exec bash assets/07-xdp/live-support/run-xdp-receiver-live.sh
