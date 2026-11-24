from pathlib import Path
import base64,datetime,hashlib,json,subprocess
root=Path('/financial-low-latency')
state={k:v for k,v in (line.split('=',1) for line in (root/'Documents/reports/run-state/02-trading-baseline.env').read_text().splitlines() if '=' in line)}
change=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-manual-order-ui'
report=root/'Documents/reports/course-runs'/change
report.mkdir(parents=True)
payload={'run_dir':state['RUN_DIR'],'change':change,'files':{}}
for name in ['index.html','terminal.css','terminal.js']:
 before=(Path('/tmp/flle-manual-ui-before')/name).read_bytes();after=(root/'apps/flle-trading-lab/web'/name).read_bytes()
 payload['files'][name]={'before_sha256':hashlib.sha256(before).hexdigest(),'after_sha256':hashlib.sha256(after).hexdigest(),'data':base64.b64encode(after).decode()}
remote=r'''
from pathlib import Path
import base64,hashlib,json,os,shutil,subprocess,sys
p=json.loads(sys.stdin.read())
d=Path(p['run_dir']);web=d/'web';manifest=d/'source.sha256'
pid=(d/'gateway.pid').read_text().strip()
cmdline=Path('/proc')/pid/'cmdline'
cmd=cmdline.read_bytes();assert b'flle_trading.gateway' in cmd and str(web).encode() in cmd
stat=(Path('/proc')/pid/'stat').read_text().split()[21]
subprocess.run(['sha256sum','-c','source.sha256'],cwd=d,stdout=subprocess.DEVNULL,check=True)
for name,entry in p['files'].items():
 assert name in ('index.html','terminal.css','terminal.js')
 assert hashlib.sha256((web/name).read_bytes()).hexdigest()==entry['before_sha256'],name+' preimage changed'
 assert hashlib.sha256(base64.b64decode(entry['data'])).hexdigest()==entry['after_sha256']
backup=d/'web-updates'/p['change'];backup.mkdir(parents=True,exist_ok=False)
for name in p['files']:shutil.copy2(web/name,backup/name)
shutil.copy2(manifest,backup/'source.sha256')
old=manifest.read_text();lines=old.splitlines();updated=[];seen=set()
for line in lines:
 digest,name=line.split(None,1);name=name.lstrip('*')
 if name.startswith('web/') and name[4:] in p['files']:
  digest=p['files'][name[4:]]['after_sha256'];seen.add(name[4:])
 updated.append(digest+'  '+name)
assert seen==set(p['files'])
try:
 for name,entry in p['files'].items():
  stage=web/(name+'.'+p['change']+'.tmp');stage.write_bytes(base64.b64decode(entry['data']));stage.chmod((web/name).stat().st_mode & 0o777);stage.replace(web/name)
 stage=backup/'source.updated.sha256';stage.write_text('\n'.join(updated)+'\n');shutil.copy2(stage,manifest)
 subprocess.run(['sha256sum','-c','source.sha256'],cwd=d,stdout=subprocess.DEVNULL,check=True)
 assert cmdline.read_bytes()==cmd
 assert (Path('/proc')/pid/'stat').read_text().split()[21]==stat
except BaseException:
 for name in p['files']:shutil.copy2(backup/name,web/name)
 shutil.copy2(backup/'source.sha256',manifest)
 raise
print(json.dumps({'change':p['change'],'run_dir':str(d),'backup':str(backup),'gateway_pid':pid,'gateway_start_ticks':stat,'gateway_unchanged':True,'source_manifest_pass':True,'files':{n:{'before_sha256':e['before_sha256'],'after_sha256':e['after_sha256']} for n,e in p['files'].items()}}))
'''
# Pass the code as a quoted Python -c argument; JSON is stdin data, never shell code.
import shlex
command=['ssh','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=6','root@10.1.1.101','python3 -c '+shlex.quote(remote)]
result=subprocess.run(command,input=json.dumps(payload),text=True,capture_output=True,timeout=45)
(report/'remote.stdout').write_text(result.stdout);(report/'remote.stderr').write_text(result.stderr)
(report/'run.env').write_text('RUN_ID='+change+'\nEXIT_CODE='+str(result.returncode)+'\nPARENT_RUN_ID='+state['RUN_ID']+'\n')
print(result.stdout);print(result.stderr)
if result.returncode:raise SystemExit(result.returncode)
receipt=json.loads(result.stdout)
(root/'Documents/reports/run-state/02-manual-order-ui.env').write_text('RUN_ID='+change+'\nREPORT_DIR='+str(report)+'\nPARENT_RUN_ID='+state['RUN_ID']+'\n')
Path('/tmp/flle-manual-ui-deployed.json').write_text(json.dumps(receipt,indent=2)+'\n')
print('REPORT_DIR='+str(report))
