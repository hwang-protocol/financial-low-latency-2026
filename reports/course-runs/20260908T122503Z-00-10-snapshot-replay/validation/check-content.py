from pathlib import Path
import re,json,subprocess,hashlib
R=Path('/financial-low-latency');s=json.loads((R/'Documents/reports/run-state/full-course-replay.json').read_text());out=R/s['OUT']/'validation';out.mkdir(exist_ok=True);results=[]
def section(t,title):
 m=re.search(r'^## '+re.escape(title)+r'\s*\n(.*?)(?=^## |\Z)',t,re.M|re.S);return m[0] if m else None
for p in sorted((R/'Documents/newDoc').glob('[0-9][0-9]-*.md')):
 old=(R/s['OUT']/'source-before'/p.name).read_text();new=p.read_text()
 heads=lambda t:set(re.findall(r'^#{1,6} .+$',t,re.M))
 imgs=lambda t:set(re.findall(r'<img[^>]+src="([^"]+)"|!\[[^\]]*\]\(([^)]+)\)',t))
 row=dict(chapter=p.name,removed_headings=sorted(heads(old)-heads(new)),removed_images=sorted(imgs(old)-imgs(new)),learning_objectives_unchanged=section(old,'本章学习目标')==section(new,'本章学习目标'),understanding_check_unchanged=section(old,'理解检查')==section(new,'理解检查'))
 assert not row['removed_headings'] and not row['removed_images'] and row['learning_objectives_unchanged'] and row['understanding_check_unchanged'],row
 results.append(row)
inline=[]
assets={p.read_text().strip():str(p.relative_to(R)) for p in (R/"Documents/newDoc/assets").rglob("*.sh")}
full_assets=[]
for c in s['CARDS']:
 code=(R/s['OUT']/'cards'/(c['id']+'.sh')).read_text();assert code in (R/c['source']).read_text(),c['id']
 if code.startswith('#!') and c['chapter']>'01':
  assert code.strip() in assets,c['id']
  full_assets.append(dict(card=c['id'],asset=assets[code.strip()]))
 m=re.search(r'^SELF="(?:\$REPO_ROOT|/financial-low-latency)/([^"\n]+)"',code,re.M)
 if m:
  asset=R/m[1]
  assert code.strip()==asset.read_text().strip(),(c['id'],str(asset),'inline differs from asset')
  inline.append(c['id'])
(out/'content-retention.json').write_text(json.dumps(dict(baseline=s['GIT_HEAD'],chapters=results,executable_blocks_exact=len(s['CARDS']),inline_assets_exact=inline,full_assets_exact=full_assets),ensure_ascii=False,indent=2)+'\n')
print('PASS 11 chapter headings/images/objectives/questions preserved;',len(s['CARDS']),'exact Bash blocks;',len(inline),'full inline assets exact')
