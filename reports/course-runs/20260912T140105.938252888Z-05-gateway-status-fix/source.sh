#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
MIGRATION_OUT="$(cat /tmp/flle-ch05-migration-out)"
REPAIR_RUN_ID="$(date -u +%Y%m%dT%H%M%S.%NZ)-05-gateway-status-fix"
REPAIR_OUT="Documents/reports/course-runs/$REPAIR_RUN_ID"
mkdir -p "$REPAIR_OUT/raw"
PARENT_RUN_ID="$(sed -n 's/^RUN_ID=//p' Documents/reports/run-state/02-trading-baseline.env)"
printf 'RUN_ID=%s\nPARENT_RUN_ID=%s\nPHASE=DEPLOY_GATEWAY_STATUS_FIX\n' "$REPAIR_RUN_ID" "$PARENT_RUN_ID" > "$REPAIR_OUT/run.env"
printf '%s\n' "$REPAIR_OUT" > /tmp/flle-ch05-gateway-repair-out
cp "$0" "$REPAIR_OUT/source.sh"
source apps/flle-trading-lab/scripts/transport_labctl.sh preflight "$PARENT_RUN_ID"
verify_gateway_identity
"${SCP[@]}" "$OBSERVER_HOST:$RUN_DIR/flle_trading/gateway.py" "$REPAIR_OUT/raw/gateway-before.py"
"${SCP[@]}" "$OBSERVER_HOST:$RUN_DIR/source.sha256" "$REPAIR_OUT/raw/source-before.sha256"
"${SCP[@]}" "$OBSERVER_HOST:$RUN_DIR/gateway.identity" "$REPAIR_OUT/raw/gateway-before.identity"
old_sha="$(sha256sum "$REPAIR_OUT/raw/gateway-before.py" | cut -d' ' -f1)"
new_sha="$(sha256sum apps/flle-trading-lab/flle_trading/gateway.py | cut -d' ' -f1)"
stop_remote_process "$OBSERVER_HOST" gateway flle_trading.gateway 8088
"${SCP[@]}" apps/flle-trading-lab/flle_trading/gateway.py "$OBSERVER_HOST:$RUN_DIR/flle_trading/gateway.py.chapter05-new"
"${SSH[@]}" "$OBSERVER_HOST" python3 - "$RUN_DIR" "$old_sha" "$new_sha" <<'PY'
from pathlib import Path
import hashlib,sys
run=Path(sys.argv[1]);old,new=sys.argv[2:];path=run/'flle_trading/gateway.py';staged=path.with_name('gateway.py.chapter05-new');manifest=run/'source.sha256'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(path)==old and sha(staged)==new
lines=manifest.read_text().splitlines();matches=[i for i,line in enumerate(lines) if line.split('  ',1)[1]=='flle_trading/gateway.py'];assert len(matches)==1
assert lines[matches[0]].split()[0]==old
staged.replace(path);lines[matches[0]]=new+'  flle_trading/gateway.py';manifest.write_text('\n'.join(lines)+'\n')
print('gateway_source_update=PASS old_sha256='+old+' new_sha256='+new)
PY
start_gateway
verify_gateway_identity
"${SCP[@]}" "$OBSERVER_HOST:$RUN_DIR/source.sha256" "$REPAIR_OUT/raw/source-after.sha256"
"${SCP[@]}" "$OBSERVER_HOST:$RUN_DIR/gateway.identity" "$REPAIR_OUT/raw/gateway-after.identity"
verify_deployed_inputs
printf 'PHASE=COMPLETE\nEXIT_CODE=0\n' >> "$REPAIR_OUT/run.env"
(cd "$REPAIR_OUT"; find raw -type f -print0 | sort -z | xargs -0 sha256sum; sha256sum run.env source.sh) > "$REPAIR_OUT/SHA256SUMS"
printf 'gateway_repair=%s\n' "$REPAIR_OUT"
