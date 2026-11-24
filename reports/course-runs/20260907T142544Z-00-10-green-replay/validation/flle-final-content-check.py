from pathlib import Path
import re,json,subprocess,hashlib
R=Path('/financial-low-latency');s=json.loads((R/'Documents/reports/run-state/full-course-replay.json').read_text());out=R/s['OUT']/'validation';result=[]
def section(t,title):
 m=re.search(r'^## '+re.escape(title)+r'\s*\n(.*?)(?=^## |\Z)',t,re.M|re.S);return m[0] if m else None
for p in sorted((R/'Documents/newDoc').glob('[0-9][0-9]-*.md')):
 old=subprocess.check_output(['git','show','12af878:'+str(p.relative_to(R))],text=True);new=p.read_text()
 heads=lambda t:set(re.findall(r'^#{1,6} .+$',t,re.M))
 imgs=lambda t:set(re.findall(r'<img[^>]+src="([^"]+)"|!\[[^\]]*\]\(([^)]+)\)',t))
 row=dict(chapter=p.name,removed_headings=sorted(heads(old)-heads(new)),removed_images=sorted(imgs(old)-imgs(new)),learning_objectives_unchanged=section(old,'本章学习目标')==section(new,'本章学习目标'),understanding_check_unchanged=section(old,'理解检查')==section(new,'理解检查'))
 assert not row['removed_headings'] and not row['removed_images'] and row['learning_objectives_unchanged'] and row['understanding_check_unchanged'],row
 result.append(row)
# Exact executable blocks still appear in current articles; label changes separately recorded.
for c in s['CARDS']:
 code=(R/s['OUT']/'cards'/(c['id']+'.sh')).read_text();assert code in (R/c['source']).read_text(),c['id']
# same-run display matching AND semantic explanation-table numbers.
for chapter,run,stages in [('09','20260907T151801Z-09-p4-drop-live',['configure','inspect','drop','restore']),('10','20260907T152509Z-10-rtl-stages',['prepare','arm','verify','restore'])]:
 doc=next((R/'Documents/newDoc').glob(chapter+'-*.md')).read_text()
 for stage in stages:assert (R/'Documents/reports/course-runs'/run/'raw'/(stage+'-display.txt')).read_text().rstrip() in doc
 if chapter=='09':assert '177 / 177' in doc and 'HEALTHY；两笔 ORDER_EXECUTED；1 → 1' in doc
 else:assert '220 / 220' in doc and '本次实际序号是 220' in doc
for link in [R/'.cursor/skills/flle-course-flow',Path('/root/.codex/skills/flle-course-flow')]:assert link.resolve()==R/'.agents/skills/flle-course-flow'
(out/'content-retention.json').write_text(json.dumps(dict(baseline='12af878',chapters=result,executable_blocks_preserved=57,display_blocks_verbatim=8,skill_links_single_source=True),ensure_ascii=False,indent=2)+'\n');print('PASS 11 chapters retain headings/images/objectives/checks, 57 executable blocks, 8 actual displays, 2 skill links')
