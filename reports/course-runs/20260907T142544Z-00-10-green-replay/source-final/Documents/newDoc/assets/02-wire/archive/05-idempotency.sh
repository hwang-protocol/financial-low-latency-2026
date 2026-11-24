#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-02-idempotency"
OUT="Documents/reports/course-runs/$RUN_ID"
mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"

printf '===== root@10.1.1.101 · python3 =====\n'; ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.101 \
  python3 - <<'PY' 2>&1 | tee "$OUT/raw/result.txt"
# 本例直接把规范化不可变 tuple 当作请求指纹，不做哈希。
results = {}

action_count = 0

def submit(session, client_order_id, request):
    global action_count
    key = (session, client_order_id)

    # 同一键、同一请求才重放；同一键带不同请求必须报冲突。
    if key in results:
        old_request, old_result = results[key]
        if request != old_request:
            return "CONFLICT"
        return "REPLAY:" + old_result

    action_count += 1
    result = "ORDER_ACCEPTED"
    results[key] = (request, result)
    return "NEW:" + result

# 连续提交两次相同订单请求，模拟应用层重试。
request = ("BUY", "AAPL", 10, 1234501)
first = submit(7, 7001, request)
second = submit(7, 7001, request)
conflict = submit(7, 7001, ("BUY", "AAPL", 11, 1234501))

assert (first, second, conflict, action_count) == (
    "NEW:ORDER_ACCEPTED", "REPLAY:ORDER_ACCEPTED", "CONFLICT", 1)
print("first=" + first)
print("second=" + second)
print("conflict=" + conflict)
print("action_count=%d" % action_count)
PY

(cd "$OUT" && sha256sum raw/result.txt run.env >SHA256SUMS); printf 'evidence=%s\n' "$OUT"
