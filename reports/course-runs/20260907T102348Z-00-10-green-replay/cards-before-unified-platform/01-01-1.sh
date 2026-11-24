#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-01-vm-apt-china-mirror"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"

{
for host in 10.1.1.1 10.1.1.2 10.1.1.11 10.1.1.101; do
  printf '\n===== root@%s =====\n' "$host"
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes "root@$host" \
    bash -s -- "$host" <<'REMOTE'
set -Eeuo pipefail
REMOTE_HOST="$1"
. /etc/os-release
printf '$ cat /etc/os-release\n'; cat /etc/os-release
printf '$ dpkg --print-architecture\n'; dpkg --print-architecture
if [ "$ID" != ubuntu ] || [ "$VERSION_CODENAME" != jammy ]; then
  printf 'STOP: this card expects Ubuntu jammy\n' >&2; exit 1
fi
[ -e /etc/apt/sources.list.flle-original ] || cp -a /etc/apt/sources.list /etc/apt/sources.list.flle-original
install -m 0644 /dev/stdin /etc/apt/sources.list <<'SOURCES'
deb https://mirrors.aliyun.com/ubuntu/ jammy main restricted universe multiverse
deb https://mirrors.aliyun.com/ubuntu/ jammy-updates main restricted universe multiverse
deb https://mirrors.aliyun.com/ubuntu/ jammy-backports main restricted universe multiverse
deb https://mirrors.aliyun.com/ubuntu/ jammy-security main restricted universe multiverse
SOURCES
printf '$ cat /etc/apt/sources.list\n'; cat /etc/apt/sources.list
printf '$ apt-get -o Acquire::Retries=3 update\n'
apt-get -o Acquire::Retries=3 update
printf '$ apt-cache policy g++-11\n'; apt-cache policy g++-11
if [ "$REMOTE_HOST" = 10.1.1.101 ]; then
  printf '$ apt-get -y install g++-11 make\n'
  DEBIAN_FRONTEND=noninteractive apt-get -o Acquire::Retries=3 -y install g++-11 make
  printf '$ command -v g++-11 make python3\n'; command -v g++-11 make python3
  printf '$ g++-11 --version\n'; g++-11 --version | head -1
fi
REMOTE
done
} 2>&1 | tee "$OUT/raw/result.txt"
(cd "$OUT" && sha256sum raw/result.txt run.env >SHA256SUMS); printf 'evidence=%s\n' "$OUT"
