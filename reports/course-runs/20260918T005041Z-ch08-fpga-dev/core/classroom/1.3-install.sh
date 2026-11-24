#!/usr/bin/env bash
set -Eeuo pipefail
ip -4 -o address show | grep -q '10.1.1.101/'
source /opt/flle-ch08-dev/current.env
cd "$FLLE_DEV/tools"
sha256sum -c SHA256SUMS
mkdir -p "$FLLE_DEV/work"
dpkg -i deb/iverilog_11.0-1.1_amd64.deb 2>&1 | tee "$FLLE_DEV/work/iverilog-install.log"
python3 -m venv --without-pip "$FLLE_DEV/venv"
PYTHONPATH="$FLLE_DEV/tools/wheels/pip-25.2-py3-none-any.whl" \
  "$FLLE_DEV/venv/bin/python" -m pip install --no-index \
  --find-links="$FLLE_DEV/tools/wheels" \
  -r "$FLLE_DEV/tools/requirements.txt" \
  2>&1 | tee "$FLLE_DEV/work/python-install.log"
{
  dpkg-query -W -f='${Package} ${Version}\n' iverilog
  "$FLLE_DEV/venv/bin/python" -m pip check
  "$FLLE_DEV/venv/bin/yowasp-yosys" -V
} 2>&1 | tee "$FLLE_DEV/work/tools.txt"
printf 'development_environment=READY host=10.1.1.101\n'
