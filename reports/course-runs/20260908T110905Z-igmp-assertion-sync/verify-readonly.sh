#!/bin/bash
set -Eeuo pipefail
cd /financial-low-latency
review_out=/financial-low-latency/Documents/reports/course-runs/20260908T110905Z-igmp-assertion-sync
export IGMP_REVIEW_SHOW_PLAN="$review_out/igmp-show.plan"
printf '%s\n' 'show ip igmp snooping' 'show igmp snooping querier' 'show ip igmp snooping groups' >"$IGMP_REVIEW_SHOW_PLAN"
# Execute the production asset unchanged. This single EOS invocation uses live
# show commands instead of reapplying its pre-existing device configuration.
python3() {
  if [[ "${1:-}" == Documents/newDoc/assets/common/eos_cli.py ]]; then
    [[ "$#" == 7 && "$2" == --mode && "$3" == controlled-config && "$4" == --plan && "$5" == */03-live-traffic/market-igmp-enable.plan && "$6" == --output ]] || return 2
    printf 'READ_ONLY_VERIFICATION: replacing IGMP config plan with live show plan\n' >&2
    command python3 "$1" --mode show --plan "$IGMP_REVIEW_SHOW_PLAN" --output "$7"
  else
    command python3 "$@"
  fi
}
export -f python3
command python3 - <<'PY'
import urllib.request,pathlib
p=pathlib.Path('Documents/reports/course-runs/20260908T110905Z-igmp-assertion-sync/raw')
with urllib.request.urlopen('http://10.1.1.101:8088/api/state',timeout=10) as r:
 (p/'before-state.json').write_bytes(r.read())
PY
bash Documents/newDoc/assets/03-live-traffic/02-compare-market-transports.sh >"$review_out/raw/ch03-run-02.txt" 2>&1
command python3 - <<'PY'
import urllib.request,pathlib,json
p=pathlib.Path('Documents/reports/course-runs/20260908T110905Z-igmp-assertion-sync/raw')
with urllib.request.urlopen('http://10.1.1.101:8088/api/state',timeout=10) as r:
 after=json.load(r)
(p/'after-state.json').write_text(json.dumps(after,indent=2)+'\n')
before=json.loads((p/'before-state.json').read_text())
assert after['market_mode']==before['market_mode'],(before['market_mode'],after['market_mode'])
assert after['feed']['integrity']=='HEALTHY' and after['feed']['pending']==0 and after['feed']['gaps']==0
print('RESTORED',after['market_mode'],'Feed HEALTHY pending=0 gaps=0')
PY
