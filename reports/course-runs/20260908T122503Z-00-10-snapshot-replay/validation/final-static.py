from pathlib import Path
import subprocess,json,hashlib,sys
R=Path('/financial-low-latency');out=Path(__file__).resolve().parent
checks=[['python3',str(out/'check-content.py')],['python3','Documents/newDoc/assets/common/verify-filter-course-cards.py'],['python3','Documents/newDoc/assets/common/verify-filter-output-labels.py'],['git','diff','--check']]
results=[]
for index,cmd in enumerate(checks):
 p=subprocess.run(cmd,cwd=R,text=True,capture_output=True);(out/('static-'+str(index)+'.txt')).write_text(p.stdout+p.stderr);results.append(dict(command=cmd,exit=p.returncode));assert p.returncode==0,p.stdout+p.stderr
visual=R/'Documents/newDoc/images/course-visuals'
for manifest in [visual/'SHA256SUMS',*sorted(visual.glob('*-diagrams/SHA256SUMS'))]:
 if not manifest.exists():continue
 p=subprocess.run(['sha256sum','-c','--quiet',manifest.name],cwd=manifest.parent,text=True,capture_output=True);results.append(dict(command=['sha256sum','-c',str(manifest.relative_to(R))],exit=p.returncode));assert p.returncode==0,p.stdout+p.stderr
(out/'static-results.json').write_text(json.dumps(dict(status='PASS',checks=results),indent=2)+'\n');print('PASS content, cards, output labels, whitespace, image manifests')
