#!/usr/bin/env bash
# Chapter 7 final gate: restore/reuse the Chapter 6 lab and prove it with a
# risk-aware, position-neutral pair of real Socket/SoupBinTCP/OUCH orders.
set -Eeuo pipefail
cd /financial-low-latency

STATE="Documents/reports/run-state/02-trading-baseline.env"
CTL="apps/flle-trading-lab/scripts/transport_labctl.sh"
API="http://10.1.1.101:8088"
ENTRY_SCRIPT="Documents/newDoc/assets/07-arista-time/13-trading-online-final.sh"

# Handoff is conditional: calling the DPDK->SFC transition while already in
# SFC is intentionally rejected by the controller.
if test -s "$STATE"; then
  current_run="$(sed -n 's/^RUN_ID=//p' "$STATE")"
  mode="$(bash "$CTL" status "$current_run" 2>/dev/null | \
    python3 -c 'import json,sys; print(json.load(sys.stdin).get("mode", ""))' \
    2>/dev/null || true)"
  if test "$mode" = DPDK; then
    bash Documents/newDoc/assets/06-kernel-bypass/09-four-path-handoff.sh
  fi
fi

if ! prep_output="$(bash Documents/newDoc/assets/06-kernel-bypass/03-four-path-lab-ready.sh)"; then
  echo '准备 D 复用失败。常见原因：实验二 LANZ 底栏覆盖了 .101 网页后未按 source.sha256 恢复。' >&2
  parent="$(sed -n 's/^RUN_ID=//p' "$STATE" 2>/dev/null || true)"
  if test -n "$parent"; then
    ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.101 \
      "set -eu; cd '/var/tmp/flle-trading-lab-$parent'; sha256sum -c source.sha256" \
      2>&1 | grep -v ': OK$' >&2 || true
  fi
  exit 1
fi
. "$STATE"
PARENT_RUN_ID="$RUN_ID"
RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-07-trading-online-final"
OUT="Documents/reports/course-runs/$RUN_ID"
RAW="$OUT/raw"
test ! -e "$OUT"
mkdir -p "$RAW/source"
ENTRY_SCRIPT_SHA256="$(sha256sum "$ENTRY_SCRIPT" | awk '{print $1}')"
printf 'RUN_ID=%s\nPARENT_RUN_ID=%s\nRESULT_KIND=CH07_TRADING_ONLINE_FINAL\nENTRY_SCRIPT_SHA256=%s\n' \
  "$RUN_ID" "$PARENT_RUN_ID" "$ENTRY_SCRIPT_SHA256" >"$OUT/run.env"
install -m 0644 "$ENTRY_SCRIPT" "$RAW/source/13-trading-online-final.sh"
printf '%s\n' "$prep_output" >"$RAW/prep-d.txt"

bash "$CTL" status "$PARENT_RUN_ID" >"$RAW/status-before.json"
curl -fsS "$API/api/transport-lab" >"$RAW/transport-before.json"
curl -fsS "$API/api/state" >"$RAW/state-before.json"
position_before="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["positions"]["AAPL"])' "$RAW/state-before.json")"
if test "$position_before" -ge 0; then
  first_side=SELL; first_limit=1; second_side=BUY; second_limit=999999999999
else
  first_side=BUY; first_limit=999999999999; second_side=SELL; second_limit=1
fi

