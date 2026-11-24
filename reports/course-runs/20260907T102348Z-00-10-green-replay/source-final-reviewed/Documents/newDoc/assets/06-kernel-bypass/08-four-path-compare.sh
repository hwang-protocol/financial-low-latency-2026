#!/usr/bin/env bash
# Run 5: formal balanced comparison. Long machine output is raw-only.
set -Eeuo pipefail
cd /financial-low-latency
. Documents/reports/run-state/02-trading-baseline.env
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
# Preserve a previous completed/partial report before a fresh measurement.
if test -d "$OUT/four-path-comparison" || test -f "$OUT/raw/four-path-measure.txt"; then
  history="$OUT/comparison-history/$(date -u +%Y%m%dT%H%M%S.%NZ)"
  mkdir -p "$history"
  test ! -d "$OUT/four-path-comparison" || mv "$OUT/four-path-comparison" "$history/"
  for name in four-path-measure.txt four-path-balanced-analysis.txt; do
    test ! -f "$OUT/raw/$name" || cp "$OUT/raw/$name" "$history/$name"
  done
fi
bash apps/flle-trading-lab/scripts/transport_labctl.sh measure "$RUN_ID" \
  >"$OUT/raw/four-path-measure.txt" 2>&1
(cd "$OUT/four-path-comparison" && sha256sum -c SHA256SUMS >/dev/null)
python3 apps/flle-trading-lab/scripts/analyze_four_transport_raw.py \
  "$OUT/four-path-comparison" 2>&1 | tee "$OUT/raw/four-path-balanced-analysis.txt"
(cd "$OUT/four-path-comparison/balanced-analysis" && sha256sum -c SHA256SUMS >/dev/null)
(cd "$OUT" && { find raw -type f -print0; printf '%s\0' four-path-comparison/SHA256SUMS four-path-comparison/balanced-analysis/SHA256SUMS run.env; } | LC_ALL=C sort -z | xargs -0 sha256sum >SHA256SUMS)
