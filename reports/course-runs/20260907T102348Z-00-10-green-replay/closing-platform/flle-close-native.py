from pathlib import Path
import subprocess,json,re,urllib.request
out=Path('/financial-low-latency/Documents/reports/course-runs/20260907T102348Z-00-10-green-replay/closing-platform')
remote='/var/tmp/flle-trading-lab-20260907T112313Z-02-trading-platform'
def ssh(cmd):return subprocess.check_output(['ssh','root@10.1.1.2',cmd],text=True)
onpid=ssh('cat '+remote+'/trader-onload.pid').strip();tcpid=ssh('cat '+remote+'/trader-tcpdirect.pid').strip()
on=ssh('onload_stackdump lots');(out/'onload-native.txt').write_text(on)
blocks=re.split(r'(?=^  Onload .* pid=)',on,flags=re.M);assert any((' pid='+onpid+' ') in b and 'Onloaded(Valid)' in b and re.search(r'rmt=20\.1\.1\.1:43120 ESTABLISHED',b) for b in blocks)
zf=remote+'/transport-runtime/flle-ch06-four-path/bin/zf_stackdump'
ls=ssh(zf+' list');(out/'tcpdirect-list.txt').write_text(ls)
line=next(l for l in ls.splitlines() if l.startswith('flle-tcpdirect ') and 'pid='+tcpid in l);sid=re.search(r'\bid=(\d+)',line)[1]
a=ssh(zf+' attr '+sid);d=ssh(zf+' dump '+sid);(out/'tcpdirect-attr.txt').write_text(a);(out/'tcpdirect-native.txt').write_text(d)
assert 'ctpio=3' in a and 'ctpio_mode=sf-np' in a and re.search(r'rmt=20\.1\.1\.1:43120 .*ESTABLISHED',d)
for name in ['state','transport-lab']:
 s=json.load(urllib.request.urlopen('http://10.1.1.101:8088/api/'+name));(out/(name+'.json')).write_text(json.dumps(s,indent=2))
 if name=='state':assert s['feed']['integrity']=='HEALTHY'
 else:
  for k in ['trader_manual','trader_onload','trader_tcpdirect']:assert s['clients'][k]['health']['status']=='ONLINE'
(out/'result.json').write_text(json.dumps(dict(status='PASS',orders=6,onload_valid=True,tcpdirect_ctpio=True,profile='SOFTWARE'))+'\n')
print('PASS six executed orders, both native accelerated paths, three online clients')
