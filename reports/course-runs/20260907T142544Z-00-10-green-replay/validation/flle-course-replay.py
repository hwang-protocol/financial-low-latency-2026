from pathlib import Path
from datetime import datetime,timezone
import subprocess,json,re,sys,hashlib,time,os
ROOT=Path('/financial-low-latency');STATE=ROOT/'Documents/reports/run-state/full-course-replay.json'
def now():return datetime.now(timezone.utc).isoformat()
def save(s):STATE.write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n');(ROOT/s['OUT']/'session.json').write_text(STATE.read_text())
if sys.argv[1]=='init':
 rid=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-00-10-green-replay';out=ROOT/'Documents/reports/course-runs'/rid
 for d in ['cards','raw','source-before']:(out/d).mkdir(parents=True,exist_ok=True)
 cards=[]
 for f in sorted((ROOT/'Documents/newDoc').glob('[0-9][0-9]-*.md')):
  t=f.read_text();(out/'source-before'/f.name).write_text(t);ms=list(re.finditer(r'<div style="border-left:6px solid (#[a-fA-F0-9]+);[^\n]*</div>',t));n=0
  for i,c in enumerate(ms):
   label=re.sub('<[^>]+>','',c.group())
   if c.group(1).lower() not in ('#15803d','#ea580c') or '模拟' in label:continue
   n+=1;end=ms[i+1].start() if i+1<len(ms) else len(t);seg=t[c.end():end]
   for j,b in enumerate(re.finditer(r'^(?P<fence>```|~~~)bash\n(?P<code>.*?)^(?P=fence)\s*$',seg,re.M|re.S),1):
    code=b.group('code');cid=f'{f.name[:2]}-{n:02}-{j}';(out/'cards'/f'{cid}.sh').write_text(code);cards.append({'id':cid,'chapter':f.name[:2],'source':str(f.relative_to(ROOT)),'line':t.count('\n',0,c.start())+1,'label':label,'sha256':hashlib.sha256(code.encode()).hexdigest(),'status':'PENDING','attempts':[]})
 s={'RUN_ID':rid,'OUT':str(out.relative_to(ROOT)),'STATUS':'RUNNING','STARTED':now(),'BASELINE_AUDIT':'20260907T101558Z-post-snapshot-clean-audit','AUTHORIZATION':'User authorized full chapter 00-10 live sequential classroom replay and necessary fixes; no git history operations.','CARDS':cards,'BROWSER_CHECKS':[],'FIXES':[]};save(s)
 paths=sorted(set([*ROOT.glob('Documents/newDoc/[0-9][0-9]-*.md'),*ROOT.glob('Documents/newDoc/assets/**/*.sh'),*ROOT.glob('Documents/newDoc/assets/**/*.py'),*ROOT.glob('apps/flle-trading-lab/scripts/*'),*ROOT.glob('apps/flle-trading-lab/src/**/*')]))
 (out/'source-before/SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(ROOT))+'\n' for p in paths if p.is_file()))
 print(rid,len(cards),'Bash cards; browser card pending separately');sys.exit()
s=json.loads(STATE.read_text());out=ROOT/s['OUT']
if sys.argv[1]=='run':
 for cid in sys.argv[2:]:
  card=next(c for c in s['CARDS'] if c['id']==cid);code=out/'cards'/f'{cid}.sh';a={'started':now(),'sha256':hashlib.sha256(code.read_bytes()).hexdigest(),'log':f'raw/{cid}-attempt-{len(card["attempts"])+1}.txt'};card['attempts'].append(a);card['status']='RUNNING';s['CURRENT_CARD']=cid;save(s);print('START',cid,card['label'][:60],flush=True)
  before=set((ROOT/'Documents/reports/course-runs').iterdir());start=time.monotonic()
  with (out/a['log']).open('w') as log:
   p=subprocess.Popen(['bash',str(code)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT);a['pid']=p.pid;save(s);rc=p.wait()
  a.update(ended=now(),exit=rc,seconds=round(time.monotonic()-start,2),created_runs=sorted(p.name for p in set((ROOT/'Documents/reports/course-runs').iterdir())-before));card['status']='COMMAND_PASS_PENDING_REVIEW' if rc==0 else 'FAILED';save(s);print('END',cid,'exit',rc,'seconds',a['seconds'],'new_runs',a['created_runs'],flush=True);print('\n'.join((out/a['log']).read_text(errors='replace').splitlines()[-12:]),flush=True)
  if rc:sys.exit(rc)
elif sys.argv[1]=='review':
 for cid in sys.argv[2:]:
  c=next(c for c in s['CARDS'] if c['id']==cid);assert c['attempts'][-1]['exit']==0;c['status']='PASS';c['reviewed_at']=now();c['evidence_paths']=re.findall(r'^evidence=(.+)$',(out/c['attempts'][-1]['log']).read_text(errors='replace'),re.M)
 save(s);print('reviewed',sys.argv[2:])
elif sys.argv[1]=='status':
 for c in s['CARDS']:print(c['id'],c['status'])
