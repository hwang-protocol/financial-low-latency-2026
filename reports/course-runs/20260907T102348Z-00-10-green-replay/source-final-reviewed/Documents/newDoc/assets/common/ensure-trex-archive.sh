#!/usr/bin/env bash
# Management-plane cache distribution only; no interface or TRex process changes.
set -Eeuo pipefail
cd /financial-low-latency
archive=artifacts/blobs/trex/3.08/v3.08.tar.gz
expected=d2ac73627906c4ce01127c1c6954464fab373463966ea9592509446e74972b5f
printf '%s  %s\n' "$expected" "$archive" | sha256sum -c -
target=/opt/flle/prewarm/trex/v3.08.tar.gz
if ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
  "test \"\$(sha256sum '$target' 2>/dev/null | cut -d' ' -f1)\" = '$expected'"; then
  printf 'TRex 归档已校验；复用 .11 缓存，公网下载 0 字节。\n'
  exit 0
fi
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
  "set -eu; test ! -e '$target'; install -d -m 0755 /opt/flle/prewarm/trex"
remote="$(ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 'mktemp /opt/flle/prewarm/trex/.incoming-XXXXXX')"
trap 'ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 "rm -f -- '\''$remote'\''"' EXIT
scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes "$archive" "root@10.1.1.11:$remote"
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.11 \
  "set -eu; test \"\$(sha256sum '$remote' | cut -d' ' -f1)\" = '$expected'; chmod 0644 '$remote'; ln '$remote' '$target'"
printf 'TRex 归档已从 .111 分发并校验；公网下载 0 字节。\n'
