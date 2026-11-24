#!/usr/bin/env bash
# Stage the official SDK reader once; do not start a collector or enable LANZ.
set -Eeuo pipefail
REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../.." && pwd)"
case "${1:-}" in ''|--check) ;; *) exit 2;; esac
READER="$REPO_ROOT/artifacts/blobs/arista/lanz-reader-v1/flle-lanz-reader-linux-amd64"
EXPECTED=e6f58a6bd287f7776de936c8b82d5629c4b9afb14b92b721605eb783a0490083
DEST=/opt/flle/lanz-reader-v1
SSH=(ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.101)
printf '%s  %s\n' "$EXPECTED" "$READER" | sha256sum -c - >/dev/null
check(){
  "${SSH[@]}" "set -eu; test -x '$DEST/flle-lanz-reader'; printf '%s  %s\n' '$EXPECTED' '$DEST/flle-lanz-reader' | sha256sum --quiet -c -"
}
if ! check >/dev/null 2>&1; then
  if test "${1:-}" = --check; then
    echo 'LANZ 官方客户端未准备。请在 .111 重跑第二章“恢复并启动交易系统”的上线命令。' >&2
    exit 2
  fi
  STAGE="$("${SSH[@]}" "set -eu; mkdir -p '$DEST'; mktemp -d '$DEST/.stage.XXXXXX'")"
  [[ "$STAGE" = "$DEST"/.stage.* ]] || exit 2
  cleanup(){ "${SSH[@]}" "rm -rf -- '$STAGE'"; }
  trap cleanup EXIT
  scp -q -o BatchMode=yes -o StrictHostKeyChecking=yes "$READER" "root@10.1.1.101:$STAGE/reader"
  "${SSH[@]}" "set -eu; printf '%s  %s\n' '$EXPECTED' '$STAGE/reader' | sha256sum -c -; chmod 755 '$STAGE/reader'; mv '$STAGE/reader' '$DEST/flle-lanz-reader'"
  check
fi
printf 'lanz_reader=PREPARED host=.101 service=NOT_STARTED\n'
