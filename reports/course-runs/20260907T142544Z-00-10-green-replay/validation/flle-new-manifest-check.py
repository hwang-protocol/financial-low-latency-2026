from pathlib import Path
import json,re,hashlib
R=Path('/financial-low-latency');s=json.loads((R/'Documents/reports/run-state/full-course-replay.json').read_text());whole=R/s['OUT'];roots=set()
for c in s['CARDS']:
 if not c['attempts'] or c['attempts'][-1].get('exit')!=0:continue
 a=c['attempts'][-1];roots.update(R/'Documents/reports/course-runs'/n for n in a['created_runs'])
 t=(whole/a['log']).read_text(errors='replace')
 for v in re.findall(r'^(?:evidence=|本轮证据目录：)(.+)$',t,re.M):
  p=Path(v.strip());roots.add(p if p.is_absolute() else R/p)
warm=whole/'warm-preparation/prep-repeat.txt'
if warm.exists():
 for v in re.findall(r'^evidence=(.+)$',warm.read_text(),re.M):roots.add(R/v.strip())
paths=set()
for root in roots:
 if root.exists():paths.update(root.rglob('*SHA256SUMS'))
paths={p for p in paths if p.is_file() and 'source-before' not in p.parts}
original=whole/'source-version-history/first_trade-before-transport-quote.py';oldsha=hashlib.sha256(original.read_bytes()).hexdigest() if original.exists() else ''
results=[];cache={}
def digest(p):
 if p not in cache:cache[p]=hashlib.sha256(p.read_bytes()).hexdigest()
 return cache[p]
for manifest in sorted(paths):
 item={'manifest':str(manifest.relative_to(R)),'verified':0,'historical_source':[],'errors':[]}
 for line in manifest.read_text().splitlines():
  if not line.strip():continue
  m=re.fullmatch(r'([a-f0-9]{64})\s+\*?(.+)',line)
  if not m:item['errors'].append({'line':line,'error':'unrecognized format'});continue
  sha,name=m.groups();p=Path(name);candidates=[p] if p.is_absolute() else [manifest.parent/p,manifest.parent.parent/p,R/p]
  if manifest.name=='LIVE-SUPPORT-SHA256SUMS':candidates.append(R/'Documents/newDoc/assets/07-arista-time'/p)
  good=next((p for p in candidates if p.is_file() and digest(p)==sha),None)
  if good:item['verified']+=1
  elif name.endswith('apps/flle-trading-lab/tests/first_trade.py') and sha==oldsha:
   item['historical_source'].append({'referenced':name,'expected':sha,'retained_as':str(original.relative_to(R))});item['verified']+=1
  else:item['errors'].append({'file':name,'expected':sha,'existing':[str(p) for p in candidates if p.exists()]})
 results.append(item)
out=whole/'validation';out.mkdir(exist_ok=True);report={'manifests':len(results),'items':sum(x['verified'] for x in results),'historical_source_uses':sum(len(x['historical_source']) for x in results),'errors':sum(len(x['errors']) for x in results),'results':results};(out/'child-manifests.json').write_text(json.dumps(report,indent=2)+'\n');print({k:v for k,v in report.items() if k!='results'})
for x in results:
 if x['errors']:print(x)
raise SystemExit(bool(report['errors']))
