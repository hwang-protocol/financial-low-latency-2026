#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-08-xdp-actions"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"

printf '%s\n' '' '跳板机 / action-model' '===== 查六类输入的动作 =====' '[Action] 对: 仅目标 Type A 为 DROP，其余 PASS  证: 区分格式判断、证券条件与最终 action' '$ python3 - < Documents/newDoc/assets/08-xdp/xdp_action_model.py' \
  | tee "$OUT/raw/result.txt"
python3 - < Documents/newDoc/assets/08-xdp/xdp_action_model.py \
  2>&1 | tee -a "$OUT/raw/result.txt"
(cd "$OUT" && sha256sum raw/result.txt run.env >SHA256SUMS)
echo "evidence=$OUT"
