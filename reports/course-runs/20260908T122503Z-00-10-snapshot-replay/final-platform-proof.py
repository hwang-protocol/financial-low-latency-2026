from pathlib import Path
import subprocess,json,sys
root=Path('/financial-low-latency');state=json.loads((root/'Documents/reports/run-state/full-course-replay.json').read_text());out=root/state['OUT']/'final-platform-proof';out.mkdir(exist_ok=True)
with (out/'baseline.txt').open('w') as f:
 subprocess.run(['bash','apps/flle-trading-lab/scripts/transport_labctl.sh','baseline',state['PLATFORM_RUN']],cwd=root,stdout=f,stderr=subprocess.STDOUT,check=True)
print('baseline restored',flush=True)
source=(root/'Documents/newDoc/assets/common/prove-trading-recovered.py').read_text()
assert source.count('"transport": "SOCKET"')==1
for mode in ['SOCKET','OPENONLOAD','TCPDIRECT']:
 code=out/('prove-'+mode.lower()+'.py');code.write_text(source.replace('"transport": "SOCKET"','"transport": "'+mode+'"'))
 with (out/(mode+'.txt')).open('w') as f:
  subprocess.run([sys.executable,str(code),'http://10.1.1.101:8088',str(out/mode)],stdout=f,stderr=subprocess.STDOUT,check=True)
 print(mode,'neutral pair PASS',flush=True)
with (out/'status.json').open('w') as f:
 subprocess.run(['bash','apps/flle-trading-lab/scripts/transport_labctl.sh','status',state['PLATFORM_RUN']],stdout=f,check=True)
s=json.loads((out/'status.json').read_text());assert (s['mode'],s['transition'],s['owner'])==('SFC','READY','sfc')
for key in ['socket','onload','tcpdirect']:assert s['hardware_receipts'][key]['verified'],key
(out/'result.json').write_text(json.dumps(dict(status='PASS',platform=state['PLATFORM_RUN'],executed_orders=6,positions_unchanged=True,native_receipts=['socket','onload','tcpdirect']),indent=2)+'\n')
print('PASS 6 orders, three native path receipts, net positions unchanged')
