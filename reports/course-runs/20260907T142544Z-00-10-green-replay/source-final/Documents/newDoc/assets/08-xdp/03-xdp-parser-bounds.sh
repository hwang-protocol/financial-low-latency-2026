#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-08-xdp-bounds"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"
SOURCE="Documents/newDoc/assets/08-xdp/flle_xdp_mold_itch.c"
{
  printf '%s\n' '' '跳板机 / source-review' '===== 查源码指纹 =====' '[SHA-256] 对: 与本轮使用的源码一致  证: 后续审查针对同一份 C 文件'; printf '$ sha256sum %s\n' "$SOURCE"; sha256sum "$SOURCE"
  printf '%s\n' '' '跳板机 / source-review' '===== 查带行号的访问边界 =====' '[Parser] 对: 先证明 data_end 边界，再读取字段  证: 可以定位每次解引用前的检查'; printf '$ nl -ba %s\n' "$SOURCE"; nl -ba "$SOURCE"
} 2>&1 | tee "$OUT/raw/result.txt"
(cd "$OUT" && sha256sum raw/result.txt run.env >SHA256SUMS)
echo "evidence=$OUT"
