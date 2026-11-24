from pathlib import Path
import json,hashlib,datetime,subprocess
R=Path('/financial-low-latency');s=json.loads((R/'Documents/reports/run-state/full-course-replay.json').read_text());out=R/s['OUT']
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
cards=[]
for c in s['CARDS']:
 assert c['status'] in ['PASS','PASS_AFTER_FIX'],(c['id'],c['status'])
 attempts=[]
 for a in c['attempts']:
  p=out/a['log'];attempts.append({**{k:a.get(k) for k in ['started','ended','exit','seconds','sha256','created_runs']},'log':str(p.relative_to(R)),'log_sha256':digest(p)})
 cards.append(dict(id=c['id'],source=c['source'],status=c['status'],attempts=attempts,review=c.get('review'),performance_verdict=c.get('performance_verdict')))
validation={}
for name in ['content-retention','manifests','static-results','markdown-parse','05-performance-review','06-independent-recalculation']:
 p=out/'validation'/(name+'.json');validation[name]=json.loads(p.read_text())
final={name:json.loads((out/path).read_text()) for name,path in [('hosts','final-audit/result.json'),('startup','final-audit/startup-verification.json'),('endpoints','final-audit/endpoint-result.json'),('orders','final-platform-proof/result.json')]}
assert all(v.get('status','PASS')=='PASS' for v in final.values())
final['host_facts']={}
for host in ['1','2','11','101']:
 d=json.loads((out/'final-audit'/(host+'.json')).read_text());final['host_facts'][host]={k:d[k] for k in ['hostname','kernel','boot_id','pci','hugepages','sfc_loaded','core_hashes']}
 final['host_facts'][host]['addresses']={i['ifname']:[a['local']+'/'+str(a['prefixlen']) for a in i['addr_info']] for i in json.loads(d['addresses']['out'])}

files=subprocess.check_output(['git','diff','--name-only'],cwd=R,text=True).splitlines()
receipt=dict(schema='flle.snapshot-full-replay.v1',run_id=s['RUN_ID'],status=s['STATUS'],started=s['STARTED'],completed=s['ENDED'],initial_head=s['GIT_HEAD'],initial_worktree_clean=True,zero_edit_snapshot_pass=False,bash_cards=cards,non_bash=[{k:v for k,v in c.items() if k!='segment'} for c in s.get('NON_BASH_CARDS',[])],pauses={ch:json.loads((out/('pauses-'+ch+'.json')).read_text()) for ch in ['09','10']},validation=validation,final=final,modified_tracked_files=files,new_files=['apps/flle-trading-lab/tests/test_listener_startup.py','Documents/design/FLLE_Snapshot_Replay_And_Polish_2026-09-08.md','Documents/design/evidence/snapshot-replay-20260908.json'],editorial_review=s['EDITORIAL_REVIEW'],fixes=s['FIXES'],root_evidence_manifest=dict(path=str((out/'SHA256SUMS').relative_to(R)),sha256=digest(out/'SHA256SUMS')),limits=['Chapter 04 browser intentionally left to user; API and configs checked','Chapter 10 eight simulated physical-hardware command cards not executed','Fixed-CV performance batch rejected by unchanged environmental control gate; no selective rerun','No second fresh snapshot replay of final code after startup fix; same entry fully redeployed then sequentially continued','No Git history or remote write operations'])
p=R/'Documents/design/evidence/snapshot-replay-20260908.json';p.parent.mkdir(exist_ok=True);p.write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');print(p,'bytes',p.stat().st_size)
