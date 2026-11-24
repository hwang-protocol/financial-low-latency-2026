#!/usr/bin/env bash
# Compatibility entry: platform prerequisites are installed in Chapter 02.
set -Eeuo pipefail
cd /financial-low-latency
exec bash Documents/newDoc/assets/02-trading-baseline/00a-runtime-prep.sh "$@"
