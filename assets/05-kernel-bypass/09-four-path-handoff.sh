#!/usr/bin/env bash
# Experiment finish: return to the reusable SFC console and keep its GUI online.
set -Eeuo pipefail
cd /qyt-fll
. reports/run-state/02-trading-baseline.env
OUT="reports/course-runs/$RUN_ID"; RAW="$OUT/raw"; mkdir -p "$RAW"
CTL="apps/flle-trading-lab/scripts/transport_labctl.sh"
bash "$CTL" sfc "$RUN_ID" >"$RAW/final-sfc-control.json"
reuse_state="$(bash "$CTL" reuse-state "$RUN_ID")"
test "$reuse_state" = REUSABLE
printf '%s\n' "$reuse_state" >"$RAW/final-reuse-state.txt"
http_code="$(curl -fsS -o "$RAW/final-transport-lab.json" -w '%{http_code}' --max-time 3 http://10.1.1.101:8088/api/transport-lab)"
test "$http_code" = 200
python3 apps/flle-trading-lab/scripts/verify-book-handoff.py http://10.1.1.101:8088 >"$RAW/final-book-feed.json"
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
printf '===== 第 05 章 · 收尾检查 =====
# 1. 网卡与客户端：已恢复本章常用的 SFC 模式。
data_plane=SFC/READY/sfc  # X2522 由 sfc 驱动管理
clients=Kernel Socket, Onload, TCPDirect ONLINE  # 前三路在线
dpdk=WAITING  # 等待切到 DPDK 模式，属于正常状态

# 2. 网页与数据链路：页面可访问，Trader 到 Exchange 连通。
web=http://10.1.1.101:8088/ HTTP %s
data_link=ping 3/3  # 发出 3 个探测包，收到 3 个回复

# 3. 本章收尾通过，保留控制台供后续使用。
result=READY
next=第 06 章
# 完整检查记录保存在：
evidence=%s
' "$http_code" "$OUT" | tee "$RAW/final-result.txt"
(cd "$OUT" && find . -type f ! -path './SHA256SUMS' -print0 | LC_ALL=C sort -z | xargs -0 sha256sum >SHA256SUMS)
