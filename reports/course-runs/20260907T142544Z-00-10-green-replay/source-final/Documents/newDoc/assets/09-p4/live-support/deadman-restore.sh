#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
source Documents/newDoc/assets/common/flle-remote.sh
RUN_ID="${1:?RUN_ID required}"; ORIGINAL_MODE="${2:?market mode required}"
[[ "$RUN_ID" =~ ^[0-9]{8}T[0-9]{6}Z-(08-xdp-inline-live|09-p4-drop-live)$ ]]
sleep "${FLLE_DEADMAN_DELAY:-240}"
ASSET=Documents/newDoc/assets/09-p4
EOS=Documents/newDoc/assets/common/eos_cli.py
OUT="Documents/reports/course-runs/$RUN_ID/raw"
curl -fsS -X POST -H 'Content-Type: application/json' -d "{\"market_mode\":\"$ORIGINAL_MODE\"}" http://10.1.1.101:8088/api/market >/dev/null || true
python3 "$EOS" --plan "$ASSET/p4-trading-restore-endpoints.plan" --output "$OUT/deadman-eos-endpoints.txt" --mode controlled-config || true
ssh -n "${FLLE_SSH_OPTS[@]}" root@10.1.1.11 "ip link set dev ens64f0np0 xdp off 2>/dev/null || true; if test -s '/var/tmp/$RUN_ID/simple_switch.pid'; then pid=\$(cat '/var/tmp/$RUN_ID/simple_switch.pid'); kill \"\$pid\" 2>/dev/null || true; fi; ip link set dev ens64f0np0 down; ip link set dev ens64f1np1 down" || true
python3 "$EOS" --plan "$ASSET/p4-trading-restore-final.plan" --output "$OUT/deadman-eos-final.txt" --mode controlled-config || true
curl -fsS -X POST -H 'Content-Type: application/json' -d '{"action":"RESTART"}' http://10.1.1.101:8088/api/replay >/dev/null || true
bash Documents/newDoc/assets/common/feed-guardianctl.sh direct >"$OUT/deadman-feed-guardian.txt" 2>&1 || true
printf 'deadman=FIRED run=%s\n' "$RUN_ID"
