#!/usr/bin/env bash
set -Eeuo pipefail
ip -4 -o address show | grep -q '10.1.1.101/'
source /opt/flle-ch08-dev/current.env
cd "$FLLE_DEV/work/simulation"
sha256sum -c compile.sha256
vvp filter.vvp 2>&1 | tee simulation.log
