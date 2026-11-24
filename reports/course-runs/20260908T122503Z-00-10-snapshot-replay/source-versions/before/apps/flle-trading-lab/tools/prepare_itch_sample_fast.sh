#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 4 ]; then
  echo "usage: $0 SOURCE_GZ OUTPUT_ITCH MANIFEST_JSON FILTER_BINARY" >&2
  exit 2
fi

SOURCE_GZ="$1"
OUTPUT_ITCH="$2"
MANIFEST_JSON="$3"
FILTER_BINARY="$4"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_TMP="${OUTPUT_ITCH}.tmp"
STATS_TMP="${MANIFEST_JSON}.stats.tmp"

test -s "$SOURCE_GZ"
test -x "$FILTER_BINARY"
gzip -t "$SOURCE_GZ"
SOURCE_SHA256="$(sha256sum "$SOURCE_GZ" | awk '{print $1}')"
gzip -dc "$SOURCE_GZ" | "$FILTER_BINARY" "$STATS_TMP" >"$OUTPUT_TMP"
OUTPUT_SHA256="$(sha256sum "$OUTPUT_TMP" | awk '{print $1}')"
mv "$OUTPUT_TMP" "$OUTPUT_ITCH"
python3 "$SCRIPT_DIR/finalize_itch_manifest.py" \
  --source "$SOURCE_GZ" \
  --source-sha256 "$SOURCE_SHA256" \
  --output "$OUTPUT_ITCH" \
  --output-sha256 "$OUTPUT_SHA256" \
  --stats "$STATS_TMP" \
  --manifest "$MANIFEST_JSON"
rm -f "$STATS_TMP"
