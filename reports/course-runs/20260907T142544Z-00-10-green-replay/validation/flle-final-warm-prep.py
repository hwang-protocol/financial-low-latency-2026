from pathlib import Path
import json,subprocess,time,urllib.request,threading
R=Path('/financial-low-latency');s=json.loads((R/'Documents/reports/run-state/full-course-replay.json').read_text());out=R/s['OUT']/'warm-preparation';out.mkdir(exist_ok=True)
def state():
 with urllib.request.urlopen('http://10.1.1.101:8088/api/state',timeout=5) as f:return json.load(f)
assert state()['feed']['integrity']=='HEALTHY'
observed=[];stop=threading.Event()
def observe():
 while not stop.is_set():
  try:
   d=state();observed.append({'time':time.time(),'feed':d.get('feed'),'mode':d.get('data_plane_mode'),'profile':d.get('experiment_profile')})
  except Exception as exc:observed.append({'time':time.time(),'error':str(exc)})
  stop.wait(.5)
t=threading.Thread(target=observe);t.start()
try:
 with (out/'prep-repeat.txt').open('w') as f:subprocess.run(['bash','Documents/newDoc/assets/02-trading-baseline/00a-runtime-prep.sh'],stdout=f,stderr=subprocess.STDOUT,check=True)
finally:stop.set();t.join();(out/'feed-monitor.json').write_text(json.dumps(observed,indent=2))
assert observed and all(x.get('feed',{}).get('integrity')=='HEALTHY' for x in observed)
assert state()['feed']['integrity']=='HEALTHY'
(out/'result.json').write_text(json.dumps({'status':'PASS','healthy_samples':len(observed)},indent=2)+'\n');print('PASS warm runtime prep',len(observed),'healthy observations')
