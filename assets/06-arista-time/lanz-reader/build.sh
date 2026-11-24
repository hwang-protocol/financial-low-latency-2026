#!/usr/bin/env bash
# Maintainer-only offline build; the lesson deploys the prebuilt binary.
set -Eeuo pipefail
cd "$(dirname -- "${BASH_SOURCE[0]}")"
GO_BIN="${GO_BIN:-go}"
test -s vendor/modules.txt || { echo '先解压已封存的源码包（包含 vendor），或在课前执行 go mod vendor。' >&2; exit 2; }
test "$("$GO_BIN" env GOVERSION)" = go1.24.13
export CGO_ENABLED=0 GOOS=linux GOARCH=amd64 GOAMD64=v1 GOTOOLCHAIN=local GOPROXY=off
"$GO_BIN" build -mod=vendor -trimpath -buildvcs=false -ldflags='-s -w -buildid=' \
  -o "${1:-flle-lanz-reader}" .
