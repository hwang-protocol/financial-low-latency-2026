#!/usr/bin/env bash
set -Eeuo pipefail
cd /qyt-fll
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-10-ready-valid"
OUT="reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"

printf '===== jump-host =====\n$ python3 -\n' | tee "$OUT/raw/result.txt"
python3 - <<'PY' 2>&1 | tee -a "$OUT/raw/result.txt"
valid = [1, 1, 1, 1]
ready = [1, 0, 0, 1]
payload = [42, 43, 43, 43]
accepted = []
for cycle in range(4):
    fire = valid[cycle] and ready[cycle]
    if fire:
        accepted.append(payload[cycle])
    print('cycle=%d valid=%d ready=%d payload=%d accept=%d' %
          (cycle, valid[cycle], ready[cycle], payload[cycle], fire))
print('accepted=%s' % accepted)
PY
(cd "$OUT" && sha256sum raw/result.txt run.env >SHA256SUMS)
printf 'evidence=%s\n' "$OUT"