issue_order() {
  local label="$1" side="$2" limit="$3" reply oid state ready=0
  reply="$(curl -fsS -X POST -H 'Content-Type: application/json' \
    -d "{\"symbol\":\"AAPL\",\"side\":\"$side\",\"quantity\":1,\"limit_price_x10000\":$limit,\"transport\":\"SOCKET\"}" \
    "$API/api/order")"
  printf '%s\n' "$reply" >"$RAW/$label-reply.json"
  oid="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["client_order_id"])' <<<"$reply")"
  for _ in $(seq 1 80); do
    state="$(curl -fsS "$API/api/state")"
    if python3 -c 'import json,sys; oid=int(sys.argv[1]); rows=[r for r in json.loads(sys.argv[2]).get("orders",[]) if int(r.get("client_order_id",0))==oid]; raise SystemExit(not(rows and rows[0].get("result")=="ORDER_EXECUTED" and int(rows[0].get("order_rtt_ns",0))>0))' "$oid" "$state"; then
      ready=1
      printf '%s\n' "$state" >"$RAW/$label-state.json"
      break
    fi
    sleep 0.1
  done
  test "$ready" -eq 1
  python3 - "$oid" "$RAW/$label-state.json" "$RAW/$label-result.json" <<'PY'
import json, sys
oid = int(sys.argv[1])
state = json.load(open(sys.argv[2], encoding="utf-8"))
row = next(r for r in state["orders"] if int(r.get("client_order_id", 0)) == oid)
json.dump({"client_order_id": oid, "result": row["result"],
           "order_rtt_ns": int(row["order_rtt_ns"]), "side": row["side"]},
          open(sys.argv[3], "w", encoding="utf-8"), ensure_ascii=False, indent=2)
PY
}

issue_order reduce-risk "$first_side" "$first_limit"
issue_order restore-position "$second_side" "$second_limit"

bash "$CTL" status "$PARENT_RUN_ID" >"$RAW/status-after.json"
curl -fsS "$API/api/transport-lab" >"$RAW/transport-after.json"
curl -fsS "$API/api/state" >"$RAW/state-after.json"
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 \
  'LC_ALL=C ping -q -I ens64np1 -c 3 -W 1 20.1.1.1' >"$RAW/ping.txt"

python3 - "$RAW/status-after.json" "$RAW/transport-after.json" \
  "$RAW/state-before.json" "$RAW/state-after.json" \
  "$RAW/reduce-risk-result.json" "$RAW/restore-position-result.json" \
  "$RAW/ping.txt" "$RAW/result.txt" "$OUT" <<'PY'
import json, sys
control, gui, before, after, first, second = [
    json.load(open(path, encoding="utf-8")) for path in sys.argv[1:7]
]
ping = open(sys.argv[7], encoding="utf-8").read()
assert (control["mode"], control["transition"], control["owner"]) == ("SFC", "READY", "sfc")
assert control["hardware_receipts"]["socket"]["verified"] is True
assert all(gui["clients"][name]["health"]["status"] == "ONLINE"
           for name in ("trader_manual", "trader_onload", "trader_tcpdirect"))
assert gui["clients"]["trader_dpdk"]["health"]["status"] == "WAITING"
assert before["positions"]["AAPL"] == after["positions"]["AAPL"]
assert first["result"] == second["result"] == "ORDER_EXECUTED"
assert "3 packets transmitted, 3 received" in ping
lines = [
    "===== 第 07 章章末交易上线验收 =====",
    "result=PASS",
    "data_plane=SFC/READY/sfc",
    "clients=Socket, Onload, TCPDirect ONLINE; DPDK WAITING",
    "web=http://10.1.1.101:8088/ HTTP 200",
    "data_link=ping 3/3",
    f"real_orders=2/2 ORDER_EXECUTED via Socket/SoupBinTCP/OUCH; rtt_ns={first['order_rtt_ns']}/{second['order_rtt_ns']}",
    f"position_AAPL={before['positions']['AAPL']}->{after['positions']['AAPL']} unchanged",
    "handoff=conditional; already-SFC is reused without transition",
    "evidence=" + sys.argv[9],
]
open(sys.argv[8], "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("\n".join(lines))
PY

(cd "$OUT" && find raw -type f -print0 | sort -z | xargs -0 sha256sum >SHA256SUMS)
printf 'root_sha256=%s\n' "$(sha256sum "$OUT/SHA256SUMS" | awk '{print $1}')"
