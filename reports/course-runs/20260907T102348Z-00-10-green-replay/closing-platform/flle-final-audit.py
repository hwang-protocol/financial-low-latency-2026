from pathlib import Path
import subprocess,json,hashlib,re,tempfile,datetime
ROOT=Path('/financial-low-latency');session=json.loads((ROOT/'Documents/reports/run-state/full-course-replay.json').read_text());out=ROOT/session['OUT']/'final-audit';out.mkdir(exist_ok=True)
run=session['PLATFORM_RUN'];remote='/var/tmp/flle-trading-lab-'+run
probe=r'''
import json,subprocess,pathlib,hashlib,os
run=__import__('sys').argv[1]
def cmd(args):
 p=subprocess.run(args,text=True,capture_output=True);return dict(rc=p.returncode,out=p.stdout,err=p.stderr)
r={'hostname':os.uname().nodename,'kernel':os.uname().release,'boot_id':pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'links':cmd(['ip','-j','-d','link']),'addresses':cmd(['ip','-j','addr']),'pci':[],'processes':cmd(['ps','-eo','pid,comm']),'hugepages':{p.name:p.read_text().strip() for p in pathlib.Path('/sys/kernel/mm/hugepages/hugepages-2048kB').glob('nr_hugepages')}}
for p in pathlib.Path('/sys/bus/pci/devices').glob('*'):
 if (p/'class').read_text().strip()=='0x020000':r['pci'].append(dict(bdf=p.name,driver=(p/'driver').resolve().name if (p/'driver').exists() else None,net=[n.name for n in (p/'net').glob('*')]))
r['interfaces']={n.name:dict(mac=(n/'address').read_text().strip(),operstate=(n/'operstate').read_text().strip(),qdisc=cmd(['tc','-j','qdisc','show','dev',n.name]),ingress=cmd(['tc','-j','filter','show','dev',n.name,'ingress']),egress=cmd(['tc','-j','filter','show','dev',n.name,'egress'])) for n in pathlib.Path('/sys/class/net').glob('*')}
p=pathlib.Path(run);r['source_manifest']=cmd(['bash','-c','cd "$1" && sha256sum -c source.sha256','bash',run]) if (p/'source.sha256').exists() else None
r['deployed_manifest']=cmd(['bash','-c','cd "$1" && sha256sum -c deployed.sha256','bash',run]) if (p/'deployed.sha256').exists() else None
r['sfc_loaded']=pathlib.Path('/sys/module/sfc/version').read_text().strip() if pathlib.Path('/sys/module/sfc/version').exists() else None
r['core_hashes']={str(x.relative_to(p)):hashlib.sha256(x.read_bytes()).hexdigest() for x in [p/'flle-exchange',p/'flle-trader'] if x.is_file()}
print(json.dumps(r))
'''
for host in ['1','2','11','101']:
 p=subprocess.run(['ssh','-o','BatchMode=yes','root@10.1.1.'+host,'python3','-c',__import__('shlex').quote(probe),remote],text=True,capture_output=True,check=True)
 (out/(host+'.json')).write_text(p.stdout);d=json.loads(p.stdout)
 for key in ['source_manifest','deployed_manifest']:
  if d[key] is not None:assert d[key]['rc']==0,(host,key,d[key]['err'])
 if host in ['1','2']:assert d['sfc_loaded']=='6.1.0.1009'
 for i in d['interfaces'].values():
  for direction in ['ingress','egress']:
   assert json.loads(i[direction]['out'] or '[]')==[],(host,direction)
 for n in json.loads(d['links']['out']):assert not n.get('xdp',{}).get('attached'),(host,n)
 procs=d['processes']['out'];assert not re.search(r'\b(simple_switch|mold_filter_ada|t-rex-64|_t-rex-64|ptp4l|phc2sys)\b',procs),host
 if host=='11':
  for name in ['ens64f0np0','ens64f1np1']:assert d['interfaces'][name]['operstate']=='down'
  assert all(x['driver']=='bnxt_en' for x in d['pci'] if x['net'] and x['net'][0].startswith('ens64'))
  assert d['hugepages']['nr_hugepages']=='0'
for suffix in ['state','health','transport-lab']:
 p=subprocess.run(['curl','-fsS','http://10.1.1.101:8088/api/'+suffix],text=True,capture_output=True,check=True);(out/(suffix+'.json')).write_text(p.stdout)
d=json.loads((out/'state.json').read_text());assert d['data_plane_mode']=='SFC' and d['data_plane_transition']=='READY'
assert d.get('feed',{}).get('integrity')=='HEALTHY',d.get('feed')
assert d['replay']['status']=='PLAYING'
# Read full switch configuration only into a protected temporary file, then redact.
with tempfile.TemporaryDirectory(prefix='flle-final-eos-') as tmp:
 t=Path(tmp);(t/'plan').write_text('show startup-config\nshow running-config\nshow vlan\nshow interfaces status\nshow ptp\n')
 subprocess.run(['python3',str(ROOT/'Documents/newDoc/assets/common/eos_cli.py'),'--mode','show','--plan',str(t/'plan'),'--output',str(t/'output')],stdout=subprocess.DEVNULL,check=True)
 text=(t/'output').read_text();start=text.split('$ show startup-config\n',1)[1].split('\n$ show running-config',1)[0]
 assert not re.search(r'^vlan (20|100|200|3101)\b',start,re.M)
 assert 'switchport access vlan 20' not in start
 redacted='\n'.join('[REDACTED]' if re.search(r'username|secret|password|ssh-key|snmp-server community',l,re.I) else l for l in text.splitlines())
 (out/'eos-redacted.txt').write_text(redacted+'\n')
 previous=Path(Path('/tmp/flle-snapshot-private-path').read_text().strip())/'eos-output.txt'
 if previous.exists():
  old=previous.read_text().split('$ show startup-config\n',1)[1].split('\n$ show ',1)[0]
  def config(t):return '\n'.join(x.strip() for x in t.splitlines() if not x.startswith('show ') and x.strip())
  assert config(start)==config(old),'startup config changed since pre-reboot audit'
 else:raise RuntimeError('original startup transcript unavailable; cannot claim unchanged')
 (out/'startup-verification.json').write_text(json.dumps({'unchanged':True,'no_course_vlans':True,'startup_sha256':hashlib.sha256(config(start).encode()).hexdigest()},indent=2)+'\n')
(out/'result.json').write_text(json.dumps({'status':'PASS','checked_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'platform_run':run},indent=2)+'\n')
print('PASS final host/interface/process/source/Feed/GUI/startup audit',out)
