#!/usr/bin/env bash
# Run on .101 after Chapter 08 has distributed sources and installed the tools.
set -Eeuo pipefail
umask 077
ip -4 -o address show | grep -Fq '10.1.1.101/'
CH09_FOUNDATION_ENV="${CH09_FOUNDATION_ENV:-/opt/flle-ch08-dev/current.env}"
if [[ ! -s $CH09_FOUNDATION_ENV ]]; then
  echo '缺少第08章开发环境；请先完成第08章1.1—1.3。' >&2; exit 1
fi
unset CH09_SRC RUN_ID
source "$CH09_FOUNDATION_ENV"
if [[ -z ${CH09_SRC:-} || ! -f $CH09_SRC/market_filter.sv || ! -d $CH09_SRC/v80 ]]; then
  echo '第08章未分发本章源码；请用最新版重做第08章1.1—1.3。' >&2; exit 1
fi
for tool in verilator g++ gcc make iverilog vvp python3; do
  command -v "$tool" >/dev/null || {
    printf '缺少 %s；请完成第08章1.3的共享工具安装。\n' "$tool" >&2; exit 1;
  }
done
CH09_FOUNDATION_RUN="$RUN_ID"
CH09_ORIGINAL_SRC="$CH09_SRC"
CH09_RUN="$(date -u +%Y%m%dT%H%M%SZ)-ch09-fpga-dev"
CH09_TEST_DIR="/opt/flle-ch09-dev/$CH09_RUN"
mkdir -p /opt/flle-ch09-dev
mkdir -- "$CH09_TEST_DIR"
CH09_SRC="$CH09_TEST_DIR/src"
printf 'CH09_RUN=%q\nCH09_TEST_DIR=%q\nCH09_SRC=%q\nCH09_FOUNDATION_RUN=%q\nCH09_ORIGINAL_SRC=%q\nCH09_STATUS=PREPARING\n' \
  "$CH09_RUN" "$CH09_TEST_DIR" "$CH09_SRC" "$CH09_FOUNDATION_RUN" \
  "$CH09_ORIGINAL_SRC" > "$CH09_TEST_DIR/dev.env"
cp "$CH09_TEST_DIR/dev.env" /opt/flle-ch09-dev/current.env
cp -a -- "$CH09_ORIGINAL_SRC" "$CH09_SRC"
mkdir "$CH09_TEST_DIR/work"
cd "$CH09_TEST_DIR"
find src -type f -print0 | sort -z | xargs -0 sha256sum > inputs.sha256
{
  dpkg-query -W -f='${Package} ${Version}\n' iverilog verilator gcc g++ make
  verilator --version
  g++ --version
  make --version
  python3 --version
} > work/tools.txt 2>&1
printf 'CH09_STATUS=READY\n' >> dev.env
cp dev.env /opt/flle-ch09-dev/current.env
cat work/tools.txt
printf 'CH09_RUN=%s\nCH09_SRC=%s\nCH09_TEST_DIR=%s\n' "$CH09_RUN" "$CH09_SRC" "$CH09_TEST_DIR"
