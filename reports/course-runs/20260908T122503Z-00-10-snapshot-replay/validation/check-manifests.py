from pathlib import Path
import json,re,hashlib
R=Path('/financial-low-latency');s=json.loads((R/'Documents/reports/run-state/full-course-replay.json').read_text());out=R/s['OUT'];roots=set();cache={};checked=[];errors=[];historical=[]
for c in s['CARDS']:
 for a in c['attempts']:
  if a.get('exit')!=0:continue
  roots.update(R/'Documents/reports/course-runs'/n for n in a.get('created_runs',[]))
  text=(out/a['log']).read_text(errors='replace')
  for name in re.findall(r'^(?:evidence=|本轮证据目录：)([^\n]+)',text,re.M):
   p=Path(name.strip());roots.add(p if p.is_absolute() else R/p)
def sha(p):
 st=p.stat();key=(str(p),st.st_size,st.st_mtime_ns)
 if key not in cache:
  h=hashlib.sha256()
  with p.open('rb') as f:
   for b in iter(lambda:f.read(1048576),b''):h.update(b)
  cache[key]=h.hexdigest()
 return cache[key]
manifests=set()
for root in roots:
 if root.is_dir():manifests.update(root.rglob('SHA256SUMS'))
for manifest in sorted(manifests):
 for line in manifest.read_text().splitlines():
  m=re.match(r'^([0-9a-f]{64}) [ *](.+)$',line)
  if not m:errors.append([str(manifest),'unparsed line',line]);continue
  digest,name=m.groups();p=Path(name)
  candidates=[p] if p.is_absolute() else [manifest.parent/p,R/p]
  match=next((q for q in candidates if q.is_file() and sha(q)==digest),None)
  if match:checked.append([str(manifest.relative_to(R)),name]);continue
  # Resolve an external source reference against its immutable pre-run copy.
  relative=next((q.relative_to(R) for q in candidates if q.is_relative_to(R)),None)
  archives=[]
  if relative:
   archives=[out/'source-versions/before'/relative]
   for prefix in ['Documents/','apps/']:
    if str(relative).startswith(prefix):archives.append(out/'source-versions/before'/str(relative)[len(prefix):])
  old=next((q for q in archives if q.is_file() and sha(q)==digest),None)
  if old:historical.append(dict(manifest=str(manifest.relative_to(R)),reference=name,verified_copy=str(old.relative_to(R)),sha256=digest))
  else:errors.append([str(manifest),name,'missing or digest mismatch'])
result=dict(status='PASS' if not errors else 'FAIL',roots=len(roots),manifests=len(manifests),direct_matches=len(checked),archived_source_matches=historical,errors=errors)
(out/'validation/manifests.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False));assert not errors
