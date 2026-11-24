#!/usr/bin/env python3
"""Execute an exact article green card and retain each attempt, including failures."""
import datetime,hashlib,json,os,pathlib,subprocess,sys,time
out=pathlib.Path(__file__).resolve().parent
root=pathlib.Path('/financial-low-latency')
manifest_path=out/'manifest.json'
manifest=json.loads(manifest_path.read_text())
key=sys.argv[1]
card=next(c for c in manifest['cards'] if c['key']==key)
assert card['kind']=='bash','Manual web card needs its own observation'
script=root/card['script']
assert hashlib.sha256(script.read_bytes()).hexdigest()==card['command_sha256']
number=1+sum(a['key']==key for a in manifest['attempts'])
log=out/'logs'/f'{key}-attempt-{number}.log'
record={'key':key,'attempt':number,'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'log':str(log.relative_to(root)),'status':'RUNNING'}
manifest['attempts'].append(record)
manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(f'START {key} {card["title"]} attempt={number} log={log}',flush=True)
start=time.monotonic()
with log.open('wb') as sink:
 p=subprocess.Popen(['bash',str(script)],cwd=root,stdout=sink,stderr=subprocess.STDOUT)
 code=p.wait()
record.update(exit_code=code,duration_s=round(time.monotonic()-start,2),finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='EXIT_ZERO' if code==0 else 'FAILED',log_sha256=hashlib.sha256(log.read_bytes()).hexdigest())
manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print('\n'.join(log.read_text(errors='replace').splitlines()[-45:]),flush=True)
print(f'END {key} rc={code} duration={record["duration_s"]}s',flush=True)
sys.exit(code)
