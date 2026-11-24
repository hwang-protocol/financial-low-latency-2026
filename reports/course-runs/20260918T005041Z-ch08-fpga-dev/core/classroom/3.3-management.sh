#!/usr/bin/env bash
set -Eeuo pipefail
ip -4 -o address show | grep -q '10.1.1.101/'
source /opt/flle-ch08-dev/current.env
cd "$FLLE_CORE/test-support/openfdk"
sha256sum -c SHA256SUMS
"$FLLE_DEV/venv/bin/python" -B "$FLLE_CORE/test_eos_control.py" "$PWD" \
  2>&1 | tee "$FLLE_DEV/work/management.log"
