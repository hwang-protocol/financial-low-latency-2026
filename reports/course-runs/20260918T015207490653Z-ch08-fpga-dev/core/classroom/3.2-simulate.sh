#!/usr/bin/env bash
set -Eeuo pipefail
exec python3 "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/stage-runner.py" 3.2
