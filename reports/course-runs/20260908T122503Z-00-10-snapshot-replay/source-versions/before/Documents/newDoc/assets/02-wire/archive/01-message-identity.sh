#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-02-message-identity"
OUT="Documents/reports/course-runs/$RUN_ID"
mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"

printf '===== root@10.1.1.101 · python3 =====\n'; ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.101 \
  python3 - <<'PY' 2>&1 | tee "$OUT/raw/result.txt"
# 当前实验只接受 session=2026081001，把旧连接或旧运行隔离出去。
current_session = 2026081001

# seen 只记录当前 session 中已经处理过的 sequence。
seen = set()

# 每个元组依次表示 session、sequence、correlation、业务提示。
messages = [
    (2026081001, 1001, 7001, "AAPL_TICK"),
    (2026081001, 1001, 7001, "AAPL_TICK_REPLAY"),
    (2026080901, 1001, 6001, "YESTERDAY_REPLAY"),
    (2026081001, 1002, 7001, "SAME_CHAIN_NEXT_MSG"),
]

for session, sequence, correlation, note in messages:
    # 判断顺序很重要：先排除旧 session，再做本轮去重。
    if session != current_session:
        result = "OLD_SESSION"
    elif sequence in seen:
        result = "DUPLICATE"
    else:
        seen.add(sequence)
        result = "NEW"

    # 打印原始字段和分类结果，方便逐行人工核对。
    print(session, sequence, correlation, result, note)

print("seen_sequences=%s" % sorted(seen))
PY

(cd "$OUT" && sha256sum raw/result.txt run.env >SHA256SUMS); printf 'evidence=%s\n' "$OUT"
