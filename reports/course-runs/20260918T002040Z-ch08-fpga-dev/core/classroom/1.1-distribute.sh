#!/usr/bin/env bash
set -Eeuo pipefail
FLLE_REPO=/financial-low-latency
FLLE_ASSET="$FLLE_REPO/Documents/newDoc/assets/08-arista-fpga-draft"
FLLE_CACHE="$FLLE_REPO/artifacts/blobs/ch08-fpga-dev"
cd "$FLLE_CACHE"
printf '46640355f35963cd3a31ae0d57450e2ff263b5c2a456a3333a9f3f129590d471  SHA256SUMS\n' | sha256sum -c -
sha256sum -c SHA256SUMS
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-ch08-fpga-dev"
FLLE_RESULT="$FLLE_REPO/Documents/reports/course-runs/$RUN_ID"
FLLE_DEV="/opt/flle-ch08-dev/$RUN_ID"
mkdir -p "$FLLE_RESULT" "$FLLE_REPO/Documents/reports/run-state"
cp -a "$FLLE_ASSET" "$FLLE_RESULT/core"
cp -a "$FLLE_CACHE" "$FLLE_RESULT/tools"
(cd "$FLLE_RESULT" && tar --exclude=__pycache__ -czf inputs.tgz core tools)
(cd "$FLLE_RESULT" && sha256sum inputs.tgz > inputs.sha256)
printf 'RUN_ID=%q\nFLLE_DEV=%q\nFLLE_CORE=%q\nRESULT_DIR=%q\nSTARTED_AT_UTC=%q\nPURPOSE=ch08-fpga-development\nPROFILE_ID=vm101-ubuntu22.04-offline\nSTATUS=ACTIVE\n' \
  "$RUN_ID" "$FLLE_DEV" "$FLLE_DEV/core" "$FLLE_RESULT" "$(date -u +%FT%TZ)" > "$FLLE_RESULT/dev.env"
ssh root@10.1.1.101 bash -s -- "$FLLE_DEV" <<'REMOTE'
set -euo pipefail
ip -4 -o address show | grep -q '10.1.1.101/'
. /etc/os-release
test "$ID:$VERSION_ID:$(dpkg --print-architecture)" = ubuntu:22.04:amd64
mkdir -p /opt/flle-ch08-dev
mkdir -- "$1"
REMOTE
scp "$FLLE_RESULT/inputs.tgz" "$FLLE_RESULT/inputs.sha256" \
  "$FLLE_RESULT/dev.env" "root@10.1.1.101:$FLLE_DEV/"
ssh root@10.1.1.101 bash -s -- "$FLLE_DEV" <<'REMOTE'
set -euo pipefail
cd "$1"
sha256sum -c inputs.sha256
tar -xzf inputs.tgz
cp dev.env /opt/flle-ch08-dev/current.env
REMOTE
cp "$FLLE_RESULT/dev.env" "$FLLE_REPO/Documents/reports/run-state/ch08-fpga-dev.env"
printf 'development_host=10.1.1.101\nRUN_ID=%s\nworkspace=%s\n' "$RUN_ID" "$FLLE_DEV"
