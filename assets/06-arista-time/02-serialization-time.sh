#!/usr/bin/env bash
set -Eeuo pipefail
cd /qyt-fll
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-07-serialization"
OUT="reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"

python3 - <<'PY' 2>&1 | tee "$OUT/raw/result.txt"
rate = 10_000_000_000
# 与正文一致：以太帧长度包含 4 字节 FCS，不含前导码和帧间隙。
small_bytes = 64
large_bytes = 1518
small_ns = small_bytes * 8 * 1_000_000_000 / rate
large_ns = large_bytes * 8 * 1_000_000_000 / rate
difference_ns = large_ns - small_ns
print("# 10G：帧长含 FCS；以下仅计算帧本身的发送时间，不含前导码与帧间隙。")
print("64B_ns=%.1f" % small_ns)
print("1518B_ns=%.1f" % large_ns)
print("difference_ns=%.1f" % difference_ns)
PY
(cd "$OUT" && sha256sum raw/result.txt run.env >SHA256SUMS)
echo "evidence=$OUT"
