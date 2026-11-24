#!/usr/bin/env bash
set -Eeuo pipefail
cd /financial-low-latency
source Documents/reports/run-state/02-trading-baseline.env
PARENT_RUN_ID="$RUN_ID"
SNAPSHOT_CHECK_ID="$(date -u +%Y%m%dT%H%M%SZ)-06-snapshot-ready"
OUT="$PWD/Documents/reports/course-runs/$SNAPSHOT_CHECK_ID"
mkdir -p "$OUT/raw"
printf 'SNAPSHOT_CHECK_ID=%s\nPARENT_RUN_ID=%s\nOUT=%s\nSTATUS=CHECKING\n' "$SNAPSHOT_CHECK_ID" "$PARENT_RUN_ID" "$OUT" > Documents/reports/run-state/06-snapshot-ready.env
cp /tmp/flle-ch06-snapshot-ready.sh "$OUT/entry.sh"
echo "SNAPSHOT_CHECK=$OUT"
bash Documents/newDoc/assets/06-arista-time/13-trading-online-final.sh > "$OUT/raw/final-gate.txt" 2>&1
tail -n 11 "$OUT/raw/final-gate.txt"
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=8 root@10.1.1.2 python3 - > "$OUT/raw/receiver.json" <<'PY'
import json,pathlib,subprocess
pci=pathlib.Path('/sys/bus/pci/devices/0000:03:00.0')
nic='ens64np1'
info=json.loads(subprocess.check_output(['ip','-j','-details','addr','show','dev',nic]))[0]
owner=(pci/'driver').resolve().name
processes=subprocess.check_output(['ps','-eo','comm='],text=True).splitlines()
assert owner=='sfc'
assert info['address']=='00:0f:53:d3:af:21'
assert 'UP' in info['flags'] and info.get('operstate')=='UP'
assert any(a.get('local')=='20.1.1.2' for a in info['addr_info'])
assert not info.get('master')
assert not info.get('xdp',{}).get('prog') and not info.get('xdp',{}).get('prog_id')
assert not pathlib.Path('/var/tmp/flle-market-filter.cmd').exists()
assert not any(p.strip().startswith('mold_filter') for p in processes)
print(json.dumps({'result':'PASS','driver':owner,'link':info,'rtl_control_absent':True,'rtl_process_absent':True},indent=2))
PY
ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=8 root@10.1.1.11 python3 - > "$OUT/raw/tool-ports.json" <<'PY'
import json,pathlib,subprocess
rows=[]
for bdf,nic in [('0000:03:00.0','ens64f0np0'),('0000:03:00.1','ens64f1np1')]:
 p=pathlib.Path('/sys/bus/pci/devices')/bdf
 owner=(p/'driver').resolve().name
 info=json.loads(subprocess.check_output(['ip','-j','-details','addr','show','dev',nic]))[0]
 assert owner=='bnxt_en'
 assert 'UP' not in info['flags'] and not info['addr_info']
 assert not info.get('master')
 assert not info.get('xdp',{}).get('prog') and not info.get('xdp',{}).get('prog_id')
 rows.append({'bdf':bdf,'driver':owner,'link':info})
processes=subprocess.check_output(['ps','-eo','comm='],text=True).splitlines()
assert not any(any(w in p for w in ('simple_switch','t-rex-64','testpmd')) for p in processes)
print(json.dumps({'result':'PASS','ports':rows,'traffic_generator_and_p4_absent':True},indent=2))
PY
cat > "$OUT/switch-show.plan" <<'PLAN'
show vlan id 20
show interfaces status
show running-config interfaces Ethernet1
show running-config interfaces Ethernet2
show running-config interfaces Ethernet11
show running-config interfaces Ethernet12
show monitor session
PLAN
python3 Documents/newDoc/assets/common/eos_cli.py --plan "$OUT/switch-show.plan" --output "$OUT/raw/switch.txt" --mode show > "$OUT/raw/switch-cli.txt" 2>&1
python3 - "$OUT/raw/switch.txt" <<'PY'
import pathlib,re,sys
s=pathlib.Path(sys.argv[1]).read_text()
for port in (1,2,11,12):
 section=s.split(f'$ show running-config interfaces Ethernet{port}\n',1)[1].split('\n$ ',1)[0]
 assert 'switchport access vlan 20' in section,section
 assert 'switchport mode trunk' not in section
 assert not re.search(r'^\s+shutdown\s*$',section,re.M)
 assert re.search(rf'^Et{port}\s+\S+\s+20\s+',s,re.M)
monitor=s.split('$ show monitor session\n',1)[1]
assert not any(name in monitor for name in ('FLLEXDP','FLLETS')),monitor
print('SWITCH_PASS: Et1/2/11/12 VLAN20; no FLLEXDP/FLLETS mirror')
PY
curl -fsS --max-time 10 http://10.1.1.101:8088/api/state > "$OUT/raw/state.json"
curl -fsS --max-time 10 http://10.1.1.101:8088/api/transport-lab > "$OUT/raw/transport.json"
python3 - "$OUT" <<'PY'
import json,pathlib,sys
p=pathlib.Path(sys.argv[1]); s=json.loads((p/'raw/state.json').read_text()); t=json.loads((p/'raw/transport.json').read_text())
assert s['experiment_profile']=='TRANSPORT'
assert (t['mode'],t['transition'],t['owner'])==('SFC','READY','sfc')
assert all(t['clients'][k]['health']['status']=='ONLINE' for k in ('trader_manual','trader_onload','trader_tcpdirect'))
assert t['clients']['trader_dpdk']['health']['status']=='WAITING'
assert s['health']['exchange']['status']==s['health']['gateway']['status']=='ONLINE'
assert s['replay']['status']=='PLAYING'
assert s['feed']['trading_gate']=='OPEN'
report={'result':'SNAPSHOT_READY','profile':'TRANSPORT','data_plane':'SFC/READY/sfc','clients':'Socket, Onload, TCPDirect ONLINE; DPDK WAITING','next_step':'Chapter 07 preparation A; not started','chapter06_final_gate':'PASS','receiver_no_xdp':True,'receiver_no_rtl':True,'tool_ports':'bnxt_en/DOWN/no-IP','switch':'Et1/Et2/Et11/Et12 VLAN20; no course mirror','replay_status':s['replay']['status'],'replay_session':s['feed']['session'],'positions':s['positions'],'snapshot_created_by_agent':False}
(p/'raw/result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(report,ensure_ascii=False))
PY
(cd "$OUT" && find raw -type f -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS)
printf 'SNAPSHOT_CHECK_ID=%s\nPARENT_RUN_ID=%s\nOUT=%s\nSTATUS=SNAPSHOT_READY\nNEXT_STEP=CH07_PREP_A\n' "$SNAPSHOT_CHECK_ID" "$PARENT_RUN_ID" "$OUT" > Documents/reports/run-state/06-snapshot-ready.env
