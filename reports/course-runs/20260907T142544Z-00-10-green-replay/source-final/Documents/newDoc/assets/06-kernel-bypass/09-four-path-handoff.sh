#!/usr/bin/env bash
# Experiment finish: return to the reusable SFC console and keep its GUI online.
set -Eeuo pipefail
cd /financial-low-latency
. Documents/reports/run-state/02-trading-baseline.env
OUT="Documents/reports/course-runs/$RUN_ID"; RAW="$OUT/raw"; mkdir -p "$RAW"
CTL="apps/flle-trading-lab/scripts/transport_labctl.sh"
bash "$CTL" sfc "$RUN_ID" >"$RAW/final-sfc-control.json"
reuse_state="$(bash "$CTL" reuse-state "$RUN_ID")"
test "$reuse_state" = REUSABLE
printf '%s\n' "$reuse_state" >"$RAW/final-reuse-state.txt"
http_code="$(curl -fsS -o "$RAW/final-transport-lab.json" -w '%{http_code}' --max-time 3 http://10.1.1.101:8088/api/transport-lab)"
test "$http_code" = 200
python3 - "$RAW/final-transport-lab.json" <<'PY'
import json, sys
x = json.load(open(sys.argv[1]))
assert (x["mode"], x["transition"], x["owner"]) == ("SFC", "READY", "sfc")
assert all(x["clients"][n]["health"]["status"] == "ONLINE" for n in ("trader_manual", "trader_onload", "trader_tcpdirect"))
assert x["clients"]["trader_dpdk"]["health"]["status"] == "WAITING"
PY
ping_out="$(ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 'LC_ALL=C ping -q -I ens64np1 -c 3 -W 1 20.1.1.1')"
grep -Fq '3 packets transmitted, 3 received' <<<"$ping_out"
printf '%s\n' "$ping_out" >"$RAW/final-ping.txt"
printf '===== 第 06 章恢复常用四路控制台 =====\nresult=READY\ndata_plane=SFC/READY/sfc\nclients=Socket, Onload, TCPDirect ONLINE\ndpdk=WAITING\nweb=http://10.1.1.101:8088/ HTTP %s\ndata_link=ping 3/3\nnext=第 07 章\nevidence=%s\n' "$http_code" "$OUT" | tee "$RAW/final-result.txt"
(cd "$OUT" && find . -type f ! -path './SHA256SUMS' -print0 | LC_ALL=C sort -z | xargs -0 sha256sum >SHA256SUMS)
