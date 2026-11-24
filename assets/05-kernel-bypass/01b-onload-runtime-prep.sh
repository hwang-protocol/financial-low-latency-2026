#!/usr/bin/env bash
# Compatibility entry: platform prerequisites are installed in Chapter 02.
set -Eeuo pipefail
cd /qyt-fll
exec bash assets/02-trading-baseline/00a-runtime-prep.sh "$@"
