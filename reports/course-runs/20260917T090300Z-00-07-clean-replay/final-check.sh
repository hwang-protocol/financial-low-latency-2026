#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
AUDIT=Documents/reports/course-runs/20260917T090300Z-00-07-clean-replay
. Documents/reports/run-state/02-trading-baseline.env
mkdir -p "$AUDIT/final"
python3 apps/flle-trading-lab/scripts/verify-book-handoff.py http://10.1.1.101:8088 >"$AUDIT/final/book-feed.json"
bash apps/flle-trading-lab/scripts/transport_labctl.sh status "$RUN_ID" >"$AUDIT/final/control.json"
curl -fsS http://10.1.1.101:8088/api/state >"$AUDIT/final/state.json"
curl -fsS http://10.1.1.101:8088/api/transport-lab >"$AUDIT/final/clients.json"
for asset in index.html terminal.js terminal.css; do
  curl -fsS "http://10.1.1.101:8088/$asset" >"$AUDIT/final/$asset"
  cmp "apps/flle-trading-lab/web/$asset" "$AUDIT/final/$asset"
done
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.101 "cd '/var/tmp/flle-trading-lab-$RUN_ID'; sha256sum -c source.sha256" >"$AUDIT/final/deployed-inputs.txt"
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes root@10.1.1.2 'set -eu; systemctl is-enabled flle-platform-boot.service; cat /var/lib/flle/active-platform; ip -details link show dev ens64np1; readlink /sys/bus/pci/devices/0000:03:00.0/driver; LC_ALL=C ping -q -I ens64np1 -c 3 -W 1 20.1.1.1' >"$AUDIT/final/receiver-and-boot.txt"
bash -c 'set -Eeuo pipefail; source Documents/newDoc/assets/07-xdp/live-support/xdp-run-state.sh; load_state; check_recovery_ready; echo recovered_new_session=PASS' >"$AUDIT/final/xdp-recovery-ready.txt"
python3 - "$AUDIT" "$RUN_ID" <<'PY'
import json,pathlib,sys
p=pathlib.Path(sys.argv[1])/'final'
c=json.loads((p/'control.json').read_text());s=json.loads((p/'state.json').read_text());g=json.loads((p/'clients.json').read_text());r=(p/'receiver-and-boot.txt').read_text()
assert (c['mode'],c['transition'],c['owner'])==('SFC','READY','sfc')
assert s['feed']['integrity']=='HEALTHY' and s['feed']['trading_gate']=='OPEN' and s['replay']['status']=='PLAYING'
assert s['strategy']['enabled'] is False
assert all(g['clients'][n]['health']['status']=='ONLINE' for n in ['trader_manual','trader_onload','trader_tcpdirect'])
assert g['clients']['trader_dpdk']['health']['status']=='WAITING'
assert r.startswith('enabled\n') and sys.argv[2] in r and 'prog/xdp' not in r and '3 packets transmitted, 3 received' in r
result={'result':'PASS','platform_run':sys.argv[2],'mode':'SFC/READY/sfc','session':s['session'],'feed':'HEALTHY/OPEN','replay':'PLAYING','strategy_enabled':False,'clients':'three ONLINE; DPDK WAITING','xdp_attached':False,'boot_enabled':True,'web_sources_match':True,'data_ping':'3/3'}
(p/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
PY
