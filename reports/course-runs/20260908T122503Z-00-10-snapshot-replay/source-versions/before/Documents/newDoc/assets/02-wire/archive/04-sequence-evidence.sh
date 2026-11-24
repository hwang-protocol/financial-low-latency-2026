#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-02-sequence-evidence"
OUT="Documents/reports/course-runs/$RUN_ID"
mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"

printf '===== root@10.1.1.101 · python3 =====\n'; ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.101 \
  python3 - <<'PY' 2>&1 | tee "$OUT/raw/result.txt"
# seen 保存已经处理过的 sequence，用来发现重复。
seen = set()

# highest 保存目前见过的最大 sequence，用来发现 gap 和 late。
highest = -1

# counts 保存四类结果的累计次数，方便最后核对。
counts = {"NEW": 0, "DUPLICATE": 0, "GAP": 0, "LATE": 0}

for sequence in [0, 1, 2, 2, 4, 3]:
    # 判断顺序：先查重复，再判断迟到，再判断跳号。
    if sequence in seen:
        result = "DUPLICATE"
    elif sequence < highest:
        result = "LATE"
    elif sequence > highest + 1:
        result = "GAP"
    else:
        result = "NEW"
    seen.add(sequence)
    highest = max(highest, sequence)
    counts[result] += 1

    # 每收到一个 sequence，就打印一次分类结果。
    print("sequence=%d result=%s" % (sequence, result))

print("counts=" + ",".join("%s:%d" % item for item in sorted(counts.items())))
PY

(cd "$OUT" && sha256sum raw/result.txt run.env >SHA256SUMS); printf 'evidence=%s\n' "$OUT"
