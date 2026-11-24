#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-04-loki-timeline"
OUT="Documents/reports/course-runs/$RUN_ID"; mkdir -p "$OUT/raw"
printf 'RUN_ID=%s\n' "$RUN_ID" >"$OUT/run.env"

printf '===== root@10.1.1.101 · Loki timeline =====\n'; ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.101 \
  bash -s -- "$RUN_ID" <<'REMOTE' 2>&1 | tee "$OUT/raw/result.txt"
set -Eeuo pipefail
run_id="$1"
cd /opt/flle/observability
printf '$ docker compose ps loki\n'; docker compose ps loki
python3 - "$run_id" <<'PY'
import json, sys, time, urllib.parse, urllib.request
run_id = sys.argv[1]
states = ["normal", "fault", "recovered"]
now = time.time_ns()
values = [[str(now + i), json.dumps({"run_id": run_id, "state": state})]
          for i, state in enumerate(states)]
body = {"streams": [{"stream": {"job": "flle_micro", "run_id": run_id}, "values": values}]}
request = urllib.request.Request("http://127.0.0.1:3100/loki/api/v1/push",
    data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
response = urllib.request.urlopen(request, timeout=3)
print("push_http_status=%d" % response.status)
response.read()
time.sleep(0.3)
query = urllib.parse.urlencode({"query": '{job="flle_micro",run_id="%s"}' % run_id,
                                "start": str(now - 1), "end": str(now + 10)})
result = json.load(urllib.request.urlopen("http://127.0.0.1:3100/loki/api/v1/query_range?" + query, timeout=3))
print(json.dumps(result, sort_keys=True))
lines = [item[1] for stream in result["data"]["result"] for item in stream["values"]]
found = sorted(json.loads(line)["state"] for line in lines)
print("states=" + ",".join(found))
PY
REMOTE
(cd "$OUT" && sha256sum raw/result.txt run.env >SHA256SUMS); printf 'evidence=%s\n' "$OUT"
